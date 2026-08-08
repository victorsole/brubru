"""
Turn an official EU legal title into the name a person would actually say.

The curated alias stores in ``title_display`` cover the files Brussels talks
about ("Artificial Intelligence Act", "GDPR"). They will never cover the long
tail of routine acts, and for those the instrument designation is all we can
parse out: "Council Decision (EU) 2026/1544", "Corrigendum to Regulation (EU)
2019/5". That is a code, not a name. It tells a user nothing about whether the
file matters to them.

This module closes that gap by asking the free open-model chain to compress the
official title into a short subject line:

    "Council Decision (EU) 2026/1544 of 17 November 2025 on the conclusion, on
     behalf of the Union, of the Protocol on the implementation of the
     Sustainable Fisheries Partnership Agreement between the European Union and
     the Government of the Cook Islands (2025-2032)"
        -> "EU-Cook Islands fisheries protocol"

Two rules govern the design.

**Never in the request path.** Results are cached on
``legislative_carriages.short_title`` and produced by a backfill script. A
dashboard load never waits on a model.

**Never invent.** A synthesised label is shown to the user as the name of a
legal act, so a hallucinated country, year or instrument would be a factual
error on the face of the product. The prompt forbids new information, and
``_is_faithful`` then checks the output mechanically: every significant word
and every number in the label must already appear in the source title. Anything
that fails is discarded and the caller keeps the instrument designation. A
boring-but-true label beats an interesting invented one.

Provider: the shared open-model chain in ``multi_provider_service``. No
Anthropic — the "no new Anthropic code" rule covers everything outside Chat.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional, Set

logger = logging.getLogger(__name__)


# A label longer than this is not a name, it is a sentence.
MAX_LABEL_CHARS = 60

# Words the model may introduce even though they are not in the source title:
# joiners and EU shorthand that carry no factual claim of their own.
_ALLOWED_NEW_WORDS: Set[str] = {
    "eu", "the", "a", "an", "of", "on", "for", "and", "in", "to", "with",
    "rules", "law", "act", "reform", "update", "deal", "scheme",
}

# Source words that carry no meaning, so their absence from the label is fine
# and their presence in it proves nothing.
_STOPWORDS: Set[str] = {
    "the", "of", "on", "for", "and", "in", "to", "with", "a", "an", "as",
    "by", "from", "that", "this", "which", "certain", "laying", "down",
    "amending", "repealing", "establishing", "concerning", "regarding",
    "within", "between", "behalf", "union", "european", "council",
    "parliament", "commission", "regulation", "directive", "decision",
    "corrigendum", "position", "taken", "conclusion", "implementation",
    "protocol", "agreement", "annex", "appendices", "article", "no",
}

_SYSTEM_PROMPT = (
    "You name EU legal acts for a policy-monitoring product. Given the full "
    "official title of an act, reply with the short name a Brussels "
    "professional would use in conversation.\n\n"
    "Rules:\n"
    f"- At most {MAX_LABEL_CHARS} characters.\n"
    "- Use ONLY information present in the title. Never add a country, date, "
    "number, institution or topic that is not already there.\n"
    "- Drop the instrument type, the act number, the adoption date and the "
    "phrases 'on the conclusion', 'on behalf of the Union', 'of the European "
    "Parliament and of the Council'.\n"
    "- Keep the subject: what the act is actually about.\n"
    "- British English. No quotation marks, no full stop, no preamble.\n"
    "- Reply with the name and nothing else.\n\n"
    "Examples:\n"
    "Title: Council Decision (EU) 2026/1544 of 17 November 2025 on the "
    "conclusion, on behalf of the Union, of the Protocol on the implementation "
    "of the Sustainable Fisheries Partnership Agreement between the European "
    "Union and the Government of the Cook Islands (2025-2032)\n"
    "Name: EU-Cook Islands fisheries protocol\n\n"
    "Title: Regulation (EU) 2024/1689 laying down harmonised rules on "
    "artificial intelligence\n"
    "Name: Artificial Intelligence Act\n"
)


def _fold(text: str) -> str:
    """Lower-case, strip accents, so 'Decisión' and 'Decision' compare equal."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )


def _words(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", _fold(text)))


def _numbers(text: str) -> Set[str]:
    return set(re.findall(r"\d+", text))


def _is_faithful(label: str, source_title: str) -> bool:
    """True when the label introduces no information the title does not have.

    Mechanical, deliberately strict, and independent of the prompt: the model
    is not trusted to have followed instructions. Every number in the label
    must appear in the title, and every significant word must either appear in
    the title or be an allowed joiner.
    """
    if not label:
        return False

    if not _numbers(label) <= _numbers(source_title):
        return False

    source_words = _words(source_title)
    for word in _words(label):
        if word in source_words or word in _ALLOWED_NEW_WORDS:
            continue
        # Allow a word the title contains as a stem ("fisheries" vs "fishery",
        # "Islands" vs "Island") — a prefix match of 5+ characters.
        if len(word) >= 5 and any(
            src.startswith(word[:5]) for src in source_words if len(src) >= 5
        ):
            continue
        return False

    # A label made only of joiners says nothing; treat it as a failure.
    return bool(_words(label) - _ALLOWED_NEW_WORDS - _STOPWORDS)


def _clean(raw: str) -> str:
    """Strip the decoration models add around a one-line answer."""
    label = (raw or "").strip()
    # Models sometimes answer "Name: X" despite being told not to.
    label = re.sub(r"^\s*(name|short name|answer)\s*:\s*", "", label, flags=re.I)
    label = label.split("\n")[0].strip()
    # Brubru ships no em-dashes in user-facing text, and a model will happily
    # produce one (plus en-dashes and non-breaking hyphens) in names like
    # "EU-Cook Islands". Normalise every dash-like character to a plain hyphen
    # here, at the boundary, rather than trusting the prompt.
    label = re.sub(r"[‐-―−]", "-", label)
    # Trailing punctuation before the closing quote ("...protocol".) means the
    # quotes have to come off after the full stop, not before it.
    label = label.rstrip(".").strip()
    return label.strip('"').strip("'").strip().rstrip(".").strip()


async def synthesise_short_title(
    title: str, *, max_chars: int = MAX_LABEL_CHARS
) -> Optional[str]:
    """A short human name for this act, or None if one cannot be produced safely.

    None is a normal outcome, not an error: no provider configured, the model
    declined, or the answer failed the faithfulness check. Callers fall back to
    the instrument designation from ``title_display.short_title``.
    """
    source = (title or "").strip()
    if not source:
        return None
    if len(source) <= max_chars:
        # Already short enough to be its own name.
        return None

    try:
        from services.ai.multi_provider_service import get_multi_provider_service

        service = get_multi_provider_service()
    except Exception as exc:  # pragma: no cover - provider config is optional
        logger.warning("title synthesis unavailable: %s", exc)
        return None

    try:
        response = await service.generate(
            system_prompt=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Title: {source}\nName:"}],
            # Generous despite the one-line answer: the head of the chain is a
            # reasoning model, and a tight cap is spent on reasoning tokens
            # before any answer is emitted. The label is bounded by max_chars
            # after cleaning, not by the token budget.
            max_tokens=400,
            temperature=0.0,
        )
    except Exception as exc:
        logger.warning("title synthesis failed: %s", exc)
        return None

    # ProviderResponse carries the text on `message` (see
    # services/ai/multi_provider_service.py); it has no `content` attribute.
    label = _clean(getattr(response, "message", "") or "")
    if not label or len(label) > max_chars:
        logger.info("title synthesis rejected (length): %r", label[:80])
        return None
    if not _is_faithful(label, source):
        logger.info(
            "title synthesis rejected (unfaithful): %r for %r", label, source[:80]
        )
        return None
    return label
