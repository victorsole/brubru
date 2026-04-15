"""
Institutional Publication model.

Unified shape for every item ingested by the generic RSS ingester across all
EU institutional feeds. Consumed internally by chatbot/Bubble and externally
via /api/v1/publications.
"""

from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
import uuid

from core.database import Base


class InstitutionalPublication(Base):
    __tablename__ = "institutional_publications"
    __table_args__ = (
        UniqueConstraint("source_slug", "external_id", name="institutional_publications_external_id_unique"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source_slug = Column(String(100), nullable=False, index=True)
    institution_slug = Column(String(100), nullable=False, index=True)
    category = Column(String(50), index=True)

    external_id = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    html_content = Column(Text)
    language = Column(String(10), default="en")

    published_date = Column(DateTime(timezone=True), index=True)
    updated_date = Column(DateTime(timezone=True))

    policy_areas = Column(ARRAY(Text), default=list)
    tags = Column(ARRAY(Text), default=list)
    authors = Column(ARRAY(Text), default=list)
    extra_metadata = Column(JSONB, default=dict)

    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
