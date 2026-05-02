"""
/api/v1/discover — Cellar SPARQL discovery surface.

Live queries against the EU Publications Office Cellar metadata graph
(http://publications.europa.eu/webapi/rdf/sparql).

Distinct from /api/v1/laws, which queries Brubru's local eu_laws table
(8,710-law subset enriched for retrieval). /api/v1/discover/* hits the
full corpus (3.79M works including case law, proposals, opinions, treaties)
in real time.

Endpoints:
    GET /api/v1/discover/cellar/recent
    GET /api/v1/discover/cellar/celex/{celex}
    GET /api/v1/discover/cellar/celex/{celex}/relationships
    GET /api/v1/discover/cellar/celex/{celex}/languages
    GET /api/v1/discover/cellar/eurovoc
    GET /api/v1/discover/cellar/eurovoc/{concept_id}/acts
"""

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from services.api_clients.cellar_sparql_client import CellarSPARQLClient
from services.api_clients.fmx4_notice_parser import fetch_notice

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover/cellar", tags=["v1-discover"])


# ----------------------------- response shapes -----------------------------

class CellarRecentItem(BaseModel):
    celex: str
    work_uri: Optional[str] = Field(None, description="Cellar work URI (used for FMX4 retrieval)")
    document_date: Optional[date] = Field(None, description="cdm:work_date_document")
    title: Optional[str] = None
    eurlex_url: Optional[str] = None


class CellarMetadata(BaseModel):
    celex: str
    work_uri: Optional[str] = None
    title: Optional[str] = None
    document_date: Optional[date] = None
    eli: Optional[str] = None
    resource_type_uri: Optional[str] = None
    resource_type_label: Optional[str] = None
    in_force: bool
    date_in_force: Optional[str] = None
    date_end_validity: Optional[str] = None
    available_languages: list[str] = Field(default_factory=list)
    eurovoc_concepts: list[str] = Field(default_factory=list)
    eurlex_url: str


class CellarRelation(BaseModel):
    relation: str = Field(..., description="CDM relationship predicate URI")
    related_celex: str
    direction: str = Field(..., description="'outgoing' (this work -> other) or 'incoming' (other -> this work)")


class EuroVocConcept(BaseModel):
    concept_uri: str
    label: str


# ----------------------------- helpers -----------------------------

def _eurlex_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s.split("T")[0])
    except (ValueError, AttributeError):
        return None


# ----------------------------- endpoints -----------------------------

@router.get(
    "/recent",
    response_model=PaginatedResponse[CellarRecentItem],
    summary="Recent EU acts (live SPARQL discovery)",
    description=(
        "Live discovery of EU acts published in a date range. Queries the Publications "
        "Office Cellar SPARQL endpoint directly — covers the full 3.79M-work corpus, "
        "including case law and proposals not in the local eu_laws table."
    ),
)
async def recent_cellar_acts(
    request: Request,
    published_from: date = Query(..., description="Lower bound (YYYY-MM-DD)"),
    published_to: Optional[date] = Query(None, description="Upper bound (YYYY-MM-DD); defaults to today"),
    sectors: Optional[str] = Query(
        None,
        description=(
            "Comma-separated CELEX sector codes to filter on "
            "(e.g. '3' = legislation in force, '5' = proposals, '6' = case law). "
            "Default: all sectors."
        ),
    ),
    language: str = Query("ENG", description="ISO-3 language code (uppercase) for titles"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRecentItem]:
    if published_to is None:
        published_to = date.today()
    if published_from > published_to:
        raise HTTPException(
            status_code=422,
            detail={"error": "published_from must be <= published_to", "reason_code": "invalid_range"},
        )

    sector_list = [s.strip() for s in sectors.split(",")] if sectors else None
    offset = (page - 1) * limit

    async with CellarSPARQLClient() as client:
        rows = await client.discover_by_date_range(
            date_from=published_from,
            date_to=published_to,
            sectors=sector_list,
            language=language.upper(),
            limit=limit,
            offset=offset,
        )

    items = [
        CellarRecentItem(
            celex=r["celex"],
            work_uri=r.get("work"),
            document_date=_to_date(r.get("date")),
            title=r.get("title"),
            eurlex_url=_eurlex_url(r["celex"]),
        )
        for r in rows
        if r.get("celex")
    ]

    # SPARQL doesn't give us a cheap exact total. We use the page size as a hint.
    total = offset + len(items) + (limit if len(items) == limit else 0)
    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        coverage_complete=False,  # SPARQL is live; pagination is approximate
    )


@router.get(
    "/celex/{celex}",
    response_model=CellarMetadata,
    summary="Full Cellar metadata for a CELEX",
    description=(
        "Live SPARQL fetch: title, ELI, resource type (with English label), in-force "
        "status, validity dates, available languages, and EuroVoc concepts attached "
        "to the work. Useful when /api/v1/laws/{celex} returns nothing (act outside "
        "Brubru's cached corpus)."
    ),
)
async def cellar_celex_metadata(
    request: Request,
    celex: str = Path(..., description="CELEX number, e.g. 32016R0679"),
    language: str = Query("ENG", description="ISO-3 language code (uppercase) for titles"),
    user: User = Depends(api_user_with_rate_limit),
) -> CellarMetadata:
    async with CellarSPARQLClient() as client:
        meta = await client.get_celex_metadata(celex, language=language.upper())
        if not meta:
            raise HTTPException(status_code=404, detail={"error": f"CELEX {celex} not found in Cellar", "reason_code": "not_found"})

        # Parallel-friendly enrichment
        languages = await client.get_available_languages(celex)
        eurovoc = await client.get_eurovoc_concepts(celex)

        type_label = None
        if meta.get("resourceTypeUri"):
            type_label = await client.resolve_resource_type(meta["resourceTypeUri"])

    return CellarMetadata(
        celex=celex,
        work_uri=meta.get("work"),
        title=meta.get("title"),
        document_date=_to_date(meta.get("date")),
        eli=meta.get("eli"),
        resource_type_uri=meta.get("resourceTypeUri"),
        resource_type_label=type_label,
        in_force=meta.get("in_force", False),
        date_in_force=meta.get("dateInForce"),
        date_end_validity=meta.get("dateEnd"),
        available_languages=languages,
        eurovoc_concepts=eurovoc,
        eurlex_url=_eurlex_url(celex),
    )


@router.get(
    "/celex/{celex}/relationships",
    response_model=PaginatedResponse[CellarRelation],
    summary="Acts related to a CELEX (amends/repeals/consolidates)",
)
async def cellar_celex_relationships(
    request: Request,
    celex: str = Path(...),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRelation]:
    async with CellarSPARQLClient() as client:
        rows = await client.get_related_acts(celex)

    items = [
        CellarRelation(
            relation=r["relation"],
            related_celex=r["relatedCelex"],
            direction=r.get("direction", "outgoing"),
        )
        for r in rows
        if r.get("relation") and r.get("relatedCelex")
    ]
    return build_envelope(items=items, total=len(items), page=1, limit=max(1, len(items)), coverage_complete=False)


@router.get(
    "/celex/{celex}/languages",
    summary="Languages and downloadable manifestations for an act",
    description=(
        "Parses the Formex notice for the CELEX and returns all (language, format, "
        "URL) tuples. Useful for picking a specific language version of the act in "
        "FMX4 (canonical structured XML), XHTML, PDF/A-1a, PDF/A-2a, or DOCX. "
        "Corrigendum CELEX numbers (with R(NN) suffix) are not supported by the "
        "EU Publications Office and will return 422."
    ),
)
async def cellar_celex_languages(
    request: Request,
    celex: str = Path(...),
    user: User = Depends(api_user_with_rate_limit),
) -> dict:
    try:
        meta = await fetch_notice(celex)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": str(e), "reason_code": "no_notice"})

    return {
        "celex": meta.celex or celex,
        "cellar_uri": meta.cellar_uri,
        "eli": meta.eli,
        "oj_reference": meta.oj_reference,
        "languages": meta.languages_available,
        "language_count": len(meta.languages_available),
        "manifestations": [m.to_dict() for m in meta.manifestations],
        "manifestation_count": len(meta.manifestations),
        "titles": meta.titles,
    }


@router.get(
    "/eurovoc",
    response_model=PaginatedResponse[EuroVocConcept],
    summary="Search EuroVoc thesaurus",
)
async def search_eurovoc(
    request: Request,
    q: str = Query(..., min_length=2, description="Free-text search term"),
    language: str = Query("en", description="ISO-2 language code for labels"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[EuroVocConcept]:
    async with CellarSPARQLClient() as client:
        rows = await client.search_eurovoc_concepts(keyword=q, language=language, limit=limit)

    items = [EuroVocConcept(concept_uri=r["concept"], label=r["label"]) for r in rows if r.get("concept")]
    return build_envelope(items=items, total=len(items), page=1, limit=limit, coverage_complete=False)


@router.get(
    "/eurovoc/{concept_id}/acts",
    response_model=PaginatedResponse[CellarRecentItem],
    summary="Acts tagged with a EuroVoc concept",
)
async def acts_by_eurovoc(
    request: Request,
    concept_id: str = Path(..., description="EuroVoc concept ID (digits) or full URI"),
    published_from: Optional[date] = Query(None, description="Lower bound on document date"),
    language: str = Query("ENG", description="ISO-3 language code for titles"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRecentItem]:
    async with CellarSPARQLClient() as client:
        rows = await client.get_acts_by_eurovoc(
            eurovoc_concept=concept_id,
            date_from=published_from,
            language=language.upper(),
            limit=limit,
        )

    items = [
        CellarRecentItem(
            celex=r["celex"],
            work_uri=r.get("work"),
            document_date=_to_date(r.get("date")),
            title=r.get("title"),
            eurlex_url=_eurlex_url(r["celex"]),
        )
        for r in rows
        if r.get("celex")
    ]
    return build_envelope(
        items=items,
        total=len(items),
        page=1,
        limit=limit,
        published_from=published_from,
        coverage_complete=False,
    )
