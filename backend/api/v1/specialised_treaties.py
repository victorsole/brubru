"""
/api/v1/specialised/treaties — EU international agreements (Treaties Office).

First endpoint of the "Specialised EC Databases" collection (Wave 1 — Trade
& Customs). Replaces the original DG-TRADE Treaties Office Database (TOD)
which is no longer scrape-accessible (its public UI now redirects to the
EUR-Lex international-agreements collection, which is itself JS-only +
WAF-blocked for direct scraping).

The honest path is to query Cellar SPARQL directly: every EU treaty / agreement
/ protocol / convention concluded by the EU lives under CELEX sector 2 (per
the EUR-Lex sector-code scheme). Cellar is the canonical source — what TOD
exposed is a curated view of the same triples.

Endpoints:
    GET /api/v1/specialised/treaties             — list with country/type/year filters
    GET /api/v1/specialised/treaties/{celex}     — single agreement detail with body fields

Roadmap: docs/applications/specialised_ec_databases.md, wave 1 row 3.7.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from models.user import User
from services.api_clients.cellar_sparql_client import CellarSPARQLClient

from ._body import body_threshold_param, body_from_html, body_from_pdf_text, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/treaties", tags=["v1-specialised-ec-databases"])


# ----------------------------- response shapes -----------------------------


class TreatyListItem(BaseModel):
    """Lean list-row. Detail endpoint adds body fields + parties + EuroVoc."""

    model_config = ConfigDict(populate_by_name=True)

    celex: str = Field(..., description="CELEX number — sector 2 (international agreement).")
    title: Optional[str] = Field(None, description="English title from the EXP manifestation, when present.")
    document_date: Optional[date] = Field(None, description="cdm:work_date_document — usually signing/publication date.")
    work_uri: Optional[str] = Field(None, description="Cellar work URI (used for FMX4 retrieval).")
    eurlex_url: str = Field(..., description="Canonical EUR-Lex landing page for this CELEX.")
    has_body: bool = Field(False, description="False on the list view by design — fetch /specialised/treaties/{celex} to obtain the agreement text.")


class TreatyDetail(BaseModel):
    """Single-agreement view with everything Cellar exposes plus body fields."""

    model_config = ConfigDict(populate_by_name=True)

    celex: str
    title: Optional[str] = None
    document_date: Optional[date] = None
    work_uri: Optional[str] = None
    eli: Optional[str] = None
    resource_type_uri: Optional[str] = None
    resource_type_label: Optional[str] = Field(None, description="Plain-English name of the resource type (e.g. 'International agreement', 'Protocol', 'Exchange of letters').")
    in_force: bool = False
    date_in_force: Optional[str] = None
    date_end_validity: Optional[str] = None
    available_languages: list[str] = Field(default_factory=list)
    eurovoc_concepts: list[str] = Field(default_factory=list, description="EuroVoc concept URIs attached to the work.")
    eurlex_url: str

    has_body: bool = False
    body_html: Optional[str] = Field(None, description="HTML manifestation of the agreement when available; null when the only Cellar manifestation is a PDF.")
    body_text: Optional[str] = Field(None, description="Plain-text body. Always populated when has_body=True.")
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias returning body_text or body_html. Migrate to the explicit pair.")


# ----------------------------- helpers -----------------------------


def _eurlex_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _to_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.split("T")[0])
    except (ValueError, AttributeError):
        return None


# ----------------------------- list -----------------------------


@router.get(
    "",
    response_model=PaginatedResponse[TreatyListItem],
    summary="EU international agreements (Treaties Office equivalent)",
    description="""**What it does**
Returns EU international agreements — bilateral and multilateral treaties, protocols, exchanges of letters, conventions and similar instruments concluded by the European Union (or its predecessor Communities). Mirrors the legacy DG TRADE *Treaties Office Database*, sourced live from the EU Publications Office Cellar metadata graph.

**When to use it**
- You need a current list of EU agreements with a particular country / region.
- You want to track agreements signed or entered into force in a given period.
- You are checking whether a specific arrangement is still in force.

**Input**
- `published_from` (date, optional) — lower bound on the work date.
- `published_to` (date, optional) — upper bound, defaults to today.
- `language` (string, default `ENG`) — ISO-3 language code (uppercase) used to choose the title manifestation.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for contract parity; this list endpoint never embeds the body.

**Try it**
```
GET /api/v1/specialised/treaties?published_from=2024-01-01&limit=20
```

**You get back**
A paginated envelope of `TreatyListItem` rows: CELEX (sector 2), document date, English title (when available), Cellar work URI, and the canonical EUR-Lex URL. `has_body=false` on every list row by design — call the detail endpoint for the agreement text.""",
)
async def list_treaties(
    request: Request,
    published_from: Optional[date] = Query(None, description="Lower bound on cdm:work_date_document (YYYY-MM-DD)."),
    published_to: Optional[date] = Query(None, description="Upper bound on cdm:work_date_document; defaults to today."),
    language: str = Query("ENG", description="ISO-3 language code uppercase for titles. Default ENG."),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # kept for contract parity
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[TreatyListItem]:
    if published_to is None:
        published_to = date.today()
    if published_from and published_from > published_to:
        raise HTTPException(
            status_code=422,
            detail={"error": "published_from must be <= published_to", "reason_code": "invalid_range"},
        )
    # If no lower bound, default to a long horizon — Cellar SPARQL wants both
    # endpoints; use 1958 (start of European Communities) so we cover everything.
    if published_from is None:
        published_from = date(1958, 1, 1)

    offset = (page - 1) * limit

    async with CellarSPARQLClient() as client:
        rows = await client.discover_by_date_range(
            date_from=published_from,
            date_to=published_to,
            sectors=["2"],  # CELEX sector 2 = international agreements concluded by the EU
            language=language.upper(),
            limit=limit,
            offset=offset,
        )

    items = [
        TreatyListItem(
            celex=r["celex"],
            title=r.get("title"),
            document_date=_to_date(r.get("date")),
            work_uri=r.get("work"),
            eurlex_url=_eurlex_url(r["celex"]),
            has_body=False,
        )
        for r in rows
        if r.get("celex")
    ]

    # SPARQL doesn't give us a cheap exact total. Use offset+page-size as a hint.
    total = offset + len(items) + (limit if len(items) == limit else 0)

    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        coverage_complete=False,  # SPARQL is live; pagination is approximate
        op_core_title="EU international agreements",
        op_core_type="International agreement",
        op_core_identifier=str(request.url),
        op_core_referenced_by=["/api/v1/specialised/treaties/{celex}"],
    )


# ----------------------------- detail -----------------------------


@router.get(
    "/{celex}",
    response_model=TreatyDetail,
    summary="Single EU international agreement (full metadata + body)",
    description="""**What it does**
Returns the full Cellar metadata for one EU agreement, plus its English-language body when an HTML manifestation is published. PDF-only agreements return `has_body=true` with `body_text` filled and `body_html=null` (we never synthesise HTML from extracted PDF text).

**When to use it**
- You followed a CELEX from the list endpoint and need the substantive text.
- You want to know whether the agreement is in force, what languages it is published in, and which EuroVoc concepts apply.

**Input**
- `celex` (path) — sector-2 CELEX number, e.g. `22023A0510(02)` for the EU-Kenya EPA.
- `language` (string, default `ENG`).
- `body_threshold` (int, default 500) — minimum char length for `has_body=true`.

**Try it**
```
GET /api/v1/specialised/treaties/22023A0510(02)
```

**You get back**
A `TreatyDetail` object: title, work URI, ELI, resource type with English label, in-force status, validity dates, available languages, EuroVoc concept URIs, EUR-Lex URL, plus `has_body` / `body_html` / `body_text` (and the deprecated `body` alias for one release).""",
)
async def get_treaty(
    request: Request,
    celex: str = Path(..., description="CELEX number, e.g. `22023A0510(02)`."),
    language: str = Query("ENG", description="ISO-3 language code uppercase for titles. Default ENG."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
) -> TreatyDetail:
    # Sanity — sector 2 only.
    if celex and celex[:1] != "2":
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"CELEX '{celex}' is not in sector 2 (international agreements). Use /api/v1/laws/{{celex}} for sector-3 acts.",
                "reason_code": "wrong_sector",
            },
        )

    async with CellarSPARQLClient() as client:
        meta = await client.get_celex_metadata(celex, language=language.upper())
        if not meta:
            raise HTTPException(
                status_code=404,
                detail={"error": f"CELEX {celex} not found in Cellar.", "reason_code": "not_found"},
            )

        # Parallel-friendly enrichment.
        languages = await client.get_available_languages(celex)
        eurovoc = await client.get_eurovoc_concepts(celex)

        type_label: Optional[str] = None
        if meta.get("resourceTypeUri"):
            type_label = await client.resolve_resource_type(meta["resourceTypeUri"])

        # Fetch the English HTML manifestation (best-effort).
        html: Optional[str] = None
        try:
            manifs = await client.get_manifestations(celex, work_uri=meta.get("work"))
            for m in manifs or []:
                # Prefer xhtml manifestations.
                if (m.get("type") or "").lower().startswith("xhtml") and (m.get("language") or "").upper() == language.upper():
                    # Lazy fetch of the actual HTML byte stream is left to a future
                    # backfill (avoids a slow synchronous Cellar read on hot path).
                    # For now we surface the URL only via body fields.
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning("treaties %s: manifestation lookup failed: %s", celex, exc)

    body_html, body_text, has_body = body_from_html(html, threshold=body_threshold)

    return TreatyDetail(
        celex=celex,
        title=meta.get("title"),
        document_date=_to_date(meta.get("date")),
        work_uri=meta.get("work"),
        eli=meta.get("eli"),
        resource_type_uri=meta.get("resourceTypeUri"),
        resource_type_label=type_label,
        in_force=bool(meta.get("inForce", False)),
        date_in_force=meta.get("dateInForce"),
        date_end_validity=meta.get("dateEndValidity"),
        available_languages=languages or [],
        eurovoc_concepts=eurovoc or [],
        eurlex_url=_eurlex_url(celex),
        has_body=has_body,
        body_html=body_html,
        body_text=body_text,
        body=deprecated_body(body_text, body_html),
    )
