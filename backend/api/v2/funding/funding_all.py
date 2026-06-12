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

_DESC = """**What it does**
One feed of every decentralised EU funding item — calls for **tender**, **grants** and calls for **expression of interest** that EU agencies publish on their own sites — across every body, in one call. This is the data that does **not** appear in TED below threshold or in the central Funding & Tenders Portal.

**When to use it**
"Show me every open EU funding opportunity that matches my interest", regardless of which agency runs it. Filter by `type` (tender/grant/eoi_call/startup_funding), `body` (agency code), `status` (open/closed, matched in the summary), and `deadline` (`since`/`until` on the closing date).

**Input**
`type`, `body`, `status`, `q` (free text), `since`/`until` (deadline range), `order`, `page`, `limit`.

**Try it**
```
GET /api/v2/funding/all?type=tender&order=recent
GET /api/v2/funding/all?body=efca&q=vessel
```

**You get back**
A paginated list; each item carries `body_code` (the agency), `item_type`, title, the `reference · status · deadline` summary, `document_date` (the deadline) and the link.

**Data freshness**
Live from the database; refreshed as each agency's procurement pages are re-synced. The central TED tenders are at `/api/v2/funding/tenders`."""


@router.get("/all", response_model=PaginatedResponse[EconomyItem], tags=["v2-funding"],
            summary="All decentralised EU funding — tenders, grants & calls across every body")
async def funding_all(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    type: Optional[str] = Query(None, description="tender | grant | eoi_call | startup_funding"),
    body: Optional[str] = Query(None, description="Agency code, e.g. efca, cedefop, ema."),
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
    where = ["item_type = ANY(:types)"]
    params = {"types": list(_FUNDING_TYPES), "limit": limit, "offset": (page - 1) * limit}
    if type:
        if type not in _FUNDING_TYPES:
            raise HTTPException(status_code=400, detail=f"type must be one of {list(_FUNDING_TYPES)}")
        where = ["item_type = :it"]; params["it"] = type
    if body:
        where.append("body_code = :bc"); params["bc"] = body
    if status:
        where.append("summary ILIKE :st"); params["st"] = f"%{status}%"
    if q:
        where.append("(title ILIKE :q OR summary ILIKE :q OR body_txt ILIKE :q)"); params["q"] = f"%{q}%"
    if since:
        where.append("document_date >= :since"); params["since"] = since
    if until:
        where.append("document_date <= :until"); params["until"] = until
    clause = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {clause}"), params).scalar() or 0
    rows = db.execute(
        text(f"SELECT {_LIST_COLS} FROM economy_items WHERE {clause} "
             f"ORDER BY {_ORDER_SQL[order]} LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    return build_envelope([_row_to_item(r, with_body=False) for r in rows], total, page, limit)
