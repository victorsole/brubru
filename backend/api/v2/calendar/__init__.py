"""
EU Calendar domain — /api/v2/calendar/*.

The unified EU institutional calendar — plenary, committee, Council, College and
agency events in one feed. Ported from v1 via the v1-delegation pattern: the body
delegates to the working v1 handlers, then remaps each event onto the mandatory
5-datapoint contract (v1's CalendarEventItem predates it):
    public_url    = the event's source_url (or agenda_url)
    document_date = the event start date
    body_txt/html = composed from title + institution + type + dates + status
    creation_date = null (not exposed by the v1 item)
Tag v2-calendar → grouped in the "EU Calendar" Postman folder.
"""
from __future__ import annotations

import html as _html
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1 import calendar as _v1
from api.v1.calendar import CalendarEventItem

router = APIRouter(prefix="/calendar")


class CalendarEventV2(CalendarEventItem):
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = None
    creation_date: Optional[datetime] = None


def _to_v2(it: CalendarEventItem, *, with_body: bool) -> CalendarEventV2:
    lines = [it.title]
    if it.institution:
        lines.append(f"Institution: {it.institution}")
    if it.event_type:
        lines.append(f"Type: {it.event_type}")
    if it.start_date:
        lines.append(f"Start: {it.start_date}")
    if it.end_date:
        lines.append(f"End: {it.end_date}")
    if it.status:
        lines.append(f"Status: {it.status}")
    if it.description:
        lines += ["", it.description]
    body_txt = "\n".join(str(x) for x in lines)
    body_html = "<ul>" + "".join(f"<li>{_html.escape(str(x))}</li>" for x in lines if x) + "</ul>"
    return CalendarEventV2(
        **it.model_dump(),
        public_url=it.source_url or it.agenda_url,
        body_txt=(body_txt if with_body else None),
        body_html=(body_html if with_body else None),
        document_date=it.start_date,
        creation_date=None,
    )


@router.get(
    "/events",
    response_model=PaginatedResponse[CalendarEventV2],
    tags=["v2-calendar"],
    summary="Unified EU institutional calendar — plenary, committees, Council, College, agencies",
    description="""**What it does**
One feed of EU institutional events across the institutions — European Parliament plenary + committee meetings, Council and European Council meetings, Commission College meetings, and agency events — with dates, institution, type, linked procedures and (for EP committee meetings) the webstream URL.

**When to use it**
To track when the institutions are meeting on the files you follow. Filter by `institution`, `event_type`, `committee`, `commission_dg`, and a `date_from`/`date_to` window; use `updated_from` for incremental sync.

**Input**
`institution`, `event_type`, `committee`, `commission_dg`, `date_from`, `date_to`, `updated_from`/`updated_to`, `limit` (max 100), `page`.

**Try it**
```
GET /api/v2/calendar/events?institution=EP&event_type=PLENARY
GET /api/v2/calendar/events?date_from=2026-06-15&date_to=2026-06-30
```

**You get back**
A paginated envelope. Each event carries `institution`, `event_type`, `title`, `start_date`/`end_date`, linked `procedure_refs`, `webstream_url` where applicable, plus the 5 datapoints (`public_url`, `document_date` = start date; `body_txt`/`body_html` null on the list — fetch the detail endpoint).

**Data freshness**
Synced from the institutions' agendas (EP doceo, Council, College agenda, agency calendars).""",
)
async def list_calendar_events(
    request: Request,
    institution: Optional[str] = Query(None, description="EP | COUNCIL | EUROPEAN_COUNCIL | COMMISSION | ECJ | ECB | ESMA | EMA | EBA | EIOPA | COR | EESC"),
    event_type: Optional[str] = Query(None, description="PLENARY | COMMITTEE_MEETING | COUNCIL_MEETING | COLLEGE_MEETING | ..."),
    committee: Optional[str] = Query(None, description="EP committee code"),
    commission_dg: Optional[str] = Query(None, description="e.g. AGRI, CNECT, ENV"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — events last_updated >= value."),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to."),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CalendarEventV2]:
    resp = await _v1.list_calendar_events(
        request=request, institution=institution, event_type=event_type, committee=committee,
        commission_dg=commission_dg, date_from=date_from, date_to=date_to,
        updated_from=updated_from, updated_to=updated_to, updated_end=updated_end,
        limit=limit, page=page, user=user, db=db)
    items = [_to_v2(it, with_body=False) for it in resp.data]
    return build_envelope(items, resp.total, page, limit)


@router.get(
    "/events/{event_id}",
    response_model=CalendarEventV2,
    tags=["v2-calendar"],
    summary="Look up one calendar event by its Brubru-internal id (full body)",
    description="""**What it does**
Returns one EU calendar event in full, including the composed `body_txt` / `body_html` and all 5 datapoints.

**Input**
`event_id` — the Brubru-internal event id from the list endpoint.

**Try it**
```
GET /api/v2/calendar/events/{event_id}
```

**You get back**
A single `CalendarEventV2` with the full record + the 5 datapoints, or HTTP 404.

**Data freshness**
Same as the list endpoint.""",
)
async def get_calendar_event(
    event_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CalendarEventV2:
    it = await _v1.get_calendar_event_detail(event_id=event_id, user=user, db=db)
    return _to_v2(it, with_body=True)
