"""
EU Calendar Pydantic Schemas.

Request/response models for the My EU Calendar API.

Created: February 2026
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date, time
from uuid import UUID
from enum import Enum


# ============================================================================
# Enums (mirror SQLAlchemy enums for API validation)
# ============================================================================

class InstitutionType(str, Enum):
    EP = "EP"
    COUNCIL = "COUNCIL"
    EUROPEAN_COUNCIL = "EUROPEAN_COUNCIL"
    COMMISSION = "COMMISSION"
    ECJ = "ECJ"
    ECB = "ECB"
    ESMA = "ESMA"
    EMA = "EMA"
    EBA = "EBA"
    EIOPA = "EIOPA"
    COR = "COR"
    EESC = "EESC"
    # All-EU bodies (migration 102, 1 Jun 2026) — MUST mirror the model
    # InstitutionEnum or every response containing one of these rows 500s.
    EDPS = "EDPS"
    OMBUDSMAN = "OMBUDSMAN"
    EIB = "EIB"
    ECA = "ECA"
    ECHA = "ECHA"
    ENISA = "ENISA"
    EUIPO = "EUIPO"
    EUAA = "EUAA"
    EUROJUST = "EUROJUST"
    FRA = "FRA"
    EU_OSHA = "EU_OSHA"
    EUROFOUND = "EUROFOUND"
    ACER = "ACER"
    ECDC = "ECDC"
    AMLA = "AMLA"
    CEPOL = "CEPOL"
    EIT = "EIT"
    CPVO = "CPVO"
    EMSA = "EMSA"
    EEAS = "EEAS"
    # EU Funding & Tenders Portal events (migration 141, 15 June 2026). Mirror
    # the model enum — a missing value 500s the whole calendar response.
    FUNDING = "FUNDING"
    # Added 22 April 2026 to mirror the model enum after euagenda.eu
    # integration (think tanks, conferences, webinars). Missing this value
    # made every response containing a THIRD_PARTY row fail Pydantic
    # validation and 500 the whole calendar response — fixed 13 May 2026.
    THIRD_PARTY = "THIRD_PARTY"


class EventType(str, Enum):
    PLENARY_SESSION = "plenary_session"
    COMMITTEE_WEEK = "committee_week"
    COMMITTEE_MEETING = "committee_meeting"
    GROUP_WEEK = "group_week"
    RECESS = "recess"
    COUNCIL_MEETING = "council_meeting"
    INFORMAL_MEETING = "informal_meeting"
    EUROPEAN_COUNCIL_SUMMIT = "european_council_summit"
    EUROGROUP = "eurogroup"
    COMMISSION_COLLEGE_MEETING = "commission_college_meeting"
    COMMISSIONER_MEETING = "commissioner_meeting"
    COURT_HEARING = "court_hearing"
    ECB_GOVERNING_COUNCIL = "ecb_governing_council"
    AGENCY_EVENT = "agency_event"
    SPECIAL_DATE = "special_date"
    COMITOLOGY_MEETING = "comitology_meeting"
    EXPERT_GROUP_MEETING = "expert_group_meeting"
    GRANT_DEADLINE = "grant_deadline"
    # Third-party (euagenda.eu) event types — same root cause as
    # THIRD_PARTY institution above. Mirror the model enum.
    CONFERENCE = "conference"
    WEBINAR = "webinar"
    ROUNDTABLE = "roundtable"
    TRAINING = "training"
    WORKSHOP = "workshop"


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    POSTPONED = "postponed"


# ============================================================================
# Response Models
# ============================================================================

class CalendarEventResponse(BaseModel):
    """Full calendar event for API responses."""
    id: UUID
    institution: InstitutionType
    event_type: EventType
    title: str
    description: Optional[str] = None

    start_date: date
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    all_day: bool = True

    council_configuration: Optional[str] = None
    ep_activity_type: Optional[str] = None
    ep_committee_code: Optional[str] = None
    commission_dg: Optional[str] = None

    policy_areas: Optional[List[str]] = []
    status: EventStatus = EventStatus.SCHEDULED

    source_url: Optional[str] = None
    agenda_url: Optional[str] = None

    procedure_refs: Optional[List[str]] = []
    related_documents: Optional[Dict[str, Any]] = {}

    source: str
    external_id: Optional[str] = None
    last_updated: Optional[datetime] = None

    # eMeeting enrichment: the committee meeting's agenda document(s), matched by
    # committee + date (surface-not-ingest). Each entry:
    # {item_title, meeting_date, pdf_url, source_url}.
    emeeting_agendas: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CalendarEventListResponse(BaseModel):
    """Paginated list of calendar events."""
    total: int
    events: List[CalendarEventResponse]


class CalendarRangeResponse(BaseModel):
    """All events in a date range (no pagination, for calendar views)."""
    date_from: date
    date_to: date
    total: int
    events: List[CalendarEventResponse]


class TodayDigestResponse(BaseModel):
    """Today's events digest for 'My EU Today' panel."""
    today_count: int
    today_events: List[CalendarEventResponse]
    tomorrow_count: int
    tomorrow_events: List[CalendarEventResponse]
    ai_summary: Optional[str] = None


# ============================================================================
# Reference Data
# ============================================================================

class InstitutionInfo(BaseModel):
    """Institution info for frontend display."""
    code: str
    name: str
    short_name: str
    mdi_icon: str
    colour: str
    calendar_url: Optional[str] = None


class PolicyAreaInfo(BaseModel):
    """Policy area info for frontend display."""
    code: str
    label: str
    colour: str
    ep_committee_codes: List[str] = []
    council_configs: List[str] = []


# ============================================================================
# Sync
# ============================================================================

class SyncResultResponse(BaseModel):
    """Result of a calendar sync operation."""
    source: str
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0


class SyncAllResultResponse(BaseModel):
    """Result of syncing all sources."""
    results: List[SyncResultResponse]
    total_added: int = 0
    total_updated: int = 0
    total_errors: int = 0
