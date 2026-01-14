"""
Newsletter Orchestrator

Coordinates newsletter scraping, storage, and indexing.
Manages the full pipeline from scraping to database storage to vector indexing.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.database import SessionLocal
from models.newsletter import (
    NewsletterSource,
    NewsletterContent,
)
from .ec_newsletter_scraper import ECNewsletterScraper
from .newsletter_config import (
    ALL_NEWSLETTERS,
    TIER1_NEWSLETTERS,
    get_newsletters_by_tier,
    get_scrapable_newsletters,
    get_rss_newsletters,
)

logger = logging.getLogger(__name__)


class NewsletterOrchestrator:
    """
    Orchestrates newsletter scraping and storage.

    Handles:
    - Newsletter source initialization
    - Scheduled scraping
    - Content storage and deduplication
    - Error handling and retry logic
    """

    def __init__(self):
        self.scraper = ECNewsletterScraper()
        logger.info("Newsletter Orchestrator initialized")

    async def initialize_sources(self, db: Session, force_update: bool = False):
        """
        Initialize newsletter sources in database from configuration.

        Args:
            db: Database session
            force_update: If True, update existing sources with new config
        """
        logger.info(f"Initializing {len(ALL_NEWSLETTERS)} newsletter sources...")

        sources_created = 0
        sources_updated = 0

        for config in ALL_NEWSLETTERS:
            # Check if source already exists
            existing = db.query(NewsletterSource).filter(
                and_(
                    NewsletterSource.dg_code == config["dg_code"],
                    NewsletterSource.service_id == config["service_id"]
                )
            ).first()

            if existing:
                if force_update:
                    # Update existing source with new config
                    for key, value in config.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.now()
                    sources_updated += 1
                    logger.debug(f"Updated source: {config['newsletter_name']}")
            else:
                # Create new source
                source = NewsletterSource(
                    dg_name=config["dg_name"],
                    newsletter_name=config["newsletter_name"],
                    dg_code=config["dg_code"],
                    service_id=config["service_id"],
                    subscription_url=config.get("subscription_url"),
                    archive_url=config.get("archive_url"),
                    ingestion_method=config["ingestion_method"],
                    rss_feed_url=config.get("rss_feed_url"),
                    publication_frequency=config["publication_frequency"],
                    strategic_tier=config["strategic_tier"],
                    is_active=True,
                    source_metadata={
                        "description": config.get("description", ""),
                        "topics": config.get("topics", []),
                    }
                )
                db.add(source)
                sources_created += 1
                logger.debug(f"Created source: {config['newsletter_name']}")

        db.commit()
        logger.info(f"Sources initialized: {sources_created} created, {sources_updated} updated")

    async def scrape_all_newsletters(
        self,
        db: Session,
        tier: Optional[str] = None,
        limit_per_newsletter: int = 10
    ):
        """
        Scrape all active newsletters.

        Args:
            db: Database session
            tier: If specified, only scrape this tier (e.g., 'tier1')
            limit_per_newsletter: Max items to scrape per newsletter
        """
        # Get active sources
        query = db.query(NewsletterSource).filter(NewsletterSource.is_active == True)

        if tier:
            query = query.filter(NewsletterSource.strategic_tier == tier)

        sources = query.all()

        logger.info(f"Scraping {len(sources)} newsletter sources...")

        total_scraped = 0
        total_saved = 0

        for source in sources:
            try:
                logger.info(f"Scraping: {source.newsletter_name} ({source.dg_code})")

                if source.ingestion_method == "scrape" and source.archive_url:
                    # Web scraping
                    newsletters = await self.scraper.scrape_newsletter_archive(
                        dg_code=source.dg_code,
                        service_id=source.service_id,
                        limit=limit_per_newsletter
                    )

                    saved = await self._save_newsletters(db, source, newsletters)
                    total_scraped += len(newsletters)
                    total_saved += saved

                elif source.ingestion_method == "rss" and source.rss_feed_url:
                    # RSS feed
                    newsletters = await self.scraper.scrape_rss_feed(source.rss_feed_url)

                    saved = await self._save_newsletters(db, source, newsletters)
                    total_scraped += len(newsletters)
                    total_saved += saved

                # Update last_scraped_at
                source.last_scraped_at = datetime.now()
                db.commit()

            except Exception as e:
                logger.error(f"Failed to scrape {source.newsletter_name}: {str(e)}")
                continue

        logger.info(f"Scraping complete: {total_scraped} items scraped, {total_saved} saved to database")

        return {
            "total_scraped": total_scraped,
            "total_saved": total_saved,
            "sources_scraped": len(sources)
        }

    async def _save_newsletters(
        self,
        db: Session,
        source: NewsletterSource,
        newsletters: List[dict]
    ) -> int:
        """
        Save newsletter items to database with deduplication.

        Args:
            db: Database session
            source: Newsletter source
            newsletters: List of newsletter data dictionaries

        Returns:
            Number of items saved
        """
        saved_count = 0

        for item in newsletters:
            try:
                # Check for duplicate by content fingerprint
                existing = db.query(NewsletterContent).filter(
                    NewsletterContent.content_fingerprint == item.get('content_fingerprint')
                ).first()

                if existing:
                    logger.debug(f"Duplicate found, skipping: {item.get('title', '')[:50]}")
                    continue

                # Create new content item
                content = NewsletterContent(
                    source_id=source.id,
                    publication_date=item.get('publication_date') or datetime.now(),
                    title=item.get('title', 'Untitled'),
                    summary=item.get('summary'),
                    full_content=item.get('full_content'),
                    content_type='general',  # Can be enhanced with classification later
                    language='en',
                    original_url=item.get('link'),
                    content_fingerprint=item.get('content_fingerprint'),
                    topics=source.source_metadata.get('topics', []) if source.source_metadata else [],
                    content_metadata=item.get('metadata', {}),
                )

                db.add(content)
                saved_count += 1

            except Exception as e:
                logger.error(f"Failed to save newsletter item: {str(e)}")
                continue

        db.commit()
        logger.info(f"Saved {saved_count} new items for {source.newsletter_name}")

        return saved_count

    async def scrape_sources_due_for_update(self, db: Session):
        """
        Scrape only newsletters that are due for update based on their scrape_interval_hours.

        Args:
            db: Database session
        """
        now = datetime.now()

        # Find sources that need scraping
        sources = db.query(NewsletterSource).filter(
            and_(
                NewsletterSource.is_active == True,
                (NewsletterSource.last_scraped_at == None) |
                (NewsletterSource.last_scraped_at < now - timedelta(hours=NewsletterSource.scrape_interval_hours))
            )
        ).all()

        if not sources:
            logger.info("No newsletters due for update")
            return

        logger.info(f"Found {len(sources)} newsletters due for update")

        total_scraped = 0
        total_saved = 0

        for source in sources:
            try:
                logger.info(f"Updating: {source.newsletter_name}")

                if source.ingestion_method == "scrape" and source.archive_url:
                    newsletters = await self.scraper.scrape_newsletter_archive(
                        dg_code=source.dg_code,
                        service_id=source.service_id,
                        limit=20  # Get more items for regular updates
                    )

                    saved = await self._save_newsletters(db, source, newsletters)
                    total_scraped += len(newsletters)
                    total_saved += saved

                elif source.ingestion_method == "rss" and source.rss_feed_url:
                    newsletters = await self.scraper.scrape_rss_feed(source.rss_feed_url)

                    saved = await self._save_newsletters(db, source, newsletters)
                    total_scraped += len(newsletters)
                    total_saved += saved

                # Update timestamp
                source.last_scraped_at = datetime.now()
                db.commit()

            except Exception as e:
                logger.error(f"Failed to update {source.newsletter_name}: {str(e)}")
                continue

        logger.info(f"Update complete: {total_scraped} items scraped, {total_saved} saved")

        return {
            "total_scraped": total_scraped,
            "total_saved": total_saved,
            "sources_updated": len(sources)
        }

    def get_recent_newsletters(
        self,
        db: Session,
        days: int = 7,
        tier: Optional[str] = None,
        limit: int = 50
    ) -> List[NewsletterContent]:
        """
        Get recent newsletter content.

        Args:
            db: Database session
            days: Number of days to look back
            tier: Filter by strategic tier
            limit: Maximum number of items to return

        Returns:
            List of NewsletterContent objects
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = db.query(NewsletterContent).join(NewsletterSource).filter(
            NewsletterContent.publication_date >= cutoff_date
        )

        if tier:
            query = query.filter(NewsletterSource.strategic_tier == tier)

        query = query.order_by(NewsletterContent.publication_date.desc())

        return query.limit(limit).all()


# Convenience functions for scripts
async def initialize_newsletter_sources(force_update: bool = False):
    """Initialize newsletter sources in database"""
    db = SessionLocal()
    try:
        orchestrator = NewsletterOrchestrator()
        await orchestrator.initialize_sources(db, force_update=force_update)
        logger.info("Newsletter sources initialized successfully")
    finally:
        db.close()


async def scrape_tier1_newsletters():
    """Scrape only Tier 1 (mission-critical) newsletters"""
    db = SessionLocal()
    try:
        orchestrator = NewsletterOrchestrator()
        result = await orchestrator.scrape_all_newsletters(
            db,
            tier="tier1",
            limit_per_newsletter=10
        )
        logger.info(f"Tier 1 scraping complete: {result}")
        return result
    finally:
        db.close()


async def scrape_all_newsletters_full():
    """Scrape all newsletters (all tiers)"""
    db = SessionLocal()
    try:
        orchestrator = NewsletterOrchestrator()
        result = await orchestrator.scrape_all_newsletters(
            db,
            limit_per_newsletter=15
        )
        logger.info(f"Full scraping complete: {result}")
        return result
    finally:
        db.close()


async def update_newsletters():
    """Update newsletters that are due for refresh"""
    db = SessionLocal()
    try:
        orchestrator = NewsletterOrchestrator()
        result = await orchestrator.scrape_sources_due_for_update(db)
        logger.info(f"Newsletter update complete: {result}")
        return result
    finally:
        db.close()
