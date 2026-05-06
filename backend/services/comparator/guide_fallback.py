"""
Knowledge-guide fallback for the Comparator.

When `legislative_carriages.oeil_procedure_data` is sparse (which happens for
freshly-tabled procedures whose OEIL has not been re-synced yet), we fall back
to Brubru's knowledge guides. Many guides have rich `QUICK FACTS` blocks that
encode rapporteur, lead committee, and status, written by hand by the policy
team — so they fill the gap exactly when the structured carriage data is
missing.

Public surface:

    find_guide_for_carriage(file_ref, carriage_row) -> Optional[GuideMatch]
    rapporteur_from_guide(guide) -> Optional[CellResult]
    lead_committee_from_guide(guide) -> Optional[CellResult]
    last_event_from_guide(guide) -> Optional[CellResult]

Each cell result follows the same shape as `cell_extractors`:
    {"value": str | None, "citation": dict | None}

Citations point back to the matching Brubru chat surface so the user can read
the full guide. We never fabricate values — if the regex doesn't find the
field, we return None and the cell stays empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from knowledge_base.knowledge_loader import KnowledgeLoader


# ---------------------------------------------------------------------------
# Guide loader (singleton)
# ---------------------------------------------------------------------------

_LOADER: Optional[KnowledgeLoader] = None


def _loader() -> KnowledgeLoader:
    global _LOADER
    if _LOADER is None:
        _LOADER = KnowledgeLoader()
        _LOADER.load_all()
    return _LOADER


# ---------------------------------------------------------------------------
# Match a guide to a procedure
# ---------------------------------------------------------------------------

@dataclass
class GuideMatch:
    guide_id: str
    title: str
    body: str
    matched_via: str       # 'oeil_ref' | 'celex' | 'title' | 'alias'


def find_guide_for_carriage(
    file_ref: str,
    carriage_row: Optional[Dict[str, Any]],
) -> Optional[GuideMatch]:
    """Find the best matching Brubru knowledge guide for a procedure.

    Search strategy:
      1. Look for the OEIL procedure_ref appearing verbatim in any guide body
      2. Look for any of the carriage's CELEX numbers in any guide body
      3. Fall back to title-keyword search through `KnowledgeLoader.search_guides`
    """
    if file_ref is None and carriage_row is None:
        return None

    loader = _loader()
    # KnowledgeLoader.guides is dict[str, str] — keys are guide_ids, values are
    # the raw markdown bodies.
    guides_index: Dict[str, str] = loader.guides if hasattr(loader, "guides") else {}
    if not guides_index:
        return None

    def _title_from_body(body: str, fallback: str) -> str:
        for line in (body or "").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line.lstrip("# ").strip() or fallback
            if line:
                return fallback
        return fallback

    # 1. Direct OEIL ref match in body
    if "(" in (file_ref or "") and "/" in (file_ref or ""):
        for gid, body in guides_index.items():
            if file_ref in (body or ""):
                return GuideMatch(
                    guide_id=gid,
                    title=_title_from_body(body, gid),
                    body=body or "",
                    matched_via="oeil_ref",
                )

    # 2. CELEX match in body — works for proposals (e.g. EU Inc carriage has
    #    celex_numbers = ['52026PC0321'] which appears in 28th_regime guide
    #    as `COM(2026) 321 final`).
    celex_candidates: List[str] = []
    if carriage_row:
        celex_candidates.extend(carriage_row.get("celex_numbers") or [])
    if (file_ref or "") and (file_ref or "")[:1].isdigit() and len(file_ref) >= 10:
        celex_candidates.append(file_ref)
    for celex in celex_candidates:
        com_str = _proposal_celex_to_com(celex)
        for gid, body in guides_index.items():
            text_body = body or ""
            if (celex and celex in text_body) or (com_str and com_str in text_body):
                return GuideMatch(
                    guide_id=gid,
                    title=_title_from_body(text_body, gid),
                    body=text_body,
                    matched_via="celex",
                )

    # 3. Title-based fuzzy fallback
    if carriage_row and carriage_row.get("oeil_procedure_data"):
        title_lookup = carriage_row["oeil_procedure_data"].get("lookup_title")
        if title_lookup and isinstance(title_lookup, str) and len(title_lookup) > 8:
            hits = loader.search_guides(title_lookup)
            if hits:
                top = hits[0]
                gid = top.get("id") if isinstance(top, dict) else None
                if gid and gid in guides_index:
                    body = guides_index[gid] or ""
                    return GuideMatch(
                        guide_id=gid,
                        title=_title_from_body(body, gid),
                        body=body,
                        matched_via="title",
                    )

    return None


def _proposal_celex_to_com(celex: str) -> Optional[str]:
    """52026PC0321 -> 'COM(2026) 321'. Returns None for non-proposal CELEX."""
    m = re.match(r"^5(\d{4})PC(\d{3,4})$", celex or "")
    if not m:
        return None
    year, num = m.group(1), m.group(2).lstrip("0") or "0"
    return f"COM({year}) {num}"


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------

# Each parser returns Optional[CellResult] = {"value": str, "citation": dict}.

def _guide_citation(guide: GuideMatch, anchor_query: str) -> Dict[str, Any]:
    """Build a citation pointing back to Brubru's chat with a query that
    surfaces the full guide. The chat will pull the guide into context."""
    from urllib.parse import quote_plus
    return {
        "source": f"Brubru knowledge guide ({guide.guide_id})",
        "guide_id": guide.guide_id,
        "matched_via": guide.matched_via,
        "url": f"https://brubru.beresol.eu/main?q={quote_plus(anchor_query)}",
    }


_RAPPORTEUR_PATTERNS: List[re.Pattern[str]] = [
    # Bold form: "**EP rapporteur: Name (...)**"
    re.compile(r"\*\*\s*EP\s+rapporteur\s*:\s*([^*\n]+?)\*\*", re.IGNORECASE),
    # Plain: "- EP rapporteur: Name (...)" / "Lead rapporteur: Name"
    re.compile(r"(?:^|\n)\s*-\s*\**\s*(?:EP\s+)?Lead\s+rapporteur\s*:\s*([^\n*]+)", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*-\s*\**\s*(?:EP\s+)?Rapporteur\s*:\s*([^\n*]+)", re.IGNORECASE),
]

_MEP_PROFILE_URL = re.compile(
    r"https?://(?:www\.)?europarl\.europa\.eu/meps/[a-z]{2}/(\d+)/[A-Z_'`’ ]+(?:/home)?",
    re.IGNORECASE,
)


def rapporteur_from_guide(guide: GuideMatch) -> Optional[Dict[str, Any]]:
    """Extract a rapporteur name + group from QUICK FACTS lines.

    Also pulls the rapporteur's MEP profile URL (europarl.europa.eu/meps/...)
    when present in the same paragraph or anywhere in the guide body.
    """
    body = guide.body or ""
    for pat in _RAPPORTEUR_PATTERNS:
        m = pat.search(body)
        if m:
            raw = m.group(1).strip().strip(".:")
            value = re.split(r"[.;]\s+", raw)[0].strip()
            value = value.rstrip("*").strip()
            if not value or value.lower() in {"tbc", "tbd", "to be confirmed", "to be assigned"}:
                continue
            if len(value) > 160:
                continue
            # Prefer the MEP URL from the same paragraph (the line + ~2 next lines)
            window = body[m.start():m.end() + 600]
            mep_url: Optional[str] = None
            mep_id: Optional[str] = None
            url_match = _MEP_PROFILE_URL.search(window) or _MEP_PROFILE_URL.search(body)
            if url_match:
                mep_url = url_match.group(0)
                mep_id = url_match.group(1)
            citation = _guide_citation(guide, f"Tell me about {guide.title}")
            if mep_url:
                citation = {
                    **citation,
                    "url": mep_url,
                    "mep_id": mep_id,
                    "source": "European Parliament MEP profile",
                }
            return {"value": value, "citation": citation}
    return None


_COMMITTEE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\*\*\s*EP\s+lead\s+committee\s*:\s*([^*\n]+?)\*\*", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*-\s*\**\s*EP\s+lead\s+committee\s*:\s*([^\n*]+)", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*-\s*\**\s*Lead\s+committee\s*:\s*([^\n*]+)", re.IGNORECASE),
]


def lead_committee_from_guide(guide: GuideMatch) -> Optional[Dict[str, Any]]:
    """Extract lead committee from QUICK FACTS, with EP committee homepage URL."""
    from services.comparator.cell_extractors import _committee_url  # local import
    body = guide.body or ""
    for pat in _COMMITTEE_PATTERNS:
        m = pat.search(body)
        if m:
            raw = m.group(1).strip().strip(".:")
            value = re.split(r"\s+[—–-]\s+", raw)[0].strip()
            value = value.rstrip("*").strip()
            if not value or len(value) > 80:
                continue
            url = _committee_url(value)
            citation = _guide_citation(guide, f"Tell me about {guide.title}")
            if url:
                citation = {
                    **citation,
                    "url": url,
                    "source": "European Parliament committee homepage",
                }
            return {"value": value, "citation": citation}
    return None


_STATUS_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"(?:^|\n)\s*-\s*\**\s*Status\s*:\s*([^\n*]+)", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*-\s*\**\s*Current\s+status\s*:\s*([^\n*]+)", re.IGNORECASE),
]


def last_event_from_guide(guide: GuideMatch) -> Optional[Dict[str, Any]]:
    """Returns a one-line "what's the latest" extracted from the guide.

    Useful when oeil_key_events is empty. Less precise than the carriage path —
    falls back to the QUICK FACTS Status line.
    """
    body = guide.body or ""
    for pat in _STATUS_PATTERNS:
        m = pat.search(body)
        if m:
            raw = m.group(1).strip().strip(".:").rstrip("*").strip()
            if not raw or len(raw) > 200:
                continue
            return {
                "value": raw,
                "citation": _guide_citation(guide, f"Tell me about {guide.title}"),
            }
    return None
