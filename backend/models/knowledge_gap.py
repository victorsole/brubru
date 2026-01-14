"""
Knowledge Gap Model

SQLAlchemy model for tracking AI "I don't know" responses.
Part of Phase C: Knowledge Base Improvements - Gap Analysis
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class KnowledgeGap(Base):
    """
    Tracks when the AI admits it doesn't have information.

    Used for:
    - Identifying missing data in knowledge base
    - Prioritising knowledge base expansion
    - Understanding user needs vs current coverage
    """
    __tablename__ = "knowledge_gaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Query information
    query = Column(Text, nullable=False)
    detected_topic = Column(Text, nullable=True)
    policy_area = Column(String(100), nullable=True)

    # Gap classification
    missing_data_type = Column(String(50), nullable=True)
    # Values: 'legislation', 'procedure', 'mep', 'date', 'statistic', 'document'

    # Context
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    conversation_id = Column(String(100), nullable=True)
    ai_response_excerpt = Column(Text, nullable=True)  # First 500 chars

    # Analysis (filled after review)
    root_cause = Column(String(50), nullable=True)
    # Values: 'not_indexed', 'not_fetched', 'not_exists', 'outdated'
    resolution_notes = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    user = relationship("User", backref="knowledge_gaps")

    def __repr__(self):
        return f"<KnowledgeGap {self.id}: {self.query[:50]}...>"


# Missing data type constants
class MissingDataType:
    LEGISLATION = 'legislation'
    PROCEDURE = 'procedure'
    MEP = 'mep'
    DATE = 'date'
    STATISTIC = 'statistic'
    DOCUMENT = 'document'
    UNKNOWN = 'unknown'


# Root cause constants
class GapRootCause:
    NOT_INDEXED = 'not_indexed'  # Data exists but not in our index
    NOT_FETCHED = 'not_fetched'  # API available but not called
    NOT_EXISTS = 'not_exists'    # Data genuinely doesn't exist
    OUTDATED = 'outdated'        # Data too old to be useful
