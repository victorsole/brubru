"""
Legislative-journey comparative analysis.

For one dossier, assembles the text journey and asks a non-Anthropic LLM to
compare the layers:

  Legislative file (has a Commission proposal):
    1. Commission proposal (the regulation / directive text)
    2. Rapporteur's draft report
    3. Other MEPs' amendments
    4. Rapporteur + shadows' compromise amendments
    5. The final committee voting list

  Resolution / own-initiative file (no proposal): layers 2-5 only.

Per the project's hard rule, NEW non-chat AI uses the non-Anthropic stack
(Mistral -> GPT-4 -> Gemini). Full text is sent (the documents live on the
un-walled meetdocs host), so Gemini's long context is preferred; the assembled
prompt is bounded so the GPT-4 / Mistral fallbacks still fit. Results cache in
``file_journey_analyses`` keyed by procedure + a hash of the contributing docs.
"""

import asyncio
import hashlib
import json
import logging
import re
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.analysis.pdf_text_extractor import get_pdf_text

logger = logging.getLogger(__name__)

# Primary engine: the open-source HF Qwen3-30B (256K context) used for the
# transcript summaries - cheap, non-Anthropic, sanctioned OSS path. GPT-4o /
# Mistral are fallbacks if HF is unavailable.
_HF_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai"

# Per-engine source-text budget (chars, ~4 chars/token). The HF Inference
# Providers router (featherless) serves Qwen on a shared tier that 429s
# ("insufficient capacity") on very large requests, so we keep the HF request
# at ~45K tokens - reliable and cheap, covers most dossiers in full via the
# max-min allocation. The GPT-4o fallback gets the bigger budget for the few
# giant files where HF declines.
_HF_CHAR_CAP = 180_000
_TOTAL_CHAR_CAP = 350_000

# Legislative procedure suffixes (these carry a Commission proposal).
_LEGISLATIVE_SUFFIXES = {"COD", "CNS", "APP", "NLE", "BUD", "SYN", "AVC", "BUI", "ACI"}

# The journey layers, in order, with a plain-language label.
_LAYER_DEFS = [
    ("proposal", "Commission proposal", "commission_document"),
    ("draft_report", "Rapporteur's draft report", "draft_report"),
    ("amendment", "MEPs' amendments", "amendment"),
    ("compromise_amendments", "Compromise amendments", "compromise_amendments"),
    ("voting_list", "Final voting list", "voting_list"),
]


def _suffix(procedure_ref: str) -> str:
    m = re.search(r"\(([A-Z]+)\)", procedure_ref or "")
    return m.group(1) if m else ""


def _latest_doc(db: Session, procedure_ref: str, doc_kind: str) -> Optional[dict]:
    """The most recent eMeeting doc of a kind for a procedure (with a pdf)."""
    try:
        row = db.execute(text(
            """
            SELECT doc_kind, reference, item_title, title, committee_code,
                   meeting_date::text AS meeting_date, pdf_url, source_url
            FROM ep_emeeting_documents
            WHERE procedure_ref = :p AND doc_kind = :k AND pdf_url IS NOT NULL
            ORDER BY meeting_date DESC NULLS LAST
            LIMIT 1
            """
        ), {"p": procedure_ref, "k": doc_kind}).mappings().first()
        return dict(row) if row else None
    except Exception:
        db.rollback()
        return None


def _doc_set_hash(docs: List[dict]) -> str:
    parts = sorted(f"{d['key']}:{d.get('pdf_url') or ''}:{d.get('meeting_date') or ''}" for d in docs)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def resolve_doc_set(db: Session, procedure_ref: str) -> List[dict]:
    """Resolve the contributing documents for a dossier (one latest per layer)."""
    out: List[dict] = []
    for key, label, kind in _LAYER_DEFS:
        doc = _latest_doc(db, procedure_ref, kind)
        if doc:
            out.append({"key": key, "label": label, **doc})
    return out


def _build_messages(procedure_ref: str, is_legislative: bool, layers: List[dict],
                    total_cap: int = _TOTAL_CHAR_CAP) -> tuple[str, list]:
    kind_word = "legislative file (it has a Commission proposal)" if is_legislative \
        else "non-legislative file (a resolution / own-initiative report, with no Commission proposal)"
    present = ", ".join(l["label"] for l in layers)
    system_prompt = (
        "You are a senior EU legislative analyst writing for a public-affairs "
        "professional. You compare the successive texts of a dossier as it moves "
        "through the European Parliament committee stage, and explain in plain "
        "British English what changes at each step and where the political fight "
        "is. No jargon, no institutional codes in the prose, no em-dashes, no "
        "emojis.\n\n"
        f"This is a {kind_word}. The documents provided, in order, are: {present}.\n\n"
        "Return ONLY a JSON object (no markdown fence) with this shape:\n"
        "{\n"
        '  "summary": "2 to 4 sentences a busy reader can grasp at a glance: what '
        'this dossier is and the single most important thing the committee stage '
        'changed or is contesting.",\n'
        '  "overview": "one short paragraph framing the journey",\n'
        '  "by_layer": {\n'
        '     "<layer_key>": "what this layer proposes and, for every layer after '
        'the first, how it changes the previous one. 2 to 5 sentences."\n'
        "  },\n"
        '  "contested_points": ["the specific articles / themes where MEPs disagree, '
        'each one short line"],\n'
        '  "where_the_fight_is": "one or two sentences on the live battleground '
        'going into the vote",\n'
        '  "caveats": "note here if any document text was truncated or missing, else empty string"\n'
        "}\n"
        "Use ONLY these layer_key values for keys actually present: "
        "proposal, draft_report, amendment, compromise_amendments, voting_list. "
        "Never invent article numbers, vote tallies, or names that are not in the text."
    )

    # Max-min fair allocation of the total budget across layers: process smallest
    # first, each gets min(its size, an equal share of what's left). This gives
    # the small but decision-critical layers (compromise amendments, voting list)
    # their FULL text and splits the rest between the big ones (proposal,
    # amendments) - so every layer is always represented, never starved by order.
    alloc: dict = {}
    remaining_budget = total_cap
    remaining_layers = len(layers)
    for l in sorted(layers, key=lambda x: len(x.get("_text") or "")):
        share = remaining_budget // remaining_layers if remaining_layers else 0
        take = min(len(l.get("_text") or ""), share)
        alloc[id(l)] = take
        remaining_budget -= take
        remaining_layers -= 1

    # Build the blocks in journey order (oldest layer first) using the allocation.
    blocks = []
    for l in layers:
        full = l.get("_text") or ""
        take = alloc.get(id(l), 0)
        body = full[:take]
        l["_prompt_truncated"] = take < len(full)
        l["_in_prompt"] = take > 0
        blocks.append(
            f"===== LAYER: {l['key']} ({l['label']}) =====\n"
            f"Reference: {l.get('reference') or l.get('item_title') or ''}\n"
            f"Committee: {l.get('committee_code') or ''}  Date: {l.get('meeting_date') or ''}\n\n"
            f"{body}"
        )
    user = (f"Dossier procedure: {procedure_ref}\n\n" + "\n\n".join(blocks)) if blocks else procedure_ref
    return system_prompt, [{"role": "user", "content": user}]


async def _call_llm(procedure_ref: str, is_legislative: bool, layers: List[dict]
                    ) -> tuple[Optional[dict], Optional[str], Optional[str]]:
    """Non-Anthropic. Primary = HF Qwen3-30B (256K ctx, big source budget);
    fallbacks = GPT-4o then Mistral (smaller budget). Messages are reassembled
    per engine so each gets as much text as its window allows. Returns
    (parsed_json, engine, model)."""
    last_err = None

    # 1. HF Qwen (open-source, cheap, long context) - the sanctioned OSS path.
    # featherless 429s intermittently on capacity, so retry a couple of times
    # before giving up to the paid fallback.
    try:
        from services.ai.huggingface_service import get_huggingface_service
        system_prompt, messages = _build_messages(procedure_ref, is_legislative, layers, _HF_CHAR_CAP)
        hf = get_huggingface_service()
        hf_messages = [{"role": "system", "content": system_prompt}] + messages
        for attempt in range(3):
            raw = await hf.chat_completion(
                model=_HF_MODEL, messages=hf_messages, max_tokens=2600, temperature=0.2,
            )
            parsed = _parse_json(raw or "")
            if parsed is not None:
                return parsed, "HuggingFace", _HF_MODEL
            if attempt < 2:
                await asyncio.sleep(5 * (attempt + 1))  # 5s, 10s backoff
        logger.warning("[journey] HF Qwen exhausted retries, falling back")
    except Exception as e:
        last_err = e
        logger.warning("[journey] HF Qwen failed: %s", e)

    # 2/3. GPT-4o then Mistral (smaller window -> smaller source budget).
    from services.ai.multi_provider_service import MistralProvider, OpenAIProvider
    system_prompt, messages = _build_messages(procedure_ref, is_legislative, layers, _TOTAL_CHAR_CAP)
    for Provider in (OpenAIProvider, MistralProvider):
        try:
            provider = Provider()
            if not provider.is_available:
                continue
            resp = await provider.generate(
                system_prompt=system_prompt, messages=messages,
                max_tokens=2600, temperature=0.2,
            )
            raw = (resp.message or "").strip() if resp else ""
            parsed = _parse_json(raw)
            if parsed is not None:
                return parsed, getattr(provider, "name", Provider.__name__), getattr(Provider, "MODEL", None)
        except Exception as e:
            last_err = e
            logger.warning("[journey] %s failed: %s", Provider.__name__, e)

    logger.error("[journey] all engines failed: %s", last_err)
    return None, None, None


def _parse_json(raw: str) -> Optional[dict]:
    # Strip a markdown fence if the model added one, then take the outermost {...}.
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None


def _clean(s: Optional[str]) -> str:
    # House rule: no em-dashes in Brubru-surfaced text.
    return (s or "").replace(" — ", ", ").replace("—", ", ").replace("–", "-").strip()


async def generate_journey(db: Session, carriage) -> Optional[dict]:
    """Generate (or regenerate) the journey analysis for a carriage. Upserts and
    returns the stored row as a dict, or None if there's nothing to analyse."""
    procedure_ref = getattr(carriage, "oeil_procedure_ref", None)
    if not procedure_ref:
        return None

    docs = resolve_doc_set(db, procedure_ref)
    if not docs:
        return None

    is_legislative = any(d["key"] == "proposal" for d in docs) or _suffix(procedure_ref) in _LEGISLATIVE_SUFFIXES
    # A resolution has no proposal layer even if a stray COM doc is attached.
    if _suffix(procedure_ref) in {"INI", "RSP", "RSO", "INL", "DEA", "REG"}:
        is_legislative = False
        docs = [d for d in docs if d["key"] != "proposal"]

    if not docs:
        return None

    doc_hash = _doc_set_hash(docs)

    # Extract text for each layer (cached per PDF).
    for d in docs:
        ext = get_pdf_text(db, d.get("pdf_url"))
        d["_text"] = (ext or {}).get("text", "")
        d["_char_count"] = (ext or {}).get("char_count", 0)
        d["_pdf_truncated"] = bool((ext or {}).get("truncated"))
    docs = [d for d in docs if d["_char_count"] > 0]
    if not docs:
        return None

    parsed, engine, model = await _call_llm(procedure_ref, is_legislative, docs)
    if parsed is None:
        _mark_error(db, procedure_ref, carriage)
        return None

    by_layer = parsed.get("by_layer", {}) if isinstance(parsed.get("by_layer"), dict) else {}
    layers_payload = [{
        "kind": d["key"],
        "label": d["label"],
        "doc_ref": d.get("reference") or d.get("item_title"),
        "committee_code": d.get("committee_code"),
        "meeting_date": d.get("meeting_date"),
        "pdf_url": d.get("pdf_url"),
        "source_url": d.get("source_url"),
        "char_count": d["_char_count"],
        "truncated": bool(d.get("_pdf_truncated") or d.get("_prompt_truncated")),
        "summary": _clean(by_layer.get(d["key"], "")),
    } for d in docs]

    comparison = {
        "overview": _clean(parsed.get("overview")),
        "contested_points": [_clean(x) for x in (parsed.get("contested_points") or []) if x][:12],
        "where_the_fight_is": _clean(parsed.get("where_the_fight_is")),
        "caveats": _clean(parsed.get("caveats")),
    }
    summary = _clean(parsed.get("summary"))

    return _upsert(db, procedure_ref, carriage, is_legislative, doc_hash,
                   layers_payload, comparison, summary, engine, model, len(docs))


def _upsert(db, procedure_ref, carriage, is_legislative, doc_hash, layers,
            comparison, summary, engine, model, n) -> dict:
    proposal_celex = None
    for d in layers:
        if d["kind"] == "proposal":
            proposal_celex = d.get("doc_ref")
    params = {
        "p": procedure_ref,
        "cid": str(getattr(carriage, "id", None)) if getattr(carriage, "id", None) else None,
        "leg": is_legislative, "h": doc_hash, "celex": proposal_celex,
        "layers": json.dumps(layers), "cmp": json.dumps(comparison),
        "summary": summary, "engine": engine, "model": model, "n": n,
    }
    db.execute(text(
        """
        INSERT INTO file_journey_analyses
            (procedure_ref, carriage_id, is_legislative, doc_set_hash, proposal_celex,
             layers, comparison, summary, engine, model, source_doc_count, status, generated_at)
        VALUES (:p, :cid, :leg, :h, :celex, CAST(:layers AS jsonb), CAST(:cmp AS jsonb),
                :summary, :engine, :model, :n, 'ready', NOW())
        ON CONFLICT (procedure_ref) DO UPDATE SET
            carriage_id = EXCLUDED.carriage_id, is_legislative = EXCLUDED.is_legislative,
            doc_set_hash = EXCLUDED.doc_set_hash, proposal_celex = EXCLUDED.proposal_celex,
            layers = EXCLUDED.layers, comparison = EXCLUDED.comparison,
            summary = EXCLUDED.summary, engine = EXCLUDED.engine, model = EXCLUDED.model,
            source_doc_count = EXCLUDED.source_doc_count, status = 'ready', generated_at = NOW()
        """
    ), params)
    db.commit()
    return get_journey(db, procedure_ref)


def _mark_error(db, procedure_ref, carriage) -> None:
    try:
        db.execute(text(
            """
            INSERT INTO file_journey_analyses (procedure_ref, carriage_id, doc_set_hash, status)
            VALUES (:p, :cid, 'error', 'error')
            ON CONFLICT (procedure_ref) DO UPDATE SET status = 'error', generated_at = NOW()
            """
        ), {"p": procedure_ref, "cid": str(getattr(carriage, "id", None)) if getattr(carriage, "id", None) else None})
        db.commit()
    except Exception:
        db.rollback()


def get_journey(db: Session, procedure_ref: str) -> Optional[dict]:
    """Read the cached analysis for a procedure, or None."""
    try:
        row = db.execute(text(
            """
            SELECT procedure_ref, carriage_id::text AS carriage_id, is_legislative,
                   doc_set_hash, proposal_celex, layers, comparison, summary,
                   engine, model, source_doc_count, status, generated_at::text AS generated_at
            FROM file_journey_analyses WHERE procedure_ref = :p
            """
        ), {"p": procedure_ref}).mappings().first()
        return dict(row) if row else None
    except Exception:
        db.rollback()
        return None


def current_doc_set_hash(db: Session, procedure_ref: str) -> Optional[str]:
    """The hash of the dossier's CURRENT doc set, to detect staleness."""
    docs = resolve_doc_set(db, procedure_ref)
    if _suffix(procedure_ref) in {"INI", "RSP", "RSO", "INL", "DEA", "REG"}:
        docs = [d for d in docs if d["key"] != "proposal"]
    return _doc_set_hash(docs) if docs else None


async def precompute_tracked(db: Session, limit: int = 5) -> dict:
    """Generate journeys for dossiers that are missing or stale, tracked first.

    Covers the whole universe of carriages with committee documents (tracked
    ones prioritised), ``limit`` per run, sequential with a short pause so the
    shared HF tier keeps serving the cheap engine rather than 429-ing into the
    paid fallback. Skips fresh ones via the doc-set hash, so successive runs work
    through the backlog and then just keep tracked files fresh.
    """
    from models.legislative_train import LegislativeCarriage

    rows = db.execute(text(
        """
        SELECT c.id, c.oeil_procedure_ref,
               EXISTS (SELECT 1 FROM user_carriage_tracks t
                       WHERE t.carriage_id = c.id AND t.archived_at IS NULL) AS is_tracked
        FROM legislative_carriages c
        WHERE c.oeil_procedure_ref IS NOT NULL
          AND EXISTS (SELECT 1 FROM ep_emeeting_documents d
                      WHERE d.procedure_ref = c.oeil_procedure_ref
                        AND d.doc_kind IN ('draft_report','amendment','compromise_amendments',
                                           'voting_list','opinion','draft_opinion','commission_document'))
        ORDER BY is_tracked DESC, c.last_updated DESC NULLS LAST
        """
    )).mappings().all()

    done, skipped, failed = 0, 0, 0
    for r in rows:
        if done >= limit:
            break
        ref = r["oeil_procedure_ref"]
        cur = current_doc_set_hash(db, ref)
        existing = get_journey(db, ref)
        if existing and existing["status"] == "ready" and existing["doc_set_hash"] == cur:
            skipped += 1
            continue
        carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == r["id"]).first()
        if not carriage:
            continue
        try:
            res = await generate_journey(db, carriage)
            if res:
                done += 1
            else:
                failed += 1
            await asyncio.sleep(2)  # be gentle on the shared HF tier
        except Exception as exc:  # one bad dossier must not stop the batch
            logger.warning("[journey] precompute failed for %s: %s", ref, exc)
            db.rollback()
            failed += 1

    return {"generated": done, "skipped_fresh": skipped, "failed": failed,
            "candidates": len(rows), "limit": limit}
