"""
RSS Feed Processor

Service for parsing RSS feeds and storing entries in the database.
Part of Phase 5: RSS Feed Aggregation Service

Features:
- Parse RSS/Atom feeds
- Store entries in database
- Duplicate detection
- Feed health monitoring
- Automatic keyword extraction
- Entry quality scoring
- AI-powered content enrichment
"""

# Ensure /app is in path for Cloud Run
import sys
import os
_app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from models.rss_feed import RSSFeed
from models.rss_entry import RSSEntry
from .rss_aggregator import RSSAggregator, AggregatedFeedEntry
from services.ai.content_analyzer import ContentAnalyzer

logger = logging.getLogger(__name__)


class RSSProcessor:
    """
    RSS Feed Processor for parsing and storing RSS entries.

    Responsibilities:
    - Parse RSS/Atom feeds using RSSAggregator
    - Store feed metadata and entries in database
    - Detect and handle duplicates
    - Calculate quality scores
    - Track feed health metrics
    - Update feed statistics
    """

    def __init__(self, db_session: Session, enable_ai_enrichment: bool = True):
        """
        Initialize RSS processor.

        Args:
            db_session: SQLAlchemy database session
            enable_ai_enrichment: Enable AI-powered content enrichment
        """
        self.db = db_session
        self.aggregator = RSSAggregator()
        self.enable_ai_enrichment = enable_ai_enrichment

        # Initialize AI content analyzer if enabled
        if self.enable_ai_enrichment:
            try:
                self.content_analyzer = ContentAnalyzer()
                logger.info("Initialized RSS Processor with AI enrichment enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize ContentAnalyzer: {e}. AI enrichment disabled.")
                self.enable_ai_enrichment = False
                self.content_analyzer = None
        else:
            self.content_analyzer = None
            logger.info("Initialized RSS Processor without AI enrichment")

    async def process_all_feeds(
        self,
        since: Optional[datetime] = None,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """
        Process all RSS feeds from all sources.

        Args:
            since: Only process entries after this date
            force_update: Force update even if feed was recently fetched

        Returns:
            Processing statistics
        """
        logger.info("Processing all RSS feeds")

        stats = {
            "feeds_processed": 0,
            "new_entries": 0,
            "duplicates": 0,
            "errors": 0,
            "sources": {}
        }

        sources = ["european_parliament", "eurlex", "oeil", "council", "think_tank"]

        for source in sources:
            try:
                source_stats = await self.process_source_feeds(source, since, force_update)
                stats["sources"][source] = source_stats
                stats["feeds_processed"] += source_stats.get("feeds_processed", 0)
                stats["new_entries"] += source_stats.get("new_entries", 0)
                stats["duplicates"] += source_stats.get("duplicates", 0)
            except Exception as e:
                logger.error(f"Failed to process source {source}: {str(e)}")
                stats["errors"] += 1

        logger.info(f"Processed all feeds: {stats}")
        return stats

    async def process_source_feeds(
        self,
        source: str,
        since: Optional[datetime] = None,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """
        Process feeds from specific source.

        Args:
            source: Source name (european_parliament, eurlex, etc.)
            since: Only process entries after this date
            force_update: Force update even if feed was recently fetched

        Returns:
            Processing statistics
        """
        logger.info(f"Processing feeds from source: {source}")

        stats = {
            "feeds_processed": 0,
            "new_entries": 0,
            "duplicates": 0
        }

        try:
            # Fetch entries from aggregator
            entries = await self.aggregator.fetch_by_source(source, since)

            # Group entries by feed
            feed_entries: Dict[str, List[AggregatedFeedEntry]] = {}
            for entry in entries:
                feed_key = f"{source}_{entry.feed_name}"
                if feed_key not in feed_entries:
                    feed_entries[feed_key] = []
                feed_entries[feed_key].append(entry)

            # Process each feed
            for feed_key, feed_entry_list in feed_entries.items():
                try:
                    # Get or create feed in database
                    feed = self._get_or_create_feed(source, feed_entry_list[0].feed_name)

                    # Check if feed needs update
                    if not force_update and not feed.is_due_for_fetch:
                        logger.debug(f"Skipping feed {feed_key} - not due for update")
                        continue

                    # Process entries for this feed
                    entry_stats = self._process_feed_entries(feed, feed_entry_list)
                    stats["new_entries"] += entry_stats["new"]
                    stats["duplicates"] += entry_stats["duplicates"]
                    stats["feeds_processed"] += 1

                    # Update feed metadata
                    feed.mark_fetch_success()
                    if feed_entry_list:
                        feed.last_entry_date = max(e.published for e in feed_entry_list)
                        feed.last_updated_at = datetime.now(timezone.utc)

                    # Update statistics
                    self._update_feed_statistics(feed)

                except Exception as e:
                    logger.error(f"Failed to process feed {feed_key}: {str(e)}")
                    if 'feed' in locals():
                        feed.mark_fetch_error(str(e))

            # Commit changes
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to process source {source}: {str(e)}")
            self.db.rollback()
            raise

        return stats

    def _get_or_create_feed(self, source: str, feed_name: str) -> RSSFeed:
        """
        Get existing feed or create new one.

        Args:
            source: Source name
            feed_name: Feed name

        Returns:
            RSSFeed instance
        """
        # Construct feed URL (this would be actual RSS feed URL in production)
        feed_url = f"https://{source}.europa.eu/rss/{feed_name}"

        # Try to find existing feed
        stmt = select(RSSFeed).where(
            and_(
                RSSFeed.source == source,
                RSSFeed.category == feed_name
            )
        )
        feed = self.db.execute(stmt).scalar_one_or_none()

        if not feed:
            # Create new feed
            feed = RSSFeed(
                name=f"{source} - {feed_name}",
                url=feed_url,
                source=source,
                category=feed_name,
                description=f"RSS feed for {source} {feed_name}",
                is_active=True
            )
            self.db.add(feed)
            self.db.flush()  # Get ID without committing
            logger.info(f"Created new RSS feed: {feed.name}")

        return feed

    def _process_feed_entries(
        self,
        feed: RSSFeed,
        entries: List[AggregatedFeedEntry]
    ) -> Dict[str, int]:
        """
        Process and store feed entries.

        Args:
            feed: RSS feed instance
            entries: List of aggregated entries

        Returns:
            Statistics (new, duplicates)
        """
        stats = {"new": 0, "duplicates": 0}

        for agg_entry in entries:
            try:
                # Check if entry already exists
                if self._is_duplicate(feed.id, agg_entry):
                    stats["duplicates"] += 1
                    continue

                # Create new RSS entry
                entry = RSSEntry(
                    feed_id=feed.id,
                    guid=agg_entry.id,
                    link=agg_entry.link,
                    title=agg_entry.title,
                    summary=agg_entry.summary,
                    content=agg_entry.content,
                    author=agg_entry.author or None,
                    published_at=agg_entry.published,
                    categories=agg_entry.categories,
                    language=agg_entry.language or "en",
                    institution=agg_entry.source,
                    is_processed=False
                )

                # Apply AI enrichment if enabled
                if self.enable_ai_enrichment and self.content_analyzer:
                    try:
                        self._enrich_entry_with_ai(entry)
                    except Exception as e:
                        logger.warning(f"AI enrichment failed for entry '{entry.title}': {e}")
                        # Continue without enrichment

                # Process entry (extract keywords, calculate quality)
                entry.mark_as_processed()

                # Add to database
                self.db.add(entry)
                stats["new"] += 1

            except Exception as e:
                logger.error(f"Failed to process entry '{agg_entry.title}': {str(e)}")
                continue

        return stats

    def _is_duplicate(self, feed_id, agg_entry: AggregatedFeedEntry) -> bool:
        """
        Check if entry already exists in database.

        Args:
            feed_id: Feed UUID
            agg_entry: Aggregated entry to check

        Returns:
            True if duplicate exists
        """
        # Check by guid
        if agg_entry.id:
            stmt = select(RSSEntry).where(
                and_(
                    RSSEntry.feed_id == feed_id,
                    RSSEntry.guid == agg_entry.id
                )
            )
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing:
                return True

        # Check by link
        stmt = select(RSSEntry).where(
            and_(
                RSSEntry.feed_id == feed_id,
                RSSEntry.link == agg_entry.link
            )
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            return True

        # Check by title and date (fuzzy match)
        if agg_entry.published:
            # Allow 1 hour window for publication time differences
            time_window_start = agg_entry.published - timedelta(hours=1)
            time_window_end = agg_entry.published + timedelta(hours=1)

            stmt = select(RSSEntry).where(
                and_(
                    RSSEntry.feed_id == feed_id,
                    RSSEntry.title == agg_entry.title,
                    RSSEntry.published_at >= time_window_start,
                    RSSEntry.published_at <= time_window_end
                )
            )
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing:
                return True

        return False

    def _update_feed_statistics(self, feed: RSSFeed):
        """
        Update feed statistics.

        Args:
            feed: RSS feed instance
        """
        # Count total entries
        stmt = select(RSSEntry).where(RSSEntry.feed_id == feed.id)
        total_entries = len(self.db.execute(stmt).scalars().all())
        feed.total_entries = total_entries

        # Calculate average entries per day
        if feed.created_at:
            days_active = (datetime.now(timezone.utc) - feed.created_at).days
            if days_active > 0:
                feed.average_entries_per_day = total_entries // days_active

        # Update health status
        feed.update_health_status()

    async def process_feed_by_url(self, feed_url: str) -> Dict[str, Any]:
        """
        Process specific feed by URL.

        Args:
            feed_url: RSS feed URL

        Returns:
            Processing statistics
        """
        logger.info(f"Processing feed: {feed_url}")

        # This would fetch and parse the specific feed
        # For now, return empty stats
        return {
            "new_entries": 0,
            "duplicates": 0,
            "errors": 0
        }

    def get_recent_entries(
        self,
        hours: int = 24,
        limit: int = 50,
        source: Optional[str] = None
    ) -> List[RSSEntry]:
        """
        Get recent RSS entries from database.

        Args:
            hours: Get entries from last N hours
            limit: Maximum number of entries
            source: Filter by source

        Returns:
            List of RSS entries
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        stmt = select(RSSEntry).where(
            RSSEntry.published_at >= since
        )

        if source:
            stmt = stmt.where(RSSEntry.institution == source)

        stmt = stmt.order_by(RSSEntry.published_at.desc()).limit(limit)

        entries = self.db.execute(stmt).scalars().all()
        return list(entries)

    def get_feed_health_report(self) -> List[Dict[str, Any]]:
        """
        Get health report for all feeds.

        Returns:
            List of feed health metrics
        """
        stmt = select(RSSFeed).where(RSSFeed.is_active == True)
        feeds = self.db.execute(stmt).scalars().all()

        report = []
        for feed in feeds:
            report.append({
                "name": feed.name,
                "source": feed.source,
                "is_healthy": feed.is_healthy,
                "error_rate": feed.error_rate,
                "total_entries": feed.total_entries,
                "last_fetched": feed.last_fetched_at,
                "last_error": feed.last_error,
                "average_entries_per_day": feed.average_entries_per_day
            })

        return report

    def cleanup_old_entries(self, days: int = 90) -> int:
        """
        Archive or delete old RSS entries.

        Args:
            days: Archive entries older than N days

        Returns:
            Number of archived entries
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = select(RSSEntry).where(
            and_(
                RSSEntry.published_at < cutoff_date,
                RSSEntry.is_archived == False
            )
        )

        old_entries = self.db.execute(stmt).scalars().all()

        for entry in old_entries:
            entry.is_archived = True

        self.db.commit()

        logger.info(f"Archived {len(old_entries)} old RSS entries")
        return len(old_entries)

    def _enrich_entry_with_ai(self, entry: RSSEntry):
        """
        Enrich RSS entry with AI-powered analysis.

        Args:
            entry: RSS entry to enrich

        Modifies entry metadata with:
        - Policy area classifications
        - Extracted entities (MEPs, institutions, legislation)
        - CELEX numbers
        - Sentiment analysis
        """
        if not self.content_analyzer:
            return

        content = f"{entry.title}\n\n{entry.summary or ''}\n\n{entry.content or ''}"

        # Classify policy areas
        try:
            policy_areas = self.content_analyzer.classify_policy_areas(
                entry.title,
                entry.summary or entry.content or ""
            )
            if policy_areas:
                # Store in metadata
                if not entry.entry_metadata:
                    entry.entry_metadata = {}
                entry.entry_metadata["policy_areas"] = policy_areas
                logger.debug(f"Classified policy areas for '{entry.title}': {policy_areas}")
        except Exception as e:
            logger.warning(f"Policy classification failed: {e}")

        # Extract entities
        try:
            entities = self.content_analyzer.extract_entities(content)
            if entities:
                if not entry.entry_metadata:
                    entry.entry_metadata = {}
                entry.entry_metadata["entities"] = entities
                logger.debug(f"Extracted {len(entities.get('meps', []))} MEPs, "
                           f"{len(entities.get('institutions', []))} institutions")
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")

        # Detect CELEX numbers
        try:
            celex_numbers = self.content_analyzer.detect_celex_numbers(content)
            if celex_numbers:
                if not entry.entry_metadata:
                    entry.entry_metadata = {}
                entry.entry_metadata["celex_numbers"] = celex_numbers
                logger.debug(f"Detected CELEX numbers: {celex_numbers}")
        except Exception as e:
            logger.warning(f"CELEX detection failed: {e}")

        # Analyze sentiment
        try:
            sentiment = self.content_analyzer.analyze_sentiment(
                entry.title,
                entry.summary or ""
            )
            if sentiment:
                if not entry.entry_metadata:
                    entry.entry_metadata = {}
                entry.entry_metadata["sentiment"] = sentiment
                logger.debug(f"Sentiment for '{entry.title}': {sentiment['label']}")
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")

    async def close(self):
        """Close aggregator connections"""
        await self.aggregator.close()
        logger.info("Closed RSS Processor")
