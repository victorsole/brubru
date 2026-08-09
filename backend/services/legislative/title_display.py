"""
How a legislative file is named on screen.

One place decides the label for a file, so the briefing cards, the file modal
and anything else that shows a dossier agree. Official EU legal titles run
150-400 characters and often carry the CELEX glued to the front
("CELEX:32019R0005R(03): Corrigendum to ..."), which is a database identifier
rather than prose. Rendering that raw is what made the My EU Bubble briefing
card unreadable.

The rules, in order:
  1. A curated alias, from two stores already in the repo and both keyed on a
     stable identifier, so nothing here is guessed: procedure_aliases.json by
     OEIL reference, then the legislation acronym KB by CELEX.
  2. Otherwise the instrument designation parsed off the head of the title
     ("Council Decision (EU) 2026/1544"), which is the part professionals scan
     for and the only part that fits on one line.
  3. Otherwise the title itself, clipped on a word boundary.

The full title is never discarded: callers keep it for tooltips, accessible
names and detail views.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Some legislative_carriages titles are stored with the CELEX glued on the
# front: "CELEX:32019R0005R(03): Corrigendum to Regulation (EU) 2019/5 of ...".
# That is a database identifier, not prose, and reading it as the opening
# words of a sentence is exactly what made the briefing card unreadable. Lift
# it out so it can be shown as a reference pill beside a clean title.
_CELEX_PREFIX = re.compile(
    r"^CELEX:\s*([0-9]{5}[A-Z]{1,2}[0-9]{4}(?:R\(\d{2}\))?)\s*:\s*"
)


def split_celex_prefix(title: str) -> tuple[str, Optional[str]]:
    """Return (clean title, CELEX) — CELEX is None when there is no prefix."""
    if not title:
        return title, None
    match = _CELEX_PREFIX.match(title)
    if not match:
        return title, None
    remainder = title[match.end():].strip()
    # Never hand back an empty title: if the row is nothing but a CELEX, the
    # original string is still the most useful thing to show.
    return (remainder or title), match.group(1)


# The instrument designation at the head of an official EU legal title:
# "Council Decision (EU) 2026/1544 of 17 November 2025 on ...". This is the
# part a policy professional actually scans for, and it is the only part short
# enough to sit on one line. Everything after it is the subject clause, which
# routinely runs several hundred characters, so it stays in `title` (tooltip)
# and in the file modal rather than on the card.
#
# The qualifier is repeated, not optional-once: EU instruments routinely stack
# two ("Council Implementing Decision", "Commission Delegated Regulation"). An
# earlier single-qualifier version matched none of those, so every implementing
# and delegated act fell through to the clip-at-70-characters path and the
# briefing card read "Council Implementing Decision (EU) 2026/1923 of 30 July
# 2026 amending...". The treaty marker also has to admit CFSP, which names a
# large share of Council decisions.
_INSTRUMENT = re.compile(
    r"^(Corrigendum to\s+)?"
    r"((?:(?:Commission|Council|European\s+Parliament|Delegated|Implementing)\s+)*"
    r"(?:Regulation|Directive|Decision|Recommendation|Opinion|Resolution))\s*"
    r"\(((?:EU|EC|EEC|Euratom|CFSP|CE)(?:,\s*Euratom)?)\)\s*(?:No\s*)?([\d/]+)",
    re.IGNORECASE,
)

# Longest a fallback short title may run before it is clipped on a word
# boundary. Titles that carry no instrument designation ("Critical Medicines
# Act", "Situation in Cuba") are usually already short and pass through whole.
_SHORT_TITLE_MAX = 70


# The acronym KB holds one entry per language for the same instrument
# ("GDPR", "RGPD", "AVG" all point at 32016R0679), distinguished only by the
# language its full_title is written in. These are the instrument words that
# identify a language UNAMBIGUOUSLY: "Directive" is shared by EN and FR and
# "Directiva" by ES and CA, so neither can classify an entry on its own. An
# entry whose title starts with an ambiguous word stays unclassified and is
# only used as a last resort — better a correct English acronym than a
# confidently wrong Catalan one.
_ACRONYM_LANG_WORDS: Dict[str, tuple] = {
    "en": ("regulation", "decision"),
    "es": ("reglamento", "decisión"),
    "ca": ("reglament", "decisió"),
    "fr": ("règlement", "décision"),
    "it": ("regolamento", "direttiva", "decisione"),
    "nl": ("verordening", "richtlijn", "besluit"),
}


@lru_cache(maxsize=1)
def _celex_to_acronym() -> Dict[str, Dict[str, str]]:
    """CELEX -> {language: acronym} from the legislation acronym KB.

    The KB is keyed by alias ("GDPR" -> {celex, full_title, ...}); we need the
    inverse, split by language so a Dutch user gets "AVG" and an English one
    "GDPR". Entries whose language cannot be determined land under "" and are
    used only when nothing better exists.
    """
    try:
        from services.parsers.law_alias_resolver import _load_acronyms
    except Exception:  # pragma: no cover - KB is optional at runtime
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        for alias, payload in (_load_acronyms() or {}).items():
            celex = (payload or {}).get("celex")
            if not celex or not alias:
                continue
            head = ((payload or {}).get("full_title") or "").strip().lower()
            lang = ""
            for code, words in _ACRONYM_LANG_WORDS.items():
                if head.startswith(words):
                    lang = code
                    break
            bucket = out.setdefault(celex, {})
            # First alias for a language wins; the KB lists the canonical form
            # first and later duplicates are spelling variants.
            bucket.setdefault(lang, alias)
    except Exception as exc:  # pragma: no cover
        logger.warning("could not build CELEX->acronym map: %s", exc)
        return {}
    return out


def _acronym_for(celex: str, lang: str) -> Optional[str]:
    """The acronym for this CELEX in the user's language, else English."""
    bucket = _celex_to_acronym().get(celex)
    if not bucket:
        return None
    for key in (lang, "en", ""):
        if bucket.get(key):
            return bucket[key]
    return next(iter(bucket.values()), None)


def curated_alias(
    ref: Optional[str], celex: Optional[str], lang: str = "en"
) -> Optional[str]:
    """The name a Brussels professional would actually use for this file.

    Two curated sources, both already in the repo and both keyed on a stable
    identifier, so nothing here is guessed:
      1. procedure_aliases.json, by OEIL procedure reference
         ("2021/0106(COD)" -> "Artificial Intelligence Act")
      2. the legislation acronym KB, by CELEX ("32016R0679" -> "GDPR")
    Returns None when neither knows the file, which is the common case for
    routine acts: the caller then falls back to the instrument designation.
    """
    if ref:
        try:
            from services.parsers.procedure_alias_resolver import _load_procedures

            entry = (_load_procedures() or {}).get(ref)
            curated = (entry or {}).get("title")
            if curated:
                return curated
        except Exception as exc:  # pragma: no cover
            logger.warning("procedure alias lookup failed for %s: %s", ref, exc)
    if celex:
        alias = _acronym_for(celex, lang)
        if alias:
            return alias
    return None


def short_title(title: str) -> str:
    """A one-line label for a file: the instrument designation where the title
    has one, otherwise the title itself, clipped on a word boundary."""
    if not title:
        return title
    match = _INSTRUMENT.match(title)
    if match:
        prefix = (match.group(1) or "").strip()
        instrument = " ".join(match.group(2).split())
        return " ".join(
            part
            for part in (prefix, instrument, f"({match.group(3)})", match.group(4))
            if part
        )
    if len(title) <= _SHORT_TITLE_MAX:
        return title
    return title[:_SHORT_TITLE_MAX].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def file_item(
    title: str,
    ref: Optional[str],
    carriage_id: Any,
    detail: Optional[str] = None,
    areas: Optional[List[str]] = None,
    lang: str = "en",
    cached_short_title: Optional[str] = None,
) -> Dict[str, Any]:
    """One openable file line for ProactiveBriefing.items.

    `short_title` is what a card should render; `title` is the full official
    title, for tooltips, accessible names and any consumer that wants it.
    `areas` comes from the carriage's own policy_areas column, so the topic
    shown beside a file is structured data, never parsed out of the prose.
    """
    clean_title, celex = split_celex_prefix(title or "")
    return {
        "title": clean_title,
        # The cached name first (legislative_carriages.short_title, written by
        # scripts/backfill_carriage_short_titles.py: a curated alias or an
        # AI-synthesised subject line that passed the faithfulness check), then
        # a live curated lookup, then the instrument designation. Never the
        # full title: those run 150-400 characters and swamp the card.
        "short_title": (
            (cached_short_title or "").strip()
            or curated_alias(ref, celex, lang)
            or short_title(clean_title)
        ),
        # Prefer the procedure reference; fall back to the CELEX we lifted out
        # of the title so the identifier is never simply lost. Not rendered on
        # the briefing card — the file modal carries it.
        "ref": ref or celex,
        "carriage_id": str(carriage_id) if carriage_id else None,
        "detail": detail,
        "areas": [a for a in (areas or []) if a][:2],
    }
