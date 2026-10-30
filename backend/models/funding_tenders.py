"""SQLAlchemy models for migration 047 — three F&T portal collections.

All three tables ship `is_test BOOLEAN DEFAULT FALSE` so any future fixture
row can be filtered out at query time.
"""

import uuid

from sqlalchemy import (
    ARRAY,
    Boolean,
    CHAR,
    Column,
    Date,
    DateTime,
    Numeric,
    String,
    FetchedValue,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


class FtCallForProposals(Base):
    __tablename__ = "ft_calls_for_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(String(120), nullable=False, unique=True)
    call_id = Column(String(120))
    framework_programme = Column(String(120))
    title = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(String(40))
    type_of_action = Column(String(80))
    deadline = Column(DateTime)
    deadline_secondary = Column(DateTime)
    indicative_budget = Column(Numeric(20, 2))
    budget_currency = Column(String(8), default="EUR")
    source_url = Column(Text, nullable=False)
    documents_url = Column(Text)
    keywords = Column(ARRAY(Text), default=list)
    target_audience = Column(ARRAY(Text), default=list)
    is_test = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime)
    # The portal's startDate; published_at is the earlier of the first publication and it (migration 319).
    opening_date = Column(DateTime)
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime, server_default=func.now())
    detected_lang = Column(String(8))  # ISO-639-1; feeds the translation overlay
    # Migration 234: when Brubru first recorded the row, and when its CONTENT last
    # changed (a trigger ignores scraped_at/last_updated, which every sync rewrites).
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    content_updated_at = Column(DateTime(timezone=True), server_default=FetchedValue(), server_onupdate=FetchedValue())


class FtCallForTenders(Base):
    __tablename__ = "ft_calls_for_tenders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_reference = Column(String(120), nullable=False, unique=True)
    contracting_authority = Column(Text)
    title = Column(Text, nullable=False)
    description = Column(Text)
    contract_type = Column(String(60))
    status = Column(String(40))
    estimated_value = Column(Numeric(20, 2))
    value_currency = Column(String(8), default="EUR")
    deadline = Column(DateTime)
    source_url = Column(Text, nullable=False)
    documents_url = Column(Text)
    cpv_codes = Column(ARRAY(Text), default=list)
    is_test = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime)
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    detected_lang = Column(String(8))
    scraped_at = Column(DateTime, server_default=func.now())
    # Migration 234: when Brubru first recorded the row, and when its CONTENT last
    # changed (a trigger ignores scraped_at/last_updated, which every sync rewrites).
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    content_updated_at = Column(DateTime(timezone=True), server_default=FetchedValue(), server_onupdate=FetchedValue())


class FtFundedProject(Base):
    __tablename__ = "ft_funded_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(120), nullable=False, unique=True)
    project_acronym = Column(String(120))
    title = Column(Text, nullable=False)
    objective = Column(Text)
    framework_programme = Column(String(120))
    type_of_action = Column(String(80))
    coordinator_name = Column(Text)
    coordinator_country = Column(CHAR(2))
    start_date = Column(Date)
    end_date = Column(Date)
    total_cost = Column(Numeric(20, 2))
    eu_contribution = Column(Numeric(20, 2))
    cost_currency = Column(String(8), default="EUR")
    status = Column(String(40))  # planned | ongoing | ended | terminated | suspended | unknown (services/funding/project_status.py)
    source_status = Column(String(32))  # the source's own word (CORDIS or F&T Portal); migration 311, served since 312
    source_url = Column(Text, nullable=False)
    is_test = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime)
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime, server_default=func.now())
    detected_lang = Column(String(8))
    # In the table all along, never mapped: the item body's "Keywords" section was always empty and
    # nothing could filter on them (26 Oct 2026, partner search).
    keywords = Column(Text)
    topic_code = Column(Text)
    coordinator_pic = Column(String(20))
    organisations = Column(JSONB)  # the CORDIS consortium (scripts/ingest_cordis_projects.py)
