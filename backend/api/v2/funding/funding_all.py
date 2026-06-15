"""GET /api/v2/funding/all — every decentralised EU funding item, all bodies.

The cross-cutting aggregate: tenders, grants and calls for expression of interest
published by EU agencies on their own sites (the data that never reaches TED below
threshold or the central F&T Portal), in one feed, filterable by type, body,
status and deadline. As more agencies are added to the Funding & Tenders folder,
they appear here automatically. The central TED (`/funding/tenders`) and F&T
Portal calls remain separate dedicated endpoints.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from ..economy_endpoints import (EconomyItem, _row_to_item, _LIST_COLS, _ORDER_SQL,
                                  _ORDERS, build_envelope)

router = APIRouter()

_FUNDING_TYPES = ("tender", "grant", "eoi_call", "startup_funding")
# Plus the cohesion / structural-fund allocations (eu_cohesion_finances), unioned in.
_ALL_TYPES = _FUNDING_TYPES + ("cohesion_allocation", "solidarity_case", "cap_payment")

# UNION of (a) decentralised agency funding items, (b) the per-fund cohesion
# allocations, (c) EU Solidarity Fund disaster cases, and (d) the CAP fund
# payments (EAGF/EAFRD), all mapped to the same EconomyItem shape. The agency
# side is pre-filtered to funding item_types; the rest are mapped on the fly.
_UNION_CTE = """
WITH all_funding AS (
    SELECT id, body_code, item_type, title, summary, public_url,
           document_date, creation_date, source_kind
    FROM economy_items
    WHERE item_type = ANY(:ftypes)
    UNION ALL
    SELECT id, lower(fund) AS body_code, 'cohesion_allocation' AS item_type,
           cci_title AS title,
           (upper(fund) || ' · ' || coalesce(ms, '') || ' · '
             || coalesce(financial_allocation_category, '')
             || ' · total EUR ' || coalesce(round(total)::text, '0')) AS summary,
           public_url, document_date, created_at AS creation_date, 'cohesion' AS source_kind
    FROM eu_cohesion_finances
    UNION ALL
    SELECT id, 'eusf' AS body_code, 'solidarity_case' AS item_type,
           name_of_disaster AS title,
           (coalesce(applicant_country, '') || ' · ' || coalesce(year_of_occurrence::text, '')
             || ' · ' || coalesce(disaster_type, '')
             || ' · EUSF paid EUR ' || coalesce(round(eusf_grant_paid_meur)::text, '0') || 'm') AS summary,
           public_url, document_date, created_at AS creation_date, 'cohesion' AS source_kind
    FROM eu_solidarity_fund
    UNION ALL
    SELECT id, lower(fund) AS body_code, 'cap_payment' AS item_type,
           (upper(fund) || ' — ' || coalesce(ms, '')) AS title,
           (coalesce(ms, '') || ' · total EUR ' || coalesce(round(total_eur)::text, '0')) AS summary,
           public_url, document_date, created_at AS creation_date, 'cohesion' AS source_kind
    FROM eu_cap_payments
)
"""

_DESC = """**What it does**
One feed of **every EU fund** Brubru covers — the decentralised agency funding items (calls for **tender**, **grants** and calls for **expression of interest**), the per-programme grant calls ingested for their own endpoints (Justice `body=just`, Innovation Fund `body=innovfund`), AND the per-fund cohesion / structural-fund allocations (ERDF, ESF+, Cohesion Fund, JTF, Interreg, EMFAF, AMIF, ISF), the EU Solidarity Fund and the CAP funds (EAGF, EAFRD) — across every body, in one call.

**When to use it**
"Show me everything across EU funding", whether an agency tender, a Justice/Innovation-Fund grant call, or a Member State's cohesion-fund allocation. Filter by `type` (tender/grant/eoi_call/startup_funding/cohesion_allocation/solidarity_case/cap_payment), `body` (agency code or fund code, e.g. `efca`, `erdf`, `just`, `innovfund`), `status`, `q` (free text), and `since`/`until` on the date.

**Input**
`type`, `body`, `status`, `q` (free text), `since`/`until` (date range), `order`, `page`, `limit`.

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


@router.get("/all", response_model=PaginatedResponse[EconomyItem], tags=["v2-funding"],
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
    since: Optional[date] = Query(None, description="Deadline on/after this date (YYYY-MM-DD)."),
    until: Optional[date] = Query(None, description="Deadline on/before this date (YYYY-MM-DD)."),
    order: str = Query("recent", description="recent | oldest | title."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    if order not in _ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS)}")
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
    if since:
        where.append("document_date >= :since"); params["since"] = since
    if until:
        where.append("document_date <= :until"); params["until"] = until
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.execute(
        text(f"{_UNION_CTE} SELECT count(*) FROM all_funding{clause}"), params
    ).scalar() or 0
    rows = db.execute(
        text(f"{_UNION_CTE} SELECT {_LIST_COLS} FROM all_funding{clause} "
             f"ORDER BY {_ORDER_SQL[order]} LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    return build_envelope([_row_to_item(r, with_body=False) for r in rows], total, page, limit)
