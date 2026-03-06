"""
Daily EU Brief Model

Stores scraped EU institutional news headlines shown on the chat page.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Column, String, Integer, Text, Date, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class DailyBrief(Base):
    __tablename__ = "daily_briefs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brief_date = Column(Date, nullable=False, index=True)
    headline = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)
    category = Column(String(20), nullable=False, default="ec")
    priority = Column(Integer, nullable=False, default=99)
    snippet = Column(Text, nullable=True)
    suggested_query = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_daily_briefs_date_priority', 'brief_date', 'priority'),
    )

    def __repr__(self):
        return f"<DailyBrief {self.brief_date}: {self.headline[:50]}>"
