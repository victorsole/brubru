"""
EP Resolutions Models - Phase 1.3

Database models for tracking EP resolutions (INL, INI, RSP) and linking
them to eventual legislative proposals as predictive signals.

Resolution types:
- INL: Legislative initiative (EP requests Commission to propose legislation)
- INI: Own-initiative report (non-binding recommendations)
- RSP: Resolution (on current issues, emergencies, etc.)
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, ForeignKey,
    Date, Float, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship

from core.database import Base


class ResolutionType(str, enum.Enum):
    """Type of EP resolution"""
    INL = "INL"  # Legislative initiative
    INI = "INI"  # Own-initiative report
    RSP = "RSP"  # Resolution
    OTHER = "OTHER"


class MatchMethod(str, enum.Enum):
    """How a resolution was matched to legislation"""
    OEIL_CROSSREF = "OEIL_CROSSREF"  # Explicit OEIL cross-reference
    COMMISSION_FOLLOWUP = "COMMISSION_FOLLOWUP"  # EP "Actions Taken" document
    TITLE_SIMILARITY = "TITLE_SIMILARITY"  # Semantic title matching
    EUROVOC_MATCH = "EUROVOC_MATCH"  # Same EuroVoc policy area
    MANUAL = "MANUAL"  # Manually linked


class EPResolution(Base):
    """
    EP Resolution (INL, INI, RSP procedures).
    These often precede and predict legislative action.
    """
    __tablename__ = "ep_resolutions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Procedure identification
    procedure_ref = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    resolution_type = Column(SQLEnum(ResolutionType), nullable=False, index=True)

    # Dates
    adoption_date = Column(Date, nullable=True, index=True)
    vote_date = Column(DateTime, nullable=True)

    # Committee info
    lead_committee = Column(String(10), nullable=True, index=True)
    rapporteur = Column(String(255), nullable=True)

    # Content
    summary = Column(Text, nullable=True)
    eurovoc_codes = Column(ARRAY(String), nullable=True)
    policy_areas = Column(ARRAY(String), nullable=True)

    # Vote results (summary)
    vote_for = Column(Integer, default=0)
    vote_against = Column(Integer, default=0)
    vote_abstention = Column(Integer, default=0)
    vote_total = Column(Integer, default=0)

    # Links
    oeil_url = Column(String(500), nullable=True)
    text_url = Column(String(500), nullable=True)  # Final adopted text

    # Status
    has_commission_followup = Column(Boolean, default=False)
    followup_checked_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    legislation_links = relationship(
        "ResolutionToLegislation",
        back_populates="resolution",
        cascade="all, delete-orphan"
    )
    mep_votes = relationship(
        "ResolutionMEPVote",
        back_populates="resolution",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_ep_resolutions_type_date", "resolution_type", "adoption_date"),
    )

    def __repr__(self):
        return f"<EPResolution {self.procedure_ref}: {self.title[:50]}...>"

    @property
    def vote_passed(self) -> bool:
        """Did the resolution pass (simple majority)?"""
        return self.vote_for > self.vote_against

    @property
    def vote_margin(self) -> int:
        """Margin of votes (positive = passed, negative = failed)"""
        return self.vote_for - self.vote_against

    @property
    def support_percentage(self) -> float:
        """Percentage of votes in favour"""
        if self.vote_total == 0:
            return 0.0
        return self.vote_for / self.vote_total * 100


class ResolutionMEPVote(Base):
    """
    Individual MEP votes on resolutions.
    Used to predict how MEPs will vote on related legislation.
    """
    __tablename__ = "resolution_mep_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resolution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ep_resolutions.id", ondelete="CASCADE"),
        nullable=False
    )
    mep_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ep_members.id"),
        nullable=False
    )

    # Vote
    vote = Column(String(20), nullable=False)  # FOR, AGAINST, ABSTENTION, DID_NOT_VOTE

    # Snapshot at vote time
    group_code = Column(String(20), nullable=True)
    country_code = Column(String(3), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    resolution = relationship("EPResolution", back_populates="mep_votes")

    __table_args__ = (
        UniqueConstraint("resolution_id", "mep_id", name="uq_resolution_mep_vote"),
        Index("ix_resolution_mep_votes_mep", "mep_id"),
        Index("ix_resolution_mep_votes_resolution", "resolution_id"),
    )

    def __repr__(self):
        return f"<ResolutionMEPVote {self.mep_id}: {self.vote}>"


class ResolutionToLegislation(Base):
    """
    Links resolutions to related legislative procedures.
    A single resolution may lead to multiple legislative files,
    and legislation may be linked to multiple preceding resolutions.
    """
    __tablename__ = "resolution_to_legislation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source resolution
    resolution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ep_resolutions.id", ondelete="CASCADE"),
        nullable=False
    )

    # Target legislation
    legislative_procedure_ref = Column(String(50), nullable=False, index=True)
    legislative_title = Column(Text, nullable=True)

    # Link to LegislativeCarriage if exists
    carriage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("legislative_carriages.id", ondelete="SET NULL"),
        nullable=True
    )

    # Match info
    match_method = Column(SQLEnum(MatchMethod), nullable=False)
    confidence = Column(Float, default=1.0)  # 0.0 to 1.0
    match_details = Column(JSONB, nullable=True)  # Additional match info

    # Timing
    days_to_proposal = Column(Integer, nullable=True)  # Days from resolution to proposal

    # Verification
    verified = Column(Boolean, default=False)
    verified_by = Column(String(255), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    resolution = relationship("EPResolution", back_populates="legislation_links")

    __table_args__ = (
        UniqueConstraint(
            "resolution_id", "legislative_procedure_ref",
            name="uq_resolution_legislation"
        ),
        Index("ix_resolution_legislation_method", "match_method"),
        Index("ix_resolution_legislation_confidence", "confidence"),
    )

    def __repr__(self):
        return f"<ResolutionToLegislation {self.resolution_id} -> {self.legislative_procedure_ref}>"


class CommissionFollowup(Base):
    """
    Tracks Commission follow-up to EP resolutions.
    Source: EP "Actions Taken" documents and Commission communications.
    """
    __tablename__ = "commission_followups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    resolution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ep_resolutions.id", ondelete="CASCADE"),
        nullable=False
    )

    # Commission response
    com_reference = Column(String(100), nullable=True)  # COM(2024) 123
    followup_date = Column(Date, nullable=True)
    followup_type = Column(String(50), nullable=True)  # proposal, communication, report

    # Content
    title = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    document_url = Column(String(500), nullable=True)

    # Status
    results_in_legislation = Column(Boolean, default=False)
    legislative_ref = Column(String(50), nullable=True)  # If resulted in proposal

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_commission_followups_resolution", "resolution_id"),
    )

    def __repr__(self):
        return f"<CommissionFollowup {self.resolution_id}: {self.com_reference}>"
