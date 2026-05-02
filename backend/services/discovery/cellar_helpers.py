"""
Cellar SPARQL helpers, parameterised per Brubru canonical feature.

Each function wraps CellarSPARQLClient with feature-specific defaults so the
caller doesn't have to know SPARQL or sector codes.

Canonical feature map:
    Chat                                -> already wired (context_builder._fetch_cellar_discovery_block)
    Amendator                           -> find_recent_amendable_proposals
    My EU Bubble / Legislative Tracker  -> stream_oj_delta (Task 6 — replaces OJ scraper)
    EU Law Comply                       -> find_acts_for_eurovoc_concept
    Tenderator                          -> find_acts_for_tender_topic
    API                                 -> already wired (api/v1/cellar_discover.py)
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from services.api_clients.cellar_sparql_client import CellarSPARQLClient


# ----------------------------------------------------------------------
# Amendator — discover recent COD/CNS/APP proposals worth featuring
# ----------------------------------------------------------------------

# CELEX type-letter codes that are amendable (proposal procedures + adopted secondary legislation).
# Used together with sector + type filtering.
AMENDABLE_TYPE_LETTERS = {"PC", "PR", "PA", "L", "R", "D"}


async def find_recent_amendable_proposals(
    days: int = 30,
    limit: int = 10,
    language: str = "ENG",
) -> List[Dict[str, Any]]:
    """
    Sector-5 (Commission proposals) + sector-3 (in-force secondary legislation)
    surfaced as candidates for the Amendator example rotation.

    Returns rows with keys: celex, work, date, title.
    """
    end = date.today()
    start = end - timedelta(days=days)
    async with CellarSPARQLClient() as client:
        rows = await client.discover_by_date_range(
            date_from=start,
            date_to=end,
            sectors=["5", "3"],
            language=language,
            limit=limit,
        )
    # Cheap server-side post-filter: amendable type letters only.
    keep: List[Dict[str, Any]] = []
    for r in rows:
        celex = r.get("celex") or ""
        # Skip clearly non-amendable kinds (recommendations, opinions, communications)
        if any(marker in celex for marker in ("DC", "OP", "RR", "X")):
            continue
        keep.append(r)
    return keep[:limit]


# ----------------------------------------------------------------------
# EU Law Comply — find legislation relevant to a EuroVoc concept
# ----------------------------------------------------------------------

async def find_acts_for_eurovoc_concept(
    eurovoc_concept_id: str,
    only_in_force: bool = True,
    since: Optional[date] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Discover EU acts tagged with a given EuroVoc concept.

    Args:
        eurovoc_concept_id: Concept ID (e.g. "5460" for data protection) or full URI.
        only_in_force: If True (default), filter to acts currently in force.
        since: Optional lower bound on document date.
        limit: Max rows to return.
    """
    async with CellarSPARQLClient() as client:
        rows = await client.get_acts_by_eurovoc(
            eurovoc_concept=eurovoc_concept_id,
            date_from=since,
            limit=limit * 2 if only_in_force else limit,
        )

        if not only_in_force:
            return rows[:limit]

        # Live in-force filter — small N, parallel-friendly
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            celex = row.get("celex")
            if not celex:
                continue
            status = await client.get_force_status(celex)
            if status.get("in_force"):
                filtered.append({**row, **status})
            if len(filtered) >= limit:
                break
        return filtered


async def search_eurovoc_then_find_acts(
    keyword: str,
    only_in_force: bool = True,
    limit: int = 20,
    language: str = "en",
) -> Dict[str, Any]:
    """
    EU Law Comply convenience: keyword -> EuroVoc concept -> in-force acts.

    Used by the Comply analyzer when a sector/topic name needs to be resolved
    to applicable legislation. Returns dict with keys: concept, acts.
    """
    async with CellarSPARQLClient() as client:
        concepts = await client.search_eurovoc_concepts(
            keyword=keyword, language=language, limit=1
        )
    if not concepts:
        return {"concept": None, "acts": []}

    concept = concepts[0]
    acts = await find_acts_for_eurovoc_concept(
        eurovoc_concept_id=concept["concept"],
        only_in_force=only_in_force,
        limit=limit,
    )
    return {"concept": concept, "acts": acts}


# ----------------------------------------------------------------------
# Tenderator — cross-reference a tender topic to regulatory framework
# ----------------------------------------------------------------------

async def find_acts_for_tender_topic(
    topic_keyword: str,
    only_in_force: bool = True,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Tenderator companion: given a tender's CPV-derived topic keyword
    ("environmental services", "IT consulting"), surface the regulatory
    framework an SME bidding for the tender should comply with.
    """
    pack = await search_eurovoc_then_find_acts(
        keyword=topic_keyword, only_in_force=only_in_force, limit=limit
    )
    return pack.get("acts", [])


# ----------------------------------------------------------------------
# Legislative Tracker — date-range delta (used by Task 6 OJ scraper migration)
# ----------------------------------------------------------------------

async def stream_oj_delta(
    since: date,
    until: Optional[date] = None,
    sectors: Optional[List[str]] = None,
    language: str = "ENG",
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Stream EU acts published in [since, until] for ingestion into eu_laws.

    Drop-in replacement for the daily OJ-RSS scrapers — uses the canonical
    Cellar metadata graph as source of truth.
    """
    if until is None:
        until = date.today()
    async with CellarSPARQLClient() as client:
        return await client.discover_by_date_range(
            date_from=since,
            date_to=until,
            sectors=sectors,
            language=language,
            limit=limit,
        )
