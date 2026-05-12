"""
W4 P2 entity models — partner-grade ingestion targets queued for scrapers.

- ParliamentaryQuestion (1.15) — EP written + oral questions
- TransparencyMeeting (1.8) — Commission Transparency Initiative meeting register
- RSBOpinion (1.10) — Regulatory Scrutiny Board opinions on impact assessments
- DelegatedAct + ImplementingAct (B.4) — Commission delegated and implementing acts
- TRISNotification (B.6) — Member State technical-regulation notifications

Tables are created via Alembic migration (see migrations/versions/038_*).
Until scrapers are ingestion-ready, endpoints return empty result sets.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Text, Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB

from core.database import Base


# ============================================================================
# 1.15 EP Parliamentary Questions
# ============================================================================


class QuestionTypeEnum(str, enum.Enum):
    WRITTEN = "written"
    ORAL = "oral"
    PRIORITY = "priority"
    QUESTION_TIME = "question_time"


class ParliamentaryQuestion(Base):
    """EP written + oral parliamentary questions and Commission/Council answers."""

    __tablename__ = "parliamentary_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    question_reference = Column(String(50), nullable=False, unique=True, index=True)  # e.g. E-001234/2026
    question_type = Column(
        SQLEnum(QuestionTypeEnum, name="question_type_enum", create_type=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=QuestionTypeEnum.WRITTEN,
    )
    parliamentary_term = Column(Integer, default=10, nullable=False)

    subject = Column(Text, nullable=False)
    text_question = Column(Text, nullable=True)
    text_answer = Column(Text, nullable=True)

    submitted_date = Column(Date, nullable=True, index=True)
    answered_date = Column(Date, nullable=True)

    asking_mep_ids = Column(ARRAY(String), default=list)
    asking_mep_names = Column(ARRAY(String), default=list)
    answering_institution = Column(String(50), nullable=True)
    answering_commissioner = Column(String(255), nullable=True)

    committees = Column(ARRAY(String), default=list)
    procedure_ref = Column(String(50), nullable=True)
    related_celex = Column(ARRAY(String), default=list)
    policy_areas = Column(ARRAY(String), default=list)

    source_url = Column(Text, nullable=True)
    answer_url = Column(Text, nullable=True)

    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        Index("ix_parl_q_submitted", "submitted_date"),
        Index("ix_parl_q_term", "parliamentary_term"),
    )


# ============================================================================
# 1.8 Commission Transparency Initiative — meetings register
# ============================================================================


class TransparencyMeeting(Base):
    """Commission Transparency Initiative meeting register entry.

    Each row = one published meeting between a Commission cabinet/DG official
    and an external interest representative.
    """

    __tablename__ = "transparency_meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    host_uuid = Column(String(64), nullable=False, index=True)  # cabinet/DG host UUID
    host_name = Column(String(255), nullable=True)
    host_role = Column(String(255), nullable=True)  # "Commissioner", "Cabinet member", "Director-General"
    host_dg = Column(String(20), nullable=True, index=True)
    host_cabinet = Column(String(100), nullable=True)

    meeting_date = Column(Date, nullable=False, index=True)
    location = Column(String(255), nullable=True)
    subject = Column(Text, nullable=False)

    organisation_met = Column(String(500), nullable=False, index=True)
    transparency_register_id = Column(String(50), nullable=True, index=True)
    organisation_type = Column(String(50), nullable=True)  # "company", "association", "NGO", ...

    # Free-text representatives field (often a list of names)
    representatives = Column(Text, nullable=True)

    source_url = Column(Text, nullable=False)

    policy_areas = Column(ARRAY(String), default=list)
    related_celex = Column(ARRAY(String), default=list)

    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    __table_args__ = (
        Index("ix_tr_meet_org", "organisation_met"),
        Index("ix_tr_meet_date", "meeting_date"),
        Index("ix_tr_meet_dg", "host_dg"),
    )


# ============================================================================
# 1.10 Regulatory Scrutiny Board (RSB) opinions
# ============================================================================


class RSBVerdictEnum(str, enum.Enum):
    POSITIVE = "positive"
    POSITIVE_WITH_RESERVATIONS = "positive_with_reservations"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class RSBOpinion(Base):
    """RSB opinion on a Commission impact assessment / evaluation."""

    __tablename__ = "rsb_opinions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opinion_reference = Column(String(100), nullable=False, unique=True, index=True)

    title = Column(Text, nullable=False)
    target_initiative = Column(String(255), nullable=True)  # name/description of the IA target
    target_dg = Column(String(20), nullable=True, index=True)
    procedure_ref = Column(String(50), nullable=True, index=True)

    opinion_type = Column(String(50), nullable=False, default="impact_assessment")  # impact_assessment | evaluation | fitness_check
    verdict = Column(
        SQLEnum(RSBVerdictEnum, name="rsb_verdict_enum", create_type=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=RSBVerdictEnum.UNKNOWN,
    )
    opinion_date = Column(Date, nullable=False, index=True)

    summary = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    pdf_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=False)

    policy_areas = Column(ARRAY(String), default=list)

    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


# ============================================================================
# B.4 Delegated + implementing acts (Commission, comitology / RegDel registers)
# ============================================================================


class SecondaryActTypeEnum(str, enum.Enum):
    DELEGATED = "delegated"
    IMPLEMENTING = "implementing"


class SecondaryActStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    ADOPTED = "adopted"
    OBJECTED = "objected"
    REJECTED = "rejected"
    PUBLISHED = "published"
    UNKNOWN = "unknown"


class SecondaryAct(Base):
    """Delegated and implementing acts — discriminator on `act_type`.

    Backs both /api/v1/delegated-acts and /api/v1/implementing-acts.
    """

    __tablename__ = "secondary_acts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    act_type = Column(
        SQLEnum(SecondaryActTypeEnum, name="secondary_act_type_enum", create_type=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True,
    )
    reference = Column(String(100), nullable=False, unique=True, index=True)  # CRD/CIM reference
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    parent_celex = Column(String(30), nullable=True, index=True)  # The base law being amended
    parent_procedure_ref = Column(String(50), nullable=True)

    status = Column(
        SQLEnum(SecondaryActStatusEnum, name="secondary_act_status_enum", create_type=True,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=SecondaryActStatusEnum.UNKNOWN,
    )

    proposing_dg = Column(String(20), nullable=True, index=True)
    publication_date = Column(Date, nullable=True, index=True)
    objection_deadline = Column(Date, nullable=True)
    ep_scrutiny = Column(JSONB, default=dict)  # { result, date, vote_for, vote_against, ... }
    council_scrutiny = Column(JSONB, default=dict)

    celex = Column(String(30), nullable=True)
    source_url = Column(Text, nullable=False)
    pdf_url = Column(Text, nullable=True)
    # Body text backfilled from Cellar (migration 051). XHTML-stripped plain
    # text or PDF-extracted text for adopted CELEXes.
    text_body = Column(Text, nullable=True)
    # HTML body backfilled from Cellar XHTML manifestation (migration 071).
    body_html = Column(Text, nullable=True)
    body_fetched_at = Column(DateTime, nullable=True)
    # Internal record id in the Interinstitutional Register of Delegated Acts.
    # Lets the v1 endpoint build a specific /delegatedActs/{regdel_id}?lang=en
    # citizen URL instead of a generic search URL (migration 071).
    regdel_id = Column(Integer, nullable=True)

    policy_areas = Column(ARRAY(String), default=list)

    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


# ============================================================================
# B.6 TRIS — Member State technical regulation notifications
# ============================================================================


class TRISNotification(Base):
    """TRIS notification of a national technical regulation under Directive 2015/1535."""

    __tablename__ = "tris_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    notification_number = Column(String(50), nullable=False, unique=True, index=True)  # e.g. 2026/0123/FR
    notifying_country = Column(String(3), nullable=False, index=True)  # ISO-3166-1 alpha-2 (e.g. FR)
    title = Column(Text, nullable=False)
    short_summary = Column(Text, nullable=True)
    full_text_summary = Column(Text, nullable=True)

    notification_date = Column(Date, nullable=False, index=True)
    standstill_until = Column(Date, nullable=True)

    sector = Column(String(255), nullable=True, index=True)
    products_or_services = Column(Text, nullable=True)
    main_content = Column(Text, nullable=True)

    commission_observations_url = Column(Text, nullable=True)
    member_state_observations = Column(JSONB, default=list)
    detailed_opinions = Column(JSONB, default=list)

    source_url = Column(Text, nullable=False)
    pdf_url = Column(Text, nullable=True)

    policy_areas = Column(ARRAY(String), default=list)
    related_celex = Column(ARRAY(String), default=list)

    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
