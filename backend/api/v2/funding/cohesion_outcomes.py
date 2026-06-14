"""Cohesion / structural funds — per-fund achievement & outcome indicators.

/api/v2/funding/<fund>/outcomes         — list (cheap; body null)
/api/v2/funding/<fund>/outcomes/{id}    — one indicator row in full (body)

Backed by ``eu_cohesion_outcomes`` (DG REGIO Cohesion Open Data Platform, Socrata
dataset xi3a-zddk, "2021-2027 Achievement Details"). The "what the money
achieves" complement to ``cohesion_finances``. Follows the standard v2 item
contract (5 datapoints + list/detail split). Built one fund at a time.
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
from api.v1._envelope import PaginatedResponse, build_envelope
from .cohesion_finances import _DataPoints

router = APIRouter()


class CohesionOutcomeItem(_DataPoints):
    id: int = Field(..., description="Stable Brubru row id (use it on the detail endpoint).")
    fund: str
    ms: Optional[str] = None
    ms_name: Optional[str] = None
    cci: Optional[str] = None
    programme_short_title: Optional[str] = None
    policy_objective_name: Optional[str] = None
    specific_objective_name: Optional[str] = None
    category_of_region: Optional[str] = None
    indicator_type_output_result: Optional[str] = None
    ind_code: Optional[str] = None
    indicator_short_name: Optional[str] = None
    indicator_long_name: Optional[str] = None
    measurement_unit: Optional[str] = None
    baseline_value: Optional[float] = None
    milestone_value_2024: Optional[float] = None
    target_value_2029: Optional[float] = None
    decided_value: Optional[float] = None
    implemented_value: Optional[float] = None


_STRUCT = (
    "fund, ms, ms_name, cci, programme_short_title, policy_objective_name, "
    "specific_objective_name, category_of_region, indicator_type_output_result, "
    "ind_code, indicator_short_name, indicator_long_name, measurement_unit, "
    "baseline_value, milestone_value_2024, target_value_2029, decided_value, implemented_value"
)
_LIST_COLS = f"id, public_url, document_date, created_at AS creation_date, {_STRUCT}"
_DETAIL_COLS = f"id, public_url, body_txt, body_html, document_date, created_at AS creation_date, {_STRUCT}"


def _row_to_item(r, *, with_body: bool) -> CohesionOutcomeItem:
    d = dict(r)
    if not with_body:
        d["body_txt"] = None
        d["body_html"] = None
    return CohesionOutcomeItem(**d)


def register_fund_outcomes(*, slug: str, fund_code: str, fund_name: str, tag: str = "v2-funding") -> None:
    """Add list `GET /<slug>/outcomes` + detail `GET /<slug>/outcomes/{id}`."""

    @router.get(
        f"/{slug}/outcomes",
        response_model=PaginatedResponse[CohesionOutcomeItem],
        tags=[tag],
        summary=f"{fund_name} ({fund_code}) — 2021-2027 achievement indicators (outputs & results)",
        description=f"""**What it does**
Lists the 2021-2027 achievement indicators of the **{fund_name} ({fund_code})** — what the fund is delivering. One row per programme indicator, carrying the indicator name, measurement unit, baseline, 2024 milestone, 2029 target, and the decided + implemented values, plus the 5 datapoints (`body_txt`/`body_html` null here; fetch the detail endpoint for the body).

**When to use it**
To measure progress and targets rather than money: how many people supported, entities helped, capacity created, per programme and Member State. For the euro allocations see `/api/v2/funding/{slug}`.

**Input**
- `ms` — Member State ISO code.
- `type` — `result` (RESF), `output` (OESF), or `common` (COMMON). Substring also accepted.
- `q` — substring on the indicator name or body.
- `limit` (default 50, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v2/funding/{slug}/outcomes?type=result&ms=ES
GET /api/v2/funding/{slug}/outcomes?q=unemployed
```

**You get back**
A `PaginatedResponse[CohesionOutcomeItem]` envelope. Each item carries `id`, `public_url`, `document_date`, `creation_date`, the indicator fields (`indicator_long_name`, `measurement_unit`, `baseline_value`, `target_value_2029`, `implemented_value`, ...) and `body_txt`/`body_html` = null. Only the latest reporting cycle is served.

**Data freshness**
Synced weekly (Sunday 05:00 UTC) from `cohesiondata.ec.europa.eu`, dataset xi3a-zddk (latest TOD cycle only).""",
    )
    async def list_outcomes(  # noqa: ANN202
        request: Request,
        ms: Optional[str] = Query(None, description="Member State ISO code"),
        type: Optional[str] = Query(None, description="result (RESF) | output (OESF) | common (COMMON)"),
        q: Optional[str] = Query(None, description="Substring on the indicator name or body"),
        limit: int = Query(50, ge=1, le=200),
        page: int = Query(1, ge=1),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> PaginatedResponse[CohesionOutcomeItem]:
        type_map = {"result": "RESF", "output": "OESF", "common": "COMMON"}
        where = ["fund = :fund"]
        params: dict = {"fund": fund_code}
        if ms:
            where.append("ms ILIKE :ms"); params["ms"] = ms
        if type:
            where.append("indicator_type_output_result ILIKE :itype")
            params["itype"] = f"%{type_map.get(type.lower(), type)}%"
        if q:
            where.append("(indicator_long_name ILIKE :q OR body_txt ILIKE :q)"); params["q"] = f"%{q}%"
        where_sql = " AND ".join(where)

        total = db.execute(text(f"SELECT COUNT(*) FROM eu_cohesion_outcomes WHERE {where_sql}"), params).scalar() or 0
        params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
        rows = db.execute(
            text(f"SELECT {_LIST_COLS} FROM eu_cohesion_outcomes WHERE {where_sql} "
                 f"ORDER BY implemented_value DESC NULLS LAST, cci, ind_code LIMIT :limit OFFSET :offset"), params2,
        ).mappings().all()
        items = [_row_to_item(r, with_body=False) for r in rows]
        return build_envelope(
            items, total=total, page=page, limit=limit,
            op_core_title=f"{fund_name} ({fund_code}) 2021-2027 achievement indicators",
            op_core_type="dataset", op_core_identifier=f"cohesiondata:xi3a-zddk:{fund_code}",
        )

    @router.get(
        f"/{slug}/outcomes/{{row_id}}",
        response_model=CohesionOutcomeItem,
        tags=[tag],
        summary=f"Look up one {fund_code} achievement indicator in full",
        description=f"""**What it does**
Returns one {fund_name} ({fund_code}) achievement-indicator row by its Brubru id, including the full `body_txt` + `body_html`.

**When to use it**
After locating an indicator via the list endpoint, fetch the full record with the composed body.

**Input**
- `row_id` (path) — the `id` from the list endpoint.

**Try it**
```
GET /api/v2/funding/{slug}/outcomes/123
```

**You get back**
A single `CohesionOutcomeItem` with `body_txt` + `body_html` populated, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same weekly sync as the list endpoint.""",
    )
    async def get_outcome_row(  # noqa: ANN202
        row_id: int = Path(..., description="Brubru row id from the list endpoint"),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> CohesionOutcomeItem:
        r = db.execute(
            text(f"SELECT {_DETAIL_COLS} FROM eu_cohesion_outcomes WHERE id = :id AND fund = :fund"),
            {"id": row_id, "fund": fund_code},
        ).mappings().fetchone()
        if not r:
            raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No {fund_code} indicator with id {row_id}"})
        return _row_to_item(r, with_body=True)


# ---- Registered fund outcomes (one line per fund; built one at a time) ----
# NB: this dataset's fund codes are 'ESF+' (with plus) and 'Interreg Funds'.
register_fund_outcomes(slug="erdf", fund_code="ERDF", fund_name="European Regional Development Fund")
register_fund_outcomes(slug="esf-plus", fund_code="ESF+", fund_name="European Social Fund Plus")
register_fund_outcomes(slug="cohesion-fund", fund_code="CF", fund_name="Cohesion Fund")
register_fund_outcomes(slug="jtf", fund_code="JTF", fund_name="Just Transition Fund")
register_fund_outcomes(slug="interreg", fund_code="Interreg Funds", fund_name="Interreg (European Territorial Cooperation)")
register_fund_outcomes(slug="emfaf", fund_code="EMFAF", fund_name="European Maritime, Fisheries and Aquaculture Fund")
register_fund_outcomes(slug="amif", fund_code="AMIF", fund_name="Asylum, Migration and Integration Fund")
register_fund_outcomes(slug="isf", fund_code="ISF", fund_name="Internal Security Fund")
