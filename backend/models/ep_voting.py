"""
EP Voting Models - Phase 1.1

Database models for European Parliament voting data from HowTheyVote.eu.
Stores MEPs, political groups, votes, and individual voting records.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, ForeignKey,
    Date, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship

from core.database import Base


class VotePosition(str, enum.Enum):
    """MEP vote position in a roll-call vote"""
    FOR = "FOR"
    AGAINST = "AGAINST"
    ABSTENTION = "ABSTENTION"
    DID_NOT_VOTE = "DID_NOT_VOTE"


class VoteResult(str, enum.Enum):
    """Overall result of a vote"""
    ADOPTED = "ADOPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ProcedureType(str, enum.Enum):
    """Legislative procedure types"""
    COD = "COD"  # Ordinary legislative procedure (codecision)
    CNS = "CNS"  # Consultation
    APP = "APP"  # Consent (approval)
    NLE = "NLE"  # Non-legislative enactment
    INI = "INI"  # Own-initiative report
    INL = "INL"  # Legislative initiative
    RSP = "RSP"  # Resolution
    BUD = "BUD"  # Budget
    DEC = "DEC"  # Discharge
    OTHER = "OTHER"


# --- Political Groups ---

class EPPoliticalGroup(Base):
    """
    EP Political Groups (e.g., EPP, S&D, Renew)
    Source: HowTheyVote groups.csv
    """
    __tablename__ = "ep_political_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False, index=True)
    official_label = Column(String(255), nullable=False)
    label = Column(String(100), nullable=False)
    short_label = Column(String(20), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    members = relationship("EPGroupMembership", back_populates="group")
    sections = relationship("EPSection", back_populates="group")

    def __repr__(self):
        return f"<EPPoliticalGroup {self.code}: {self.label}>"


class EPSection(Base):
    """
    Sections within EP Groups (e.g., Greens vs EFA, ALDE vs EDP)
    Source: data/manual/ep_sections.csv
    """
    __tablename__ = "ep_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_code = Column(String(20), ForeignKey("ep_political_groups.code"), nullable=False)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    group = relationship("EPPoliticalGroup", back_populates="sections")
    delegations = relationship("EPDelegation", back_populates="section")

    __table_args__ = (
        UniqueConstraint("group_code", "code", name="uq_section_group_code"),
    )

    def __repr__(self):
        return f"<EPSection {self.group_code}/{self.code}: {self.name}>"


# --- Delegations ---

class EPDelegation(Base):
    """
    National party delegations within EP groups
    Source: data/manual/ep_delegations.csv
    """
    __tablename__ = "ep_delegations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_code = Column(String(20), ForeignKey("ep_political_groups.code"), nullable=False)
    section_id = Column(UUID(as_uuid=True), ForeignKey("ep_sections.id"), nullable=True)
    country_code = Column(String(3), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    parties_included = Column(ARRAY(String), nullable=True)
    num_meps = Column(Integer, default=0)
    delegation_chair = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    section = relationship("EPSection", back_populates="delegations")
    members = relationship("EPMember", back_populates="delegation")

    __table_args__ = (
        Index("ix_ep_delegations_group_country", "group_code", "country_code"),
    )

    def __repr__(self):
        return f"<EPDelegation {self.name} ({self.country_code})>"


# --- MEPs ---

class EPMember(Base):
    """
    Members of the European Parliament
    Source: HowTheyVote members.csv + TrackMyEU enrichment
    """
    __tablename__ = "ep_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    htv_id = Column(Integer, unique=True, nullable=False, index=True)  # HowTheyVote ID
    ep_id = Column(Integer, nullable=True, index=True)  # Official EP ID

    # Personal info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=False, index=True)
    country_code = Column(String(3), nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)

    # National party (from TrackMyEU or manual data)
    national_party = Column(String(255), nullable=True)
    national_party_abbrev = Column(String(50), nullable=True)

    # Current group/delegation (denormalized for quick access)
    current_group_code = Column(String(20), nullable=True)
    delegation_id = Column(UUID(as_uuid=True), ForeignKey("ep_delegations.id"), nullable=True)

    # Contact
    email = Column(String(255), nullable=True)
    twitter = Column(String(100), nullable=True)
    facebook = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    term = Column(Integer, default=10)  # Current term (10 = 2024-2029)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    delegation = relationship("EPDelegation", back_populates="members")
    group_memberships = relationship("EPGroupMembership", back_populates="member")
    votes = relationship("EPMemberVote", back_populates="member")

    __table_args__ = (
        Index("ix_ep_members_name", "last_name", "first_name"),
    )

    def __repr__(self):
        return f"<EPMember {self.full_name} ({self.country_code})>"


class EPGroupMembership(Base):
    """
    MEP membership in political groups over time
    Source: HowTheyVote group_memberships.csv
    """
    __tablename__ = "ep_group_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("ep_members.id"), nullable=False)
    group_code = Column(String(20), ForeignKey("ep_political_groups.code"), nullable=False)
    term = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # NULL = current membership

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    member = relationship("EPMember", back_populates="group_memberships")
    group = relationship("EPPoliticalGroup", back_populates="members")

    __table_args__ = (
        Index("ix_ep_group_memberships_member", "member_id"),
        Index("ix_ep_group_memberships_group_term", "group_code", "term"),
    )

    def __repr__(self):
        return f"<EPGroupMembership {self.member_id} -> {self.group_code} (Term {self.term})>"


# --- Votes ---

class EPVote(Base):
    """
    Roll-call votes in the European Parliament
    Source: HowTheyVote votes.csv
    """
    __tablename__ = "ep_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    htv_id = Column(Integer, unique=True, nullable=False, index=True)  # HowTheyVote vote ID

    # Vote identification
    timestamp = Column(DateTime, nullable=False, index=True)
    display_title = Column(Text, nullable=False)
    reference = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)

    # Amendment info (if applicable)
    amendment_subject = Column(String(255), nullable=True)
    amendment_number = Column(String(50), nullable=True)
    is_main = Column(Boolean, default=False)  # Is this the main/final vote?

    # Procedure reference (links to OEIL/Legislative Train)
    procedure_reference = Column(String(50), nullable=True, index=True)
    procedure_title = Column(Text, nullable=True)
    procedure_type = Column(SQLEnum(ProcedureType), nullable=True)
    procedure_stage = Column(String(100), nullable=True)

    # Vote counts
    count_for = Column(Integer, default=0)
    count_against = Column(Integer, default=0)
    count_abstention = Column(Integer, default=0)
    count_did_not_vote = Column(Integer, default=0)

    # Result
    result = Column(SQLEnum(VoteResult), default=VoteResult.UNKNOWN)
    texts_adopted_reference = Column(String(100), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    member_votes = relationship("EPMemberVote", back_populates="vote", cascade="all, delete-orphan")
    committee_votes = relationship("EPCommitteeVote", back_populates="vote", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ep_votes_procedure", "procedure_reference"),
        Index("ix_ep_votes_date", "timestamp"),
    )

    def __repr__(self):
        return f"<EPVote {self.htv_id}: {self.display_title[:50]}...>"

    @property
    def total_votes(self) -> int:
        return self.count_for + self.count_against + self.count_abstention

    @property
    def participation_rate(self) -> float:
        total = self.total_votes + self.count_did_not_vote
        return self.total_votes / total if total > 0 else 0.0


class EPMemberVote(Base):
    """
    Individual MEP votes on roll-call votes
    Source: HowTheyVote member_votes.csv
    """
    __tablename__ = "ep_member_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vote_id = Column(UUID(as_uuid=True), ForeignKey("ep_votes.id", ondelete="CASCADE"), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey("ep_members.id"), nullable=False)

    # Vote position
    position = Column(SQLEnum(VotePosition), nullable=False)

    # Snapshot of member's group at vote time
    country_code = Column(String(3), nullable=False)
    group_code = Column(String(20), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    vote = relationship("EPVote", back_populates="member_votes")
    member = relationship("EPMember", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("vote_id", "member_id", name="uq_member_vote"),
        Index("ix_ep_member_votes_member", "member_id"),
        Index("ix_ep_member_votes_vote", "vote_id"),
        Index("ix_ep_member_votes_position", "position"),
        Index("ix_ep_member_votes_group", "group_code"),
    )

    def __repr__(self):
        return f"<EPMemberVote {self.member_id}: {self.position}>"


class EPCommitteeVote(Base):
    """
    Maps votes to responsible committees
    Source: HowTheyVote responsible_committee_votes.csv
    """
    __tablename__ = "ep_committee_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vote_id = Column(UUID(as_uuid=True), ForeignKey("ep_votes.id", ondelete="CASCADE"), nullable=False)
    committee_code = Column(String(10), nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    vote = relationship("EPVote", back_populates="committee_votes")

    __table_args__ = (
        UniqueConstraint("vote_id", "committee_code", name="uq_committee_vote"),
    )

    def __repr__(self):
        return f"<EPCommitteeVote {self.vote_id}: {self.committee_code}>"


# --- User Tracking ---

class UserVoteTrack(Base):
    """
    User subscriptions to track specific votes or procedures
    """
    __tablename__ = "user_vote_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vote_id = Column(UUID(as_uuid=True), ForeignKey("ep_votes.id", ondelete="CASCADE"), nullable=True)
    procedure_reference = Column(String(50), nullable=True)  # Track all votes for a procedure

    notes = Column(Text, nullable=True)
    notify_on_update = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_user_vote_tracks_user", "user_id"),
        Index("ix_user_vote_tracks_procedure", "procedure_reference"),
    )

    def __repr__(self):
        return f"<UserVoteTrack user={self.user_id}>"


# --- Import Tracking ---

class EPDataImport(Base):
    """
    Track HowTheyVote data imports for auditing
    """
    __tablename__ = "ep_data_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)  # 'howtheyvote', 'trackmyeu', 'manual'
    import_type = Column(String(50), nullable=False)  # 'members', 'votes', 'member_votes', etc.

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    records_processed = Column(Integer, default=0)
    records_added = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    errors = Column(Integer, default=0)

    error_details = Column(JSONB, nullable=True)
    source_metadata = Column(JSONB, nullable=True)  # Release version, etc.

    status = Column(String(20), default="running")  # running, completed, failed

    def __repr__(self):
        return f"<EPDataImport {self.source}/{self.import_type}: {self.status}>"
