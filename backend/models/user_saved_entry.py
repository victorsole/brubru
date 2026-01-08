"""
User Saved Entry Model

SQLAlchemy model for bookmarked/saved RSS entries.
Part of My EU Bubble - Phase 1: RSS Feed Infrastructure
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..core.database import Base


class UserSavedEntry(Base):
    """
    User Saved Entry model.

    Allows users to bookmark/save RSS entries for later reference
    in their My EU Bubble. Users can add notes and tags to saved entries.
    """
    __tablename__ = "user_saved_entries"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rss_entry_id = Column(UUID(as_uuid=True), ForeignKey("rss_entries.id", ondelete="CASCADE"), nullable=False, index=True)

    # User annotations
    notes = Column(Text, nullable=True)  # Personal notes about this entry
    tags = Column(ARRAY(String(100)), nullable=True)  # User-defined tags for organization

    # Collection/folder
    collection_name = Column(String(100), nullable=True, index=True)  # Group saved items (e.g., "Climate Policy")

    # Priority/reminder
    is_starred = Column(String, default=False)  # Mark as important
    reminder_at = Column(DateTime(timezone=True), nullable=True)  # Set reminder to review later

    # Timestamps
    saved_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)  # Last time user viewed saved item

    # Relationships
    user = relationship("User", backref="saved_entries")
    rss_entry = relationship("RSSEntry", backref="saved_by_users")

    def __repr__(self):
        return f"<UserSavedEntry(user_id={self.user_id}, entry_id={self.rss_entry_id})>"

    @property
    def has_notes(self) -> bool:
        """Check if user added notes"""
        return self.notes is not None and len(self.notes.strip()) > 0

    @property
    def has_tags(self) -> bool:
        """Check if user added tags"""
        return self.tags is not None and len(self.tags) > 0

    @property
    def days_saved(self) -> int:
        """Calculate how many days ago this was saved"""
        from datetime import datetime, timezone
        delta = datetime.now(timezone.utc) - self.saved_at
        return delta.days

    @property
    def needs_reminder(self) -> bool:
        """Check if reminder is due"""
        if self.reminder_at is None:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) >= self.reminder_at
