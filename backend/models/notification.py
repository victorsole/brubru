"""
Notification Model

Database model for user notifications and alerts.
Part of My EU Bubble - Phase 5: Advanced Features
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from core.database import Base


class Notification(Base):
    """
    User notification model.

    Stores alerts about:
    - New RSS entries matching user interests
    - Legislative status changes
    - Amendment deadlines
    - Policy updates
    """

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Notification type
    notification_type = Column(String(50), nullable=False, index=True)
    # Types: new_feed_entry, status_change, deadline, policy_update, amendment_update

    # Content
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)

    # Metadata
    notif_metadata = Column(JSON, nullable=True)
    # Stores type-specific data like entry_id, procedure_reference, etc.

    # Related entities
    related_entity_type = Column(String(50), nullable=True)
    # Types: rss_entry, user_document, procedure, legislation
    related_entity_id = Column(UUID(as_uuid=True), nullable=True)

    # Priority and status
    priority = Column(String(20), default="normal")
    # Priorities: low, normal, high, urgent
    is_read = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="notifications")

    def mark_as_read(self):
        """Mark notification as read."""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)

    def to_dict(self):
        """Convert notification to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "action_url": self.action_url,
            "metadata": self.notif_metadata,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": str(self.related_entity_id) if self.related_entity_id else None,
            "priority": self.priority,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
            "read_at": self.read_at.isoformat() if self.read_at else None
        }

    def __repr__(self):
        return f"<Notification {self.id} - {self.notification_type} - {self.title}>"
