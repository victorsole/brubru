"""
Legislative Train Database Models

SQLAlchemy models for Legislative Train Schedule data.

ENHANCED (January 2025):
- LegislativePackage model for package hierarchy
- Timeline support in LegislativeCarriage
- Text type and spotlight tags
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    ADOPTED = "adopted"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class TextTypeEnum(str, enum.Enum):
    """Legislative text type"""
    LEGISLATIVE = "legislative"
    NON_LEGISLATIVE = "non_legislative"
    UNKNOWN = "unknown"


class CarriageSourceEnum(str, enum.Enum):
    """Source of the legislative carriage data"""
    LEGISLATIVE_TRAIN = "legislative_train"  # From EC Legislative Train Schedule
    OEIL_DIRECT = "oeil_direct"  # Directly from OEIL/EP (not in Legislative Train)
    EP_OPENDATA = "ep_opendata"  # From EP Open Data API
    EURLEX = "eurlex"  # From EUR-Lex RSS feeds


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
    theme_slug = Column(String)  # URL slug for this priority

    # Statistics (computed from carriages)
    total_files = Column(Integer, default=0)
    files_by_status = Column(JSON, default={})  # {"announced": 15, "tabled": 72, ...}

    # Metadata
    url = Column(String)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    carriages = relationship("LegislativeCarriage", back_populates="train", cascade="all, delete-orphan")
    packages = relationship("LegislativePackage", back_populates="train", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LegislativeTrain {self.priority_number}: {self.name}>"


class LegislativePackage(Base):
    """
    Package within the Legislative Train (NEW in 2025).

    Packages are thematic groupings that can have sub-packages.
    Example: "Vision for Agriculture and Food" contains sub-packages
    like "Sustainable food systems" and "Animal welfare".
    """
    __tablename__ = "legislative_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    train_id = Column(UUID(as_uuid=True), ForeignKey("legislative_trains.id"), nullable=True)

    # Identifiers
    slug = Column(String, unique=True, nullable=False)  # e.g., "package-vision-for-agriculture"
    name = Column(String, nullable=False)
    description = Column(Text)

    # Hierarchy
    parent_id = Column(UUID(as_uuid=True), ForeignKey("legislative_packages.id"), nullable=True)
    parent_slug = Column(String)
    is_sub_package = Column(Boolean, default=False)

    # Status counts
    status_announced = Column(Integer, default=0)
    status_tabled = Column(Integer, default=0)
    status_blocked = Column(Integer, default=0)
    status_close_to_adoption = Column(Integer, default=0)
    status_adopted = Column(Integer, default=0)
    status_withdrawn = Column(Integer, default=0)
    total_files = Column(Integer, default=0)

    # Filter metadata
    ec_priorities = Column(ARRAY(String), default=[])
    ep_committees = Column(ARRAY(String), default=[])

    # URLs
    url = Column(String)

    # Metadata
    scraped_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    train = relationship("LegislativeTrain", back_populates="packages")
    parent = relationship("LegislativePackage", remote_side=[id], backref="sub_packages")
    carriages = relationship("LegislativeCarriage", back_populates="package", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LegislativePackage {self.slug}: {self.name}>"

    @property
    def status_counts(self):
        """Return status counts as a dictionary"""
        return {
            "announced": self.status_announced,
            "tabled": self.status_tabled,
            "blocked": self.status_blocked,
            "close_to_adoption": self.status_close_to_adoption,
            "adopted": self.status_adopted,
            "withdrawn": self.status_withdrawn,
            "total": self.total_files
        }


class LegislativeCarriage(Base):
    """
    Individual legislative file within a train.

    Tracks a specific piece of EU legislation through the legislative process.
    """
    __tablename__ = "legislative_carriages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    train_id = Column(UUID(as_uuid=True), ForeignKey("legislative_trains.id"), nullable=True)
    package_id = Column(UUID(as_uuid=True), ForeignKey("legislative_packages.id"), nullable=True)

    # External IDs
    file_id = Column(String, unique=True, nullable=False)  # Legislative Train internal ID/slug
    package_slug = Column(String)  # Parent package slug for easy reference

    # Data source tracking
    source = Column(SQLEnum(CarriageSourceEnum), default=CarriageSourceEnum.LEGISLATIVE_TRAIN)

    # Basic info
    title = Column(String, nullable=False)
    # Human-readable short name for headings and list rows (migration 204).
    # A curated alias, or a subject line synthesised from `title` and checked
    # against it. NULL means callers fall back to the instrument designation
    # parsed by services/legislative/title_display.py. Written by
    # scripts/backfill_carriage_short_titles.py.
    short_title = Column(Text)
    description = Column(Text)

    # Status tracking
    current_status = Column(SQLEnum(CarriageStatusEnum), nullable=False)
    status_history = Column(JSON, default=[])  # [{status, changed_at, duration_days}, ...]
    days_in_current_status = Column(Integer)
    is_blocked = Column(Boolean, default=False)  # True if 9+ months no progress

    # NEW: Timeline (monthly status snapshots)
    timeline = Column(JSON, default=[])  # [{year, month, status, is_current}, ...]

    # NEW: Text type and spotlight
    text_type = Column(SQLEnum(TextTypeEnum), default=TextTypeEnum.UNKNOWN)
    spotlight_tags = Column(ARRAY(String), default=[])
    is_recently_updated = Column(Boolean, default=False)

    # Cross-references
    oeil_procedure_ref = Column(String)  # "2021/0106(COD)"
    celex_numbers = Column(ARRAY(String), default=[])
    eprs_briefing_ids = Column(ARRAY(String), default=[])

    # Stakeholders
    lead_committee = Column(String)  # "LIBE"
    opinion_committees = Column(ARRAY(String), default=[])
    committees = Column(ARRAY(String), default=[])
    rapporteur_mep_id = Column(String)

    # NEW: Filter metadata
    ec_priority_ids = Column(ARRAY(String), default=[])
    related_themes = Column(ARRAY(String), default=[])

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

    # OEIL page body cache — populated by backend/scripts/backfill_oeil_body.py
    # Read by /api/v1/committees/{code}/work-items to serve body_txt/body_html.
    oeil_html_body = Column(Text)
    oeil_text_body = Column(Text)
    oeil_body_fetched_at = Column(DateTime)
    ai_entities = Column(JSON, default=[])  # Extracted MEPs, committees, legislation
    ai_policy_classifications = Column(JSON, default=[])  # {"label": "...", "score": 0.9}

    # URLs
    url = Column(String)

    # Temporal data
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    expected_completion = Column(DateTime)
    enriched_at = Column(DateTime)
    enrichment_quality = Column(String)  # "high", "medium", "low"

    # EP Legislative Train editorial narrative (migration 097). The "state of
    # play" prose OEIL lacks; joined by OEIL ref. See legislative_train_narrative.py.
    legislative_train_summary = Column(Text)
    legislative_train_url = Column(Text)
    legislative_train_updated_at = Column(DateTime(timezone=True))

    # Phase 5 of docs/applications/euvoc.md — IMMC-equivalent inter-institutional
    # handoff events projected from cdm:event_legal_*. See migration 049_immc_tags.sql
    # and services/api_clients/immc_client.py for the JSONB shape.
    immc_tags = Column(JSON, default=dict)

    # Relationships
    train = relationship("LegislativeTrain", back_populates="carriages")
    package = relationship("LegislativePackage", back_populates="carriages")
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

    # Position Analysis: user's stance on this tracked file
    # Shape: {stance, notes, evidence_urls[], priority_articles[], last_updated}
    user_position = Column(JSONB, nullable=True)

    # Archive (migration 041): NULL = active, non-null = archived.
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_reason = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    carriage = relationship("LegislativeCarriage", back_populates="user_tracks")

    def __repr__(self):
        return f"<UserCarriageTrack user={self.user_id} carriage={self.carriage_id}>"
