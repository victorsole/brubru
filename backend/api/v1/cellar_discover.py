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
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from services.api_clients.cellar_sparql_client import CellarSPARQLClient

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
    # The 5 mandatory Brubru v1 datapoints (this is a live list endpoint, so
    # body fields are not fetched per-item to avoid 50 Cellar round-trips per
    # request — use /api/v1/citations/verify or /api/v1/laws/{celex}/text to
    # pull body for a specific CELEX).
    public_url: Optional[str] = Field(None, description="Citizen-facing EUR-Lex URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Null on list endpoints. Use /api/v1/citations/verify for body.")
    body_html: Optional[str] = Field(None, description="Null on list endpoints.")
    creation_date: Optional[datetime] = Field(None, description="Time of this Cellar discovery call (live endpoint).")


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
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Citizen-facing EUR-Lex URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Null on this metadata-only endpoint. Use /api/v1/citations/verify for body.")
    body_html: Optional[str] = Field(None, description="Null on this metadata-only endpoint.")
    creation_date: Optional[datetime] = Field(None, description="Time of this Cellar discovery call (live endpoint).")


class CellarRelation(BaseModel):
    relation: str = Field(..., description="CDM relationship predicate URI")
    related_celex: str
    direction: str = Field(..., description="'outgoing' (this work -> other) or 'incoming' (other -> this work)")
    # The 5 mandatory Brubru v1 datapoints — these describe the RELATED act
    # the edge points to (not this row's parent CELEX, which is in the path).
    public_url: Optional[str] = Field(None, description="EUR-Lex citizen URL of the related act.")
    body_txt: Optional[str] = Field(None, description="Null on this graph-edge endpoint — fetch via /citations/verify on the related_celex.")
    body_html: Optional[str] = Field(None, description="Null on this graph-edge endpoint.")
    document_date: Optional[date] = Field(None, description="Null on this graph-edge endpoint — Cellar relationship metadata doesn't carry the related act's date inline.")
    creation_date: Optional[datetime] = Field(None, description="Time of this Cellar relationship discovery call.")


class EuroVocConcept(BaseModel):
    concept_uri: str
    label: str
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="ShowVoc citizen URL for the EuroVoc concept.")
    body_txt: Optional[str] = Field(None, description="Concept label (taxonomy nodes don't have a body).")
    body_html: Optional[str] = Field(None, description="Null — taxonomy nodes are labels not documents.")
    document_date: Optional[date] = Field(None, description="Null — EuroVoc concepts are taxonomy entries without an adoption date.")
    creation_date: Optional[datetime] = Field(None, description="Time of this Cellar EuroVoc search call.")


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
    summary="Recently published EU acts (live)",
    description=(
        "Live discovery of EU acts published in a date range. Queries the Publications "
        "Office Cellar SPARQL endpoint directly — covers the full 3.79M-work corpus, "
        "including case law and proposals not in the local eu_laws table."
    ),
)
async def recent_cellar_acts(
    request: Request,
    published_from: date = Query(..., description="Lower bound (YYYY-MM-DD)", example="2026-04-01"),
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

    _now = datetime.utcnow()
    items = [
        CellarRecentItem(
            celex=r["celex"],
            work_uri=r.get("work"),
            document_date=_to_date(r.get("date")),
            title=r.get("title"),
            eurlex_url=_eurlex_url(r["celex"]),
            public_url=_eurlex_url(r["celex"]),
            creation_date=_now,
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
    summary="Look up an EU act by reference (full metadata)",
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
        public_url=_eurlex_url(celex),
        creation_date=datetime.utcnow(),
    )


@router.get(
    "/celex/{celex}/relationships",
    response_model=PaginatedResponse[CellarRelation],
    summary="Acts that amend, repeal, or are amended by an act",
)
async def cellar_celex_relationships(
    request: Request,
    celex: str = Path(...),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRelation]:
    async with CellarSPARQLClient() as client:
        rows = await client.get_related_acts(celex)

    _now = datetime.utcnow()
    items = [
        CellarRelation(
            relation=r["relation"],
            related_celex=r["relatedCelex"],
            direction=r.get("direction", "outgoing"),
            public_url=_eurlex_url(r["relatedCelex"]),
            creation_date=_now,
        )
        for r in rows
        if r.get("relation") and r.get("relatedCelex")
    ]
    return build_envelope(items=items, total=len(items), page=1, limit=max(1, len(items)), coverage_complete=False)


@router.get(
    "/celex/{celex}/languages",
    summary="All language versions and download formats of an act",
    description=(
        "Returns every (language, format, URL) tuple for the act, sourced "
        "directly from the Cellar metadata graph via SPARQL. Useful for "
        "picking a specific language version in FMX4 (canonical structured "
        "XML), XHTML, PDF/A-1a, PDF/A-2a, or DOCX.\n\n"
        "Note: this endpoint queries the Cellar SPARQL endpoint directly. "
        "It used to fetch the Formex notice via EUR-Lex's HTTP endpoint, "
        "which routinely returned HTTP 202 (still building) and timed out. "
        "The SPARQL path is faster and more reliable."
    ),
)
async def cellar_celex_languages(
    request: Request,
    celex: str = Path(...),
    user: User = Depends(api_user_with_rate_limit),
) -> dict:
    async with CellarSPARQLClient() as client:
        # First confirm the CELEX exists in Cellar (else 404).
        meta = await client.get_celex_metadata(celex, language="ENG")
        if not meta:
            raise HTTPException(
                status_code=404,
                detail={"error": f"CELEX {celex} not found in Cellar", "reason_code": "not_found"},
            )
        # Pass the work URI we just resolved so the manifestations query
        # skips the CELEX→work join (orders of magnitude faster).
        manifestations = await client.get_manifestations(celex, work_uri=meta.get("work"))

    languages = sorted({m["language"] for m in manifestations if m.get("language")})
    return {
        "celex": celex,
        "cellar_uri": meta.get("work"),
        "eli": meta.get("eli"),
        "languages": languages,
        "language_count": len(languages),
        "manifestations": manifestations,
        "manifestation_count": len(manifestations),
        # The 5 mandatory Brubru v1 datapoints (about the parent CELEX)
        "public_url": _eurlex_url(celex),
        "body_txt": None,  # use /api/v1/citations/verify or /laws/{celex}/text for body
        "body_html": None,
        "document_date": _to_date(meta.get("date")).isoformat() if _to_date(meta.get("date")) else None,
        "creation_date": datetime.utcnow().isoformat(),
    }


@router.get(
    "/eurovoc",
    response_model=PaginatedResponse[EuroVocConcept],
    summary="Search the EU subject thesaurus",
)
async def search_eurovoc(
    request: Request,
    q: str = Query(..., min_length=2, description="Free-text search term", example="artificial intelligence"),
    language: str = Query("en", description="ISO-2 language code for labels"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[EuroVocConcept]:
    async with CellarSPARQLClient() as client:
        rows = await client.search_eurovoc_concepts(keyword=q, language=language, limit=limit)

    _now = datetime.utcnow()
    # Derive ShowVoc deep-link from concept URI.
    # EuroVoc URIs look like http://eurovoc.europa.eu/2517 ; ShowVoc opens at
    # https://showvoc.op.europa.eu/#/datasets/EuroVoc/data?resId=http%3A//eurovoc.europa.eu/2517
    def _showvoc_url(uri: str) -> str:
        from urllib.parse import quote
        return f"https://showvoc.op.europa.eu/#/datasets/EuroVoc/data?resId={quote(uri, safe='')}"

    items = [
        EuroVocConcept(
            concept_uri=r["concept"],
            label=r["label"],
            public_url=_showvoc_url(r["concept"]),
            body_txt=r.get("label"),  # the human-readable label IS the concept's content
            creation_date=_now,
        )
        for r in rows if r.get("concept")
    ]
    return build_envelope(items=items, total=len(items), page=1, limit=limit, coverage_complete=False)


@router.get(
    "/eurovoc/{concept_id}/acts",
    response_model=PaginatedResponse[CellarRecentItem],
    summary="Acts tagged with a subject (e.g. data protection, climate)",
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

    _now = datetime.utcnow()
    items = [
        CellarRecentItem(
            celex=r["celex"],
            work_uri=r.get("work"),
            document_date=_to_date(r.get("date")),
            title=r.get("title"),
            eurlex_url=_eurlex_url(r["celex"]),
            public_url=_eurlex_url(r["celex"]),
            creation_date=_now,
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
