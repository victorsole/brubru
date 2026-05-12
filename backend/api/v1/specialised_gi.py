"""
/api/v1/specialised/gi — EU Geographical Indications (PDOs / PGIs / TSGs / etc).

Sources merged in the eu_geographical_indications table:
- eAmbrosia (DG AGRI authoritative register, ~3,994 records). Deep
  per-record detail.
- GIview (EUIPO union register, ~5,809 records). Adds pending
  applications and craft / industrial GIs.

The endpoint always returns the merged dataset. Filters by gi_type
(PDO/PGI/TSG), product_type (WINE/SPIRIT/FOOD/AROMATISED), country,
status, etc.

Endpoints:
    GET /api/v1/specialised/gi              — list with filters
    GET /api/v1/specialised/gi/types        — gi_type / product_type breakdown
    GET /api/v1/specialised/gi/{gi_id}      — single GI with body fields
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

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

router = APIRouter(prefix="/specialised/gi", tags=["v1-specialised-ec-databases"])


# ----------------------------- response shapes -----------------------------


class GiListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    gi_identifier: str
    protected_names: list[str] = Field(default_factory=list)
    file_number: Optional[str] = None
    countries: list[str] = Field(default_factory=list)
    gi_type: Optional[str] = Field(None, description="PDO / PGI / TSG / GI")
    product_type: Optional[str] = Field(None, description="WINE / SPIRIT / FOOD / AROMATISED / etc.")
    status: Optional[str] = None
    eu_protection_date: Optional[date] = None
    third_country_flag: Optional[bool] = None
    eurlex_url: Optional[str] = None
    public_url: Optional[str] = None
    source: str = Field(..., description="eambrosia / giview / merged")
    has_body: bool = False
    # 5 mandatory Brubru v1 datapoints (public_url already present above).
    body_txt: Optional[str] = Field(None, description="Plain-text composition: protected names + type + countries + product + protection date + status.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields.")
    document_date: Optional[date] = Field(None, description="EU protection date (alias of eu_protection_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru last refreshed this row.")


class GiDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    gi_identifier: str
    protected_names: list[str] = Field(default_factory=list)
    file_number: Optional[str] = None
    countries: list[str] = Field(default_factory=list)
    third_country_flag: Optional[bool] = None
    map_locations: Optional[list[dict]] = None

    gi_type: Optional[str] = None
    product_type: Optional[str] = None
    product_categories: Optional[list] = None
    cn_classification: Optional[list] = None

    status: Optional[str] = None
    eu_protection_date: Optional[date] = None
    modification_date: Optional[datetime] = None
    amendments_in_progress: Optional[bool] = None
    removed_flag: Optional[bool] = None

    legal_instrument: Optional[dict] = None
    publications: Optional[list] = None
    single_document: Optional[dict] = None
    summary_sheets: Optional[list] = None
    transcriptions: Optional[Any] = None
    amendments: Optional[Any] = None

    producer_group_name: Optional[str] = None
    producer_group_email: Optional[str] = None
    producer_group_phone: Optional[str] = None
    producer_group_url: Optional[str] = None
    producer_group_address: Optional[str] = None
    producer_group_country: Optional[str] = None
    producer_group_updated_on: Optional[datetime] = None

    competent_control_authorities: Optional[list] = None
    recognised_producers_group: Optional[list] = None
    sustainability_reports: Optional[list] = None

    source: str
    giview_source: Optional[str] = None
    giview_database: Optional[str] = None
    eambrosia_url: Optional[str] = None
    eurlex_url: Optional[str] = None
    public_url: Optional[str] = None

    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    body_source: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias for body_text/body_html.")
    fetched_at: Optional[datetime] = None
    # 5 mandatory Brubru v1 datapoints (public_url already present above).
    document_date: Optional[date] = Field(None, description="EU protection date (alias of eu_protection_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru last refreshed this row (alias of fetched_at).")


class GiTypeCount(BaseModel):
    gi_type: Optional[str]
    product_type: Optional[str]
    count: int


# ----------------------------- list -----------------------------


@router.get(
    "",
    response_model=PaginatedResponse[GiListItem],
    summary="EU Geographical Indications (PDOs / PGIs / TSGs / craft + industrial GIs)",
    description="""**What it does**
Returns Geographical Indications protected at EU level — Protected Designations of Origin (PDOs), Protected Geographical Indications (PGIs), Traditional Specialities Guaranteed (TSGs), wine GIs, spirit GIs, aromatised wine GIs, and the new craft + industrial GIs (Regulation (EU) 2023/2411). Merged from two upstream registers:

- **eAmbrosia** at `webgate.ec.europa.eu/eambrosia-api` — DG AGRI's authoritative EU register. Deep per-record detail (producer group, competent authorities, summary sheets, sustainability reports, CN classification).
- **GIview** at `tmdn.org/giview` — EUIPO's union register, broader scope (pending applications + additional third-country GIs + craft GIs).

**When to use it**
- Trade-mark / IP teams checking GI conflicts before filing a mark.
- Food / wine producers looking up registrations.
- Trade-policy researchers tracking third-country GIs protected through bilateral agreements (Korean ginseng, Mexican tequila, Japanese sake).

**Input**
- `gi_type` (string, optional) — `PDO`, `PGI`, `TSG`, `GI`.
- `product_type` (string, optional) — `WINE`, `SPIRIT`, `FOOD`, `AROMATISED`, etc.
- `country` (string, optional) — ISO-2 country code; matches any element of the `countries` array.
- `status` (string, optional) — `registered`, `applied`, `cancelled`, `under_examination`, etc.
- `third_country_flag` (bool, optional) — true to return only third-country GIs.
- `q` (string, optional) — case-insensitive search over `protected_names`.
- `protected_from` / `protected_to` (dates, optional) — bounds on `eu_protection_date`.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for contract parity; the list endpoint never embeds the body.

**Try it**
```
GET /api/v1/specialised/gi?gi_type=PDO&product_type=WINE&country=FR
```

**You get back**
A paginated envelope of `GiListItem` rows: GI identifier, protected names, file number, countries, classification, status, EU protection date, source register, EUR-Lex link to the founding regulation, public-facing URL.""",
)
async def list_gi(
    request: Request,
    gi_type: Optional[str] = Query(None),
    product_type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    third_country_flag: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    protected_from: Optional[date] = Query(None),
    protected_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # parity
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[GiListItem]:
    where: list[str] = []
    params: dict = {}
    if gi_type:
        where.append("gi_type = :gi_type"); params["gi_type"] = gi_type.upper()
    if product_type:
        where.append("product_type = :product_type"); params["product_type"] = product_type.upper()
    if country:
        where.append(":country = ANY(countries)"); params["country"] = country.upper()
    if status:
        where.append("LOWER(status) = LOWER(:status)"); params["status"] = status
    if third_country_flag is not None:
        where.append("third_country_flag = :third_country_flag"); params["third_country_flag"] = third_country_flag
    if q:
        where.append("EXISTS (SELECT 1 FROM unnest(protected_names) n WHERE n ILIKE :q)")
        params["q"] = f"%{q}%"
    if protected_from:
        where.append("eu_protection_date >= :protected_from"); params["protected_from"] = protected_from
    if protected_to:
        where.append("eu_protection_date <= :protected_to"); params["protected_to"] = protected_to
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(
        text(f"SELECT COUNT(*) FROM eu_geographical_indications {where_sql}"), params
    ).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(
        text(f"""
            SELECT gi_identifier, protected_names, file_number, countries,
                   gi_type, product_type, status, eu_protection_date,
                   third_country_flag, eurlex_url, public_url, source, has_body
              FROM eu_geographical_indications
              {where_sql}
             ORDER BY eu_protection_date DESC NULLS LAST, gi_identifier
             LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    ).mappings().all()

    def _gi_body(r):
        import html as _html
        names = ", ".join(r.get("protected_names") or []) or r["gi_identifier"]
        lines = [names]
        parts_html = [f"<h2>{_html.escape(names)}</h2>"]
        for k, v in [
            ("GI identifier", r["gi_identifier"]),
            ("Type", r.get("gi_type")),
            ("Product type", r.get("product_type")),
            ("Countries", ", ".join(r.get("countries") or []) or None),
            ("EU protection date", r.get("eu_protection_date")),
            ("Status", r.get("status")),
            ("Source", r.get("source")),
        ]:
            if not v: continue
            lines.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        return "\n".join(lines), "<article>" + "".join(parts_html) + "</article>"

    items = []
    for r in rows:
        bt, bh = _gi_body(r)
        items.append(GiListItem(
            gi_identifier=r["gi_identifier"],
            protected_names=r.get("protected_names") or [],
            file_number=r.get("file_number"),
            countries=r.get("countries") or [],
            gi_type=r.get("gi_type"),
            product_type=r.get("product_type"),
            status=r.get("status"),
            eu_protection_date=r.get("eu_protection_date"),
            third_country_flag=r.get("third_country_flag"),
            eurlex_url=r.get("eurlex_url"),
            public_url=r.get("public_url"),
            source=r["source"],
            has_body=False,
            body_txt=bt,
            body_html=bh,
            document_date=r.get("eu_protection_date"),
            creation_date=r.get("fetched_at") or r.get("updated_at"),
        ))

    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        op_core_title="EU Geographical Indications",
        op_core_type="Geographical Indication",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/specialised/gi/{gi_id}",
            "/api/v1/specialised/gi/types",
        ],
    )


# ----------------------------- types meta -----------------------------


@router.get(
    "/types",
    response_model=list[GiTypeCount],
    summary="GI type and product-type counts",
    description="""**What it does**
Returns the count of GIs by (gi_type, product_type) combination.

**When to use it**
- Building a filter dropdown.
- Quick dataset overview.

**Input**
None.

**Try it**
```
GET /api/v1/specialised/gi/types
```

**You get back**
A flat list of `GiTypeCount` objects sorted by count descending.""",
)
async def list_types(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[GiTypeCount]:
    rows = db.execute(text(
        """
        SELECT gi_type, product_type, COUNT(*) AS n
          FROM eu_geographical_indications
         GROUP BY gi_type, product_type
         ORDER BY n DESC
        """
    )).mappings().all()
    return [
        GiTypeCount(
            gi_type=r["gi_type"],
            product_type=r["product_type"],
            count=int(r["n"] or 0),
        )
        for r in rows
    ]


# ----------------------------- detail -----------------------------


@router.get(
    "/{gi_id}",
    response_model=GiDetail,
    summary="Single Geographical Indication (full record + body)",
    description="""**What it does**
Returns the full record for one GI, including (when present) the producer-group contact, competent control authorities, sustainability reports, summary-sheet body text composed from the eAmbrosia attachment, and the legal-instrument link to the founding Commission Implementing Regulation on EUR-Lex.

**When to use it**
- IP / trade-mark conflict assessment.
- Compliance teams verifying a registration.
- Researchers wanting the substantive specification text.

**Input**
- `gi_id` (path) — the EUGIxxxxxxxxxx identifier (eAmbrosia + GIview share this).
- `body_threshold` (int, default 500) — minimum char length of `body_text` to flag `has_body=True`.

**Try it**
```
GET /api/v1/specialised/gi/EUGI00000000021
```

**You get back**
A `GiDetail` object with all stored fields plus body fields when a summary sheet has been fetched and parsed.""",
)
async def get_gi(
    request: Request,
    gi_id: str = Path(..., description="GI identifier, e.g. EUGI00000000021."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> GiDetail:
    row = db.execute(text(
        "SELECT * FROM eu_geographical_indications WHERE gi_identifier = :gi LIMIT 1"
    ), {"gi": gi_id}).mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"GI '{gi_id}' not found.", "reason_code": "not_found"},
        )

    body_text = row.get("body_text")
    has_body_at_threshold = bool(body_text and len(body_text) >= body_threshold)

    return GiDetail(
        gi_identifier=row["gi_identifier"],
        protected_names=row.get("protected_names") or [],
        file_number=row.get("file_number"),
        countries=row.get("countries") or [],
        third_country_flag=row.get("third_country_flag"),
        map_locations=row.get("map_locations"),
        gi_type=row.get("gi_type"),
        product_type=row.get("product_type"),
        product_categories=row.get("product_categories"),
        cn_classification=row.get("cn_classification"),
        status=row.get("status"),
        eu_protection_date=row.get("eu_protection_date"),
        modification_date=row.get("modification_date"),
        amendments_in_progress=row.get("amendments_in_progress"),
        removed_flag=row.get("removed_flag"),
        legal_instrument=row.get("legal_instrument"),
        publications=row.get("publications"),
        single_document=row.get("single_document"),
        summary_sheets=row.get("summary_sheets"),
        transcriptions=row.get("transcriptions"),
        amendments=row.get("amendments"),
        producer_group_name=row.get("producer_group_name"),
        producer_group_email=row.get("producer_group_email"),
        producer_group_phone=row.get("producer_group_phone"),
        producer_group_url=row.get("producer_group_url"),
        producer_group_address=row.get("producer_group_address"),
        producer_group_country=row.get("producer_group_country"),
        producer_group_updated_on=row.get("producer_group_updated_on"),
        competent_control_authorities=row.get("competent_control_authorities"),
        recognised_producers_group=row.get("recognised_producers_group"),
        sustainability_reports=row.get("sustainability_reports"),
        source=row["source"],
        giview_source=row.get("giview_source"),
        giview_database=row.get("giview_database"),
        eambrosia_url=row.get("eambrosia_url"),
        eurlex_url=row.get("eurlex_url"),
        public_url=row.get("public_url"),
        has_body=has_body_at_threshold,
        body_html=row.get("body_html"),
        body_txt=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
        fetched_at=row.get("fetched_at"),
        # 5 mandatory datapoints
        document_date=row.get("eu_protection_date"),
        creation_date=row.get("fetched_at"),
    )
