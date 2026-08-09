"""
Pre-User Event Model

SQLAlchemy model for tracking pre-user funnel events and A/B test variants.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


# This table serves two purposes and they must not be conflated.
#
# FUNNEL events are the anonymous acquisition journey: one actor moving from
# landing to first question to signup. These are the only types that belong in
# an activation or conversion rate.
FUNNEL_EVENT_TYPES = {
    "page_load",
    "query_1",
    "query_2",
    "query_3",
    "follow_up_clicked",
    "smart_suggestion_clicked",
    "cta_clicked",
    "signed_up",
    "email_captured",
    "brief_headline_clicked",
    "tour_completed",
    "tour_skipped",
    "onboarding_interest_chosen",
}

# OPERATIONAL events are outreach bookkeeping written by send scripts and the
# unsubscribe endpoint. They are keyed by pre_user_id but describe something WE
# did, not something a user did. Counting them as funnel activity roughly
# doubles the apparent actor count (643 of 1,294 rows on 9 Aug 2026).
#
# These were written for months via raw SQL that bypassed this allow-list --
# `daily_brief_unsubscribe` in particular, which every brief-send script reads
# to exclude unsubscribers (services/daily_brief_email.py). Declaring them here
# is what lets the endpoint validate without silently rejecting a real
# unsubscribe, which would mean emailing people who asked us to stop.
OPERATIONAL_EVENT_TYPES = {
    "daily_brief_unsubscribe",
    "unsubscribe",
    "send_brubru_brief_eutr",
    "send_batch_es_eutr",
    "send_batch_es_vc",
    "send_batch_es_vc_followup",
}

# Accepted by the write path. Analytics must use FUNNEL_EVENT_TYPES.
VALID_EVENT_TYPES = FUNNEL_EVENT_TYPES | OPERATIONAL_EVENT_TYPES


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
