"""
Chat Analytics Model

SQLAlchemy model for tracking per-message analytics.
Part of Phase E1: Monitoring & Analytics
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from core.database import Base


class ChatAnalytics(Base):
    """
    Tracks analytics for each AI response.

    Used for:
    - Provider distribution monitoring
    - Response time tracking
    - Knowledge gap frequency analysis
    - Token usage and cost estimation
    """
    __tablename__ = "chat_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link to message/conversation
    message_id = Column(UUID(as_uuid=True), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Provider info
    provider = Column(String(50), nullable=False)  # 'Anthropic', 'OpenAI', 'Gemini'
    model = Column(String(100), nullable=False)

    # Performance metrics
    tokens_used = Column(Integer, default=0)
    response_time_ms = Column(Float, default=0)
    search_time_ms = Column(Float, default=0)

    # Quality signals
    had_knowledge_gap = Column(Boolean, default=False)
    knowledge_gap_type = Column(String(50), nullable=True)
    source_tiers_used = Column(ARRAY(Integer), nullable=True)
    citation_count = Column(Integer, default=0)

    # Context info
    context_sources_count = Column(Integer, default=0)
    query_length = Column(Integer, default=0)
    response_length = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", backref="chat_analytics")

    def __repr__(self):
        return f"<ChatAnalytics {self.id}: {self.provider}/{self.model}>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'message_id': str(self.message_id) if self.message_id else None,
            'conversation_id': str(self.conversation_id) if self.conversation_id else None,
            'provider': self.provider,
            'model': self.model,
            'tokens_used': self.tokens_used,
            'response_time_ms': self.response_time_ms,
            'search_time_ms': self.search_time_ms,
            'had_knowledge_gap': self.had_knowledge_gap,
            'knowledge_gap_type': self.knowledge_gap_type,
            'source_tiers_used': self.source_tiers_used,
            'citation_count': self.citation_count,
            'context_sources_count': self.context_sources_count,
            'query_length': self.query_length,
            'response_length': self.response_length,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
