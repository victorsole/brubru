"""
/api/v1/calendar/events — unified EU institutional calendar (EP, Council, EC, agencies).
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_calendar import EUCalendarEvent, EventTypeEnum, InstitutionEnum
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/calendar", tags=["v1-calendar"])


class CalendarEventItem(BaseModel):
    id: str
    institution: str
    event_type: str
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    all_day: bool = True
    council_configuration: Optional[str] = None
    ep_activity_type: Optional[str] = None
    ep_committee_code: Optional[str] = None
    commission_dg: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    procedure_refs: list = Field(default_factory=list)
    status: Optional[str] = None
    source_url: Optional[str] = None
    agenda_url: Optional[str] = None
    # Computed: per-event webstream URL (committee_meeting events only).
    webstream_url: Optional[str] = None


def _derive_webstream_url(institution: str, event_type: str, ep_committee_code: Optional[str]) -> Optional[str]:
    """Build the multimedia.europarl webstream URL for an EP committee meeting."""
    if not ep_committee_code:
        return None
    et = (event_type or "").lower()
    inst = (institution or "").upper()
    if "committee" in et and inst == "EP":
        return f"https://multimedia.europarl.europa.eu/en/webstreaming?committee={ep_committee_code.upper()}"
    return None


# Generic / placeholder URLs we should NEVER ship as source_url. When a row
# has one of these, we derive a more specific URL based on event_type +
# institution + committee_code + start_date. Jordi feedback #7 (30 April 2026).
_GENERIC_SOURCE_URLS = {
    "https://www.europarl.europa.eu/committees/en/documents/latest-documents",
    "https://www.europarl.europa.eu/committees/en/meetings/meeting-documents",
    "https://www.europarl.europa.eu/news/en/agenda",
    # Plenary day-less agenda root — override with ?day=YYYYMMDD when we have a date.
    "https://www.europarl.europa.eu/plenary/en/agendas.html",
    "https://www.consilium.europa.eu/en/meetings/",
    "https://commission.europa.eu/news/college-meetings_en",
}


def _derive_specific_source_url(
    institution: Optional[str],
    event_type: Optional[str],
    ep_committee_code: Optional[str],
    council_configuration: Optional[str],
    start_date,
) -> Optional[str]:
    """Build a per-event source URL when the row has no specific one.

    Patterns:
      EP plenary           -> /plenary/en/agendas.html?day=YYYYMMDD
      EP committee_meeting -> /committees/en/{COMMITTEE_LOWER}/meetings/agendas
      EP committee_week    -> /news/en/agenda
      Council meeting      -> /en/meetings/{CONFIG_LOWER}/{YYYY}/{MM}/{DD}/
      European Council     -> /en/meetings/european-council/{YYYY}/{MM}/{DD}/
      Commission college   -> /news/all-news_en
    Returns None when we can't reasonably derive one.
    """
    et = (event_type or "").lower()
    inst = (institution or "").upper()
    d = start_date

    if inst == "EP":
        if "plenary" in et:
            if d:
                return f"https://www.europarl.europa.eu/plenary/en/agendas.html?day={d.strftime('%Y%m%d')}"
            return "https://www.europarl.europa.eu/plenary/en/agendas.html"
        if et == "committee_meeting" and ep_committee_code:
            # /meetings/agendas returns 404 on EP; the committee home/highlights
            # page is the canonical entry that always 200s.
            return f"https://www.europarl.europa.eu/committees/en/{ep_committee_code.lower()}/home/highlights"
        if et == "committee_week":
            return "https://www.europarl.europa.eu/news/en/agenda"

    if inst in ("COUNCIL", "EUROPEAN_COUNCIL"):
        slug = (council_configuration or "").lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "-")
        if inst == "EUROPEAN_COUNCIL" and d:
            return f"https://www.consilium.europa.eu/en/meetings/european-council/{d.year}/{d.month:02d}/{d.day:02d}/"
        if slug and d:
            return f"https://www.consilium.europa.eu/en/meetings/{slug}/{d.year}/{d.month:02d}/{d.day:02d}/"
        if d:
            return f"https://www.consilium.europa.eu/en/meetings/calendar/?DateFrom={d.strftime('%Y/%m/%d')}&DateTo={d.strftime('%Y/%m/%d')}"

    if inst == "COMMISSION":
        return "https://commission.europa.eu/news_en"

    return None


def _resolve_source_url(
    raw_source_url: Optional[str],
    institution: Optional[str],
    event_type: Optional[str],
    ep_committee_code: Optional[str],
    council_configuration: Optional[str],
    start_date,
) -> Optional[str]:
    """Return a specific per-event URL, replacing generic placeholders.

    1. Use the DB-stored source_url if it is specific (not a known placeholder).
    2. Otherwise derive from event_type + institution + date.
    3. Otherwise return None (better than misleading the caller).
    """
    if raw_source_url and raw_source_url not in _GENERIC_SOURCE_URLS:
        return raw_source_url
    return _derive_specific_source_url(
        institution=institution,
        event_type=event_type,
        ep_committee_code=ep_committee_code,
        council_configuration=council_configuration,
        start_date=start_date,
    ) or raw_source_url  # Fall back to whatever we had if derivation also fails


@router.get(
    "/events",
    response_model=PaginatedResponse[CalendarEventItem],
    summary="Unified EU institutional calendar",
    description=(
        "Events from EP plenary, EP committees, Council configurations, Commission college, "
        "and decentralised agencies. ~400+ events indexed. Filter by institution, event type, "
        "committee, DG, and date range."
    ),
)
async def list_calendar_events(
    request: Request,
    institution: Optional[str] = Query(None, description="EP | COUNCIL | EUROPEAN_COUNCIL | COMMISSION | ECJ | ECB | ESMA | EMA | EBA | EIOPA | COR | EESC"),
    event_type: Optional[str] = Query(None, description="PLENARY | COMMITTEE_MEETING | COUNCIL_MEETING | COLLEGE_MEETING | ..."),
    committee: Optional[str] = Query(None, description="EP committee code"),
    commission_dg: Optional[str] = Query(None, description="e.g. AGRI, CNECT, ENV"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — events last_updated >= value. Returns rows ordered by last_updated desc when set."),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to. 422 if both differ."),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CalendarEventItem]:
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
                "reason_code": "conflicting_params",
            },
        )
    if updated_end and not updated_to:
        updated_to = updated_end
    if updated_from and updated_to and updated_from > updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: updated_from={updated_from} is after updated_to={updated_to}.",
                "reason_code": "invalid_date_range",
            },
        )

    query = db.query(EUCalendarEvent)
    filters = []
    if institution:
        # DB stores InstitutionEnum values in UPPERCASE (e.g. 'EP', 'COUNCIL').
        try:
            filters.append(EUCalendarEvent.institution == InstitutionEnum(institution.upper()))
        except ValueError:
            filters.append(EUCalendarEvent.institution == institution.upper())
    if event_type:
        # DB stores EventTypeEnum values in lowercase (e.g. 'committee_meeting').
        et_lower = event_type.lower()
        try:
            filters.append(EUCalendarEvent.event_type == EventTypeEnum(et_lower))
        except ValueError:
            filters.append(EUCalendarEvent.event_type == et_lower)
    if committee:
        filters.append(func.upper(EUCalendarEvent.ep_committee_code) == committee.upper())
    if commission_dg:
        filters.append(func.upper(EUCalendarEvent.commission_dg) == commission_dg.upper())
    if date_from:
        filters.append(EUCalendarEvent.start_date >= date_from)
    if date_to:
        filters.append(EUCalendarEvent.start_date <= date_to)
    if updated_from:
        filters.append(EUCalendarEvent.last_updated >= updated_from)
    if updated_to:
        filters.append(EUCalendarEvent.last_updated <= updated_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = EUCalendarEvent.last_updated.desc().nullslast()
    else:
        order_col = EUCalendarEvent.start_date.asc()
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()
    data = []
    for r in rows:
        inst_value = r.institution.value if hasattr(r.institution, "value") else (str(r.institution) if r.institution else "")
        et_value = r.event_type.value if hasattr(r.event_type, "value") else (str(r.event_type) if r.event_type else "")
        data.append(CalendarEventItem(
            id=str(r.id),
            institution=inst_value,
            event_type=et_value,
            title=r.title,
            description=r.description,
            start_date=r.start_date,
            end_date=r.end_date,
            all_day=bool(r.all_day),
            council_configuration=r.council_configuration,
            ep_activity_type=r.ep_activity_type,
            ep_committee_code=r.ep_committee_code,
            commission_dg=r.commission_dg,
            policy_areas=list(r.policy_areas or []),
            procedure_refs=list(r.procedure_refs or []),
            status=r.status.value if hasattr(r.status, "value") else (str(r.status) if r.status else None),
            source_url=_resolve_source_url(
                r.source_url, inst_value, et_value, r.ep_committee_code,
                r.council_configuration, r.start_date,
            ),
            agenda_url=r.agenda_url,
            webstream_url=_derive_webstream_url(inst_value, et_value, r.ep_committee_code),
        ))
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=date_from, published_to=date_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@router.get(
    "/events/{event_id}",
    response_model=CalendarEventItem,
    summary="Single calendar event detail by id (UUID)",
)
async def get_calendar_event_detail(
    event_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CalendarEventItem:
    r = db.query(EUCalendarEvent).filter(EUCalendarEvent.id == event_id).first()
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Calendar event id {event_id} not found",
                "reason_code": "not_found",
                "resource": "calendar_event",
                "id": event_id,
            },
        )
    inst_value = r.institution.value if hasattr(r.institution, "value") else str(r.institution or "")
    et_value = r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type or "")
    return CalendarEventItem(
        id=str(r.id),
        institution=inst_value,
        event_type=et_value,
        title=r.title,
        description=r.description,
        start_date=r.start_date,
        end_date=r.end_date,
        all_day=bool(r.all_day),
        council_configuration=r.council_configuration,
        ep_activity_type=r.ep_activity_type,
        ep_committee_code=r.ep_committee_code,
        commission_dg=r.commission_dg,
        policy_areas=list(r.policy_areas or []),
        procedure_refs=list(r.procedure_refs or []),
        status=r.status.value if hasattr(r.status, "value") else (str(r.status) if r.status else None),
        source_url=_resolve_source_url(
            r.source_url, inst_value, et_value, r.ep_committee_code,
            r.council_configuration, r.start_date,
        ),
        agenda_url=r.agenda_url,
        webstream_url=_derive_webstream_url(inst_value, et_value, r.ep_committee_code),
    )
