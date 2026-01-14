"""
Newsletter Models

SQLAlchemy models for European Commission newsletter tracking system.
"""

from sqlalchemy import Column, String, Boolean, Integer, Float, TIMESTAMP, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base


class NewsletterSource(Base):
    """European Commission newsletter source (DG or agency)"""

    __tablename__ = "newsletters_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dg_name = Column(String(100), nullable=False)
    newsletter_name = Column(String(200), nullable=False)
    dg_code = Column(String(50), nullable=False)  # e.g., 'clima', 'comp'
    service_id = Column(String(50))  # EC Newsroom service ID
    subscription_url = Column(Text)
    archive_url = Column(Text)
    ingestion_method = Column(String(20), nullable=False)  # 'rss', 'scrape', 'api'
    rss_feed_url = Column(Text)
    publication_frequency = Column(String(50))  # 'weekly', 'monthly', etc.
    strategic_tier = Column(String(10))  # 'tier1', 'tier2', 'tier3'
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(TIMESTAMP)
    scrape_interval_hours = Column(Integer, default=24)
    source_metadata = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    content_items = relationship("NewsletterContent", back_populates="source", cascade="all, delete-orphan")
    user_preferences = relationship("UserNewsletterPreference", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NewsletterSource(dg='{self.dg_name}', name='{self.newsletter_name}')>"


class NewsletterContent(Base):
    """Parsed content from EC newsletters"""

    __tablename__ = "newsletters_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("newsletters_sources.id", ondelete="CASCADE"), nullable=False)
    publication_date = Column(TIMESTAMP, nullable=False)
    retrieved_at = Column(TIMESTAMP, server_default=func.now())
    title = Column(Text, nullable=False)
    summary = Column(Text)
    full_content = Column(Text)
    content_type = Column(String(50))  # 'article', 'consultation', 'event', 'funding', 'general'
    language = Column(String(10), default='en')
    original_url = Column(Text)
    content_fingerprint = Column(String(64), unique=True)  # SHA-256 hash for deduplication
    topics = Column(ARRAY(Text))  # Policy areas/topics
    entities = Column(JSONB)  # Extracted entities (regulations, directives, people, etc.)
    content_metadata = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    source = relationship("NewsletterSource", back_populates="content_items")
    interactions = relationship("UserNewsletterInteraction", back_populates="content", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NewsletterContent(title='{self.title[:50]}...', date='{self.publication_date}')>"


class UserNewsletterPreference(Base):
    """User subscriptions to specific newsletters"""

    __tablename__ = "user_newsletter_preferences"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("newsletters_sources.id", ondelete="CASCADE"), primary_key=True)
    is_subscribed = Column(Boolean, default=True)
    priority_weight = Column(Float, default=1.0)
    notification_enabled = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    source = relationship("NewsletterSource", back_populates="user_preferences")

    def __repr__(self):
        return f"<UserNewsletterPreference(user_id='{self.user_id}', source_id='{self.source_id}')>"


class UserNewsletterTopic(Base):
    """User topic preferences for filtering newsletter content"""

    __tablename__ = "user_newsletter_topics"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic = Column(String(100), primary_key=True)
    priority_weight = Column(Float, default=1.0)
    notification_enabled = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    def __repr__(self):
        return f"<UserNewsletterTopic(user_id='{self.user_id}', topic='{self.topic}')>"


class UserNewsletterInteraction(Base):
    """User interactions with newsletter content for relevance learning"""

    __tablename__ = "user_newsletter_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(UUID(as_uuid=True), ForeignKey("newsletters_content.id", ondelete="CASCADE"), nullable=False)
    interaction_type = Column(String(20), nullable=False)  # 'view', 'click', 'save', 'dismiss', 'feedback'
    feedback_score = Column(Integer)  # 1-5 rating
    interaction_timestamp = Column(TIMESTAMP, server_default=func.now())
    interaction_metadata = Column(JSONB)

    # Relationships
    content = relationship("NewsletterContent", back_populates="interactions")

    def __repr__(self):
        return f"<UserNewsletterInteraction(type='{self.interaction_type}', timestamp='{self.interaction_timestamp}')>"
