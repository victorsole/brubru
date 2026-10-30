"""EU Solidarity Fund — /api/v2/funding/eusf.

/api/v2/funding/eusf        — list disaster cases (cheap; body null)
/api/v2/funding/eusf/{id}   — one case in full (body_txt + body_html)

Backed by ``eu_solidarity_fund`` (DG REGIO Cohesion Open Data Platform, Socrata
7a49-av34, EUSF cases 2002-2021). One row per disaster case. Amounts in EUR
million. Follows the standard v2 item contract (5 datapoints + composed body).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._date_bounds import UpperBoundDatetime
from api.v1._envelope import PaginatedResponse, build_envelope
from .cohesion_finances import _DataPoints
from ._standard import ORDERS_DOC, amount_range, published_sql, published_window, standard_order
from services.funding.shared_fields import FUND_NAMES, budget_status, budget_status_filter, amount_range_sql
from api.v1._change_window import sql_window, validate_window
from services.funding.countries import both_styles

router = APIRouter()


class EUSFCase(_DataPoints):
    id: int = Field(..., description="Stable Brubru row id (use it on the detail endpoint).")
    item_type: str = Field("solidarity_case", description="Always solidarity_case (as on /funding/budgets and /funding/all).")
    title: Optional[str] = Field(None, description="The disaster's name (`name_of_disaster`).")
    summary: Optional[str] = Field(None, description="Country · year · disaster type · EUSF paid, EUR million.")
    body_code: str = Field("eusf", description="Always eusf (body= on /funding/budgets and /funding/all).")
    body_name: Optional[str] = Field(None, description="The fund's name.")
    amount_eur: Optional[float] = Field(None, description="The grant paid in euros (`eusf_grant_paid_meur` x 1,000,000, to the euro).")
    year_of_occurrence: Optional[int] = None
    cci_number: Optional[str] = None
    applicant_country: Optional[str] = None
    name_of_disaster: Optional[str] = None
    disaster_type: Optional[str] = None
    status: Optional[str] = Field(None, description="accepted | rejected | withdrawn | under_assessment: the application's outcome, the standard words for the source's own.")
    source_status: Optional[str] = Field(None, description="The status word the source gives (Accepted, Rejected, Withdrawn, Under assessment), which `status` is set from.")
    category: Optional[str] = None
    # No damage date (23 Oct 2026, Victor): the source's own is unreliable, 13 of 197 cases dated
    # after their own application (day and month swapped: Storm Gudrun, Lorca, Lesbos), and it is
    # not when anything was published. It stays in the stored source record only.
    document_date: Optional[datetime] = Field(None, description=(
        "When the Commission last published the dataset these figures come from (the Cohesion "
        "Open Data platform's own last-refresh time). The source gives no per-case publication date."))
    total_direct_damage_meur: Optional[float] = None
    eligible_emergency_cost_meur: Optional[float] = None
    damage_pct: Optional[float] = None
    eusf_grant_paid_meur: Optional[float] = None


_STRUCT = (
    "id, year_of_occurrence, cci_number, applicant_country, name_of_disaster, disaster_type, "
    "status, category, total_direct_damage_meur, eligible_emergency_cost_meur, "
    "damage_pct, eusf_grant_paid_meur, public_url, document_date, created_at AS creation_date, "
    "updated_at AS updated_date"
)
# The shared fields of a case, composed once: this list, /funding/budgets and /funding/all serve the same words.
SHARED_SQL = ("'solidarity_case' AS item_type, name_of_disaster AS title, "
              "concat_ws(' · ', nullif(applicant_country, ''), year_of_occurrence::text, nullif(disaster_type, ''), "
              "'EUSF paid EUR ' || round(eusf_grant_paid_meur)::text || 'm') AS summary, "
              "'eusf' AS body_code, round(eusf_grant_paid_meur * 1000000) AS amount_eur")
_LIST_COLS = f"{_STRUCT}, {SHARED_SQL}"
_DETAIL_COLS = f"{_STRUCT}, {SHARED_SQL}, body_txt, body_html"


def _row_to_item(r, *, with_body: bool) -> EUSFCase:
    d = dict(r)
    d["body_name"] = FUND_NAMES["eusf"]
    d["source_status"] = d.get("status")
    d["status"] = budget_status(d.get("status"))
    if not with_body:
        d["body_txt"] = None
        d["body_html"] = None
    return EUSFCase(**d)


@router.get(
    "/eusf",
    response_model=PaginatedResponse[EUSFCase],
    tags=["v2-funding"],
    summary="EU Solidarity Fund (EUSF) — disaster cases 2002-2021",
    description="""**What it does**
Lists the **EU Solidarity Fund** disaster cases (2002-2021): floods, forest fires, earthquakes, storms, health emergencies. One row per case, with the applicant country, disaster type, accepted total direct damage and the EUSF grant paid (amounts in EUR million), plus the 5 datapoints (`body_txt`/`body_html` on every item, unless `include_body=false`).

**When to use it**
To see which disasters the EUSF responded to, in which countries, and how much was paid. The EUSF assists Member States and accession countries hit by major natural disasters (and, since 2020, major health emergencies).

**Input**
- `country` — applicant country ISO code (e.g. `DE`, `IT`).
- `disaster_type` — substring (e.g. `Floods`, `Earthquake`, `Health`).
- `status` — `accepted`, `rejected`, `withdrawn` or `under_assessment`; any other text matches the source's own word (`source_status`) as a substring.
- `year` — year of occurrence.
- `q` — substring on the disaster name or body.
- `min_amount_eur`, `max_amount_eur` — the grant paid in euros (`amount_eur`) at least / at most; `order=amount` (the default) lists the largest first.
- `limit` (default 50, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v2/funding/eusf?country=IT
GET /api/v2/funding/eusf?disaster_type=Floods
GET /api/v2/funding/eusf?year=2021
```

**You get back**
A `PaginatedResponse[EUSFCase]` envelope sorted by EUSF grant paid (largest first). Each item carries `id`, `public_url`, `document_date`, `creation_date`, the case fields (`name_of_disaster`, `disaster_type`, `applicant_country`, `total_direct_damage_meur`, `eusf_grant_paid_meur`, ...) and `body_txt`/`body_html` (unless `include_body=false`). `status` is the standard word (`accepted`, `rejected`, `withdrawn`, `under_assessment`), the source's own beside it as `source_status` (until 29 Oct 2026 `status` held the source's word).

**Data freshness**
Synced weekly (Sunday 05:00 UTC) from the DG REGIO Cohesion Open Data Platform (`cohesiondata.ec.europa.eu`, dataset 7a49-av34).""",
)
async def list_eusf(
    request: Request,
    country: Optional[str] = Query(None, description="Applicant country ISO code"),
    disaster_type: Optional[str] = Query(None, description="Disaster type substring"),
    status: Optional[str] = Query(None, description="accepted | rejected | withdrawn | under_assessment (the standard status); any other text matches the source's own word (`source_status`) as a substring."),
    year: Optional[int] = Query(None, description="Year of occurrence"),
    q: Optional[str] = Query(None, description="Substring on the disaster name or body"),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync: rows whose content changed at or after this time (updated_date)."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Upper bound of the incremental-sync window; a bare date covers the whole day."),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    published: tuple = Depends(published_window),
    amounts: tuple = Depends(amount_range),
    order: Optional[str] = Query(None, description=f"amount: the largest grant paid first (default) | {ORDERS_DOC}"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    include_body: bool = Query(
        True,
        description=(
            "Return `body_txt` / `body_html` on every item in the list (default true, "
            "the funding standard)."
        ),
    ),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EUSFCase]:
    where: list[str] = []
    params: dict = {}
    window = validate_window(created_from, created_to, updated_from, updated_to)
    if country:
        where.append("upper(applicant_country) = ANY(:cc)"); params["cc"] = both_styles(country)
    if disaster_type:
        where.append("disaster_type ILIKE :dt"); params["dt"] = f"%{disaster_type}%"
    if status:
        budget_status_filter(where, params, status)
    if year:
        where.append("year_of_occurrence = :yr"); params["yr"] = year
    if q:
        where.append("(name_of_disaster ILIKE :q OR body_txt ILIKE :q)"); params["q"] = f"%{q}%"
    sql_window(where, params, window, "created_at", "updated_at")
    published_sql(where, params, published, "document_date")
    amount_range_sql(where, params, amounts[0], amounts[1], "round(eusf_grant_paid_meur * 1000000)")   # amount_eur (step 6b)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    order_sql = standard_order(order, "eusf_grant_paid_meur DESC NULLS LAST, year_of_occurrence DESC, id DESC", published="document_date", created="created_at",
                               updated="updated_at", amount="eusf_grant_paid_meur DESC NULLS LAST, year_of_occurrence DESC, id DESC")

    total = db.execute(text(f"SELECT COUNT(*) FROM eu_solidarity_fund{clause}"), params).scalar() or 0
    params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
    rows = db.execute(
        text(f"SELECT {_DETAIL_COLS if include_body else _LIST_COLS} FROM eu_solidarity_fund{clause} "
             f"ORDER BY {order_sql} LIMIT :limit OFFSET :offset"),
        params2,
    ).mappings().all()
    items = [_row_to_item(r, with_body=include_body) for r in rows]
    return build_envelope(
        items, total=total, page=page, limit=limit,
        updated_from=window["updated_from"], updated_to=window["updated_to"],
        op_core_title="EU Solidarity Fund disaster cases 2002-2021",
        op_core_type="dataset", op_core_identifier="cohesiondata:7a49-av34",
    )


@router.get(
    "/eusf/{row_id}",
    response_model=EUSFCase,
    tags=["v2-funding"],
    summary="Look up one EU Solidarity Fund case in full",
    description="""**What it does**
Returns one EU Solidarity Fund disaster case by its Brubru id, including the full `body_txt` + `body_html`.

**Input**
- `row_id` (path) — the `id` from the list endpoint.

**Try it**
```
GET /api/v2/funding/eusf/12
```

**You get back**
A single `EUSFCase` with `body_txt` + `body_html` populated, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same weekly sync as the list endpoint.""",
)
async def get_eusf(
    row_id: int = Path(..., description="Brubru row id from the list endpoint"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> EUSFCase:
    r = db.execute(
        text(f"SELECT {_DETAIL_COLS} FROM eu_solidarity_fund WHERE id = :id"), {"id": row_id},
    ).mappings().fetchone()
    if not r:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No EUSF case with id {row_id}"})
    return _row_to_item(r, with_body=True)


get_eusf.brubru_item_key = ("eusf", "solidarity_case")
