"""
User Feed Read Model

SQLAlchemy model for tracking which RSS entries users have read.
Part of My EU Bubble - Phase 1: RSS Feed Infrastructure
"""

from sqlalchemy import Column, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..core.database import Base


class UserFeedRead(Base):
    """
    User Feed Read model.

    Tracks which RSS entries users have read to provide
    read/unread indicators in the My EU Bubble news sidebar.
    Also tracks reading time for engagement analytics.
    """
    __tablename__ = "user_feed_reads"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rss_entry_id = Column(UUID(as_uuid=True), ForeignKey("rss_entries.id", ondelete="CASCADE"), nullable=False, index=True)

    # Reading metrics
    reading_time_seconds = Column(Integer, nullable=True)  # How long user spent reading
    read_count = Column(Integer, default=1)  # Number of times user opened this entry

    # Engagement flags
    clicked_link = Column(Integer, default=False)  # Whether user clicked through to source

    # Timestamps
    first_read_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_read_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="feed_reads")
    rss_entry = relationship("RSSEntry", backref="user_reads")

    # Unique constraint: one read record per user per entry
    __table_args__ = (
        UniqueConstraint('user_id', 'rss_entry_id', name='uq_user_entry_read'),
    )

    def __repr__(self):
        return f"<UserFeedRead(user_id={self.user_id}, entry_id={self.rss_entry_id})>"

    def increment_read_count(self):
        """Update read count and timestamp when user re-reads entry"""
        from datetime import datetime, timezone
        self.read_count += 1
        self.last_read_at = datetime.now(timezone.utc)

    @property
    def is_quick_read(self) -> bool:
        """Check if user spent less than 30 seconds reading"""
        return self.reading_time_seconds is not None and self.reading_time_seconds < 30

    @property
    def is_thorough_read(self) -> bool:
        """Check if user spent more than 2 minutes reading"""
        return self.reading_time_seconds is not None and self.reading_time_seconds > 120
