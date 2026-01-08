"""
RSS Feed Scheduler

Background task scheduler for polling RSS feeds at regular intervals.
Part of My EU Bubble - Phase 1: RSS Feed Infrastructure

Features:
- Scheduled polling based on feed priorities
- Concurrent feed fetching
- Error handling and retry logic
- Feed health monitoring
- Configurable polling intervals
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from .rss_aggregator import RSSAggregator
from .rss_processor import RSSProcessor
from ...core.database import SessionLocal

logger = logging.getLogger(__name__)


class RSSScheduler:
    """
    RSS Feed Scheduler for background polling.

    Manages scheduled fetching of RSS feeds from all sources
    based on configured polling intervals and priorities.
    """

    def __init__(self):
        """Initialize RSS scheduler"""
        self.scheduler = AsyncIOScheduler()
        self.aggregator = RSSAggregator()
        self.is_running = False

        # Polling intervals (in minutes)
        self.polling_intervals = {
            "breaking_news": 15,  # Euractiv, Politico Europe
            "institutional_news": 30,  # EP, Council, Euronews
            "research": 60,  # Think Tank, JRC
        }

        logger.info("Initialized RSS Scheduler")

    def start(self):
        """Start the RSS feed scheduler"""
        if self.is_running:
            logger.warning("RSS Scheduler already running")
            return

        logger.info("Starting RSS Scheduler")

        # Schedule breaking news sources (every 15 minutes)
        self.scheduler.add_job(
            self._fetch_breaking_news,
            trigger=IntervalTrigger(minutes=self.polling_intervals["breaking_news"]),
            id="breaking_news_feeds",
            name="Fetch Breaking News Feeds",
            replace_existing=True,
            max_instances=1
        )

        # Schedule institutional news (every 30 minutes)
        self.scheduler.add_job(
            self._fetch_institutional_news,
            trigger=IntervalTrigger(minutes=self.polling_intervals["institutional_news"]),
            id="institutional_news_feeds",
            name="Fetch Institutional News Feeds",
            replace_existing=True,
            max_instances=1
        )

        # Schedule research publications (every 60 minutes)
        self.scheduler.add_job(
            self._fetch_research_feeds,
            trigger=IntervalTrigger(minutes=self.polling_intervals["research"]),
            id="research_feeds",
            name="Fetch Research Feeds",
            replace_existing=True,
            max_instances=1
        )

        # Schedule feed health check (every 6 hours)
        self.scheduler.add_job(
            self._check_feed_health,
            trigger=IntervalTrigger(hours=6),
            id="feed_health_check",
            name="Check Feed Health",
            replace_existing=True,
            max_instances=1
        )

        # Schedule cleanup of old entries (daily at 3 AM)
        self.scheduler.add_job(
            self._cleanup_old_entries,
            trigger='cron',
            hour=3,
            minute=0,
            id="cleanup_old_entries",
            name="Cleanup Old Entries",
            replace_existing=True
        )

        # Start scheduler
        self.scheduler.start()
        self.is_running = True

        logger.info("RSS Scheduler started successfully")

    def stop(self):
        """Stop the RSS feed scheduler"""
        if not self.is_running:
            logger.warning("RSS Scheduler not running")
            return

        logger.info("Stopping RSS Scheduler")

        self.scheduler.shutdown(wait=True)
        self.is_running = False

        logger.info("RSS Scheduler stopped")

    async def _fetch_breaking_news(self):
        """Fetch breaking news from Euractiv, Politico Europe"""
        logger.info("Fetching breaking news feeds")

        db = SessionLocal()
        try:
            processor = RSSProcessor(db)

            # Fetch from news media sources
            sources = ["euractiv", "politico_europe"]

            for source in sources:
                try:
                    stats = await processor.process_source_feeds(
                        source=source,
                        force_update=True
                    )
                    logger.info(f"Processed {source}: {stats}")
                except Exception as e:
                    logger.error(f"Failed to process {source}: {str(e)}")

            await processor.close()

        except Exception as e:
            logger.error(f"Failed to fetch breaking news: {str(e)}")
        finally:
            db.close()

    async def _fetch_institutional_news(self):
        """Fetch news from European Parliament, Council, Euronews"""
        logger.info("Fetching institutional news feeds")

        db = SessionLocal()
        try:
            processor = RSSProcessor(db)

            # Fetch from institutional sources
            sources = ["european_parliament", "council", "euronews_europe"]

            for source in sources:
                try:
                    stats = await processor.process_source_feeds(
                        source=source,
                        force_update=False  # Respect feed schedule
                    )
                    logger.info(f"Processed {source}: {stats}")
                except Exception as e:
                    logger.error(f"Failed to process {source}: {str(e)}")

            await processor.close()

        except Exception as e:
            logger.error(f"Failed to fetch institutional news: {str(e)}")
        finally:
            db.close()

    async def _fetch_research_feeds(self):
        """Fetch research publications from Think Tank, JRC"""
        logger.info("Fetching research feeds")

        db = SessionLocal()
        try:
            processor = RSSProcessor(db)

            # Fetch from research sources
            sources = ["think_tank", "jrc"]

            for source in sources:
                try:
                    stats = await processor.process_source_feeds(
                        source=source,
                        force_update=False
                    )
                    logger.info(f"Processed {source}: {stats}")
                except Exception as e:
                    logger.error(f"Failed to process {source}: {str(e)}")

            await processor.close()

        except Exception as e:
            logger.error(f"Failed to fetch research feeds: {str(e)}")
        finally:
            db.close()

    async def _check_feed_health(self):
        """Check health status of all feeds"""
        logger.info("Checking feed health")

        db = SessionLocal()
        try:
            processor = RSSProcessor(db)

            health_report = processor.get_feed_health_report()

            # Log unhealthy feeds
            unhealthy_feeds = [
                feed for feed in health_report
                if not feed['is_healthy']
            ]

            if unhealthy_feeds:
                logger.warning(f"Found {len(unhealthy_feeds)} unhealthy feeds:")
                for feed in unhealthy_feeds:
                    logger.warning(
                        f"  - {feed['name']}: error_rate={feed['error_rate']:.1f}%, "
                        f"last_error={feed['last_error']}"
                    )
            else:
                logger.info("All feeds are healthy")

            await processor.close()

        except Exception as e:
            logger.error(f"Failed to check feed health: {str(e)}")
        finally:
            db.close()

    async def _cleanup_old_entries(self):
        """Clean up old RSS entries (archive entries older than 90 days)"""
        logger.info("Cleaning up old entries")

        db = SessionLocal()
        try:
            processor = RSSProcessor(db)

            archived_count = processor.cleanup_old_entries(days=90)

            logger.info(f"Archived {archived_count} old entries")

            await processor.close()

        except Exception as e:
            logger.error(f"Failed to cleanup old entries: {str(e)}")
        finally:
            db.close()

    async def fetch_now(self, sources: list = None) -> Dict[str, Any]:
        """
        Manually trigger feed fetch immediately.

        Args:
            sources: List of sources to fetch, or None for all

        Returns:
            Statistics about the fetch operation
        """
        logger.info(f"Manual fetch triggered for sources: {sources or 'all'}")

        db = SessionLocal()
        try:
            processor = RSSProcessor(db)

            if sources:
                stats = {}
                for source in sources:
                    source_stats = await processor.process_source_feeds(
                        source=source,
                        force_update=True
                    )
                    stats[source] = source_stats
            else:
                stats = await processor.process_all_feeds(force_update=True)

            await processor.close()

            return stats

        except Exception as e:
            logger.error(f"Failed manual fetch: {str(e)}")
            raise
        finally:
            db.close()

    def get_job_status(self) -> Dict[str, Any]:
        """
        Get status of scheduled jobs.

        Returns:
            Dictionary with job information
        """
        jobs = self.scheduler.get_jobs()

        return {
            "is_running": self.is_running,
            "total_jobs": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in jobs
            ]
        }


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> RSSScheduler:
    """Get global RSS scheduler instance"""
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = RSSScheduler()

    return _scheduler_instance


def start_scheduler():
    """Start the global RSS scheduler"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global RSS scheduler"""
    global _scheduler_instance

    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None
