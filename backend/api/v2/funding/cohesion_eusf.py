"""EU Solidarity Fund — /api/v2/funding/eusf.

/api/v2/funding/eusf        — list disaster cases (cheap; body null)
/api/v2/funding/eusf/{id}   — one case in full (body_txt + body_html)

Backed by ``eu_solidarity_fund`` (DG REGIO Cohesion Open Data Platform, Socrata
7a49-av34, EUSF cases 2002-2021). One row per disaster case. Amounts in EUR
million. Follows the standard v2 item contract (5 datapoints + composed body).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from .cohesion_finances import _DataPoints

router = APIRouter()


class EUSFCase(_DataPoints):
    id: int = Field(..., description="Stable Brubru row id (use it on the detail endpoint).")
    year_of_occurrence: Optional[int] = None
    cci_number: Optional[str] = None
    applicant_country: Optional[str] = None
    name_of_disaster: Optional[str] = None
    disaster_type: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    first_damage_date: Optional[date] = None
    total_direct_damage_meur: Optional[float] = None
    eligible_emergency_cost_meur: Optional[float] = None
    damage_pct: Optional[float] = None
    eusf_grant_paid_meur: Optional[float] = None


_STRUCT = (
    "id, year_of_occurrence, cci_number, applicant_country, name_of_disaster, disaster_type, "
    "status, category, first_damage_date, total_direct_damage_meur, eligible_emergency_cost_meur, "
    "damage_pct, eusf_grant_paid_meur, public_url, document_date, created_at AS creation_date"
)
_LIST_COLS = _STRUCT
_DETAIL_COLS = _STRUCT + ", body_txt, body_html"


def _row_to_item(r, *, with_body: bool) -> EUSFCase:
    d = dict(r)
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
Lists the **EU Solidarity Fund** disaster cases (2002-2021): floods, forest fires, earthquakes, storms, health emergencies. One row per case, with the applicant country, disaster type, accepted total direct damage and the EUSF grant paid (amounts in EUR million), plus the 5 datapoints (`body_txt`/`body_html` null on the list — fetch the detail endpoint for the full body).

**When to use it**
To see which disasters the EUSF responded to, in which countries, and how much was paid. The EUSF assists Member States and accession countries hit by major natural disasters (and, since 2020, major health emergencies).

**Input**
- `country` — applicant country ISO code (e.g. `DE`, `IT`).
- `disaster_type` — substring (e.g. `Floods`, `Earthquake`, `Health`).
- `status` — substring (e.g. `Accepted`).
- `year` — year of occurrence.
- `q` — substring on the disaster name or body.
- `limit` (default 50, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v2/funding/eusf?country=IT
GET /api/v2/funding/eusf?disaster_type=Floods
GET /api/v2/funding/eusf?year=2021
```

**You get back**
A `PaginatedResponse[EUSFCase]` envelope sorted by EUSF grant paid (largest first). Each item carries `id`, `public_url`, `document_date`, `creation_date`, the case fields (`name_of_disaster`, `disaster_type`, `applicant_country`, `total_direct_damage_meur`, `eusf_grant_paid_meur`, ...) and `body_txt`/`body_html` = null. Use the detail endpoint for the full body.

**Data freshness**
Synced weekly (Sunday 05:00 UTC) from the DG REGIO Cohesion Open Data Platform (`cohesiondata.ec.europa.eu`, dataset 7a49-av34).""",
)
async def list_eusf(
    request: Request,
    country: Optional[str] = Query(None, description="Applicant country ISO code"),
    disaster_type: Optional[str] = Query(None, description="Disaster type substring"),
    status: Optional[str] = Query(None, description="Status substring"),
    year: Optional[int] = Query(None, description="Year of occurrence"),
    q: Optional[str] = Query(None, description="Substring on the disaster name or body"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    include_body: bool = Query(
        False,
        description=(
            "Return `body_txt` / `body_html` on every item in the list. Off by "
            "default because bodies dominate the payload, but without it the "
            "only route to the text is one detail call PER ITEM, which is not "
            "a usable way to ingest a feed."
        ),
    ),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EUSFCase]:
    where: list[str] = []
    params: dict = {}
    if country:
        where.append("applicant_country ILIKE :cc"); params["cc"] = country
    if disaster_type:
        where.append("disaster_type ILIKE :dt"); params["dt"] = f"%{disaster_type}%"
    if status:
        where.append("status ILIKE :st"); params["st"] = f"%{status}%"
    if year:
        where.append("year_of_occurrence = :yr"); params["yr"] = year
    if q:
        where.append("(name_of_disaster ILIKE :q OR body_txt ILIKE :q)"); params["q"] = f"%{q}%"
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(text(f"SELECT COUNT(*) FROM eu_solidarity_fund{clause}"), params).scalar() or 0
    params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
    rows = db.execute(
        text(f"SELECT {_DETAIL_COLS if include_body else _LIST_COLS} FROM eu_solidarity_fund{clause} "
             f"ORDER BY eusf_grant_paid_meur DESC NULLS LAST, year_of_occurrence DESC LIMIT :limit OFFSET :offset"),
        params2,
    ).mappings().all()
    items = [_row_to_item(r, with_body=include_body) for r in rows]
    return build_envelope(
        items, total=total, page=page, limit=limit,
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
