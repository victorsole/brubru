"""GET /api/v2/consultations/all — every decentralised EU agency consultation.

The cross-cutting aggregate over the agency consultations (item_type
'consultation') across every body, filterable by body, status and closing date.
The Commission's central Have Your Say consultations stay at
/api/v2/commission/consultations (a richer, dedicated source).
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

_DESC = """**What it does**
One feed of every decentralised EU agency public consultation — the consultations that EU agencies (EIOPA, BEREC, ACER, EASA, EMA, AMLA, ECHA, SRB, ERA, ECB Banking Supervision) run on their own sites and that do **not** appear on the Commission's "Have Your Say" platform.

**When to use it**
"Show me every open EU consultation that matches my interest", regardless of which agency runs it. Filter by `body` (agency code), `status` (open/closed, matched in the summary), and closing date (`since`/`until`).

**Input**
`body`, `status`, `q` (free text), `since`/`until` (closing-date range), `order`, `page`, `limit`.

**Try it**
```
GET /api/v2/consultations/all?status=open
GET /api/v2/consultations/all?body=ema
```

**You get back**
A paginated list; each item carries `body_code` (the agency), title, the `status · closing date` summary, `document_date` (the closing date) and the link.

**Data freshness**
Live from the database. The Commission's central consultations are at `/api/v2/commission/consultations`."""


@router.get("/all", response_model=PaginatedResponse[EconomyItem], tags=["v2-consultations"],
            summary="All decentralised EU agency public consultations (every body)")
async def consultations_all(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    body: Optional[str] = Query(None, description="Agency code, e.g. ema, echa, berec."),
    status: Optional[str] = Query(None, description="Match on status in the summary (e.g. open, closed)."),
    q: Optional[str] = Query(None, description="Free-text search over title, summary and body."),
    since: Optional[date] = Query(None, description="Closing date on/after this date (YYYY-MM-DD)."),
    until: Optional[date] = Query(None, description="Closing date on/before this date (YYYY-MM-DD)."),
    order: str = Query("recent", description="recent | oldest | title."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    if order not in _ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS)}")
    where = ["item_type = 'consultation'"]
    params = {"limit": limit, "offset": (page - 1) * limit}
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
