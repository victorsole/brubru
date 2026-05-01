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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

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
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime, server_default=func.now())


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
    scraped_at = Column(DateTime, server_default=func.now())


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
    status = Column(String(40))
    source_url = Column(Text, nullable=False)
    is_test = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime)
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime, server_default=func.now())
