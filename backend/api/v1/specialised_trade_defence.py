"""
/api/v1/specialised/trade-defence — EU anti-dumping, countervailing,
safeguard regulations.

Backed by the eu_trade_defence_measures table (populated by
backfill_eu_trade_defence.py from Cellar). Each row is a sector-3 type-R
regulation whose title matches the trade-defence keyword set, classified
by measure_type / duty_status / target_country / product.

Endpoints:
    GET /api/v1/specialised/trade-defence              — list with filters
    GET /api/v1/specialised/trade-defence/types        — measure-type / duty-status counts
    GET /api/v1/specialised/trade-defence/{celex}      — single measure detail with body
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

router = APIRouter(prefix="/specialised/trade-defence", tags=["v1-specialised-ec-databases"])


# ----------------------------- response shapes -----------------------------


class TradeDefenceListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    celex: str
    title: Optional[str] = None
    document_date: Optional[date] = None
    measure_type: Optional[str] = Field(
        None,
        description="Brubru-derived: anti_dumping / countervailing / safeguard / registration / other.",
    )
    duty_status: Optional[str] = Field(
        None,
        description=(
            "definitive / provisional / initiation / registration / review / "
            "expiry_review / interim_review / amendment / suspension / "
            "termination / other."
        ),
    )
    target_country: Optional[str] = None
    product: Optional[str] = None
    in_force: Optional[bool] = None
    eurlex_url: str
    has_body: bool = Field(False, description="False on list rows. Call the detail endpoint for the regulation text.")
    # 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Citizen URL — alias of eurlex_url (EUR-Lex page for this regulation).")
    body_txt: Optional[str] = Field(None, description="Plain-text composition: title + measure type + duty status + target country + product + dates. Full body on the detail endpoint.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields.")
    creation_date: Optional[datetime] = Field(None, description="Time this row was last refreshed.")


class TradeDefenceDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    celex: str
    title: Optional[str] = None
    document_date: Optional[date] = None
    work_uri: Optional[str] = None

    measure_type: Optional[str] = None
    duty_status: Optional[str] = None
    target_country: Optional[str] = None
    product: Optional[str] = None

    resource_type_uri: Optional[str] = None
    resource_type_label: Optional[str] = None
    in_force: Optional[bool] = None
    date_in_force: Optional[date] = None
    date_end_validity: Optional[date] = None
    available_languages: list[str] = Field(default_factory=list)
    eurovoc_concepts: list[str] = Field(default_factory=list)
    eurlex_url: str

    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    body_source: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias for body_text/body_html.")
    fetched_at: Optional[str] = None
    # 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Citizen URL — alias of eurlex_url.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru last fetched this regulation (alias of fetched_at).")


class TypeCount(BaseModel):
    measure_type: str
    duty_status: Optional[str]
    in_force: int
    historical: int
    total: int


# ----------------------------- list -----------------------------


@router.get(
    "",
    response_model=PaginatedResponse[TradeDefenceListItem],
    summary="EU anti-dumping, countervailing and safeguard measures",
    description="""**What it does**
Returns every Commission Implementing Regulation in Cellar that imposes, amends, suspends, terminates or reviews an EU trade-defence measure: anti-dumping duties, countervailing duties, safeguard measures, registration of imports. One row per CELEX.

**When to use it**
- Trade-policy researchers tracking which products from which countries currently face EU duties.
- Compliance teams checking whether a recent regulation imposes a duty on their imports.
- Journalists monitoring trade-defence decisions against China, Russia, Türkiye, Indonesia and others.

**Input**
- `measure_type` (string, optional) — `anti_dumping`, `countervailing`, `safeguard`, `registration`, `other`.
- `duty_status` (string, optional) — `definitive`, `provisional`, `initiation`, `review`, `expiry_review`, `interim_review`, `amendment`, `termination`, `suspension`.
- `target_country` (string, optional) — case-insensitive substring on the country/region under measure (extracted from the regulation title).
- `product` (string, optional) — case-insensitive substring on the product description.
- `in_force` (bool, optional) — true to return only regulations currently in force.
- `published_from` / `published_to` (dates, optional) — bounds on document_date.
- `q` (string, optional) — full-text search on title.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for contract parity; the list endpoint never embeds the body.

**Try it**
```
GET /api/v1/specialised/trade-defence?measure_type=anti_dumping&target_country=China&in_force=true
```

**You get back**
A paginated envelope of `TradeDefenceListItem` rows: CELEX, title, document_date, measure_type, duty_status, target_country, product, in_force flag, EUR-Lex URL.""",
)
async def list_trade_defence(
    request: Request,
    measure_type: Optional[str] = Query(None),
    duty_status: Optional[str] = Query(None),
    target_country: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    in_force: Optional[bool] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # contract parity
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TradeDefenceListItem]:
    where: list[str] = []
    params: dict = {}
    if measure_type:
        where.append("measure_type = :measure_type"); params["measure_type"] = measure_type
    if duty_status:
        where.append("duty_status = :duty_status"); params["duty_status"] = duty_status
    if target_country:
        where.append("target_country ILIKE :target_country"); params["target_country"] = f"%{target_country}%"
    if product:
        where.append("product ILIKE :product"); params["product"] = f"%{product}%"
    if in_force is not None:
        where.append("in_force = :in_force"); params["in_force"] = in_force
    if published_from:
        where.append("document_date >= :published_from"); params["published_from"] = published_from
    if published_to:
        where.append("document_date <= :published_to"); params["published_to"] = published_to
    if q:
        where.append("to_tsvector('english', COALESCE(title,'')) @@ plainto_tsquery('english', :q)")
        params["q"] = q
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(
        text(f"SELECT COUNT(*) FROM eu_trade_defence_measures {where_sql}"), params
    ).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(
        text(f"""
            SELECT celex, title, document_date,
                   measure_type, duty_status, target_country, product,
                   in_force, eurlex_url
              FROM eu_trade_defence_measures
              {where_sql}
             ORDER BY document_date DESC NULLS LAST, celex DESC
             LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    ).mappings().all()

    def _td_list_item(r):
        import html as _html
        title = r.get("title") or r["celex"]
        lines = [title]
        parts_html = [f"<h2>{_html.escape(title)}</h2>"]
        for k, v in [
            ("CELEX", r["celex"]),
            ("Measure type", r.get("measure_type")),
            ("Duty status", r.get("duty_status")),
            ("Target country", r.get("target_country")),
            ("Product", r.get("product")),
            ("Document date", r.get("document_date")),
            ("In force", "Yes" if r.get("in_force") else ("No" if r.get("in_force") is False else None)),
        ]:
            if not v: continue
            lines.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        return TradeDefenceListItem(
            celex=r["celex"],
            title=r.get("title"),
            document_date=r.get("document_date"),
            measure_type=r.get("measure_type"),
            duty_status=r.get("duty_status"),
            target_country=r.get("target_country"),
            product=r.get("product"),
            in_force=r.get("in_force"),
            eurlex_url=r["eurlex_url"],
            has_body=False,
            # 5 mandatory datapoints
            public_url=r["eurlex_url"],
            body_txt="\n".join(lines),
            body_html="<article>" + "".join(parts_html) + "</article>",
            creation_date=r.get("fetched_at") or r.get("updated_at"),
        )

    items = [_td_list_item(r) for r in rows]

    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        op_core_title="EU trade-defence measures",
        op_core_type="Trade-defence regulation",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/specialised/trade-defence/{celex}",
            "/api/v1/specialised/trade-defence/types",
        ],
    )


# ----------------------------- types meta -----------------------------


@router.get(
    "/types",
    response_model=list[TypeCount],
    summary="Measure-type and duty-status breakdown",
    description="""**What it does**
Returns each (measure_type, duty_status) combination with counts of in-force vs historical measures. Useful for picker UIs and dashboards.

**When to use it**
- Building a filter dropdown.
- Quick sanity check on the dataset.

**Input**
None.

**Try it**
```
GET /api/v1/specialised/trade-defence/types
```

**You get back**
A flat list of `TypeCount` objects, sorted by total descending.""",
)
async def list_types(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[TypeCount]:
    rows = db.execute(text(
        """
        SELECT COALESCE(measure_type,'(unknown)') AS measure_type,
               duty_status,
               COUNT(*) FILTER (WHERE in_force) AS in_force,
               COUNT(*) FILTER (WHERE in_force IS NOT TRUE) AS historical,
               COUNT(*) AS total
          FROM eu_trade_defence_measures
         GROUP BY 1, 2
         ORDER BY total DESC
        """
    )).mappings().all()
    return [
        TypeCount(
            measure_type=r["measure_type"],
            duty_status=r["duty_status"],
            in_force=int(r["in_force"] or 0),
            historical=int(r["historical"] or 0),
            total=int(r["total"] or 0),
        )
        for r in rows
    ]


# ----------------------------- detail -----------------------------


@router.get(
    "/{celex:path}",
    response_model=TradeDefenceDetail,
    summary="Single trade-defence regulation (full metadata + body)",
    description="""**What it does**
Returns the full record for one trade-defence regulation: classification, in-force status, validity dates, EuroVoc concepts, plus the regulation text itself in `body_html` / `body_text`.

**When to use it**
- You followed a CELEX from the list endpoint and need the regulation text.
- You need the in-force status to assess current applicability.
- You need EuroVoc concepts for cross-referencing.

**Input**
- `celex` (path) — sector-3 type-R CELEX, e.g. `32024R3193`.
- `body_threshold` (int, default 500) — minimum char length of `body_text` to set `has_body=True`.

**Try it**
```
GET /api/v1/specialised/trade-defence/32024R3193
```

**You get back**
A `TradeDefenceDetail` object with all metadata plus body fields.""",
)
async def get_trade_defence(
    request: Request,
    celex: str = Path(..., description="CELEX number, e.g. 32024R3193."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TradeDefenceDetail:
    row = db.execute(text(
        """
        SELECT *
          FROM eu_trade_defence_measures
         WHERE celex = :celex
         LIMIT 1
        """
    ), {"celex": celex}).mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Measure '{celex}' not found.", "reason_code": "not_found"},
        )

    body_text = row.get("body_text")
    has_body = bool(body_text and len(body_text) >= body_threshold)

    return TradeDefenceDetail(
        celex=row["celex"],
        title=row.get("title"),
        document_date=row.get("document_date"),
        work_uri=row.get("work_uri"),
        measure_type=row.get("measure_type"),
        duty_status=row.get("duty_status"),
        target_country=row.get("target_country"),
        product=row.get("product"),
        resource_type_uri=row.get("resource_type_uri"),
        resource_type_label=row.get("resource_type_label"),
        in_force=row.get("in_force"),
        date_in_force=row.get("date_in_force"),
        date_end_validity=row.get("date_end_validity"),
        available_languages=row.get("available_languages") or [],
        eurovoc_concepts=row.get("eurovoc_concepts") or [],
        eurlex_url=row["eurlex_url"],
        has_body=has_body,
        body_html=row.get("body_html"),
        body_txt=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
        fetched_at=str(row.get("fetched_at")) if row.get("fetched_at") else None,
        # 5 mandatory datapoints
        public_url=row["eurlex_url"],
        creation_date=row.get("fetched_at"),
    )
