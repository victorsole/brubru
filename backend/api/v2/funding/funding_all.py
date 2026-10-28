"""GET /api/v2/funding/all — every decentralised EU funding item, all bodies.

The cross-cutting aggregate: tenders, grants and calls for expression of interest
published by EU agencies on their own sites (the data that never reaches TED below
threshold or the central F&T Portal), in one feed, filterable by type, body,
status and deadline. As more agencies are added to the Funding & Tenders folder,
they appear here automatically. The central TED (`/funding/tenders`) and F&T
Portal calls remain separate dedicated endpoints.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from ..economy_endpoints import (EconomyItem, FundingEconomyItem, _row_to_item, _LIST_COLS, _DETAIL_COLS, _ORDER_SQL,
                                  _ORDERS, build_envelope)
from services.funding.shared_fields import with_body_names
from .cohesion_cap import SHARED_SQL as PAYMENT_SQL
from .cohesion_eusf import SHARED_SQL as SOLIDARITY_SQL
from .cohesion_finances import SHARED_SQL as ALLOCATION_SQL
from api.v1._change_window import (SYNC_ORDERS, UpperBoundDatetime, sql_order, sql_window,
                                   validate_window)

router = APIRouter()


class FundingAllItem(FundingEconomyItem):
    self: Optional[str] = Field(None, description="This item on its own endpoint (e.g. /api/v2/funding/euaa-calls/123).")


_ITEM_ROUTES: Optional[dict] = None


def _item_routes(app) -> dict:
    """(body_code, item_type) -> the item route that serves it, read from the live route table
    (each detail route is tagged brubru_item_key), so a link cannot point at a route that is not
    served. /funding/all has no item route of its own: until 20 Oct 2026 its items had no `self`."""
    global _ITEM_ROUTES
    if _ITEM_ROUTES is None:
        _ITEM_ROUTES = {}
        for r in app.routes:
            key = getattr(getattr(r, "endpoint", None), "brubru_item_key", None)
            if key and "GET" in (getattr(r, "methods", None) or ()):
                _ITEM_ROUTES.setdefault(key, r.path)
    return _ITEM_ROUTES


def _with_self(item: EconomyItem, base: str, routes: dict) -> FundingAllItem:
    path = routes.get((item.body_code, item.item_type))
    link = None
    if path and item.id is not None:
        link = base + path.replace("{item_id}", str(item.id)).replace("{row_id}", str(item.id))
    return FundingAllItem(**item.model_dump(), self=link)


def _funding_item(r, include_body: bool) -> FundingEconomyItem:
    """A row of the union with the shared fields the factory's EconomyItem lacks (status, amount_eur)."""
    return FundingEconomyItem(**_row_to_item(r, with_body=include_body).model_dump(),
                              status=r.status, amount_eur=r.amount_eur)


_FUNDING_TYPES = ("tender", "grant", "eoi_call", "startup_funding")
# Plus the cohesion / structural-fund allocations (eu_cohesion_finances), unioned in.
_ALL_TYPES = _FUNDING_TYPES + ("cohesion_allocation", "solidarity_case", "cap_payment")

# UNION of (a) decentralised agency funding items, (b) the per-fund cohesion
# allocations, (c) EU Solidarity Fund disaster cases, and (d) the CAP fund
# payments (EAGF/EAFRD), all mapped to the same EconomyItem shape. The agency
# side is pre-filtered to funding item_types; the rest are mapped on the fly.
# updated_date: every side carries its table's updated_at. The cohesion, Solidarity Fund and CAP
# tables served NULL until 20 Oct 2026, when migrations 306 and 307 made their updated_at a change
# signal (a trigger that moves it only when a served column changes; rows kept across runs).
_UNION_CTE_TMPL = """
WITH all_funding AS (
    SELECT id, body_code, item_type, title, summary, public_url,
           {b}document_date, creation_date, source_kind, updated_at, status, NULL::numeric AS amount_eur
    FROM economy_items
    WHERE item_type = ANY(:ftypes)
    UNION ALL
    SELECT id, body_code, item_type, title, summary,
           public_url, {b}document_date, created_at AS creation_date, 'cohesion' AS source_kind,
           updated_at, status, amount_eur
    FROM (SELECT *, <<ALLOCATION>> FROM eu_cohesion_finances) f
    UNION ALL
    SELECT id, body_code, item_type, title, summary,
           public_url, {b}document_date, created_at AS creation_date, 'cohesion' AS source_kind,
           updated_at, status, amount_eur
    FROM (SELECT *, <<SOLIDARITY>> FROM eu_solidarity_fund) s
    UNION ALL
    SELECT id, body_code, item_type, title, summary,
           public_url, {b}document_date, created_at AS creation_date, 'cohesion' AS source_kind,
           updated_at, NULL AS status, amount_eur
    FROM (SELECT *, <<PAYMENT>> FROM eu_cap_payments) c
)
"""


# The cohesion, Solidarity Fund and CAP rows carry the shared fields their own lists compose (one
# composition each, 28 Oct 2026: the CAP title read "EAGF — EL" here and nothing on /eagf).
_UNION_CTE_TMPL = (_UNION_CTE_TMPL.replace("<<ALLOCATION>>", ALLOCATION_SQL)
                   .replace("<<SOLIDARITY>>", SOLIDARITY_SQL).replace("<<PAYMENT>>", PAYMENT_SQL))


def _union_cte(include_body: bool) -> str:
    """The body columns are projected only when the caller wants them."""
    return _UNION_CTE_TMPL.replace("{b}", "body_txt, body_html, " if include_body else "")


_DESC = """**What it does**
One feed of **every EU fund** Brubru covers — the decentralised agency funding items (calls for **tender**, **grants** and calls for **expression of interest**), the per-programme grant calls ingested for their own endpoints (Justice `body=just`, Innovation Fund `body=innovfund`), AND the per-fund cohesion / structural-fund allocations (ERDF, ESF+, Cohesion Fund, JTF, Interreg, EMFAF, AMIF, ISF), the EU Solidarity Fund and the CAP funds (EAGF, EAFRD) — across every body, in one call.

**When to use it**
"Show me everything across EU funding", whether an agency tender, a Justice/Innovation-Fund grant call, or a Member State's cohesion-fund allocation. Filter by `type` (tender/grant/eoi_call/startup_funding/cohesion_allocation/solidarity_case/cap_payment), `body` (agency code or fund code, e.g. `efca`, `erdf`, `just`, `innovfund`), `status`, `q` (free text), and `published_from`/`published_to` on the item's date.

**Input**
`type`, `body`, `status`, `q` (free text), `published_from`/`published_to` (the item's `document_date`; `since`, `until`, `from`, `to` are aliases), `created_from`/`created_to` and `updated_from`/`updated_to` (incremental sync; a bare date as `_to` covers the whole day), `order` (page a change window with `updated_asc`), `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/all?type=cohesion_allocation&body=erdf
GET /api/v2/funding/all?type=tender&order=recent
GET /api/v2/funding/all?q=transport
```

**You get back**
A paginated list; each item carries `body_code` (the agency or fund), `item_type`, title, a summary, `document_date` and the link. Cohesion allocations carry `item_type=cohesion_allocation` and `public_url` to the fund's Cohesion Open Data page.

**Data freshness**
Live from the database; agency items refresh as their pages are re-synced; cohesion allocations refresh weekly (Sunday 05:00 UTC)."""


@router.get("/all", response_model=PaginatedResponse[FundingAllItem], tags=["v2-funding"],
            summary="All EU funding — agency tenders/grants/calls + cohesion-fund allocations, every body",
            description=_DESC)
async def funding_all(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    type: Optional[str] = Query(None, description="tender | grant | eoi_call | startup_funding | cohesion_allocation | solidarity_case | cap_payment"),
    body: Optional[str] = Query(None, description="Agency code or fund code, e.g. efca, ema, erdf, esf, jtf."),
    status: Optional[str] = Query(None, description="Match on status in the summary (e.g. open, closed)."),
    q: Optional[str] = Query(None, description="Free-text search over title, summary and body."),
    published_from: Optional[date] = Query(None, description="The item's date (`document_date`) on or after (YYYY-MM-DD); `since` and `from` are aliases."),
    published_to: Optional[date] = Query(None, description="The item's date (`document_date`) on or before (YYYY-MM-DD); `until` and `to` are aliases."),
    since: Optional[date] = Query(None, description="The same as `published_from` (it was described as a deadline until 28 Oct 2026, but always read `document_date`)."),
    until: Optional[date] = Query(None, description="The same as `published_to`."),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Content last changed on or after (ISO date or datetime, UTC). The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Content last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | title | updated_asc | updated_desc | created_asc | created_desc. Page an incremental window with updated_asc."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(
        True,
        description=(
            "Return `body_txt` / `body_html` on every item in the list (default true, "
            "the funding standard)."
        ),
    ),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    params = {"ftypes": list(_FUNDING_TYPES), "limit": limit, "offset": (page - 1) * limit}
    where: list[str] = []
    if type:
        if type not in _ALL_TYPES:
            raise HTTPException(status_code=400, detail=f"type must be one of {list(_ALL_TYPES)}")
        where.append("item_type = :it"); params["it"] = type
    if body:
        where.append("body_code = :bc"); params["bc"] = body
    if status:
        where.append("summary ILIKE :st"); params["st"] = f"%{status}%"
    if q:
        where.append("(title ILIKE :q OR summary ILIKE :q)"); params["q"] = f"%{q}%"
    since, until = published_from or since or from_, published_to or until or to
    if since:
        where.append("document_date >= :since"); params["since"] = since
    if until:
        where.append("document_date < CAST(:until AS date) + 1"); params["until"] = until
    # Every side of the union projects its table's own creation_date and updated_at (filled on
    # all 982 + 203 + 56 cohesion, Solidarity Fund and CAP rows and on every economy_items row).
    sql_window(where, params, window, "creation_date", "updated_at")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.execute(
        text(f"{_union_cte(False)} SELECT count(*) FROM all_funding{clause}"), params
    ).scalar() or 0
    # `id` alone is not unique across the UNION (the four tables' id ranges
    # overlap), so item_type completes the key and OFFSET pages cannot overlap.
    rows = db.execute(
        text(f"{_union_cte(include_body)} SELECT {_DETAIL_COLS if include_body else _LIST_COLS}, status, amount_eur "
             f"FROM all_funding{clause} "
             f"ORDER BY {sql_order(order, 'creation_date', 'updated_at') or _ORDER_SQL[order]}, item_type "
             f"LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    base, routes = str(request.base_url).rstrip("/"), _item_routes(request.app)
    items = with_body_names(db, [_with_self(_funding_item(r, include_body), base, routes) for r in rows])
    return build_envelope(items, total, page, limit,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])
