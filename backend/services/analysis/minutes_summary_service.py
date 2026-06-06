"""
On-demand AI summary of an eMeeting committee-minutes PDF.

Single-document plain-language summary via the open-source HF Qwen engine (the
sanctioned non-chat OSS path - NO Anthropic). Minutes are short, so featherless
serves them comfortably. Text + summary are cached per immutable PDF URL in
``emeeting_doc_text_cache`` (migration 116), so each minutes doc is summarised
once and reused.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.analysis.pdf_text_extractor import get_pdf_text

logger = logging.getLogger(__name__)

_HF_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai"
_MAX_CHARS = 60_000  # minutes are short; bound the request anyway

_SYSTEM = (
    "You are an EU policy analyst writing for a busy public-affairs professional. "
    "Summarise the official European Parliament committee meeting minutes below in "
    "plain British English. No jargon, no institutional codes in the prose, no "
    "em-dashes, no emojis. Use 3 to 6 short bullet points covering what the "
    "committee actually did: which dossiers it considered, what it voted or "
    "adopted and the outcome, any rapporteur or shadow appointments, and any next "
    "steps or decisions taken. Be concrete; do not invent vote tallies or names "
    "that are not in the text."
)


def get_summary(db: Session, pdf_url: str) -> Optional[dict]:
    """Cached summary for a minutes PDF, or None if not yet generated."""
    if not pdf_url:
        return None
    try:
        row = db.execute(text(
            "SELECT summary, summary_engine, summarised_at::text AS summarised_at "
            "FROM emeeting_doc_text_cache WHERE pdf_url = :u AND summary IS NOT NULL"
        ), {"u": pdf_url}).mappings().first()
        return dict(row) if row else None
    except Exception:
        db.rollback()
        return None


def _clean(s: str) -> str:
    return (s or "").replace(" — ", ", ").replace("—", ", ").replace("–", "-").strip()


async def summarise(db: Session, pdf_url: str) -> Optional[dict]:
    """Return the cached summary, or extract + summarise on demand and cache it."""
    if not pdf_url:
        return None
    cached = get_summary(db, pdf_url)
    if cached:
        return {**cached, "cached": True}

    ext = get_pdf_text(db, pdf_url)
    body = ((ext or {}).get("text") or "").strip()
    if len(body) < 200:
        return None
    body = body[:_MAX_CHARS]

    try:
        from services.ai.huggingface_service import get_huggingface_service
        hf = get_huggingface_service()
        engine = "HuggingFace"
        summary = None
        for attempt in range(3):
            raw = await hf.chat_completion(
                model=_HF_MODEL,
                messages=[{"role": "system", "content": _SYSTEM},
                          {"role": "user", "content": body}],
                max_tokens=700, temperature=0.2,
            )
            if raw and raw.strip():
                summary = _clean(raw)
                break
    except Exception as exc:
        logger.warning("[minutes-summary] HF failed for %s: %s", pdf_url, exc)
        summary = None

    # Fallback to the non-Anthropic multi-provider chain (Mistral/GPT-4) if HF declines.
    if not summary:
        try:
            from services.ai.multi_provider_service import MistralProvider, OpenAIProvider
            for Provider in (MistralProvider, OpenAIProvider):
                p = Provider()
                if not p.is_available:
                    continue
                resp = await p.generate(system_prompt=_SYSTEM,
                                        messages=[{"role": "user", "content": body}],
                                        max_tokens=700, temperature=0.2)
                if resp and (resp.message or "").strip():
                    summary = _clean(resp.message)
                    engine = getattr(p, "name", Provider.__name__)
                    break
        except Exception as exc:
            logger.warning("[minutes-summary] fallback failed for %s: %s", pdf_url, exc)

    if not summary:
        return None

    try:
        db.execute(text(
            "UPDATE emeeting_doc_text_cache SET summary = :s, summary_engine = :e, "
            "summarised_at = NOW() WHERE pdf_url = :u"
        ), {"s": summary, "e": engine, "u": pdf_url})
        db.commit()
    except Exception:
        db.rollback()

    return {"summary": summary, "summary_engine": engine, "cached": False}
