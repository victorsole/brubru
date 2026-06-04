"""
EU Calendar Event Database Models.

SQLAlchemy models for the My EU Calendar feature.

Created: February 2026
"""

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Time, Text,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


# ============================================================================
# Enums
# ============================================================================

class InstitutionEnum(str, enum.Enum):
    """EU institution codes."""
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
    # All-EU bodies for My EU Calendar event ingestion (migration 102, 1 Jun 2026):
    # bodies that are neither Commission DGs nor already enumerated.
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
    # Non-EU-institutional events (think tanks, conference organisers,
    # associations, universities, public bodies). Added 22 April 2026 for
    # euagenda.eu integration. See `euagenda_brussels_events.md` guide.
    THIRD_PARTY = "THIRD_PARTY"


class EventTypeEnum(str, enum.Enum):
    """Calendar event types."""
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
    # Phase 2 reserved
    COMITOLOGY_MEETING = "comitology_meeting"
    EXPERT_GROUP_MEETING = "expert_group_meeting"
    GRANT_DEADLINE = "grant_deadline"
    # Third-party (euagenda.eu) event types, added 22 April 2026
    CONFERENCE = "conference"
    WEBINAR = "webinar"
    ROUNDTABLE = "roundtable"
    TRAINING = "training"
    WORKSHOP = "workshop"


class EventStatusEnum(str, enum.Enum):
    """Calendar event status."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    POSTPONED = "postponed"


class ReminderPeriodEnum(str, enum.Enum):
    """Reminder period before event."""
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


# ============================================================================
# Models
# ============================================================================

class EUCalendarEvent(Base):
    """
    EU Calendar Event.

    Stores events from all EU institutions for the calendar view.
    """
    __tablename__ = "eu_calendar_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Institution and type
    institution = Column(
        SQLEnum(
            InstitutionEnum, name="institution_enum", create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    event_type = Column(
        SQLEnum(
            EventTypeEnum, name="event_type_enum", create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # Content
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Date/time
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    all_day = Column(Boolean, default=True)

    # Institution-specific metadata
    council_configuration = Column(String, nullable=True)
    ep_activity_type = Column(String, nullable=True)
    ep_committee_code = Column(String, nullable=True)
    commission_dg = Column(String, nullable=True)

    # Third-party (euagenda.eu) events: organising body + venue
    organiser = Column(Text, nullable=True)
    venue = Column(Text, nullable=True)

    # Classification
    policy_areas = Column(ARRAY(String), default=[])
    status = Column(
        SQLEnum(
            EventStatusEnum, name="event_status_enum", create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=EventStatusEnum.SCHEDULED,
    )

    # Links
    source_url = Column(String, nullable=True)
    agenda_url = Column(String, nullable=True)

    # Legislative cross-references
    procedure_refs = Column(ARRAY(String), default=[])
    related_documents = Column(JSONB, default={})

    # Source tracking
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=True)

    # Temporal
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    subscriptions = relationship(
        "UserCalendarSubscription",
        back_populates="event",
        cascade="all, delete-orphan",
        foreign_keys="UserCalendarSubscription.event_id",
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_calendar_source_external_id"),
        Index("ix_calendar_start_date", "start_date"),
        Index("ix_calendar_institution", "institution"),
        Index("ix_calendar_event_type", "event_type"),
        Index("ix_calendar_last_updated", "last_updated"),
    )

    def __repr__(self):
        return f"<EUCalendarEvent {self.institution.value}: {self.title[:50]} ({self.start_date})>"


class UserCalendarSubscription(Base):
    """
    User calendar subscription for notifications and reminders.

    Supports both institution-level subscriptions (notify_on_new)
    and per-event reminders (event_id + remind_before).
    """
    __tablename__ = "user_calendar_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Institution-level subscription (nullable = all institutions)
    institution = Column(
        SQLEnum(
            InstitutionEnum, name="institution_enum", create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    council_configuration = Column(String, nullable=True)
    ep_committee_code = Column(String, nullable=True)
    commission_dg = Column(String, nullable=True)
    notify_on_new = Column(Boolean, default=True)

    # Per-event reminder
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("eu_calendar_events.id"),
        nullable=True,
    )
    remind_before = Column(
        SQLEnum(
            ReminderPeriodEnum, name="reminder_period_enum", create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    reminded_at = Column(DateTime, nullable=True)

    # Temporal
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    user = relationship("User")
    event = relationship("EUCalendarEvent", back_populates="subscriptions")

    __table_args__ = (
        Index("ix_cal_sub_user_id", "user_id"),
        Index("ix_cal_sub_event_id", "event_id"),
    )

    def __repr__(self):
        if self.event_id:
            return f"<UserCalendarSubscription user={self.user_id} event={self.event_id}>"
        return f"<UserCalendarSubscription user={self.user_id} institution={self.institution}>"
