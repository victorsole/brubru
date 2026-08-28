"""Common Agricultural Policy funds — EAGF + EAFRD payments by Member State.

/api/v2/funding/eagf  + /eagf/{id}    — European Agricultural Guarantee Fund
/api/v2/funding/eafrd + /eafrd/{id}   — European Agricultural Fund for Rural Development

Backed by ``eu_cap_payments`` (DG REGIO Cohesion Open Data Platform, Socrata
qgpc-e9qr + 7wr2-9vpr). One row per fund x Member State. Follows the standard v2
item contract (5 datapoints + composed body + list/detail split).
"""
from __future__ import annotations

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


class CAPPaymentItem(_DataPoints):
    id: int = Field(..., description="Stable Brubru row id (use it on the detail endpoint).")
    fund: str
    ms: Optional[str] = None
    planned_eu_amount: Optional[float] = None
    net_pre_financing: Optional[float] = None
    net_interim_payments: Optional[float] = None
    total_eur: Optional[float] = None
    payment_rate: Optional[float] = None
    fy_2023: Optional[float] = None
    fy_2024: Optional[float] = None
    fy_2025: Optional[float] = None
    fy_2026: Optional[float] = None
    fy_2027: Optional[float] = None


_STRUCT = ("id, fund, ms, planned_eu_amount, net_pre_financing, net_interim_payments, "
           "total_eur, payment_rate, fy_2023, fy_2024, fy_2025, fy_2026, fy_2027")
_LIST_COLS = f"{_STRUCT}, public_url, document_date, created_at AS creation_date"
_DETAIL_COLS = f"{_STRUCT}, public_url, body_txt, body_html, document_date, created_at AS creation_date"


def _row_to_item(r, *, with_body: bool) -> CAPPaymentItem:
    d = dict(r)
    if not with_body:
        d["body_txt"] = None
        d["body_html"] = None
    return CAPPaymentItem(**d)


def register_cap_fund(*, slug: str, fund_code: str, fund_name: str, blurb: str, tag: str = "v2-funding") -> None:
    """Add list `GET /<slug>` + detail `GET /<slug>/{id}` for one CAP fund."""

    @router.get(
        f"/{slug}",
        response_model=PaginatedResponse[CAPPaymentItem],
        tags=[tag],
        summary=f"{fund_name} ({fund_code}) — EU payments by Member State (2023-2027)",
        description=f"""**What it does**
Lists the **{fund_name} ({fund_code})** EU payments by Member State for 2023-2027. {blurb} One row per Member State, with the headline EU amount and the fund-specific breakdown, plus the 5 datapoints (`body_txt`/`body_html` null on the list — fetch the detail endpoint).

**When to use it**
To see how much {fund_code} money each Member State receives under the Common Agricultural Policy.

**Input**
- `ms` — Member State ISO code (e.g. `FR`, `ES`, `PL`).
- `q` — substring on the body.
- `limit` (default 50, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v2/funding/{slug}
GET /api/v2/funding/{slug}?ms=FR
```

**You get back**
A `PaginatedResponse[CAPPaymentItem]` envelope sorted by total EU amount (largest first). Each item carries `id`, `fund`, `ms`, `total_eur`, the fund-specific fields ({'annual `fy_2023`..`fy_2026`' if fund_code == 'EAGF' else '`planned_eu_amount`, `net_interim_payments`, `payment_rate`'}), `public_url`, `document_date`, `creation_date`, and `body_txt`/`body_html` = null.

**Data freshness**
Synced weekly (Sunday 05:00 UTC) from the DG REGIO Cohesion Open Data Platform (`cohesiondata.ec.europa.eu`).""",
    )
    async def list_cap(  # noqa: ANN202
        request: Request,
        ms: Optional[str] = Query(None, description="Member State ISO code"),
        q: Optional[str] = Query(None, description="Substring on the body"),
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
    ) -> PaginatedResponse[CAPPaymentItem]:
        where = ["fund = :fund"]
        params: dict = {"fund": fund_code}
        if ms:
            where.append("ms ILIKE :ms"); params["ms"] = ms
        if q:
            where.append("body_txt ILIKE :q"); params["q"] = f"%{q}%"
        where_sql = " AND ".join(where)
        total = db.execute(text(f"SELECT COUNT(*) FROM eu_cap_payments WHERE {where_sql}"), params).scalar() or 0
        params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
        rows = db.execute(
            text(f"SELECT {_DETAIL_COLS if include_body else _LIST_COLS} FROM eu_cap_payments WHERE {where_sql} "
                 f"ORDER BY total_eur DESC NULLS LAST, ms LIMIT :limit OFFSET :offset"), params2,
        ).mappings().all()
        items = [_row_to_item(r, with_body=include_body) for r in rows]
        return build_envelope(
            items, total=total, page=page, limit=limit,
            op_core_title=f"{fund_name} ({fund_code}) payments by Member State 2023-2027",
            op_core_type="dataset", op_core_identifier=f"cohesiondata:cap:{fund_code}",
        )

    @router.get(
        f"/{slug}/{{row_id}}",
        response_model=CAPPaymentItem,
        tags=[tag],
        summary=f"Look up one {fund_code} Member State payment row in full",
        description=f"""**What it does**
Returns one {fund_name} ({fund_code}) Member State payment row by its Brubru id, including the full `body_txt` + `body_html`.

**Input**
- `row_id` (path) — the `id` from the list endpoint.

**Try it**
```
GET /api/v2/funding/{slug}/3
```

**You get back**
A single `CAPPaymentItem` with the body populated, or HTTP 404 with `reason_code: not_found`.""",
    )
    async def get_cap_row(  # noqa: ANN202
        row_id: int = Path(..., description="Brubru row id from the list endpoint"),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> CAPPaymentItem:
        r = db.execute(
            text(f"SELECT {_DETAIL_COLS} FROM eu_cap_payments WHERE id = :id AND fund = :fund"),
            {"id": row_id, "fund": fund_code},
        ).mappings().fetchone()
        if not r:
            raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No {fund_code} row with id {row_id}"})
        return _row_to_item(r, with_body=True)


# ---- Registered CAP funds (one line per fund; built one at a time) ----
register_cap_fund(
    slug="eagf", fund_code="EAGF",
    fund_name="European Agricultural Guarantee Fund",
    blurb="The EAGF is the 'first pillar' of the CAP, financing direct income support to "
          "farmers and agricultural market measures.",
)
register_cap_fund(
    slug="eafrd", fund_code="EAFRD",
    fund_name="European Agricultural Fund for Rural Development",
    blurb="The EAFRD is the 'second pillar' of the CAP, co-financing rural development "
          "programmes (the figures show planned EU amount vs net payments to date).",
)
