"""
/api/v1/specialised/transparency-register — EU Transparency Register
(interest representatives / lobbyists).

Backed by eu_transparency_register, populated daily from
transparency-register.europa.eu/odplastorganisationxml_en. ~17,247
active organisations as of May 2026.

Endpoints:
    GET /api/v1/specialised/transparency-register              — list with filters
    GET /api/v1/specialised/transparency-register/categories   — registration_category counts
    GET /api/v1/specialised/transparency-register/{code}       — single organisation detail with body
"""

from __future__ import annotations

import logging
from datetime import date, datetime
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

router = APIRouter(prefix="/specialised/transparency-register", tags=["v1-specialised-ec-databases"])


# ----------------------------- response shapes -----------------------------


class TrListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identification_code: str
    original_name: Optional[str] = None
    acronym: Optional[str] = None
    registration_category: Optional[str] = None
    head_office_country: Optional[str] = None
    head_office_city: Optional[str] = None
    website_url: Optional[str] = None
    ep_accredited_number: Optional[int] = None
    members_fte: Optional[float] = None
    costs_max: Optional[float] = None
    registration_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None
    public_url: Optional[str] = None
    has_body: bool = False


class TrDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    identification_code: str
    registration_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None

    original_name: Optional[str] = None
    acronym: Optional[str] = None
    entity_form: Optional[str] = None
    website_url: Optional[str] = None
    registration_category: Optional[str] = None

    head_office_address: Optional[str] = None
    head_office_post_code: Optional[str] = None
    head_office_city: Optional[str] = None
    head_office_country: Optional[str] = None
    head_office_phone: Optional[str] = None

    eu_office_address: Optional[str] = None
    eu_office_post_code: Optional[str] = None
    eu_office_city: Optional[str] = None
    eu_office_country: Optional[str] = None
    eu_office_phone: Optional[str] = None

    goals: Optional[str] = None
    eu_legislative_proposals: Optional[str] = None
    communication_activities: Optional[str] = None
    intergroup_activities: Optional[str] = None
    info_members: Optional[str] = None
    is_member_of: Optional[str] = None
    organisation_members: Optional[str] = None
    interest_represented: Optional[str] = None
    complementary_info: Optional[str] = None

    members_100_percent: Optional[int] = None
    members_50_percent: Optional[int] = None
    members_total: Optional[float] = None
    members_fte: Optional[float] = None
    ep_accredited_number: Optional[int] = None

    financial_year_start: Optional[date] = None
    financial_year_end: Optional[date] = None
    costs_min: Optional[float] = None
    costs_max: Optional[float] = None
    grants_total: Optional[float] = None
    intermediaries_costs: Optional[float] = None
    new_organisation: Optional[bool] = None

    levels_of_interest: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)

    public_url: Optional[str] = None

    has_body: bool = False
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    body_source: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias for body_text/body_html.")
    fetched_at: Optional[datetime] = None


class CategoryCount(BaseModel):
    registration_category: Optional[str]
    organisations: int
    ep_passes: int
    median_costs_max: Optional[float] = None


# ----------------------------- list -----------------------------


@router.get(
    "",
    response_model=PaginatedResponse[TrListItem],
    summary="EU Transparency Register (lobbyists / interest representatives)",
    description="""**What it does**
Returns organisations registered in the EU Transparency Register — the interest representatives (lobbyists, NGOs, trade unions, professional associations, think tanks, law firms, churches, etc.) who declare lobbying activity towards the European Commission and the European Parliament. Sourced from the daily public XML at `transparency-register.europa.eu/odplastorganisationxml_en` (~17,247 active organisations).

**When to use it**
- Journalists / researchers tracking who lobbies on what.
- Compliance teams running counterparty due diligence on stakeholders.
- Mapping the EU political-influence landscape by category, country or interest area.

**Input**
- `country` (string, optional) — head-office country (free-text match, case-insensitive).
- `category` (string, optional) — registration category (e.g. "Trade unions and professional associations", "Companies & groups", "NGOs"). Use the `/categories` endpoint to see all available values.
- `interest` (string, optional) — case-insensitive substring search on the `interests` array (matches policy areas like "Climate action", "Digital economy and society", "Trade").
- `q` (string, optional) — full-text search on organisation name + acronym.
- `min_fte` (float, optional) — minimum lobbyists full-time-equivalent (active staff).
- `min_costs` (float, optional) — minimum declared annual lobbying costs (lower bound).
- `ep_accredited_only` (bool, optional) — true to return only orgs with at least one EP-accredited pass.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for contract parity; the list endpoint never embeds the body.

**Try it**
```
GET /api/v1/specialised/transparency-register?country=BELGIUM&interest=climate&min_fte=1
```

**You get back**
A paginated envelope of `TrListItem` rows: identification code, name, acronym, category, head-office country/city, website, EP-accredited count, FTE, costs ceiling, registration / update timestamps, public URL.""",
)
async def list_tr(
    request: Request,
    country: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    interest: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    min_fte: Optional[float] = Query(None),
    min_costs: Optional[float] = Query(None),
    ep_accredited_only: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # parity
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TrListItem]:
    where: list[str] = []
    params: dict = {}
    if country:
        where.append("UPPER(head_office_country) = UPPER(:country)"); params["country"] = country
    if category:
        where.append("registration_category ILIKE :category"); params["category"] = f"%{category}%"
    if interest:
        where.append("EXISTS (SELECT 1 FROM unnest(interests) i WHERE i ILIKE :interest)")
        params["interest"] = f"%{interest}%"
    if q:
        where.append("(original_name ILIKE :q OR acronym ILIKE :q)")
        params["q"] = f"%{q}%"
    if min_fte is not None:
        where.append("members_fte >= :min_fte"); params["min_fte"] = min_fte
    if min_costs is not None:
        where.append("costs_max >= :min_costs"); params["min_costs"] = min_costs
    if ep_accredited_only:
        where.append("ep_accredited_number > 0")
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(
        text(f"SELECT COUNT(*) FROM eu_transparency_register {where_sql}"), params
    ).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(
        text(f"""
            SELECT identification_code, original_name, acronym, registration_category,
                   head_office_country, head_office_city, website_url,
                   ep_accredited_number, members_fte, costs_max,
                   registration_date, last_update_date, public_url, has_body
              FROM eu_transparency_register
              {where_sql}
             ORDER BY costs_max DESC NULLS LAST, original_name
             LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    ).mappings().all()

    items = [
        TrListItem(
            identification_code=r["identification_code"],
            original_name=r.get("original_name"),
            acronym=r.get("acronym"),
            registration_category=r.get("registration_category"),
            head_office_country=r.get("head_office_country"),
            head_office_city=r.get("head_office_city"),
            website_url=r.get("website_url"),
            ep_accredited_number=r.get("ep_accredited_number"),
            members_fte=float(r["members_fte"]) if r.get("members_fte") is not None else None,
            costs_max=float(r["costs_max"]) if r.get("costs_max") is not None else None,
            registration_date=r.get("registration_date"),
            last_update_date=r.get("last_update_date"),
            public_url=r.get("public_url"),
            has_body=False,
        )
        for r in rows
    ]

    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        op_core_title="EU Transparency Register",
        op_core_type="Interest representative",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/specialised/transparency-register/{code}",
            "/api/v1/specialised/transparency-register/categories",
        ],
    )


# ----------------------------- categories meta -----------------------------


@router.get(
    "/categories",
    response_model=list[CategoryCount],
    summary="Registration-category breakdown with EP-pass and costs aggregates",
    description="""**What it does**
Returns each `registration_category` with the number of organisations, the total EP-accredited passes for that category, and the median of declared maximum lobbying costs. Useful for high-level dashboards.

**When to use it**
- Building a category picker.
- Quick comparative view of which categories spend the most.

**Input**
None.

**Try it**
```
GET /api/v1/specialised/transparency-register/categories
```

**You get back**
A flat list of `CategoryCount` objects sorted by organisation count descending.""",
)
async def list_categories(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[CategoryCount]:
    rows = db.execute(text(
        """
        SELECT registration_category,
               COUNT(*) AS organisations,
               COALESCE(SUM(ep_accredited_number), 0) AS ep_passes,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY costs_max) AS median_costs
          FROM eu_transparency_register
         GROUP BY registration_category
         ORDER BY organisations DESC
        """
    )).mappings().all()
    return [
        CategoryCount(
            registration_category=r["registration_category"],
            organisations=int(r["organisations"]),
            ep_passes=int(r["ep_passes"] or 0),
            median_costs_max=(float(r["median_costs"]) if r.get("median_costs") is not None else None),
        )
        for r in rows
    ]


# ----------------------------- detail -----------------------------


@router.get(
    "/{code}",
    response_model=TrDetail,
    summary="Single organisation in the Transparency Register (full record + body)",
    description="""**What it does**
Returns the full record for one registered organisation: head and EU offices, lobbying activities (free text), declared interests, financial data (closed-year costs and grants), EP-accredited passes, and the composed body fields combining all the substantive free-text declarations into a single readable article.

**When to use it**
- Compliance / KYC workflows.
- Investigative journalism.
- Generating an organisation profile.

**Input**
- `code` (path) — Transparency Register identification code (e.g. `880143435725-46`).
- `body_threshold` (int, default 500) — minimum char length of `body_text` to flag `has_body=True`.

**Try it**
```
GET /api/v1/specialised/transparency-register/880143435725-46
```

**You get back**
A `TrDetail` object with all stored fields plus body_html / body_text composed from goals + EU legislative proposals + communication activities + intergroup activities + member info + structure + complementary info.""",
)
async def get_tr(
    request: Request,
    code: str = Path(..., description="Transparency Register identification code, e.g. 880143435725-46."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TrDetail:
    row = db.execute(text(
        "SELECT * FROM eu_transparency_register WHERE identification_code = :code LIMIT 1"
    ), {"code": code}).mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Organisation '{code}' not found.", "reason_code": "not_found"},
        )

    body_text = row.get("body_text")
    has_body_at_threshold = bool(body_text and len(body_text) >= body_threshold)

    return TrDetail(
        identification_code=row["identification_code"],
        registration_date=row.get("registration_date"),
        last_update_date=row.get("last_update_date"),
        original_name=row.get("original_name"),
        acronym=row.get("acronym"),
        entity_form=row.get("entity_form"),
        website_url=row.get("website_url"),
        registration_category=row.get("registration_category"),
        head_office_address=row.get("head_office_address"),
        head_office_post_code=row.get("head_office_post_code"),
        head_office_city=row.get("head_office_city"),
        head_office_country=row.get("head_office_country"),
        head_office_phone=row.get("head_office_phone"),
        eu_office_address=row.get("eu_office_address"),
        eu_office_post_code=row.get("eu_office_post_code"),
        eu_office_city=row.get("eu_office_city"),
        eu_office_country=row.get("eu_office_country"),
        eu_office_phone=row.get("eu_office_phone"),
        goals=row.get("goals"),
        eu_legislative_proposals=row.get("eu_legislative_proposals"),
        communication_activities=row.get("communication_activities"),
        intergroup_activities=row.get("intergroup_activities"),
        info_members=row.get("info_members"),
        is_member_of=row.get("is_member_of"),
        organisation_members=row.get("organisation_members"),
        interest_represented=row.get("interest_represented"),
        complementary_info=row.get("complementary_info"),
        members_100_percent=row.get("members_100_percent"),
        members_50_percent=row.get("members_50_percent"),
        members_total=float(row["members_total"]) if row.get("members_total") is not None else None,
        members_fte=float(row["members_fte"]) if row.get("members_fte") is not None else None,
        ep_accredited_number=row.get("ep_accredited_number"),
        financial_year_start=row.get("financial_year_start"),
        financial_year_end=row.get("financial_year_end"),
        costs_min=float(row["costs_min"]) if row.get("costs_min") is not None else None,
        costs_max=float(row["costs_max"]) if row.get("costs_max") is not None else None,
        grants_total=float(row["grants_total"]) if row.get("grants_total") is not None else None,
        intermediaries_costs=float(row["intermediaries_costs"]) if row.get("intermediaries_costs") is not None else None,
        new_organisation=row.get("new_organisation"),
        levels_of_interest=row.get("levels_of_interest") or [],
        interests=row.get("interests") or [],
        public_url=row.get("public_url"),
        has_body=has_body_at_threshold,
        body_html=row.get("body_html"),
        body_text=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
        fetched_at=row.get("fetched_at"),
    )
