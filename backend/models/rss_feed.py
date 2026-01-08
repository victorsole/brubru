"""
RSS Feed Model

SQLAlchemy model for tracking RSS feeds across EU institutions.
Part of Phase 5: RSS Feed Aggregation Service
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from ..core.database import Base


class RSSFeed(Base):
    """
    RSS Feed metadata model.

    Tracks all RSS feeds being monitored across EU institutions:
    - European Parliament (33+ feeds)
    - Council of the EU (17+ feeds)
    - EUR-Lex (multiple category feeds)
    - JRC (news, EMM, MedISys)
    - OEIL (procedure tracking)
    - Think Tank (publication types)

    Stores feed metadata, update schedules, and monitoring status.
    """
    __tablename__ = "rss_feeds"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Feed identification
    name = Column(String(200), nullable=False)  # Human-readable name
    url = Column(String(1000), nullable=False, unique=True, index=True)  # RSS feed URL
    source = Column(String(100), nullable=False, index=True)  # Institution (EuropeanParliament, Council, etc.)
    category = Column(String(100), nullable=True, index=True)  # Feed category (news, press_releases, etc.)

    # Feed metadata
    description = Column(Text, nullable=True)  # Feed description
    language = Column(String(5), default="en")  # ISO 639-1 language code
    feed_type = Column(String(50), default="rss")  # rss, atom, rdf

    # Update tracking
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)  # Last successful fetch
    last_updated_at = Column(DateTime(timezone=True), nullable=True)  # Last time feed had new content
    last_entry_date = Column(DateTime(timezone=True), nullable=True)  # Pub date of most recent entry
    next_fetch_at = Column(DateTime(timezone=True), nullable=True)  # Scheduled next fetch

    # Monitoring configuration
    update_frequency_minutes = Column(Integer, default=60)  # How often to check (minutes)
    priority = Column(Integer, default=5)  # 1-10, higher = more important
    is_active = Column(Boolean, default=True)  # Whether to actively monitor

    # Statistics
    total_entries = Column(Integer, default=0)  # Total entries processed from this feed
    fetch_success_count = Column(Integer, default=0)  # Successful fetches
    fetch_error_count = Column(Integer, default=0)  # Failed fetches
    last_error = Column(Text, nullable=True)  # Last error message
    last_error_at = Column(DateTime(timezone=True), nullable=True)  # When last error occurred

    # Feed health
    average_entries_per_day = Column(Integer, default=0)  # Average new entries per day
    is_healthy = Column(Boolean, default=True)  # Overall health status
    health_check_at = Column(DateTime(timezone=True), nullable=True)  # Last health check

    # Additional metadata (flexible JSON storage)
    feed_metadata = Column(JSONB, nullable=True)  # Extra feed-specific data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    entries = relationship("RSSEntry", back_populates="feed", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RSSFeed(id={self.id}, name={self.name}, source={self.source})>"

    @property
    def is_due_for_fetch(self) -> bool:
        """Check if feed is due for fetching based on schedule"""
        if not self.is_active:
            return False
        if self.next_fetch_at is None:
            return True
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) >= self.next_fetch_at

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage"""
        total = self.fetch_success_count + self.fetch_error_count
        if total == 0:
            return 0.0
        return (self.fetch_error_count / total) * 100

    def mark_fetch_success(self):
        """Mark successful fetch and update statistics"""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        self.last_fetched_at = now
        self.fetch_success_count += 1
        self.next_fetch_at = now + timedelta(minutes=self.update_frequency_minutes)
        self.last_error = None

    def mark_fetch_error(self, error_message: str):
        """Mark failed fetch and update error tracking"""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        self.last_fetched_at = now
        self.fetch_error_count += 1
        self.last_error = error_message
        self.last_error_at = now
        # Back off on errors: double the wait time up to 24 hours
        backoff_minutes = min(self.update_frequency_minutes * 2, 1440)
        self.next_fetch_at = now + timedelta(minutes=backoff_minutes)

    def update_health_status(self):
        """Update feed health based on error rate and activity"""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)

        # Mark unhealthy if:
        # 1. Error rate > 50%
        # 2. No successful fetch in last 48 hours
        # 3. No entries in last 30 days (for active feeds)

        self.health_check_at = now

        if self.error_rate > 50:
            self.is_healthy = False
            return

        if self.last_fetched_at:
            time_since_fetch = now - self.last_fetched_at
            if time_since_fetch > timedelta(hours=48):
                self.is_healthy = False
                return

        if self.last_entry_date and self.average_entries_per_day > 0:
            time_since_entry = now - self.last_entry_date
            if time_since_entry > timedelta(days=30):
                self.is_healthy = False
                return

        self.is_healthy = True
