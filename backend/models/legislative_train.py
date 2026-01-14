"""
Legislative Train Database Models

SQLAlchemy models for Legislative Train Schedule data.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


class CarriageStatusEnum(str, enum.Enum):
    """Legislative file status categories"""
    ANNOUNCED = "announced"
    LEGISLATIVE_INITIATIVE = "legislative_initiative"
    TABLED = "tabled"
    CLOSE_TO_ADOPTION = "close_to_adoption"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class LegislativeTrain(Base):
    """
    EC Priority 'train' with grouped legislative files.

    Represents one of 7 EC priorities (2024-2029 Commission).
    """
    __tablename__ = "legislative_trains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    priority_number = Column(Integer, nullable=False, unique=True)  # 1-7
    name = Column(String, nullable=False)
    description = Column(Text)
    commission_term = Column(String, default="2024-2029")

    # Statistics (computed from carriages)
    total_files = Column(Integer, default=0)
    files_by_status = Column(JSON, default={})  # {"announced": 15, "tabled": 72, ...}

    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    carriages = relationship("LegislativeCarriage", back_populates="train", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LegislativeTrain {self.priority_number}: {self.name}>"


class LegislativeCarriage(Base):
    """
    Individual legislative file within a train.

    Tracks a specific piece of EU legislation through the legislative process.
    """
    __tablename__ = "legislative_carriages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    train_id = Column(UUID(as_uuid=True), ForeignKey("legislative_trains.id"), nullable=True)

    # External IDs
    file_id = Column(String, unique=True, nullable=False)  # Legislative Train internal ID

    # Basic info
    title = Column(String, nullable=False)
    description = Column(Text)

    # Status tracking
    current_status = Column(SQLEnum(CarriageStatusEnum), nullable=False)
    status_history = Column(JSON, default=[])  # [{status, changed_at, duration_days}, ...]
    days_in_current_status = Column(Integer)
    is_blocked = Column(Boolean, default=False)  # True if 9+ months no progress

    # Cross-references
    oeil_procedure_ref = Column(String)  # "2021/0106(COD)"
    celex_numbers = Column(ARRAY(String), default=[])
    eprs_briefing_ids = Column(ARRAY(String), default=[])

    # Stakeholders
    lead_committee = Column(String)  # "LIBE"
    opinion_committees = Column(ARRAY(String), default=[])
    committees = Column(ARRAY(String), default=[])
    rapporteur_mep_id = Column(String)

    # Enrichment data
    oeil_procedure_data = Column(JSON)
    oeil_timeline = Column(JSON, default=[])
    oeil_key_events = Column(JSON, default=[])
    eurlex_documents = Column(JSON, default=[])
    legal_text_url = Column(String)
    eprs_matched_briefings = Column(JSON, default=[])
    eprs_match_confidence = Column(Integer)  # Store as percentage (0-100)
    policy_areas = Column(ARRAY(String), default=[])

    # AI-generated enrichment (Hugging Face)
    ai_summary = Column(Text)  # British English summary
    ai_entities = Column(JSON, default=[])  # Extracted MEPs, committees, legislation
    ai_policy_classifications = Column(JSON, default=[])  # {"label": "...", "score": 0.9}

    # Temporal data
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    expected_completion = Column(DateTime)
    enriched_at = Column(DateTime)
    enrichment_quality = Column(String)  # "high", "medium", "low"

    # Relationships
    train = relationship("LegislativeTrain", back_populates="carriages")
    user_tracks = relationship("UserCarriageTrack", back_populates="carriage", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LegislativeCarriage {self.file_id}: {self.title}>"


class CarriageStatusHistory(Base):
    """
    Historical status changes for trend analysis.

    Separate table for efficient querying of status transitions.
    """
    __tablename__ = "carriage_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carriage_id = Column(UUID(as_uuid=True), ForeignKey("legislative_carriages.id"), nullable=False)

    status = Column(SQLEnum(CarriageStatusEnum), nullable=False)
    changed_at = Column(DateTime, default=datetime.now, nullable=False)
    duration_days = Column(Integer)  # Days in previous status

    # Additional context
    notes = Column(Text)  # Manual notes about status change

    def __repr__(self):
        return f"<StatusHistory {self.carriage_id}: {self.status} @ {self.changed_at}>"


class UserCarriageTrack(Base):
    """
    User subscription to legislative file for status updates.

    Allows users to "watch" specific legislation.
    """
    __tablename__ = "user_carriage_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    carriage_id = Column(UUID(as_uuid=True), ForeignKey("legislative_carriages.id"), nullable=False)

    # Notification preferences
    notify_on_status_change = Column(Boolean, default=True)
    notify_on_blocking = Column(Boolean, default=True)
    notify_on_new_documents = Column(Boolean, default=True)

    # Tracking metadata
    tracked_since = Column(DateTime, default=datetime.now, nullable=False)
    last_notified_at = Column(DateTime)

    # Relationships
    user = relationship("User")
    carriage = relationship("LegislativeCarriage", back_populates="user_tracks")

    def __repr__(self):
        return f"<UserCarriageTrack user={self.user_id} carriage={self.carriage_id}>"
