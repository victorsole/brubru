"""
Chat Model

SQLAlchemy model for chat conversations.
Part of Phase 13: AI Context Injection - Task 13.11

Stores conversation metadata, participants, and settings.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class Chat(Base):
    """
    Chat conversation model.

    Stores metadata for AI-powered chat conversations with EU context injection.
    Each chat represents a conversation thread with a user.
    """
    __tablename__ = "chats"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User identification
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Foreign key to users table (nullable for pre-users)
    pre_user_id = Column(String(36), nullable=True, index=True)  # Anonymous session tracking

    # Chat metadata
    title = Column(String(200), nullable=True)  # Auto-generated or user-provided title
    description = Column(Text, nullable=True)  # Optional description

    # Chat settings
    use_context = Column(Boolean, default=True)  # Whether to inject EU context
    model = Column(String(100), default="claude-sonnet-4-20250514")  # AI model used
    temperature = Column(Integer, default=7)  # Temperature * 10 (0-10 range)

    # Statistics
    message_count = Column(Integer, default=0)  # Total messages in conversation
    total_tokens_used = Column(Integer, default=0)  # Cumulative tokens across all messages
    total_cost_usd = Column(Integer, default=0)  # Cost in cents (to avoid floats)

    # Context metadata
    collections_searched = Column(JSONB, nullable=True)  # Which vector collections were searched
    sources_used = Column(JSONB, nullable=True)  # List of source types used (legislation, meps, etc.)

    # Status
    is_active = Column(Boolean, default=True)  # Whether chat is active or archived
    is_starred = Column(Boolean, default=False)  # User-starred conversations
    is_shared = Column(Boolean, default=False)  # Whether conversation is shared publicly

    # Last activity
    last_message_at = Column(DateTime(timezone=True), nullable=True)  # When last message was sent
    last_message_preview = Column(String(500), nullable=True)  # Preview of last message

    # Additional metadata
    chat_metadata = Column(JSONB, nullable=True)  # Flexible storage for chat-specific data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")

    def __repr__(self):
        return f"<Chat(id={self.id}, user_id={self.user_id}, title={self.title}, messages={self.message_count})>"

    @property
    def temperature_float(self) -> float:
        """Get temperature as float (0.0-1.0)"""
        return self.temperature / 10.0

    @property
    def total_cost_usd_float(self) -> float:
        """Get total cost in USD"""
        return self.total_cost_usd / 100.0

    def add_message_stats(self, tokens: int, cost_cents: int):
        """
        Update chat statistics after adding a message.

        Args:
            tokens: Tokens used in this message
            cost_cents: Cost in cents for this message
        """
        from datetime import datetime, timezone
        self.message_count += 1
        self.total_tokens_used += tokens
        self.total_cost_usd += cost_cents
        self.last_message_at = datetime.now(timezone.utc)

    def set_last_message_preview(self, content: str, max_length: int = 500):
        """
        Set preview of last message.

        Args:
            content: Message content
            max_length: Maximum preview length
        """
        self.last_message_preview = content[:max_length] if content else None

    def archive(self):
        """Archive this chat"""
        self.is_active = False

    def unarchive(self):
        """Unarchive this chat"""
        self.is_active = True

    def star(self):
        """Star this chat"""
        self.is_starred = True

    def unstar(self):
        """Unstar this chat"""
        self.is_starred = False

    def share(self):
        """Make this chat publicly shareable"""
        self.is_shared = True

    def unshare(self):
        """Remove public sharing"""
        self.is_shared = False

    def get_summary(self) -> dict:
        """
        Get chat summary for API responses.

        Returns:
            Dict with chat summary
        """
        return {
            'id': str(self.id),
            'title': self.title,
            'message_count': self.message_count,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_message_preview': self.last_message_preview,
            'is_starred': self.is_starred,
            'is_shared': self.is_shared,
            'created_at': self.created_at.isoformat(),
            'total_tokens': self.total_tokens_used,
            'total_cost_usd': self.total_cost_usd_float
        }

    def to_dict(self) -> dict:
        """
        Convert chat to dictionary for API responses.

        Returns:
            Complete chat data as dict
        """
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'title': self.title,
            'description': self.description,
            'use_context': self.use_context,
            'model': self.model,
            'temperature': self.temperature_float,
            'message_count': self.message_count,
            'total_tokens_used': self.total_tokens_used,
            'total_cost_usd': self.total_cost_usd_float,
            'collections_searched': self.collections_searched,
            'sources_used': self.sources_used,
            'is_active': self.is_active,
            'is_starred': self.is_starred,
            'is_shared': self.is_shared,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.chat_metadata
        }


class Message(Base):
    """
    Chat message model.

    Stores individual messages within a chat conversation.
    Each message belongs to a Chat and has a role (user/assistant).
    """
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # AI response metadata (null for user messages)
    tokens_used = Column(Integer, nullable=True)
    model = Column(String(100), nullable=True)
    provider = Column(String(50), nullable=True)
    citations = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship back to chat
    chat = relationship("Chat", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, chat_id={self.chat_id}, role={self.role})>"

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'role': self.role,
            'content': self.content,
            'timestamp': self.created_at.isoformat(),
            'tokens_used': self.tokens_used,
            'model': self.model,
            'provider': self.provider,
            'citations': self.citations,
        }
