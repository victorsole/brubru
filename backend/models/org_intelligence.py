"""
Org Intelligence Model

Aggregated user activity profile for personalised AI context.
Updated by scripts/aggregate_org_intelligence.py.
"""

from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
import uuid

from core.database import Base


class OrgIntelligence(Base):
    __tablename__ = "org_intelligence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)

    # Derived from chat queries, tracked files, amendments, compliance checks
    policy_areas = Column(ARRAY(Text), default=[])
    tracked_files = Column(ARRAY(Text), default=[])
    amended_files = Column(ARRAY(Text), default=[])
    generated_docs = Column(ARRAY(Text), default=[])
    key_contacts = Column(ARRAY(Text), default=[])

    # From user profile + tender profile
    sector = Column(String(200), nullable=True)
    country = Column(String(100), nullable=True)

    # Activity counts
    query_count = Column(Integer, default=0)
    amendment_count = Column(Integer, default=0)
    document_count = Column(Integer, default=0)
    compliance_count = Column(Integer, default=0)

    # Top topics by frequency (e.g. {"AI Act": 12, "CBAM": 8, "GDPR": 5})
    top_topics = Column(JSONB, default={})

    last_query_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
