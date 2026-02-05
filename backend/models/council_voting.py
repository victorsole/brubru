"""
Council Voting Database Models - Phase 4.4

SQLAlchemy models for Council of the EU voting predictions.

Tables:
- MemberState: EU-27 member states with population data
- Government: Current and historical government compositions
- GoverningParty: Parties in each government coalition
- Minister: Ministers and their Council configurations
- MemberStatePosition: Inferred positions on EU procedures
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Text, ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from core.database import Base


class EuropeanPartyFamily(str, enum.Enum):
    """European political party families."""
    EPP = "EPP"  # European People's Party (centre-right)
    PES = "PES"  # Party of European Socialists (centre-left)
    ALDE = "ALDE"  # Alliance of Liberals (liberal)
    EGP = "EGP"  # European Green Party (green)
    ECR = "ECR"  # European Conservatives and Reformists
    ID = "ID"  # Identity and Democracy (nationalist)
    EL = "EL"  # Party of the European Left
    INDEPENDENT = "INDEPENDENT"  # Not affiliated


class PartyRole(str, enum.Enum):
    """Role in government coalition."""
    SENIOR = "senior"  # Leading party
    JUNIOR = "junior"  # Coalition partner
    SUPPORT = "support"  # External support (confidence and supply)


class PositionStance(str, enum.Enum):
    """Member state position on EU procedure."""
    SUPPORT = "support"
    OPPOSE = "oppose"
    UNDECIDED = "undecided"
    ABSTAIN = "abstain"


class StatementSentiment(str, enum.Enum):
    """Sentiment of government statement."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class CouncilConfiguration(str, enum.Enum):
    """Council of the EU configurations."""
    GAC = "GAC"  # General Affairs
    FAC = "FAC"  # Foreign Affairs
    ECOFIN = "ECOFIN"  # Economic and Financial Affairs
    JHA = "JHA"  # Justice and Home Affairs
    EPSCO = "EPSCO"  # Employment, Social Policy
    COMPET = "COMPET"  # Competitiveness
    TTE = "TTE"  # Transport, Telecommunications, Energy
    AGRIFISH = "AGRIFISH"  # Agriculture and Fisheries
    ENVI = "ENVI"  # Environment
    EYCS = "EYCS"  # Education, Youth, Culture, Sport


class MemberState(Base):
    """
    EU Member State with population and voting weight.

    Stores static data about EU-27 countries.
    """
    __tablename__ = "council_member_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso_code = Column(String(2), unique=True, nullable=False, index=True)  # DE, FR, etc.
    name = Column(String(100), nullable=False)
    name_local = Column(String(100))  # Name in local language

    # Population data (for QMV calculations)
    population = Column(Integer, nullable=False)  # In thousands
    population_percentage = Column(Float, nullable=False)
    population_updated_at = Column(DateTime)

    # EU membership
    accession_date = Column(DateTime)
    eurozone_member = Column(Boolean, default=False)
    schengen_member = Column(Boolean, default=False)

    # Metadata
    capital = Column(String(100))
    official_languages = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    governments = relationship("Government", back_populates="member_state", cascade="all, delete-orphan")
    positions = relationship("MemberStatePosition", back_populates="member_state", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MemberState {self.iso_code}: {self.name}>"


class Government(Base):
    """
    Government composition for a member state.

    Tracks coalitions and their tenure.
    """
    __tablename__ = "council_governments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_state_id = Column(UUID(as_uuid=True), ForeignKey("council_member_states.id"), nullable=False)

    # Identification
    name = Column(String(200))  # e.g., "Scholz Cabinet", "Macron II"
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)  # Null if current
    is_current = Column(Boolean, default=True, index=True)

    # Coalition info
    coalition_type = Column(String(50))  # "grand_coalition", "minority", "majority"
    coalition_description = Column(Text)

    # Stability indicators
    stability_score = Column(Float)  # 0-1, based on polls/factors
    next_election = Column(DateTime)

    # Head of government
    head_of_government = Column(String(200))
    head_party = Column(String(100))

    # EU orientation (simplified)
    eu_integration_stance = Column(Float)  # -1 (eurosceptic) to +1 (federalist)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    member_state = relationship("MemberState", back_populates="governments")
    parties = relationship("GoverningParty", back_populates="government", cascade="all, delete-orphan")
    ministers = relationship("Minister", back_populates="government", cascade="all, delete-orphan")
    statements = relationship("GovernmentStatement", back_populates="government", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_government_current', 'member_state_id', 'is_current'),
    )

    def __repr__(self):
        return f"<Government {self.name}>"


class GoverningParty(Base):
    """
    Party in a government coalition.

    Links to European party family for position inference.
    """
    __tablename__ = "council_governing_parties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    government_id = Column(UUID(as_uuid=True), ForeignKey("council_governments.id"), nullable=False)

    # Party info
    party_name = Column(String(200), nullable=False)
    party_name_english = Column(String(200))
    party_abbreviation = Column(String(20))

    # Role in coalition
    role = Column(SQLEnum(PartyRole), nullable=False, default=PartyRole.SENIOR)

    # European affiliation
    european_family = Column(SQLEnum(EuropeanPartyFamily))
    ep_group_affiliation = Column(String(20))  # EPP, S&D, Renew, etc.

    # Seats and influence
    parliament_seats = Column(Integer)
    parliament_percentage = Column(Float)
    cabinet_posts = Column(Integer)

    # Key portfolios held
    minister_portfolios = Column(ARRAY(String), default=[])

    # Policy positions (simplified)
    eu_integration = Column(Float)  # -1 to +1
    fiscal_stance = Column(Float)  # -1 (spending) to +1 (austerity)
    green_stance = Column(Float)  # -1 (anti) to +1 (pro)
    migration_stance = Column(Float)  # -1 (restrictive) to +1 (open)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    government = relationship("Government", back_populates="parties")

    def __repr__(self):
        return f"<GoverningParty {self.party_abbreviation or self.party_name}>"


class Minister(Base):
    """
    Minister who attends Council meetings.

    Maps ministers to Council configurations.
    """
    __tablename__ = "council_ministers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    government_id = Column(UUID(as_uuid=True), ForeignKey("council_governments.id"), nullable=False)
    party_id = Column(UUID(as_uuid=True), ForeignKey("council_governing_parties.id"))

    # Personal info
    name = Column(String(200), nullable=False)
    title = Column(String(200))  # Official ministerial title
    portfolio = Column(String(200))  # e.g., "Finance", "Foreign Affairs"

    # Council participation
    council_configurations = Column(ARRAY(String), default=[])  # ['ECOFIN', 'GAC']
    is_primary_for = Column(ARRAY(String), default=[])  # Primary minister for these configs

    # Political info
    party_name = Column(String(200))
    eu_experience = Column(Boolean, default=False)  # Prior EU experience

    # Tenure
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_current = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    government = relationship("Government", back_populates="ministers")
    party = relationship("GoverningParty")
    statements = relationship("GovernmentStatement", back_populates="minister")

    # Indexes
    __table_args__ = (
        Index('ix_minister_current', 'government_id', 'is_current'),
    )

    def __repr__(self):
        return f"<Minister {self.name}: {self.portfolio}>"


class GovernmentStatement(Base):
    """
    Government or minister statement on EU legislation.

    Used to infer positions on procedures.
    """
    __tablename__ = "council_government_statements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    government_id = Column(UUID(as_uuid=True), ForeignKey("council_governments.id"), nullable=False)
    minister_id = Column(UUID(as_uuid=True), ForeignKey("council_ministers.id"))

    # Statement info
    statement_date = Column(DateTime, nullable=False, index=True)
    source_url = Column(String(500))
    source_type = Column(String(50))  # "press_release", "interview", "parliament", "council"

    # Content
    topic = Column(String(500), nullable=False)
    eu_procedure_ref = Column(String(50), index=True)  # If about specific procedure
    statement_text = Column(Text)
    summary = Column(Text)

    # Analysis
    sentiment = Column(SQLEnum(StatementSentiment))
    red_lines = Column(ARRAY(String), default=[])  # Explicit conditions/demands
    compromise_signals = Column(Boolean, default=False)  # Indicates willingness to negotiate

    # Confidence in analysis
    analysis_confidence = Column(Float, default=0.5)
    manually_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    government = relationship("Government", back_populates="statements")
    minister = relationship("Minister", back_populates="statements")

    # Indexes
    __table_args__ = (
        Index('ix_statement_procedure', 'eu_procedure_ref'),
        Index('ix_statement_date', 'statement_date'),
    )

    def __repr__(self):
        return f"<GovernmentStatement {self.statement_date}: {self.topic[:50]}>"


class MemberStatePosition(Base):
    """
    Inferred position of a member state on an EU procedure.

    Aggregates evidence from statements, votes, and other sources.
    """
    __tablename__ = "council_member_state_positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_state_id = Column(UUID(as_uuid=True), ForeignKey("council_member_states.id"), nullable=False)

    # Procedure
    eu_procedure_ref = Column(String(50), nullable=False, index=True)
    procedure_title = Column(String(500))

    # Position
    position = Column(SQLEnum(PositionStance), nullable=False, default=PositionStance.UNDECIDED)
    confidence = Column(Float, default=0.5)  # 0-1

    # Evidence
    evidence_sources = Column(JSONB, default=[])  # [{type, date, summary, url}, ...]
    key_concerns = Column(ARRAY(String), default=[])
    red_lines = Column(ARRAY(String), default=[])
    compromise_areas = Column(ARRAY(String), default=[])

    # Change tracking
    position_history = Column(JSONB, default=[])  # [{date, position, reason}, ...]
    last_signal_date = Column(DateTime)

    # Prediction metadata
    inferred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    manually_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    member_state = relationship("MemberState", back_populates="positions")

    # Indexes
    __table_args__ = (
        Index('ix_position_procedure_state', 'eu_procedure_ref', 'member_state_id', unique=True),
    )

    def __repr__(self):
        return f"<MemberStatePosition {self.member_state_id}: {self.eu_procedure_ref} = {self.position}>"


class NationalParliamentVote(Base):
    """
    National parliament vote on EU-related matters.

    Tracks ratification votes, subsidiarity opinions, etc.
    """
    __tablename__ = "council_national_parliament_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_state_id = Column(UUID(as_uuid=True), ForeignKey("council_member_states.id"), nullable=False)

    # Vote info
    vote_date = Column(DateTime, nullable=False, index=True)
    vote_type = Column(String(50), nullable=False)  # "ratification", "subsidiarity", "mandate", "debate"
    chamber = Column(String(100))  # "Bundestag", "Senate", etc.

    # Topic
    topic = Column(String(500), nullable=False)
    eu_procedure_ref = Column(String(50), index=True)

    # Results
    votes_for = Column(Integer)
    votes_against = Column(Integer)
    votes_abstain = Column(Integer)
    passed = Column(Boolean)

    # Party breakdown
    party_votes = Column(JSONB, default={})  # {"SPD": {"for": 150, "against": 0}, ...}

    # Source
    source_url = Column(String(500))

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('ix_nat_parl_vote_procedure', 'eu_procedure_ref'),
    )

    def __repr__(self):
        return f"<NationalParliamentVote {self.vote_date}: {self.topic[:50]}>"
