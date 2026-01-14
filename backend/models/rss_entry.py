"""
RSS Entry Model

SQLAlchemy model for individual RSS feed entries/articles.
Part of Phase 5: RSS Feed Aggregation Service
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class RSSEntry(Base):
    """
    RSS Entry/Article model.

    Stores individual entries from RSS feeds across EU institutions.
    Each entry represents a news item, press release, publication,
    legislative update, or other content item from an RSS feed.

    Features:
    - Full-text search indexing
    - Duplicate detection via guid/link
    - Content categorization and tagging
    - User engagement tracking (saved, read status)
    """
    __tablename__ = "rss_entries"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to RSS feed
    feed_id = Column(UUID(as_uuid=True), ForeignKey("rss_feeds.id", ondelete="CASCADE"), nullable=False, index=True)

    # Entry identification
    guid = Column(String(500), nullable=True, index=True)  # RSS guid (globally unique identifier)
    link = Column(String(1000), nullable=False, index=True)  # Entry URL
    title = Column(String(500), nullable=False)  # Entry title

    # Content
    summary = Column(Text, nullable=True)  # Short description/summary
    content = Column(Text, nullable=True)  # Full content if available
    content_html = Column(Text, nullable=True)  # HTML version of content

    # Metadata
    author = Column(String(200), nullable=True)  # Author/creator
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Original publication date
    updated_at_source = Column(DateTime(timezone=True), nullable=True)  # Last update at source

    # Categorization
    categories = Column(ARRAY(String(100)), nullable=True)  # RSS categories/tags
    keywords = Column(ARRAY(String(100)), nullable=True)  # Extracted keywords
    language = Column(String(5), default="en")  # ISO 639-1 language code

    # Media attachments
    image_url = Column(String(1000), nullable=True)  # Featured image
    enclosures = Column(JSONB, nullable=True)  # Media attachments (podcasts, videos, PDFs)

    # Document type classification
    document_type = Column(String(50), nullable=True, index=True)  # regulation, directive, press_release, etc.
    institution = Column(String(100), nullable=True, index=True)  # Source institution
    policy_area = Column(String(100), nullable=True, index=True)  # Policy domain

    # AI/ML analysis results (Phase 13)
    ai_summary = Column(Text, nullable=True)  # AI-generated summary
    ai_sentiment = Column(String(20), nullable=True)  # positive, negative, neutral
    ai_relevance_score = Column(Integer, nullable=True)  # 0-100 relevance score
    ai_extracted_entities = Column(JSONB, nullable=True)  # Named entities (people, places, orgs)
    ai_topics = Column(ARRAY(String(100)), nullable=True)  # AI-detected topics

    # User engagement
    view_count = Column(Integer, default=0)  # Times viewed
    save_count = Column(Integer, default=0)  # Times saved by users
    share_count = Column(Integer, default=0)  # Times shared

    # Status flags
    is_processed = Column(Boolean, default=False)  # Fully processed and indexed
    is_duplicate = Column(Boolean, default=False)  # Marked as duplicate
    is_archived = Column(Boolean, default=False)  # Archived (old content)
    is_featured = Column(Boolean, default=False)  # Marked as important/featured

    # Quality indicators
    has_full_content = Column(Boolean, default=False)  # Has full text vs just summary
    content_length = Column(Integer, default=0)  # Character count of content
    quality_score = Column(Integer, default=50)  # 0-100 quality score

    # Additional metadata (flexible JSON storage)
    entry_metadata = Column(JSONB, nullable=True)  # Extra entry-specific data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    indexed_at = Column(DateTime(timezone=True), nullable=True)  # When added to search index

    # Relationships
    feed = relationship("RSSFeed", back_populates="entries")

    def __repr__(self):
        return f"<RSSEntry(id={self.id}, title={self.title[:50]})>"

    @property
    def age_days(self) -> int:
        """Calculate age of entry in days"""
        if not self.published_at:
            return 0
        from datetime import datetime, timezone
        delta = datetime.now(timezone.utc) - self.published_at
        return delta.days

    @property
    def is_recent(self) -> bool:
        """Check if entry is from last 7 days"""
        return self.age_days <= 7

    @property
    def is_stale(self) -> bool:
        """Check if entry is older than 90 days"""
        return self.age_days > 90

    @property
    def engagement_score(self) -> int:
        """Calculate engagement score based on views, saves, shares"""
        return (self.view_count * 1) + (self.save_count * 5) + (self.share_count * 10)

    def extract_keywords_from_content(self, max_keywords: int = 10) -> list:
        """
        Extract keywords from title and content.
        Simple implementation - would be enhanced with NLP in Phase 13.
        """
        from collections import Counter
        import re

        text = f"{self.title} {self.summary or ''} {self.content or ''}"
        # Remove special characters and convert to lowercase
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())

        # Filter out common stop words (simple list)
        stop_words = {
            'this', 'that', 'with', 'from', 'have', 'been', 'were', 'which',
            'their', 'would', 'there', 'about', 'should', 'could', 'will'
        }
        words = [w for w in words if w not in stop_words]

        # Get most common words
        counter = Counter(words)
        return [word for word, count in counter.most_common(max_keywords)]

    def calculate_quality_score(self):
        """Calculate quality score based on various factors"""
        score = 50  # Base score

        # Content completeness
        if self.has_full_content:
            score += 20
        if self.content_length > 500:
            score += 10
        if self.content_length > 2000:
            score += 10

        # Metadata completeness
        if self.author:
            score += 5
        if self.categories and len(self.categories) > 0:
            score += 5
        if self.image_url:
            score += 5

        # Freshness
        if self.is_recent:
            score += 10
        elif self.is_stale:
            score -= 20

        # Engagement
        if self.engagement_score > 50:
            score += 10

        # Ensure score is in range 0-100
        self.quality_score = max(0, min(100, score))

    def mark_as_processed(self):
        """Mark entry as fully processed"""
        from datetime import datetime, timezone
        self.is_processed = True
        self.indexed_at = datetime.now(timezone.utc)

        # Update calculated fields
        if self.content:
            self.content_length = len(self.content)
            self.has_full_content = self.content_length > 200

        # Extract keywords if not already done
        if not self.keywords:
            self.keywords = self.extract_keywords_from_content()

        # Calculate quality score
        self.calculate_quality_score()

    def check_duplicate(self, other: 'RSSEntry') -> bool:
        """
        Check if this entry is a duplicate of another.
        Compares guid, link, and title similarity.
        """
        # Exact guid match
        if self.guid and other.guid and self.guid == other.guid:
            return True

        # Exact link match
        if self.link and other.link and self.link == other.link:
            return True

        # Title similarity (simple check - would use fuzzy matching in production)
        if self.title and other.title:
            title1 = self.title.lower().strip()
            title2 = other.title.lower().strip()
            if title1 == title2:
                return True

        return False
