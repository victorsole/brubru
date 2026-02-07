"""
EP Texts Adopted Database Models.

SQLAlchemy models for EP adopted texts (resolutions, legislative acts, decisions).

Created: February 2026
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


class TextTypeEnum(str, enum.Enum):
    """Types of adopted texts."""
    RESOLUTION = "resolution"
    LEGISLATIVE_RESOLUTION = "legislative_resolution"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


class TextAdopted(Base):
    """
    An adopted text from the European Parliament plenary.

    Stores resolutions, legislative resolutions, decisions, and
    recommendations adopted in plenary sessions.
    """
    __tablename__ = "texts_adopted"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identifiers
    ta_reference = Column(String, nullable=False, unique=True)  # e.g. "P10_TA(2025)0042"
    title = Column(String, nullable=False)
    description = Column(Text)

    # Classification
    text_type = Column(
        SQLEnum(
            'resolution', 'legislative_resolution', 'decision',
            'recommendation', 'other',
            name='adopted_text_type',
            create_type=False
        ),
        default='other',
        nullable=False
    )
    procedure_ref = Column(String)  # OEIL ref e.g. "2024/0176(COD)"
    parliamentary_term = Column(Integer, default=10, nullable=False)

    # Content (optional - from detail page)
    full_text = Column(Text)

    # Temporal
    adoption_date = Column(DateTime, nullable=False)

    # Metadata (from detail page enrichment)
    committees = Column(ARRAY(String), default=[])
    rapporteur_name = Column(String)
    rapporteur_mep_id = Column(String)
    celex_number = Column(String)
    vote_results = Column(JSON)  # {for, against, abstentions}
    related_documents = Column(JSON, default=[])  # [{title, url, type}]

    # URLs
    source_url = Column(String)
    full_text_url = Column(String)
    pdf_url = Column(String)

    # Cross-references
    legislative_carriage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("legislative_carriages.id"),
        nullable=True
    )

    # Temporal tracking
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    legislative_carriage = relationship(
        "LegislativeCarriage",
        foreign_keys=[legislative_carriage_id]
    )
    user_tracks = relationship(
        "UserTextAdoptedTrack",
        back_populates="text_adopted",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index('ix_texts_adopted_ta_reference', 'ta_reference'),
        Index('ix_texts_adopted_adoption_date', 'adoption_date'),
        Index('ix_texts_adopted_procedure_ref', 'procedure_ref'),
        Index('ix_texts_adopted_parliamentary_term', 'parliamentary_term'),
        Index('ix_texts_adopted_text_type', 'text_type'),
    )

    def __repr__(self):
        return f"<TextAdopted {self.ta_reference}: {self.title[:50]}>"


class UserTextAdoptedTrack(Base):
    """
    User subscription to an adopted text.

    Allows users to "watch" specific adopted texts.
    Pattern from UserCommitteeWorkTrack.
    """
    __tablename__ = "user_text_adopted_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    text_adopted_id = Column(
        UUID(as_uuid=True),
        ForeignKey("texts_adopted.id"),
        nullable=False
    )

    # Tracking metadata
    tracked_since = Column(DateTime, default=datetime.now, nullable=False)
    notes = Column(Text)

    # Relationships
    user = relationship("User")
    text_adopted = relationship("TextAdopted", back_populates="user_tracks")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint(
            'user_id', 'text_adopted_id',
            name='uq_user_text_adopted_track'
        ),
        Index('ix_user_text_adopted_track_user_id', 'user_id'),
        Index('ix_user_text_adopted_track_text_adopted_id', 'text_adopted_id'),
    )

    def __repr__(self):
        return f"<UserTextAdoptedTrack user={self.user_id} text={self.text_adopted_id}>"
