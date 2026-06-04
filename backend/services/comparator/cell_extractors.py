"""
Cell extractors for the Comparator feature.

Each extractor takes a `file_ref` (CELEX or OEIL procedure ref) and a SQLAlchemy
Session, and returns a `CellResult` dict with two top-level keys:

    {"value": str | None, "citation": dict | None}

A null `value` MUST come with a null `citation` — if the source data is missing,
the cell renders as "unknown" rather than as a guess. This mirrors the
no-hallucination guarantee from the legal-text intelligence layer (cf. CLAUDE.md
"Document retrieval: AI MUST present T9-/A9-/PE-/COM- references...; never say
'search EUR-Lex yourself.'").

Six MVP columns:
    rapporteur, status, lead_committee, amendments_deadline,
    structure_counts, last_key_event

To add a new column: write `extract_<key>(file_ref, db) -> CellResult`, then
register it in EXTRACTORS at the bottom of this file.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional, TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.comparator.guide_fallback import (
    find_guide_for_carriage,
    lead_committee_from_guide,
    last_event_from_guide,
    rapporteur_from_guide,
)


CellResult = Dict[str, Any]   # {"value": str | None, "citation": dict | None}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_oeil_ref(file_ref: str) -> bool:
    """Heuristic: OEIL procedure refs look like '2024/0079(COD)'."""
    return "(" in file_ref and "/" in file_ref


def _is_celex(file_ref: str) -> bool:
    """Heuristic: CELEX numbers start with a digit and are 10+ chars long."""
    return bool(file_ref) and file_ref[0].isdigit() and len(file_ref) >= 10


def _fetch_carriage(db: Session, file_ref: str) -> Optional[Dict[str, Any]]:
    """Look up the legislative_carriages row by OEIL ref or by CELEX."""
    if _is_oeil_ref(file_ref):
        row = db.execute(
            text(
                """
                SELECT oeil_procedure_ref, current_status, lead_committee,
                       celex_numbers, oeil_key_events, oeil_procedure_data,
                       last_updated
                FROM legislative_carriages
                WHERE oeil_procedure_ref = :ref
                LIMIT 1
                """
            ),
            {"ref": file_ref},
        ).fetchone()
    elif _is_celex(file_ref):
        # A CELEX may live in the celex_numbers array of a carriage row
        row = db.execute(
            text(
                """
                SELECT oeil_procedure_ref, current_status, lead_committee,
                       celex_numbers, oeil_key_events, oeil_procedure_data,
                       last_updated
                FROM legislative_carriages
                WHERE :celex = ANY(celex_numbers)
                LIMIT 1
                """
            ),
            {"celex": file_ref},
        ).fetchone()
    else:
        return None
    if not row:
        return None
    return {
        "oeil_procedure_ref": row[0],
        "current_status": row[1],
        "lead_committee": row[2],
        "celex_numbers": row[3] or [],
        "oeil_key_events": row[4] or [],
        "oeil_procedure_data": row[5] or {},
        "last_updated": row[6],
    }


def _oeil_url(procedure_ref: Optional[str]) -> Optional[str]:
    """Return a working OEIL procedure-file URL.

    The legacy `oeil/popups/ficheprocedure.do` endpoint returns 404 for
    recent procedures; the live endpoint is `oeil/en/procedure-file`.
    Verified 6 May 2026 against 2024/0079(COD) + 2026/0074(COD).
    """
    if not procedure_ref:
        return None
    safe = procedure_ref.replace("(", "%28").replace(")", "%29")
    return f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={safe}"


def _eurlex_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


# 22 EP committees + 3 subcommittees → public homepage URL
# Pattern: europarl.europa.eu/committees/en/{lower}/home
_COMMITTEE_CODES = {
    "AFCO", "AFET", "AGRI", "BUDG", "CONT", "CULT", "DEVE", "ECON",
    "EMPL", "ENVI", "FEMM", "IMCO", "INTA", "ITRE", "JURI", "LIBE",
    "PECH", "PETI", "REGI", "TRAN",
    # subcommittees
    "DROI", "FISC", "SEDE", "SANT",
}
_COMMITTEE_NAME_TO_CODE = {
    "constitutional affairs": "AFCO",
    "foreign affairs": "AFET",
    "agriculture and rural development": "AGRI",
    "budgets": "BUDG",
    "budgetary control": "CONT",
    "culture and education": "CULT",
    "development": "DEVE",
    "economic and monetary affairs": "ECON",
    "employment and social affairs": "EMPL",
    "environment, public health and food safety": "ENVI",
    "environment": "ENVI",
    "women's rights and gender equality": "FEMM",
    "internal market and consumer protection": "IMCO",
    "international trade": "INTA",
    "industry, research and energy": "ITRE",
    "legal affairs": "JURI",
    "civil liberties, justice and home affairs": "LIBE",
    "fisheries": "PECH",
    "petitions": "PETI",
    "regional development": "REGI",
    "transport and tourism": "TRAN",
    "human rights": "DROI",
    "tax matters": "FISC",
    "security and defence": "SEDE",
    "public health": "SANT",
}


def _committee_url(value: Optional[str]) -> Optional[str]:
    """Map a committee name or code to its EP committee homepage."""
    if not value:
        return None
    s = value.strip()
    # Try a token that looks like a committee code (3-4 ALL-CAPS letters)
    code_match = re.search(r"\b([A-Z]{3,5})\b", s)
    if code_match and code_match.group(1) in _COMMITTEE_CODES:
        code = code_match.group(1)
        return f"https://www.europarl.europa.eu/committees/en/{code.lower()}/home"
    # Otherwise try to match by full name
    low = s.lower().strip().rstrip(".)").lstrip("(")
    for name, code in _COMMITTEE_NAME_TO_CODE.items():
        if name in low:
            return f"https://www.europarl.europa.eu/committees/en/{code.lower()}/home"
    return None


def _empty(reason: str = "no data in carriage row") -> CellResult:
    """Standard empty-cell result (with reason recorded for debugging)."""
    return {"value": None, "citation": None, "_reason": reason}


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_rapporteur(file_ref: str, db: Session) -> CellResult:
    """Lead-committee rapporteur, with political group.

    Primary: oeil_procedure_data.key_players.committee_responsible.rapporteur
    Fallback: parse the matching Brubru knowledge guide's QUICK FACTS line.
    """
    car = _fetch_carriage(db, file_ref)
    if not car:
        return _empty("file_ref not found in legislative_carriages")
    kp = (car["oeil_procedure_data"] or {}).get("key_players") or {}
    cr = kp.get("committee_responsible") or {}
    rap = cr.get("rapporteur") if isinstance(cr, dict) else None
    if rap and isinstance(rap, dict):
        name = rap.get("name") or rap.get("full_name")
        pg = rap.get("political_group")
        if name:
            value = f"{name} ({pg})" if pg else name
            return {
                "value": value,
                "citation": {
                    "source": "OEIL key players",
                    "procedure_ref": car["oeil_procedure_ref"],
                    "url": _oeil_url(car["oeil_procedure_ref"]),
                },
            }
    guide = find_guide_for_carriage(file_ref, car)
    if guide:
        gh = rapporteur_from_guide(guide)
        if gh:
            return gh
    return _empty("rapporteur missing in OEIL data and in matching guide")


def extract_status(file_ref: str, db: Session) -> CellResult:
    """Procedure current_status from legislative_carriages."""
    car = _fetch_carriage(db, file_ref)
    if not car:
        return _empty("file_ref not found in legislative_carriages")
    status = car["current_status"]
    if not status:
        return _empty("current_status null on carriage row")
    return {
        "value": status,
        "citation": {
            "source": "Brubru legislative_carriages",
            "procedure_ref": car["oeil_procedure_ref"],
            "url": _oeil_url(car["oeil_procedure_ref"]),
            "as_of": car["last_updated"].isoformat() if car["last_updated"] else None,
        },
    }


def extract_lead_committee(file_ref: str, db: Session) -> CellResult:
    """Lead committee code (e.g. 'LIBE') or full name.

    Fallback chain: legislative_carriages.lead_committee → OEIL lookup_committees
    → Brubru knowledge-guide QUICK FACTS line.
    """
    car = _fetch_carriage(db, file_ref)
    if not car:
        return _empty("file_ref not found in legislative_carriages")
    code = car["lead_committee"]
    if code:
        url = _committee_url(code) or _oeil_url(car["oeil_procedure_ref"])
        return {
            "value": code,
            "citation": {
                "source": "European Parliament committee homepage" if _committee_url(code) else "Brubru legislative_carriages.lead_committee",
                "procedure_ref": car["oeil_procedure_ref"],
                "url": url,
            },
        }
    lookups = (car["oeil_procedure_data"] or {}).get("lookup_committees") or []
    if lookups and isinstance(lookups, list):
        first = str(lookups[0])
        url = _committee_url(first) or _oeil_url(car["oeil_procedure_ref"])
        return {
            "value": first,
            "citation": {
                "source": "European Parliament committee homepage" if _committee_url(first) else "OEIL lookup_committees",
                "procedure_ref": car["oeil_procedure_ref"],
                "url": url,
            },
        }
    # Fallback to Brubru knowledge guide
    guide = find_guide_for_carriage(file_ref, car)
    if guide:
        gh = lead_committee_from_guide(guide)
        if gh:
            return gh
    return _empty("lead_committee unknown in OEIL data and in matching guide")


def extract_amendments_deadline(file_ref: str, db: Session) -> CellResult:
    """Latest 'Amendments tabled in committee' document date from documentation_gateway."""
    car = _fetch_carriage(db, file_ref)
    if not car:
        return _empty("file_ref not found in legislative_carriages")
    docs = (car["oeil_procedure_data"] or {}).get("documentation_gateway") or []
    am_docs = [
        d for d in docs
        if isinstance(d, dict) and d.get("doc_type_code") == "AM"
    ]
    if not am_docs:
        return _empty("no AM (Amendments tabled) docs in documentation_gateway")
    # Take the latest by date (DD/MM/YYYY string compare won't work; parse safely)
    def _date_key(d: Dict[str, Any]) -> str:
        date_str = d.get("date") or ""
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str
    am_docs_sorted = sorted(am_docs, key=_date_key, reverse=True)
    top = am_docs_sorted[0]
    pe_ref = top.get("pe_reference") or "PE-ref unknown"
    date_str = top.get("date")
    committee = top.get("committee") or car["lead_committee"] or ""
    value = f"{date_str} ({committee} {pe_ref})" if date_str else f"{pe_ref} ({committee})"
    return {
        "value": value,
        "citation": {
            "source": "OEIL documentation_gateway",
            "procedure_ref": car["oeil_procedure_ref"],
            "doc_type": "Amendments tabled in committee",
            "pe_reference": pe_ref,
            "url": top.get("doceo_url") or _oeil_url(car["oeil_procedure_ref"]),
        },
    }


def extract_structure_counts(file_ref: str, db: Session) -> CellResult:
    """Count of recitals + articles for the file's CELEX.

    Resolution chain:
      1. eu_laws.extra_metadata.structure_counts (cached by previous compute)
      2. eu_laws.extra_metadata.recital_article_map (populated by Brubru's
         legal-text intelligence parser when a law is annotated)
      3. Live fetch through services/parsers/EurlexFetcher (hits Cellar /
         EUR-Lex web), parsed by EurlexParser. 12 second hard timeout. The
         result is cached back into structure_counts for next time.
    """
    from services.comparator.structure_extractor import (
        cache_structure_counts,
        fetch_structure_counts,
        read_cached_counts,
    )

    car = _fetch_carriage(db, file_ref)
    celex_candidates: list[str] = []
    if car and car["celex_numbers"]:
        celex_candidates.extend(car["celex_numbers"])
    if _is_celex(file_ref):
        celex_candidates.append(file_ref)
    if not celex_candidates:
        return _empty("no CELEX associated with file_ref")

    # 1+2. cached + recital_article_map paths
    for celex in celex_candidates:
        cached = read_cached_counts(db, celex)
        if cached is not None:
            recital_count, article_count = cached
            return {
                "value": f"{recital_count} recitals · {article_count} articles",
                "citation": {
                    "source": "Brubru cached structure counts",
                    "celex": celex,
                    "url": _eurlex_url(celex),
                },
            }
        row = db.execute(
            text(
                """
                SELECT celex, extra_metadata
                FROM eu_laws
                WHERE celex = :celex
                LIMIT 1
                """
            ),
            {"celex": celex},
        ).fetchone()
        if not row:
            continue
        em = row[1] if isinstance(row[1], dict) else {}
        rim = em.get("recital_article_map") or {}
        if isinstance(rim, dict) and rim:
            article_count = len(rim)
            recital_count = len({
                rec
                for arr in rim.values() if isinstance(arr, list)
                for rec in arr
            })
            return {
                "value": f"{recital_count} recitals · {article_count} articles",
                "citation": {
                    "source": "Brubru parser (recital_article_map)",
                    "celex": celex,
                    "url": _eurlex_url(celex),
                },
            }

    # 3. On-demand fetch + parse via Cellar (hard 12 s timeout). Try every
    #    CELEX, prefer the adopted-act one (3{year}R/L/D/...) over proposals
    #    (5{year}PC/JC/DC) since Cellar only serves XHTML for adopted acts.
    def _is_adopted(c: str) -> bool:
        return bool(c) and len(c) >= 7 and c[0] == "3"

    sorted_celex = sorted(celex_candidates, key=lambda c: (0 if _is_adopted(c) else 1))
    for celex in sorted_celex:
        counts = fetch_structure_counts(celex)
        if counts is not None:
            recital_count, article_count = counts
            cache_structure_counts(db, celex, counts)
            return {
                "value": f"{recital_count} recitals · {article_count} articles",
                "citation": {
                    "source": "Brubru live parser (EUR-Lex / Cellar)",
                    "celex": celex,
                    "url": _eurlex_url(celex),
                },
            }
    # All sources exhausted (Cellar XHTML + PDF + WAF-browser HTML). This is a
    # genuine "could not parse the source document", not a transient state, so
    # don't promise that retrying will help.
    return _empty(
        "Recitals + articles could not be extracted from the source document "
        "(no machine-readable structure available for this file)."
    )


def extract_last_key_event(file_ref: str, db: Session) -> CellResult:
    """Most recent OEIL key event: '<event_type> on <date>'.

    Fallback: if oeil_key_events is empty or only carries the bare 'Legislative
    proposal' entry, look up the matching guide's QUICK FACTS Status line.
    """
    car = _fetch_carriage(db, file_ref)
    if not car:
        return _empty("file_ref not found in legislative_carriages")
    events = car["oeil_key_events"] or []
    if isinstance(events, list) and events:
        def _date_key(e: Dict[str, Any]) -> str:
            return str(e.get("date") or "")
        sorted_events = sorted(
            [e for e in events if isinstance(e, dict)],
            key=_date_key,
            reverse=True,
        )
        if sorted_events:
            top = sorted_events[0]
            et = top.get("event_type") or "Event"
            dt = top.get("date") or ""
            value = f"{et} on {dt}" if dt else et
            return {
                "value": value,
                "citation": {
                    "source": "OEIL key events",
                    "procedure_ref": car["oeil_procedure_ref"],
                    "event_type": et,
                    "event_date": dt,
                    "url": _oeil_url(car["oeil_procedure_ref"]),
                },
            }
    # Fallback to Brubru knowledge guide
    guide = find_guide_for_carriage(file_ref, car)
    if guide:
        gh = last_event_from_guide(guide)
        if gh:
            return gh
    return _empty("oeil_key_events empty and no matching guide status")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EXTRACTORS: Dict[str, Callable[[str, Session], CellResult]] = {
    "rapporteur": extract_rapporteur,
    "status": extract_status,
    "lead_committee": extract_lead_committee,
    "amendments_deadline": extract_amendments_deadline,
    "structure_counts": extract_structure_counts,
    "last_key_event": extract_last_key_event,
}


def extract_cell(column_key: str, file_ref: str, db: Session) -> CellResult:
    """Dispatch to the right extractor. Unknown keys raise KeyError."""
    fn = EXTRACTORS.get(column_key)
    if fn is None:
        raise KeyError(f"Unknown column_key '{column_key}'. Allowed: {sorted(EXTRACTORS.keys())}")
    return fn(file_ref, db)
