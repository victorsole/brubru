"""SQLAlchemy models for migration 046 — infringement procedures + funding opportunities.

Both tables ship `is_test BOOLEAN DEFAULT FALSE`. Production queries MUST filter
`is_test=False` so any synthetic/fixture rows can never leak into customer
responses. Anti-pattern reminder: see CLAUDE.md "Seed / test fixtures in
production-shared tables must be filterable at query time."
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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class InfringementProcedure(Base):
    __tablename__ = "infringement_procedures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inf_reference = Column(String(40), nullable=False, unique=True)
    member_state = Column(CHAR(2))
    procedure_stage = Column(String(64))
    sector = Column(String(120))
    title = Column(Text, nullable=False)
    summary = Column(Text)
    decision_date = Column(Date)
    source_url = Column(Text, nullable=False)
    pdf_url = Column(Text)
    related_celex = Column(ARRAY(Text), default=list)
    policy_areas = Column(ARRAY(Text), default=list)
    is_test = Column(Boolean, nullable=False, default=False)
    scraped_at = Column(DateTime, server_default=func.now())
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class FundingOpportunity(Base):
    __tablename__ = "funding_opportunities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(String(120), nullable=False, unique=True)
    call_id = Column(String(120))
    programme = Column(String(120))
    title = Column(Text, nullable=False)
    short_summary = Column(Text)
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
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime, server_default=func.now())
