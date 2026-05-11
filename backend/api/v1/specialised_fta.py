"""
/api/v1/specialised/fta — EU international agreements (FTA-equivalent surface).

Replaces the earlier /api/v1/specialised/treaties endpoint. Same data
domain — every CELEX sector-2 type-A instrument signed by the EU — but
backed by a local table (`eu_trade_agreements`) populated by
backfill_eu_trade_agreements.py instead of a live Cellar SPARQL fetch.

Why renamed: "treaties" in EU jargon means founding treaties (TEU, TFEU)
which are sector 1, NOT this surface. Users expecting trade agreements
were confused. /fta is the partner-friendly path; the description
clearly states the broader scope (FTAs + EPAs + AAs + PCAs + Fisheries
+ Aviation + tax-info + Exchange-of-Letters).

Endpoints:
    GET /api/v1/specialised/fta              — list with filters
    GET /api/v1/specialised/fta/{celex}      — single agreement detail
    GET /api/v1/specialised/fta/types        — distinct agreement_type counts
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/fta", tags=["v1-specialised-ec-databases"])


# ----------------------------- response shapes -----------------------------


class FtaListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    celex: str
    title: Optional[str] = None
    document_date: Optional[date] = None
    agreement_type: Optional[str] = Field(
        None,
        description=(
            "Brubru-derived classification: FTA, EPA, AssociationAgreement, PCA, EPCA, "
            "InterimTrade, FisheriesPartnership, Aviation, ResearchCooperation, "
            "SocialSecurity, CustomsCooperation, TaxInfoExchange, ExchangeOfLetters, "
            "Protocol, StrategicPartnership, Agreement, Other."
        ),
    )
    partner: Optional[str] = Field(None, description="Best-effort regex extract from title.")
    in_force: Optional[bool] = None
    eurlex_url: str
    has_body: bool = Field(False, description="True if this agreement has a stored body. List rows always show False; call the detail endpoint for the body itself.")


class FtaDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    celex: str
    title: Optional[str] = None
    document_date: Optional[date] = None
    work_uri: Optional[str] = None

    resource_type_uri: Optional[str] = None
    resource_type_label: Optional[str] = None
    agreement_type: Optional[str] = None
    partner: Optional[str] = None

    in_force: Optional[bool] = None
    date_in_force: Optional[date] = None
    date_end_validity: Optional[date] = None
    available_languages: list[str] = Field(default_factory=list)
    eurovoc_concepts: list[str] = Field(default_factory=list)
    eurlex_url: str

    has_body: bool = False
    body_html: Optional[str] = Field(None, description="HTML manifestation when Cellar served XHTML; null when only a PDF was available.")
    body_txt: Optional[str] = Field(None, description="Plain-text body. Always populated when has_body=True.")
    body_source: Optional[str] = Field(None, description="'xhtml' or 'pdf' depending on which Cellar manifestation produced the body.")
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias for body_text/body_html.")
    fetched_at: Optional[str] = None


class AgreementTypeCount(BaseModel):
    agreement_type: str
    in_force: int
    historical: int
    total: int


# ----------------------------- list -----------------------------


@router.get(
    "",
    response_model=PaginatedResponse[FtaListItem],
    summary="EU international agreements (FTA-equivalent surface)",
    description="""**What it does**
Returns every international agreement signed by the European Union — the "FTA" surface in partner-facing language. Despite the name, scope is broader than strict free-trade agreements: it includes Free Trade Agreements (e.g. EU-Canada CETA, EU-South Korea, EU-Vietnam), Economic Partnership Agreements (EPAs), Association Agreements (AA), Partnership and Cooperation Agreements (PCA), Fisheries Partnership Agreements, Aviation Agreements, tax-info exchanges, and the Exchange-of-Letters family. Each item is a CELEX sector-2 type-A instrument (a signed agreement, not a Council decision around one).

Use the `agreement_type` filter to narrow to strict FTAs (`agreement_type=FTA`).

**When to use it**
- Trade-policy researchers tracking the EU's bilateral and multilateral commitments.
- Compliance teams checking whether a partner country has an agreement in force.
- Journalists writing about new agreements (filter by `published_from`).

**Input**
- `agreement_type` (string, optional) — narrow to one Brubru-derived class (FTA, EPA, AssociationAgreement, FisheriesPartnership, Aviation, etc.).
- `partner` (string, optional) — case-insensitive substring match on the partner country/region.
- `in_force` (bool, optional) — true to return only agreements still in force.
- `published_from` / `published_to` (dates, optional) — bounds on document_date.
- `q` (string, optional) — full-text search on title.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for contract parity; the list endpoint never embeds the body.

**Try it**
```
GET /api/v1/specialised/fta?agreement_type=FTA&in_force=true
```

**You get back**
A paginated envelope of `FtaListItem` rows: CELEX, title, document_date, agreement_type, partner, in_force flag, EUR-Lex URL. `has_body=false` on every list row by design; the detail endpoint returns the agreement text itself.""",
)
async def list_fta(
    request: Request,
    agreement_type: Optional[str] = Query(None, description="Filter to one Brubru-derived class."),
    partner: Optional[str] = Query(None, description="Case-insensitive substring on partner."),
    in_force: Optional[bool] = Query(None, description="True = only agreements currently in force."),
    published_from: Optional[date] = Query(None, description="Lower bound on document_date."),
    published_to: Optional[date] = Query(None, description="Upper bound on document_date."),
    q: Optional[str] = Query(None, description="Full-text search on title."),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # contract parity
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FtaListItem]:
    where: list[str] = []
    params: dict = {}
    if agreement_type:
        where.append("agreement_type = :agreement_type")
        params["agreement_type"] = agreement_type
    if partner:
        where.append("partner ILIKE :partner")
        params["partner"] = f"%{partner}%"
    if in_force is not None:
        where.append("in_force = :in_force")
        params["in_force"] = in_force
    if published_from:
        where.append("document_date >= :published_from")
        params["published_from"] = published_from
    if published_to:
        where.append("document_date <= :published_to")
        params["published_to"] = published_to
    if q:
        where.append("to_tsvector('english', COALESCE(title,'')) @@ plainto_tsquery('english', :q)")
        params["q"] = q
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(
        text(f"SELECT COUNT(*) AS n FROM eu_trade_agreements {where_sql}"), params
    ).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(
        text(f"""
            SELECT celex, title, document_date, agreement_type, partner, in_force, eurlex_url, has_body
              FROM eu_trade_agreements
              {where_sql}
             ORDER BY document_date DESC NULLS LAST, celex DESC
             LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    ).mappings().all()

    items = [
        FtaListItem(
            celex=r["celex"],
            title=r.get("title"),
            document_date=r.get("document_date"),
            agreement_type=r.get("agreement_type"),
            partner=r.get("partner"),
            in_force=r.get("in_force"),
            eurlex_url=r["eurlex_url"],
            has_body=False,  # list rows always advertise False
        )
        for r in rows
    ]

    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        op_core_title="EU international agreements (FTA surface)",
        op_core_type="International agreement",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/specialised/fta/{celex}",
            "/api/v1/specialised/fta/types",
        ],
    )


# ----------------------------- types meta -----------------------------


@router.get(
    "/types",
    response_model=list[AgreementTypeCount],
    summary="Distinct agreement types with counts",
    description="""**What it does**
Returns each Brubru-derived `agreement_type` with the count of agreements still in force, the count of historical (no longer in force or unknown), and the total. Useful for picker UIs.

**When to use it**
- Building a dropdown of available agreement classifications.
- Quick sanity check after a backfill.

**Input**
None.

**Try it**
```
GET /api/v1/specialised/fta/types
```

**You get back**
A flat list of `AgreementTypeCount` objects sorted by total descending.""",
)
async def list_types(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[AgreementTypeCount]:
    rows = db.execute(text(
        """
        SELECT COALESCE(agreement_type,'(unknown)') AS agreement_type,
               COUNT(*) FILTER (WHERE in_force) AS in_force,
               COUNT(*) FILTER (WHERE in_force IS NOT TRUE) AS historical,
               COUNT(*) AS total
          FROM eu_trade_agreements
         GROUP BY 1
         ORDER BY total DESC
        """
    )).mappings().all()
    return [
        AgreementTypeCount(
            agreement_type=r["agreement_type"],
            in_force=int(r["in_force"] or 0),
            historical=int(r["historical"] or 0),
            total=int(r["total"] or 0),
        )
        for r in rows
    ]


# ----------------------------- detail -----------------------------


@router.get(
    "/{celex:path}",
    response_model=FtaDetail,
    summary="Single EU agreement (full metadata + body)",
    description="""**What it does**
Returns the full record for one agreement, including the agreement text itself in `body_html` (when Cellar served XHTML) or `body_text` only (PDF-sourced — we never synthesise HTML from extracted PDF text).

**When to use it**
- You followed a CELEX from the list endpoint and need the actual agreement text.
- You want the EuroVoc concepts attached to the work.
- You need the in-force status and validity dates.

**Input**
- `celex` (path) — sector-2 type-A CELEX, e.g. `22018A1227(01)` for EU-Japan EPA. Parens are tolerated unencoded; the FastAPI matcher uses `:path` so corrigendum suffixes (`R(01)`) work too.
- `body_threshold` (int, default 500) — minimum char length of `body_text` to set `has_body=True`.

**Try it**
```
GET /api/v1/specialised/fta/22018A1227(01)
```

**You get back**
An `FtaDetail` object with the agreement title, work URI, resource type, in-force flag, validity dates, available languages, EuroVoc concepts, EUR-Lex URL, and the body fields.""",
)
async def get_fta(
    request: Request,
    celex: str = Path(..., description="CELEX number, e.g. 22018A1227(01)."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtaDetail:
    row = db.execute(text(
        """
        SELECT celex, title, document_date, work_uri,
               resource_type_uri, resource_type_label,
               agreement_type, partner,
               in_force, date_in_force, date_end_validity,
               available_languages, eurovoc_concepts,
               eurlex_url,
               has_body, body_html, body_text, body_source,
               fetched_at
          FROM eu_trade_agreements
         WHERE celex = :celex
         LIMIT 1
        """
    ), {"celex": celex}).mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Agreement '{celex}' not found in eu_trade_agreements.", "reason_code": "not_found"},
        )

    # Re-evaluate has_body using the request's body_threshold.
    body_text = row.get("body_text")
    has_body_at_threshold = bool(body_text and len(body_text) >= body_threshold)

    return FtaDetail(
        celex=row["celex"],
        title=row.get("title"),
        document_date=row.get("document_date"),
        work_uri=row.get("work_uri"),
        resource_type_uri=row.get("resource_type_uri"),
        resource_type_label=row.get("resource_type_label"),
        agreement_type=row.get("agreement_type"),
        partner=row.get("partner"),
        in_force=row.get("in_force"),
        date_in_force=row.get("date_in_force"),
        date_end_validity=row.get("date_end_validity"),
        available_languages=row.get("available_languages") or [],
        eurovoc_concepts=row.get("eurovoc_concepts") or [],
        eurlex_url=row["eurlex_url"],
        has_body=has_body_at_threshold,
        body_html=row.get("body_html"),
        body_txt=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
        fetched_at=str(row.get("fetched_at")) if row.get("fetched_at") else None,
    )
