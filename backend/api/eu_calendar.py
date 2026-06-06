"""
EU Calendar API

FastAPI endpoints for the My EU Calendar feature.

Routes:
- GET /api/eu-calendar/events - List events with filters
- GET /api/eu-calendar/events/range - All events in date range
- GET /api/eu-calendar/events/today - Today's digest (My EU Today)
- GET /api/eu-calendar/events/{id} - Single event
- GET /api/eu-calendar/institutions - List institutions
- GET /api/eu-calendar/policy-areas - List policy areas
- POST /api/eu-calendar/sync - Trigger sync (Blue/Admin)

Access Control:
- Yellow+: Full read access
- Blue: AI summary in today digest, sync trigger
- Admin: Sync trigger

Created: February 2026
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from datetime import date, timedelta

from core.database import get_db
from models.user import User
from models.eu_calendar import (
    EUCalendarEvent,
    InstitutionEnum,
    EventTypeEnum,
    EventStatusEnum,
)
from schemas.eu_calendar_schemas import (
    CalendarEventResponse,
    CalendarEventListResponse,
    CalendarRangeResponse,
    TodayDigestResponse,
    InstitutionInfo,
    PolicyAreaInfo,
    SyncResultResponse,
    SyncAllResultResponse,
)
from knowledge_base.eu_calendar_institutions import (
    get_institutions_for_frontend,
    get_policy_areas_for_frontend,
    get_bodies_for_frontend,
    POLICY_AREAS,
)
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    committees_for_interests,
    dgs_for_interests,
    council_configs_for_interests,
    agencies_for_interests,
    keywords_for_interests,
)
from .auth import get_current_user

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eu-calendar", tags=["EU Calendar"])


# ============================================================================
# Helper: Tier check
# ============================================================================

def _require_yellow_tier(user: User):
    """Require Yellow or Blue tier."""
    if not user or user.subscription_tier == "white":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EU Calendar requires Yellow or Blue tier subscription.",
        )


def _is_blue_tier(user: User) -> bool:
    """Check if user has Blue tier."""
    return user and user.subscription_tier == "blue"


def _is_admin(user: User) -> bool:
    """Check if user is admin."""
    return user and getattr(user, "is_admin", False)


def _pi_clause(user: User):
    """Build an OR clause selecting events that touch the user's Policy Interests.

    Matches across every dimension an event might carry: EP committee, Commission
    DG, Council configuration, agency institution, calendar policy-area tag, and
    finally a title-keyword match (for third-party / agency events that have no
    structured body). Returns None when the user has no interests (so callers
    fall back to showing everything). Same PI lens the rest of MEUB uses.
    """
    interests = _interest_list(user)
    if not interests:
        return None

    committees = committees_for_interests(interests)
    dgs = dgs_for_interests(interests)
    configs = council_configs_for_interests(interests)
    agencies = agencies_for_interests(interests)
    keywords = keywords_for_interests(interests)
    # Calendar policy-area codes whose committees/configs intersect the user's —
    # lets PI catch events tagged only by policy_areas.
    pi_areas = {
        pa.code for pa in POLICY_AREAS
        if (committees & set(pa.ep_committee_codes)) or (configs & set(pa.council_configs))
    }

    clauses = []
    if committees:
        clauses.append(EUCalendarEvent.ep_committee_code.in_(list(committees)))
    if dgs:
        clauses.append(EUCalendarEvent.commission_dg.in_(list(dgs)))
    if configs:
        clauses.append(EUCalendarEvent.council_configuration.in_(list(configs)))
    if agencies:
        clauses.append(EUCalendarEvent.institution.in_(list(agencies)))
    for area in pi_areas:
        clauses.append(EUCalendarEvent.policy_areas.any(area))
    for kw in keywords:
        clauses.append(EUCalendarEvent.title.ilike(f"%{kw}%"))

    return or_(*clauses) if clauses else None


# ============================================================================
# Events
# ============================================================================

@router.get("/events", response_model=CalendarEventListResponse)
async def list_events(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    institution: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    committee_code: Optional[str] = Query(None, description="EP committee code(s), comma-separated"),
    commission_dg: Optional[str] = Query(None, description="Commission DG code(s), comma-separated"),
    council_configuration: Optional[str] = Query(None, description="Council configuration code(s), comma-separated"),
    policy_area: Optional[str] = Query(None),
    organiser: Optional[str] = Query(None, description="Organiser substring (e.g. political group / EPRS)"),
    my_interests: bool = Query(False, description="Restrict to events touching the user's Policy Interests"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List calendar events with filters and pagination."""
    _require_yellow_tier(user)

    query = db.query(EUCalendarEvent)

    if my_interests:
        clause = _pi_clause(user)
        if clause is not None:
            query = query.filter(clause)

    # Filters
    if date_from:
        query = query.filter(EUCalendarEvent.start_date >= date_from)
    if date_to:
        query = query.filter(EUCalendarEvent.start_date <= date_to)
    if institution:
        institutions = [i.strip() for i in institution.split(",")]
        query = query.filter(EUCalendarEvent.institution.in_(institutions))
    if event_type:
        query = query.filter(EUCalendarEvent.event_type == event_type)
    if committee_code:
        codes = [c.strip() for c in committee_code.split(",")]
        query = query.filter(EUCalendarEvent.ep_committee_code.in_(codes))
    if commission_dg:
        dgs = [d.strip() for d in commission_dg.split(",")]
        query = query.filter(EUCalendarEvent.commission_dg.in_(dgs))
    if council_configuration:
        cfgs = [c.strip() for c in council_configuration.split(",")]
        query = query.filter(EUCalendarEvent.council_configuration.in_(cfgs))
    if policy_area:
        query = query.filter(EUCalendarEvent.policy_areas.any(policy_area))
    if organiser:
        query = query.filter(EUCalendarEvent.organiser.ilike(f"%{organiser}%"))
    if search:
        query = query.filter(
            or_(
                EUCalendarEvent.title.ilike(f"%{search}%"),
                EUCalendarEvent.description.ilike(f"%{search}%"),
            )
        )

    # Exclude recess events by default
    query = query.filter(EUCalendarEvent.event_type != EventTypeEnum.RECESS)

    total = query.count()
    events = (
        query
        .order_by(EUCalendarEvent.start_date.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    from services.linking.emeeting_links import attach_calendar_agendas
    resp = [CalendarEventResponse.model_validate(e) for e in events]
    attach_calendar_agendas(db, resp)
    return CalendarEventListResponse(total=total, events=resp)


@router.get("/events/range", response_model=CalendarRangeResponse)
async def get_events_in_range(
    date_from: date = Query(...),
    date_to: date = Query(...),
    institution: Optional[str] = Query(None),
    committee_code: Optional[str] = Query(None, description="EP committee code(s), comma-separated"),
    commission_dg: Optional[str] = Query(None, description="Commission DG code(s), comma-separated"),
    council_configuration: Optional[str] = Query(None, description="Council configuration code(s), comma-separated"),
    policy_area: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, description="Event type(s), comma-separated"),
    organiser: Optional[str] = Query(None, description="Organiser substring (e.g. political group / EPRS)"),
    my_interests: bool = Query(False, description="Restrict to events touching the user's Policy Interests"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all events in a date range (no pagination, for calendar views)."""
    _require_yellow_tier(user)

    # Cap range at 90 days
    if (date_to - date_from).days > 90:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 90 days.",
        )

    query = db.query(EUCalendarEvent).filter(
        EUCalendarEvent.start_date >= date_from,
        EUCalendarEvent.start_date <= date_to,
    )

    if my_interests:
        clause = _pi_clause(user)
        if clause is not None:
            query = query.filter(clause)

    if institution:
        institutions = [i.strip() for i in institution.split(",")]
        query = query.filter(EUCalendarEvent.institution.in_(institutions))
    if committee_code:
        codes = [c.strip() for c in committee_code.split(",")]
        query = query.filter(EUCalendarEvent.ep_committee_code.in_(codes))
    if commission_dg:
        dgs = [d.strip() for d in commission_dg.split(",")]
        query = query.filter(EUCalendarEvent.commission_dg.in_(dgs))
    if council_configuration:
        cfgs = [c.strip() for c in council_configuration.split(",")]
        query = query.filter(EUCalendarEvent.council_configuration.in_(cfgs))
    if policy_area:
        areas = [a.strip() for a in policy_area.split(",")]
        query = query.filter(
            or_(*[EUCalendarEvent.policy_areas.any(a) for a in areas])
        )
    if event_type:
        types = [t.strip() for t in event_type.split(",")]
        query = query.filter(EUCalendarEvent.event_type.in_(types))
    if organiser:
        query = query.filter(EUCalendarEvent.organiser.ilike(f"%{organiser}%"))

    # Exclude recess
    query = query.filter(EUCalendarEvent.event_type != EventTypeEnum.RECESS)

    events = query.order_by(EUCalendarEvent.start_date.asc()).all()

    from services.linking.emeeting_links import attach_calendar_agendas
    resp = [CalendarEventResponse.model_validate(e) for e in events]
    attach_calendar_agendas(db, resp)
    return CalendarRangeResponse(
        date_from=date_from,
        date_to=date_to,
        total=len(events),
        events=resp,
    )


@router.get("/events/today", response_model=TodayDigestResponse)
async def get_today_digest(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get today's events digest for 'My EU Today' panel."""
    _require_yellow_tier(user)

    today = date.today()
    tomorrow = today + timedelta(days=1)

    today_events = (
        db.query(EUCalendarEvent)
        .filter(
            EUCalendarEvent.start_date == today,
            EUCalendarEvent.event_type != EventTypeEnum.RECESS,
        )
        .order_by(EUCalendarEvent.start_time.asc().nullsfirst())
        .all()
    )

    tomorrow_events = (
        db.query(EUCalendarEvent)
        .filter(
            EUCalendarEvent.start_date == tomorrow,
            EUCalendarEvent.event_type != EventTypeEnum.RECESS,
        )
        .order_by(EUCalendarEvent.start_time.asc().nullsfirst())
        .all()
    )

    # AI summary for Blue tier
    ai_summary = None
    if _is_blue_tier(user) and today_events:
        ai_summary = _generate_today_summary(today_events)

    from services.linking.emeeting_links import attach_calendar_agendas
    today_resp = [CalendarEventResponse.model_validate(e) for e in today_events]
    tomorrow_resp = [CalendarEventResponse.model_validate(e) for e in tomorrow_events]
    attach_calendar_agendas(db, today_resp + tomorrow_resp)
    return TodayDigestResponse(
        today_count=len(today_events),
        today_events=today_resp,
        tomorrow_count=len(tomorrow_events),
        tomorrow_events=tomorrow_resp,
        ai_summary=ai_summary,
    )


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single calendar event by ID."""
    _require_yellow_tier(user)

    event = db.query(EUCalendarEvent).filter(EUCalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    from services.linking.emeeting_links import attach_calendar_agendas
    resp = CalendarEventResponse.model_validate(event)
    attach_calendar_agendas(db, [resp])
    return resp


# ============================================================================
# Reference Data
# ============================================================================

@router.get("/institutions", response_model=List[InstitutionInfo])
async def list_institutions():
    """List all institutions with display info. Public endpoint."""
    return get_institutions_for_frontend()


@router.get("/policy-areas", response_model=List[PolicyAreaInfo])
async def list_policy_areas():
    """List all policy areas with committee/config mappings. Public endpoint."""
    return get_policy_areas_for_frontend()


@router.get("/bodies")
async def list_bodies():
    """Institution -> selectable departments (the cascading filter source).

    EP -> committees, Commission -> the 40 DGs (policy/functional), Council ->
    configurations. Institutions that ARE the body return an empty list. Public.
    """
    return get_bodies_for_frontend()


# ============================================================================
# Sync
# ============================================================================

@router.post("/sync", response_model=SyncAllResultResponse)
async def trigger_sync(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger calendar sync from all sources. Blue/Admin only."""
    if not (_is_blue_tier(user) or _is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calendar sync requires Blue tier or admin access.",
        )

    from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService

    service = EUCalendarSyncService(db=db)
    raw_result = service.sync_all()

    results = [
        SyncResultResponse(**r) for r in raw_result["results"]
    ]

    return SyncAllResultResponse(
        results=results,
        total_added=raw_result["total_added"],
        total_updated=raw_result["total_updated"],
        total_errors=raw_result["total_errors"],
    )


@router.post("/sync/committee-agendas", response_model=SyncResultResponse)
async def sync_committee_agendas(
    committees: Optional[str] = Query(
        None,
        description="Comma-separated committee codes (e.g. LIBE,ITRE). Default: all.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sync EP committee draft agendas. Blue/Admin only."""
    if not (_is_blue_tier(user) or _is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Committee agenda sync requires Blue tier or admin access.",
        )

    from services.scrapers.committee_agenda_sync_service import (
        CommitteeAgendaSyncService,
    )

    codes = [c.strip() for c in committees.split(",")] if committees else None
    service = CommitteeAgendaSyncService(db=db)
    result = await service.sync_committee_agendas(committee_codes=codes)

    return SyncResultResponse(**result)


@router.post("/sync/college-agendas", response_model=SyncResultResponse)
async def sync_college_agendas(
    days_back: int = Query(90, description="Days back to scan for published agendas"),
    year: int = Query(2026, description="Year for OJ references"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sync published Commission College agendas (OJ documents). Blue/Admin only."""
    if not (_is_blue_tier(user) or _is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="College agenda sync requires Blue tier or admin access.",
        )

    from services.scrapers.college_oj_sync_service import CollegeOJSyncService

    service = CollegeOJSyncService(db=db)
    result = await service.sync_college_agendas(
        days_back=days_back, year=year
    )

    return SyncResultResponse(**result)


# ============================================================================
# Helpers
# ============================================================================

def _generate_today_summary(events: list) -> Optional[str]:
    """Generate an AI summary of today's events (Blue tier only)."""
    try:
        from services.ai.multi_provider_service import get_multi_provider_service

        service = get_multi_provider_service()
        if not service.available_providers:
            return None

        event_lines = []
        for e in events[:10]:  # Cap at 10 events
            line = f"- {e.institution.value}: {e.title}"
            if e.description:
                line += f" ({e.description[:100]})"
            event_lines.append(line)

        prompt = (
            "Summarise today's EU institutional events in 2 concise sentences "
            "for a policy professional. Focus on what matters most. "
            "Use British English.\n\nEvents:\n" + "\n".join(event_lines)
        )

        response = service.generate_sync(
            prompt=prompt,
            max_tokens=150,
        )
        return response.strip() if response else None

    except Exception as e:
        logger.warning(f"[WARN] AI summary generation failed: {e}")
        return None
