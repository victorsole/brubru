"""
/api/v1/committee-agendas/* — EP committee draft agendas (the "order of the
day" for each committee meeting), with the full agenda document body.

Metadata is sourced from the `eu_calendar_events` rows the committee-agenda
sync produces (source='ep_committee_agenda'): committee, meeting date, the
doceo agenda-document URL, and the procedure references scheduled for
discussion. The agenda document BODY (body_txt + body_html) is fetched from the
doceo OJ PDF on demand and cached on the event's `related_documents` JSONB
(see services.scrapers.committee_agenda_body_extractor).

The 5 mandatory v1 datapoints, from real data only:
    public_url    -> agenda_url (the doceo agenda document) | source_url
    body_txt      -> text extracted from the doceo agenda PDF
    body_html     -> composed from that extracted text (one <p> per paragraph)
    document_date -> the meeting date (start_date)
    creation_date -> when Brubru first ingested the agenda (first_seen)

Note: doceo is JS-WAF-walled to most hosts, so body extraction succeeds from
the deployment host (Railway) — the same path that fills
committee_minutes.full_text. On a cache miss where the fetch is blocked, body_*
return null and the metadata still serves (honest degradation).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_calendar import EUCalendarEvent
from models.user import User

from ._body import body_threshold_param
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope
from services.scrapers.committee_agenda_body_extractor import ensure_agenda_body

router = APIRouter(prefix="/committee-agendas", tags=["v1-committee-agendas"])

_AGENDA_SOURCE = "ep_committee_agenda"


class CommitteeAgendaOut(BaseModel):
    id: str
    committee_code: Optional[str] = None
    title: str
    meeting_date: date
    agenda_url: Optional[str] = None
    source_url: Optional[str] = None
    procedure_refs: list = Field(default_factory=list)
    external_id: Optional[str] = None
    has_body: bool = False

    # The 5 mandatory Brubru v1 datapoints (real data only).
    public_url: Optional[str] = Field(
        None,
        description="Citizen URL — the doceo draft-agenda document (agenda_url), falling back to source_url.",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text body extracted from the doceo agenda document. Null only when the document could not be fetched.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML body composed from the extracted agenda text (one <p> per paragraph). Same text as body_txt, structured.",
    )
    document_date: Optional[date] = Field(
        None,
        description="The committee meeting date the agenda is for (start_date).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first ingested this agenda (eu_calendar_events.first_seen).",
    )


def _row_to_item(event: EUCalendarEvent, body_txt: Optional[str], body_html: Optional[str], threshold: int) -> CommitteeAgendaOut:
    has_body = bool(body_txt and len(body_txt) >= threshold)
    return CommitteeAgendaOut(
        id=str(event.id),
        committee_code=event.ep_committee_code,
        title=event.title,
        meeting_date=event.start_date,
        agenda_url=event.agenda_url,
        source_url=event.source_url,
        procedure_refs=list(event.procedure_refs or []),
        external_id=event.external_id,
        has_body=has_body,
        # 5 mandatory datapoints
        public_url=event.agenda_url or event.source_url,
        body_txt=body_txt,
        body_html=body_html,
        document_date=event.start_date,
        creation_date=event.first_seen,
    )


@router.get(
    "",
    response_model=PaginatedResponse[CommitteeAgendaOut],
    summary="EP committee draft agendas — the order of the day for committee meetings, with full text",
    description="""**What it does**
Returns EP committee draft agendas (the official "order of the day" for each committee meeting): the committee, the meeting date, the link to the doceo agenda document, the procedure references scheduled for discussion, and the full agenda text (`body_txt` + `body_html`). It tells you what a committee plans to take up before the meeting happens.

**When to use it**
To see what is coming up in a committee — which files are tabled for discussion or vote at the next meeting, and the full running order. Pair with `/api/v1/committees/{code}/minutes` (what happened) and `/api/v1/committee-transcripts` (what was said).

**Input**
- `committee` — EP committee/subcommittee code (e.g. `LIBE`, `ENVI`).
- `procedure_reference` — only agendas that scheduled this procedure (e.g. `2024/0079(COD)`).
- `q` — substring search on the agenda title.
- `upcoming` — `true` returns only agendas dated today or later (the planning view); default `false` returns all.
- `published_from` / `published_to` (aliased `date_from` / `date_to`) — meeting-date range.
- `updated_from` — rows updated at/after this timestamp (incremental sync).
- `body_threshold` — minimum agenda-text length (chars) for `has_body=true`. Default 500.
- `limit` (default 10, max 25 — the agenda document is fetched + cached on first access), `page` (1-indexed).

**Try it**
```
GET /api/v1/committee-agendas?committee=LIBE&upcoming=true
GET /api/v1/committee-agendas?procedure_reference=2024/0079(COD)
```

**You get back**
A `PaginatedResponse[CommitteeAgendaOut]`. Each row carries `committee_code`, `title`, `meeting_date`, `procedure_refs[]`, plus the 5 envelope datapoints: `public_url` (the agenda document), `body_txt` + `body_html` (the agenda text), `document_date` (the meeting date), and `creation_date`. `has_body` is true once the agenda document has been fetched.

**Data freshness**
Agenda metadata syncs from the EP committee pages (`backend/services/scrapers/committee_agenda_sync_service.py`); draft agendas appear ~1 week before a meeting. The agenda document body is fetched from doceo on first access and cached.""",
)
async def list_committee_agendas(
    request: Request,
    committee: Optional[str] = Query(None, description="EP committee/subcommittee code (e.g. LIBE)."),
    procedure_reference: Optional[str] = Query(None, description="Only agendas that scheduled this procedure ref."),
    q: Optional[str] = Query(None, description="Substring search on the agenda title."),
    upcoming: bool = Query(False, description="True = only agendas dated today or later."),
    published_from: Optional[date] = Query(None, alias="date_from"),
    published_to: Optional[date] = Query(None, alias="date_to"),
    updated_from: Optional[datetime] = Query(None),
    body_threshold: int = Depends(body_threshold_param),
    limit: int = Query(10, ge=1, le=25, description="Items per page (default 10, max 25 — each agenda document is fetched + cached on first access)."),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CommitteeAgendaOut]:
    E = EUCalendarEvent
    base = db.query(E).filter(E.source == _AGENDA_SOURCE)

    if committee:
        base = base.filter(func.upper(E.ep_committee_code) == committee.upper())
    if procedure_reference:
        base = base.filter(E.procedure_refs.contains([procedure_reference]))
    if q:
        base = base.filter(E.title.ilike(f"%{q}%"))
    if upcoming:
        base = base.filter(E.start_date >= date.today())
    if published_from:
        base = base.filter(E.start_date >= published_from)
    if published_to:
        base = base.filter(E.start_date <= published_to)
    if updated_from:
        base = base.filter(E.last_updated >= updated_from)

    total = base.count()
    rows = base.order_by(E.start_date.desc()).offset((page - 1) * limit).limit(limit).all()

    data = []
    for event in rows:
        body_txt, body_html = ensure_agenda_body(db, event)
        data.append(_row_to_item(event, body_txt, body_html, body_threshold))

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        updated_from=updated_from,
        coverage_complete=True,
        op_core_title="EP committee draft agendas",
        op_core_type="EP committee draft agenda",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/committees/{code}/minutes",
            "/api/v1/committee-transcripts",
        ],
    )


@router.get(
    "/{event_id}",
    response_model=CommitteeAgendaOut,
    summary="One committee draft agenda by id — full agenda text + HTML",
    description="""**What it does**
Fetches a single committee draft agenda by its Brubru-internal calendar-event UUID, with the full agenda document body (`body_txt` + `body_html`).

**When to use it**
After locating an agenda via the list endpoint, use this to pull the complete order of the day.

**Input**
- `event_id` (path) — the Brubru-internal UUID from the list endpoint's `id`.

**Try it**
```
GET /api/v1/committee-agendas/{event_id}
```

**You get back**
A single `CommitteeAgendaOut` (same shape as the list endpoint's `data[i]`), with `body_txt` + `body_html` populated when the agenda document is reachable, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Agenda body fetched from doceo on first access and cached on the event.""",
)
async def get_committee_agenda_detail(
    event_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommitteeAgendaOut:
    event = (
        db.query(EUCalendarEvent)
        .filter(EUCalendarEvent.id == event_id, EUCalendarEvent.source == _AGENDA_SOURCE)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No committee agenda with id {event_id}"})
    body_txt, body_html = ensure_agenda_body(db, event)
    return _row_to_item(event, body_txt, body_html, body_threshold)
