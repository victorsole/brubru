"""
EP Committee Work In Progress Database Models.

SQLAlchemy models for EP Committee 'Work in Progress' data.

Created: January 2026
"""

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, Text,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


class ProcedureTypeEnum(str, enum.Enum):
    """OEIL procedure types. Reference set only.

    The committee_work_items.procedure_type column is a free varchar (migration
    093) because OEIL's vocabulary is open-ended; a native enum used to collapse
    every type outside the first five to INI. Kept here for the relevance map
    and for callers that want the canonical codes.
    """
    COD = "COD"
    CNS = "CNS"
    APP = "APP"
    NLE = "NLE"
    INI = "INI"
    INL = "INL"
    RSP = "RSP"
    RSO = "RSO"
    REG = "REG"
    RPS = "RPS"
    DEA = "DEA"
    IMM = "IMM"
    BUD = "BUD"
    BUI = "BUI"
    DEC = "DEC"
    GBD = "GBD"
    ACI = "ACI"
    COS = "COS"
    DCE = "DCE"


class CommitteeRoleEnum(str, enum.Enum):
    """Committee's role in the procedure."""
    LEAD = "lead"
    ASSOCIATED = "associated"
    OPINION = "opinion"


class CommitteeWorkStatusEnum(str, enum.Enum):
    """Status of the work item."""
    IN_COMMITTEE = "in_committee"
    AWAITING_VOTE = "awaiting_vote"
    TABLED = "tabled"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class CommitteeWorkItem(Base):
    """
    Individual work item from EP Committee 'Work in Progress' pages.

    Aligned with LegislativeCarriage model patterns.
    """
    __tablename__ = "committee_work_items"

    # Primary key - UUID pattern (consistent with legislative_train.py)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identifiers
    procedure_ref = Column(String, nullable=False)  # OEIL ref: "2025/0580(CNS)"
    committee_code = Column(String(10), nullable=False)  # e.g., "AFET", "LIBE"

    # Content
    title = Column(String, nullable=False)
    description = Column(Text)
    full_description = Column(Text)

    # Procedure metadata
    # Free varchar (migration 093): OEIL has 20+ procedure types and adds more;
    # a native enum silently collapsed everything outside COD/APP/CNS/NLE/INI.
    procedure_type = Column(String(10), default="INI", nullable=False)
    committee_role = Column(
        SQLEnum(CommitteeRoleEnum),
        default=CommitteeRoleEnum.LEAD,
        nullable=False
    )

    # Calculated relevance score
    relevance_score = Column(Integer, default=40)  # 40-100 based on procedure_type

    # Rapporteur
    rapporteur_name = Column(String)
    rapporteur_mep_id = Column(String)
    shadow_rapporteurs = Column(JSON, default=[])  # [{name, group, mep_id}]

    # Status
    status = Column(
        SQLEnum(CommitteeWorkStatusEnum),
        default=CommitteeWorkStatusEnum.UNKNOWN
    )
    status_text = Column(String)  # Original status text from scraping
    stage = Column(String)  # Committee stage

    # Timeline events
    timeline_events = Column(JSON, default=[])  # [{date, event, status}]
    vote_date = Column(DateTime)
    vote_result = Column(String)

    # Related documents
    related_documents = Column(JSON, default=[])  # [{title, url, type}]
    celex_numbers = Column(ARRAY(String), default=[])

    # Cross-references to legislative_carriages
    legislative_carriage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("legislative_carriages.id"),
        nullable=True
    )

    # URLs
    oeil_url = Column(String)
    eurlex_url = Column(String)
    ep_page_url = Column(String)
    source_url = Column(String)  # URL where this was scraped from

    # Temporal data
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    legislative_carriage = relationship(
        "LegislativeCarriage",
        foreign_keys=[legislative_carriage_id]
    )
    user_tracks = relationship(
        "UserCommitteeWorkTrack",
        back_populates="work_item",
        cascade="all, delete-orphan"
    )

    # Unique constraint on (procedure_ref, committee_code)
    __table_args__ = (
        UniqueConstraint(
            'procedure_ref', 'committee_code',
            name='uq_committee_work_procedure_committee'
        ),
        Index('ix_committee_work_procedure_ref', 'procedure_ref'),
        Index('ix_committee_work_committee_code', 'committee_code'),
        Index('ix_committee_work_procedure_type', 'procedure_type'),
        Index('ix_committee_work_status', 'status'),
        Index('ix_committee_work_last_updated', 'last_updated'),
    )

    def __repr__(self):
        return f"<CommitteeWorkItem {self.procedure_ref} ({self.committee_code}): {self.title[:50]}>"

    @classmethod
    def calculate_relevance_score(cls, procedure_type: ProcedureTypeEnum) -> int:
        """Calculate relevance score based on procedure type."""
        scores = {
            ProcedureTypeEnum.COD: 100,
            ProcedureTypeEnum.APP: 80,
            ProcedureTypeEnum.CNS: 70,
            ProcedureTypeEnum.NLE: 50,
            ProcedureTypeEnum.INI: 40,
        }
        return scores.get(procedure_type, 40)


class UserCommitteeWorkTrack(Base):
    """
    User subscription to committee work item for status updates.

    Allows users to "watch" specific committee work items.
    Pattern from UserCarriageTrack.
    """
    __tablename__ = "user_committee_work_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committee_work_items.id"),
        nullable=False
    )

    # Notification preferences
    notify_on_status_change = Column(Boolean, default=True)
    notify_on_rapporteur_change = Column(Boolean, default=True)
    notify_on_new_documents = Column(Boolean, default=True)

    # Tracking metadata
    tracked_since = Column(DateTime, default=datetime.now, nullable=False)
    last_notified_at = Column(DateTime)

    # User notes
    notes = Column(Text)

    # Archive (migration 041): NULL = active, non-null = archived.
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_reason = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    work_item = relationship("CommitteeWorkItem", back_populates="user_tracks")

    # Unique constraint: user can only track each work item once
    __table_args__ = (
        UniqueConstraint(
            'user_id', 'work_item_id',
            name='uq_user_committee_work_track'
        ),
        Index('ix_user_committee_work_track_user_id', 'user_id'),
        Index('ix_user_committee_work_track_work_item_id', 'work_item_id'),
    )

    def __repr__(self):
        return f"<UserCommitteeWorkTrack user={self.user_id} work_item={self.work_item_id}>"


class CommitteeWorkStatusHistory(Base):
    """
    Historical status changes for committee work items.

    Separate table for efficient querying of status transitions.
    """
    __tablename__ = "committee_work_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committee_work_items.id"),
        nullable=False
    )

    old_status = Column(SQLEnum(CommitteeWorkStatusEnum))
    new_status = Column(SQLEnum(CommitteeWorkStatusEnum), nullable=False)
    changed_at = Column(DateTime, default=datetime.now, nullable=False)

    # Additional context
    notes = Column(Text)
    detected_during_sync = Column(Boolean, default=True)

    # Relationships
    work_item = relationship("CommitteeWorkItem")

    __table_args__ = (
        Index('ix_committee_work_status_history_work_item', 'work_item_id'),
        Index('ix_committee_work_status_history_changed_at', 'changed_at'),
    )

    def __repr__(self):
        return f"<CommitteeWorkStatusHistory {self.work_item_id}: {self.old_status} -> {self.new_status}>"
