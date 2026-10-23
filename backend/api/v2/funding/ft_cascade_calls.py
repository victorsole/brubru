"""Calls for funding in cascade — /api/v2/funding/ft-cascade-calls.

/api/v2/funding/ft-cascade-calls        — every cascade call, newest first (full text by default)
/api/v2/funding/ft-cascade-calls/{id}   — one cascade call

Open calls that EU-funded projects issue themselves (financial support to third parties), as the
Funding & Tenders Portal lists them under "Calls for funding in cascade (issued by funded
projects)". Backed by ``ft_cascade_calls`` (migration 310, scripts/ingest_ft_cascade_calls.py).
Until 23 Oct 2026 they were folded into /ft-calls-for-proposals under the identifier of the topic
that funds them, one row per topic. Built on the standard of 23 Oct: full text on by default,
50 a page up to 200, the change window, the five datapoints.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._change_window import (SYNC_ORDERS, SYNC_PARAMS_DOC, UpperBoundDatetime, sql_order, sql_window,
                                   validate_window)
from api.v1._envelope import PaginatedResponse, build_envelope

router = APIRouter()


class CascadeCallItem(BaseModel):
    id: int = Field(..., description="Brubru id of the cascade call (use it on the item route).")
    item_type: str = Field("cascade_call", description="Always `cascade_call`.")
    call_id: str = Field(..., description="The portal's own number for the call (its page is competitive-calls-cs/<call_id>).")
    title: str
    topic_id: Optional[str] = Field(None, description="The EU topic that funds the issuing project, as the portal files the call.")
    topic_title: Optional[str] = None
    project_id: Optional[str] = Field(None, description="Grant agreement number of the EU-funded project that issues the call (see /funding/ft-funded-projects/{project_id}).")
    project_acronym: Optional[str] = None
    project_name: Optional[str] = None
    framework_programme: Optional[str] = None
    status: Optional[str] = Field(None, description="forthcoming | open | closed, from the call's own dates.")
    deadline_model: Optional[str] = Field(None, description="single-stage, multiple cut-off, ... as the portal states it.")
    deadline: Optional[datetime] = Field(None, description="The next cut-off, or the last one once all have passed.")
    deadline_secondary: Optional[datetime] = Field(None, description="The final cut-off, when later than `deadline`.")
    duration: Optional[str] = Field(None, description="Expected duration of participation, as the portal states it.")
    indicative_budget: Optional[float] = Field(None, description="Total funding available.")
    budget_currency: Optional[str] = None
    public_url: Optional[str] = Field(None, description="The portal's page for this cascade call.")
    body_txt: Optional[str] = Field(None, description="The page's text: task description, submission and evaluation process, further information.")
    body_html: Optional[str] = Field(None, description="The same sections as HTML.")
    document_date: Optional[datetime] = Field(None, description="The portal's opening date/publication date (one date for a call, as the portal shows it).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first recorded the call.")
    updated_date: Optional[datetime] = Field(None, description="When the call's content last changed in Brubru; a daily re-read that finds the same call does not move it.")


_COLS = ("id, call_id, title, topic_id, topic_title, project_id, project_acronym, project_name, "
         "framework_programme, status, deadline_model, deadline, deadline_secondary, duration, "
         "indicative_budget, budget_currency, source_url AS public_url, published_at AS document_date, "
         "first_seen AS creation_date, last_updated AS updated_date")
_BODY = ", description AS body_txt, description_html AS body_html"
_ORDERS = {
    "recent": "published_at DESC NULLS LAST, id DESC",
    "oldest": "published_at ASC NULLS LAST, id ASC",
    "deadline": "deadline ASC NULLS LAST, id ASC",
}


def _item(r, *, with_body: bool) -> CascadeCallItem:
    d = dict(r)
    if not with_body:
        d["body_txt"] = d["body_html"] = None
    return CascadeCallItem(**d)


@router.get(
    "/ft-cascade-calls",
    response_model=PaginatedResponse[CascadeCallItem],
    tags=["v2-funding"],
    summary="Calls for funding in cascade — open calls issued by EU-funded projects",
    description=f"""**What it does**
Lists the calls that EU-funded projects issue themselves to pass part of their grant on to others
(financial support to third parties: start-ups, SMEs, artists, researchers, civil-society
organisations), as the Funding & Tenders Portal lists them under "Calls for funding in cascade
(issued by funded projects)". Each carries its own title, page, dates, deadline model, total funding,
the project that issues it and the EU topic that funds that project, with the full text of the call.

**When to use it**
To find money that is not a direct EU call: cascade calls are short, small and open to applicants
who would not bid for a Horizon Europe topic. Filter by status or programme, or by `project_id` to see
every call one project has issued.

**Input**
- `q` words in the title or text; `status` (comma list: forthcoming, open, closed); `programme`
  (substring); `topic_id`; `project_id`; `call_id`.
- `published_from` / `published_to` on the opening/publication date (`since`/`until` accepted);
  `deadline_from` / `deadline_to`.
- `order` (recent default | oldest | deadline | updated_asc | updated_desc | created_asc | created_desc).
- `include_body` (default true), `limit` (default 50, max 200), `page`.
{SYNC_PARAMS_DOC}

**Try it**
```
GET /api/v2/funding/ft-cascade-calls?status=open,forthcoming&order=deadline
GET /api/v2/funding/ft-cascade-calls?programme=Creative%20Europe
GET /api/v2/funding/ft-cascade-calls?updated_from=2026-10-23&order=updated_asc
```

**You get back**
A `PaginatedResponse[CascadeCallItem]` envelope: `id`, `call_id`, `title`, `topic_id`, `project_id`,
`project_acronym`, `status`, `deadline`, `indicative_budget` and the five datapoints (`public_url` =
the portal's page for the call, `document_date` = its opening/publication date).

**Data freshness**
Read daily from the portal's search service (every cascade call, closed ones included).""",
)
async def list_cascade_calls(
    request: Request,
    q: Optional[str] = Query(None, description="Words in the title or the text."),
    status: Optional[str] = Query(None, description="Comma list: forthcoming, open, closed."),
    programme: Optional[str] = Query(None, description="Substring of the programme, e.g. Horizon Europe."),
    topic_id: Optional[str] = Query(None, description="The funding topic's identifier."),
    project_id: Optional[str] = Query(None, description="The issuing project's grant agreement number."),
    call_id: Optional[str] = Query(None, description="The portal's call number."),
    published_from: Optional[date] = Query(None, description="Opened/published on or after (YYYY-MM-DD)."),
    published_to: Optional[date] = Query(None, description="Opened/published on or before (YYYY-MM-DD)."),
    since: Optional[date] = Query(None, include_in_schema=False),
    until: Optional[date] = Query(None, include_in_schema=False),
    deadline_from: Optional[date] = Query(None, description="Deadline on or after (YYYY-MM-DD)."),
    deadline_to: Optional[date] = Query(None, description="Deadline on or before (YYYY-MM-DD)."),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Content last changed on or after (ISO date or datetime, UTC). The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Content last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | deadline | updated_asc | updated_desc | created_asc | created_desc."),
    include_body: bool = Query(True, description="Return `body_txt` / `body_html` on every item (default true)."),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CascadeCallItem]:
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {list(_ORDERS) + list(SYNC_ORDERS)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    where = ["NOT is_test"]
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    if q:
        where.append("(title ILIKE :q OR description ILIKE :q)"); params["q"] = f"%{q}%"
    if status:
        wanted = [s.strip().lower() for s in status.split(",") if s.strip()]
        where.append("status = ANY(:st)"); params["st"] = wanted
    if programme:
        where.append("framework_programme ILIKE :prog"); params["prog"] = f"%{programme}%"
    for name, value in (("topic_id", topic_id), ("project_id", project_id), ("call_id", call_id)):
        if value:
            where.append(f"{name} = :{name}"); params[name] = value
    published_from, published_to = published_from or since, published_to or until
    if published_from:
        where.append("published_at >= :pf"); params["pf"] = published_from
    if published_to:
        where.append("published_at < CAST(:pt AS date) + 1"); params["pt"] = published_to
    if deadline_from:
        where.append("deadline >= :df"); params["df"] = deadline_from
    if deadline_to:
        where.append("deadline < CAST(:dt AS date) + 1"); params["dt"] = deadline_to
    sql_window(where, params, window, "first_seen", "last_updated")
    clause = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM ft_cascade_calls WHERE {clause}"), params).scalar() or 0
    order_sql = sql_order(order, "first_seen", "last_updated") or _ORDERS[order]
    rows = db.execute(
        text(f"SELECT {_COLS}{_BODY if include_body else ''} FROM ft_cascade_calls WHERE {clause} "
             f"ORDER BY {order_sql} LIMIT :limit OFFSET :offset"), params,
    ).mappings().all()
    return build_envelope([_item(r, with_body=include_body) for r in rows], total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])


@router.get(
    "/ft-cascade-calls/{item_id}",
    response_model=CascadeCallItem,
    tags=["v2-funding"],
    summary="One call for funding in cascade, in full",
    description="""**What it does**
Returns one cascade call by its Brubru `id`, with its full text.

**Input**
- `item_id` (path): the `id` from the list (the portal's number is `call_id`; filter the list with it).

**Try it**
```
GET /api/v2/funding/ft-cascade-calls/1
```

**You get back**
A single `CascadeCallItem`, or HTTP 404 with `reason_code: not_found`.""",
)
async def get_cascade_call(
    item_id: int = Path(..., description="Brubru id from the list."),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CascadeCallItem:
    r = db.execute(text(f"SELECT {_COLS}{_BODY} FROM ft_cascade_calls WHERE id = :id AND NOT is_test"),
                   {"id": item_id}).mappings().fetchone()
    if not r:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No cascade call with id {item_id}"})
    return _item(r, with_body=True)

