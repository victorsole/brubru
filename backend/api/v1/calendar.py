"""
/api/v1/calendar/events — unified EU institutional calendar (EP, Council, EC, agencies).
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
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
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CalendarEventItem]:
    query = db.query(EUCalendarEvent)
    filters = []
    if institution:
        try:
            filters.append(EUCalendarEvent.institution == InstitutionEnum(institution.upper()))
        except ValueError:
            filters.append(EUCalendarEvent.institution == institution.upper())
    if event_type:
        try:
            filters.append(EUCalendarEvent.event_type == EventTypeEnum(event_type.upper()))
        except ValueError:
            filters.append(EUCalendarEvent.event_type == event_type.upper())
    if committee:
        filters.append(func.upper(EUCalendarEvent.ep_committee_code) == committee.upper())
    if commission_dg:
        filters.append(func.upper(EUCalendarEvent.commission_dg) == commission_dg.upper())
    if date_from:
        filters.append(EUCalendarEvent.start_date >= date_from)
    if date_to:
        filters.append(EUCalendarEvent.start_date <= date_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = query.order_by(EUCalendarEvent.start_date.asc()).offset((page - 1) * limit).limit(limit).all()
    data = [
        CalendarEventItem(
            id=str(r.id),
            institution=str(r.institution) if r.institution else "",
            event_type=str(r.event_type) if r.event_type else "",
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
            status=str(r.status) if r.status else None,
            source_url=r.source_url,
            agenda_url=r.agenda_url,
        )
        for r in rows
    ]
    return build_envelope(data, total=total, page=page, limit=limit, published_from=date_from, published_to=date_to)
