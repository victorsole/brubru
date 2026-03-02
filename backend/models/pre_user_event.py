"""
Pre-User Event Model

SQLAlchemy model for tracking pre-user funnel events and A/B test variants.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


VALID_EVENT_TYPES = {
    "page_load",
    "query_1",
    "query_2",
    "query_3",
    "follow_up_clicked",
    "smart_suggestion_clicked",
    "cta_clicked",
    "signed_up",
}


class PreUserEvent(Base):
    """Tracks anonymous pre-user journey events for funnel analysis."""

    __tablename__ = "pre_user_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pre_user_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    ab_variant = Column(String(1), nullable=False)  # "A" or "B"
    event_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<PreUserEvent {self.event_type} variant={self.ab_variant} pre_user={self.pre_user_id[:8]}>"
