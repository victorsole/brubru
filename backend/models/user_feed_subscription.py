"""
User Feed Subscription Model

SQLAlchemy model for tracking user subscriptions to RSS feeds.
Part of My EU Bubble - Phase 1: RSS Feed Infrastructure
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..core.database import Base


class UserFeedSubscription(Base):
    """
    User Feed Subscription model.

    Tracks which RSS feeds users are subscribed to.
    Users can subscribe to specific feeds from various EU institutions
    to customize their My EU Bubble news sidebar.
    """
    __tablename__ = "user_feed_subscriptions"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feed_id = Column(UUID(as_uuid=True), ForeignKey("rss_feeds.id", ondelete="CASCADE"), nullable=False, index=True)

    # Subscription settings
    is_active = Column(Boolean, default=True)  # Can temporarily disable without unsubscribing
    notification_enabled = Column(Boolean, default=False)  # Get notifications for new entries

    # Timestamps
    subscribed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)  # Last time user viewed this feed
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="feed_subscriptions")
    feed = relationship("RSSFeed", backref="user_subscriptions")

    # Unique constraint: one subscription per user per feed
    __table_args__ = (
        UniqueConstraint('user_id', 'feed_id', name='uq_user_feed_subscription'),
    )

    def __repr__(self):
        return f"<UserFeedSubscription(user_id={self.user_id}, feed_id={self.feed_id})>"

    @property
    def is_new_user(self) -> bool:
        """Check if user has never viewed this feed"""
        return self.last_viewed_at is None

    @property
    def days_subscribed(self) -> int:
        """Calculate how many days user has been subscribed"""
        from datetime import datetime, timezone
        delta = datetime.now(timezone.utc) - self.subscribed_at
        return delta.days
