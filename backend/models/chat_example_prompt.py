"""
Chat Example Prompt Model

Stores admin-managed example prompts shown in the chat interface.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from core.database import Base


class ChatExamplePrompt(Base):
    __tablename__ = "chat_example_prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Prompt text to display to users
    text = Column(String(500), nullable=False)

    # Optional locale like 'en' or 'en-GB'; if null => language-agnostic
    locale = Column(String(16), nullable=True, index=True)

    # Scope to support different placement, default: 'main_chat'
    scope = Column(String(50), default="main_chat", index=True)

    # List of subscription tiers that can see this prompt (null => all)
    subscription_tiers = Column(JSONB, nullable=True)

    # Active flag
    is_active = Column(Boolean, default=True, index=True)

    # Ordering in UI
    sort_order = Column(Integer, default=0, index=True)

    # Usage analytics (how many times users clicked it)
    usage_count = Column(Integer, default=0)

    # Audit
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "text": self.text,
            "locale": self.locale,
            "scope": self.scope,
            "subscription_tiers": self.subscription_tiers,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

