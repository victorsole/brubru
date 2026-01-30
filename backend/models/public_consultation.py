"""
EC Public Consultation Database Models.

SQLAlchemy models for EC "Have Your Say" public consultations data.

Created: January 2026
"""

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Text,
    ForeignKey, Index, UniqueConstraint, Float
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

class ConsultationTypeEnum(str, enum.Enum):
    """Types of EC public consultations."""
    PUBLIC_CONSULTATION = "public_consultation"
    CALL_FOR_EVIDENCE = "call_for_evidence"
    FEEDBACK = "feedback"
    ROADMAP = "roadmap"
    INITIATIVE = "initiative"


class ConsultationStatusEnum(str, enum.Enum):
    """Status of a consultation."""
    OPEN = "open"
    UPCOMING = "upcoming"
    CLOSED = "closed"
    OUTCOME_PUBLISHED = "outcome_published"
    WITHDRAWN = "withdrawn"


class DocumentTypeEnum(str, enum.Enum):
    """Types of consultation documents."""
    QUESTIONNAIRE = "questionnaire"
    IMPACT_ASSESSMENT = "impact_assessment"
    DRAFT_ACT = "draft_act"
    EXPLANATORY_MEMO = "explanatory_memo"
    ANNEX = "annex"
    FACTSHEET = "factsheet"
    SUMMARY = "summary"
    INCEPTION_IMPACT_ASSESSMENT = "inception_impact_assessment"
    ROADMAP = "roadmap"
    OUTCOME_REPORT = "outcome_report"
    STATISTICS = "statistics"
    OTHER = "other"


class SubmissionStatusEnum(str, enum.Enum):
    """User's submission status for a consultation."""
    NOT_STARTED = "not_started"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    NOT_PARTICIPATING = "not_participating"


# ============================================================================
# Main Consultation Model
# ============================================================================

class PublicConsultation(Base):
    """
    EC Public Consultation from Have Your Say portal.

    Aligned with LegislativeCarriage and CommitteeWorkItem patterns.
    """
    __tablename__ = "public_consultations"

    # Primary key - UUID pattern
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # EC Identifiers
    initiative_id = Column(String(50), unique=True, nullable=False, index=True)
    publication_id = Column(String(50), nullable=True)

    # Content
    title = Column(Text, nullable=False)
    short_title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    full_description = Column(Text, nullable=True)
    objectives = Column(Text, nullable=True)
    target_group = Column(Text, nullable=True)

    # Type and Status
    # Note: Using native enum with values_callable to match PostgreSQL enum values
    consultation_type = Column(
        SQLEnum(
            ConsultationTypeEnum,
            name='consultation_type_enum',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=ConsultationTypeEnum.INITIATIVE,
        nullable=False
    )
    status = Column(
        SQLEnum(
            ConsultationStatusEnum,
            name='consultation_status_enum',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=ConsultationStatusEnum.OPEN,
        nullable=False,
        index=True
    )

    # Responsible Entities
    dg_responsible = Column(String(20), nullable=True, index=True)
    policy_areas = Column(ARRAY(String), default=[], nullable=False)

    # Timeline
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True, index=True)

    # Statistics
    feedback_count = Column(Integer, default=0)
    views_count = Column(Integer, nullable=True)
    feedback_by_country = Column(JSONB, nullable=True)
    feedback_by_category = Column(JSONB, nullable=True)

    # URLs
    portal_url = Column(Text, nullable=True)
    feedback_url = Column(Text, nullable=True)

    # Related Legislation
    com_references = Column(ARRAY(String), default=[])
    celex_numbers = Column(ARRAY(String), default=[])

    # Outcome (populated after deadline)
    outcome_summary = Column(Text, nullable=True)
    outcome_published_date = Column(Date, nullable=True)
    outcome_document_url = Column(Text, nullable=True)

    # Relevance scoring
    relevance_score = Column(Integer, default=50)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    scraped_at = Column(DateTime, nullable=True)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    documents = relationship(
        "ConsultationDocument",
        back_populates="consultation",
        cascade="all, delete-orphan"
    )
    user_tracks = relationship(
        "UserConsultationTrack",
        back_populates="consultation",
        cascade="all, delete-orphan"
    )
    user_inputs = relationship(
        "UserConsultationInput",
        back_populates="consultation",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index('ix_consultation_initiative_id', 'initiative_id'),
        Index('ix_consultation_status', 'status'),
        Index('ix_consultation_end_date', 'end_date'),
        Index('ix_consultation_dg', 'dg_responsible'),
        Index('ix_consultation_policy_areas', 'policy_areas', postgresql_using='gin'),
        Index('ix_consultation_last_updated', 'last_updated'),
    )

    def __repr__(self):
        return f"<PublicConsultation {self.initiative_id}: {self.title[:50]}>"

    @property
    def days_remaining(self) -> int:
        """Calculate days until deadline."""
        if not self.end_date:
            return 999
        from datetime import date
        delta = self.end_date - date.today()
        return max(0, delta.days)

    @property
    def is_closing_soon(self) -> bool:
        """Check if consultation is closing within 7 days."""
        return 0 < self.days_remaining <= 7


# ============================================================================
# Consultation Documents
# ============================================================================

class ConsultationDocument(Base):
    """
    Documents attached to a consultation.

    Includes questionnaires, impact assessments, draft acts, etc.
    """
    __tablename__ = "consultation_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_consultations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Document info
    title = Column(String(500), nullable=False)
    document_type = Column(
        SQLEnum(
            DocumentTypeEnum,
            name='consultation_document_type_enum',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=DocumentTypeEnum.OTHER,
        nullable=False
    )

    # File info
    file_url = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)  # Local storage path
    file_size = Column(Integer, nullable=True)
    file_format = Column(String(20), nullable=True)
    language = Column(String(5), default="en")

    # Extracted content (for AI analysis)
    extracted_text = Column(Text, nullable=True)
    extraction_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    consultation = relationship("PublicConsultation", back_populates="documents")

    __table_args__ = (
        Index('ix_consultation_document_consultation', 'consultation_id'),
        Index('ix_consultation_document_type', 'document_type'),
    )

    def __repr__(self):
        return f"<ConsultationDocument {self.document_type.value}: {self.title[:50]}>"


# ============================================================================
# User Tracking
# ============================================================================

class UserConsultationTrack(Base):
    """
    User subscription to a consultation for updates.

    Allows users to "watch" specific consultations.
    Pattern from UserCarriageTrack and UserCommitteeWorkTrack.
    """
    __tablename__ = "user_consultation_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    consultation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_consultations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Notification preferences
    notify_on_deadline = Column(Boolean, default=True)
    notify_on_outcome = Column(Boolean, default=True)
    notify_days_before = Column(Integer, default=7)  # Days before deadline to notify

    # User's participation status
    submission_status = Column(
        SQLEnum(
            SubmissionStatusEnum,
            name='submission_status_enum',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=SubmissionStatusEnum.NOT_STARTED
    )

    # User notes
    notes = Column(Text, nullable=True)
    priority = Column(Integer, default=0)  # User-defined priority (0=normal, 1=high, 2=critical)

    # Timestamps
    tracked_since = Column(DateTime, default=datetime.now, nullable=False)
    last_notified_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")
    consultation = relationship("PublicConsultation", back_populates="user_tracks")

    # Unique constraint: user can only track each consultation once
    __table_args__ = (
        UniqueConstraint(
            'user_id', 'consultation_id',
            name='uq_user_consultation_track'
        ),
        Index('ix_user_consultation_track_user', 'user_id'),
        Index('ix_user_consultation_track_consultation', 'consultation_id'),
    )

    def __repr__(self):
        return f"<UserConsultationTrack user={self.user_id} consultation={self.consultation_id}>"


# ============================================================================
# User Inputs / AI Proposals
# ============================================================================

class UserConsultationInput(Base):
    """
    User's input/response for a consultation.

    Stores AI-generated proposals and user's draft responses.
    Blue tier feature.
    """
    __tablename__ = "user_consultation_inputs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    consultation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_consultations.id", ondelete="CASCADE"),
        nullable=False
    )

    # AI Analysis (cached)
    ai_analysis = Column(Text, nullable=True)
    ai_analysis_date = Column(DateTime, nullable=True)
    ai_key_questions = Column(JSONB, nullable=True)  # Extracted questions from consultation

    # AI Proposals (Blue tier)
    ai_proposals = Column(JSONB, nullable=True)  # Structured proposals
    ai_proposals_date = Column(DateTime, nullable=True)
    ai_model_used = Column(String(50), nullable=True)
    ai_tokens_used = Column(Integer, nullable=True)

    # User's Draft Response
    draft_response = Column(Text, nullable=True)
    draft_last_modified = Column(DateTime, nullable=True)

    # Source Documents Used
    source_document_ids = Column(ARRAY(UUID(as_uuid=True)), default=[])

    # Outcome Alignment (after consultation closes)
    alignment_score = Column(Float, nullable=True)  # 0-100
    alignment_analysis = Column(Text, nullable=True)
    alignment_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    user = relationship("User")
    consultation = relationship("PublicConsultation", back_populates="user_inputs")

    # Unique constraint: one input per user per consultation
    __table_args__ = (
        UniqueConstraint(
            'user_id', 'consultation_id',
            name='uq_user_consultation_input'
        ),
        Index('ix_user_consultation_input_user', 'user_id'),
        Index('ix_user_consultation_input_consultation', 'consultation_id'),
    )

    def __repr__(self):
        return f"<UserConsultationInput user={self.user_id} consultation={self.consultation_id}>"


# ============================================================================
# Status History (Optional - for tracking status changes)
# ============================================================================

class ConsultationStatusHistory(Base):
    """
    Historical status changes for consultations.

    Tracks when consultations move between statuses.
    """
    __tablename__ = "consultation_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_consultations.id", ondelete="CASCADE"),
        nullable=False
    )

    old_status = Column(
        SQLEnum(
            ConsultationStatusEnum,
            name='consultation_status_enum',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=True
    )
    new_status = Column(
        SQLEnum(
            ConsultationStatusEnum,
            name='consultation_status_enum',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False
    )
    changed_at = Column(DateTime, default=datetime.now, nullable=False)

    # Additional context
    notes = Column(Text, nullable=True)
    detected_during_sync = Column(Boolean, default=True)

    # Relationships
    consultation = relationship("PublicConsultation")

    __table_args__ = (
        Index('ix_consultation_status_history_consultation', 'consultation_id'),
        Index('ix_consultation_status_history_changed_at', 'changed_at'),
    )

    def __repr__(self):
        return f"<ConsultationStatusHistory {self.consultation_id}: {self.old_status} -> {self.new_status}>"
