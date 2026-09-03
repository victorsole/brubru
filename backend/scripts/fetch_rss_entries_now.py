"""
Fetch RSS Entries Now

Manually fetches RSS entries from all subscribed feeds.
This is a temporary solution to immediately populate feed entries.

Usage:
    python -m backend.scripts.fetch_rss_entries_now
"""

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import sys
sys.path.insert(0, _REPO_ROOT)

import asyncio
import feedparser
from datetime import datetime
from sqlalchemy.orm import Session
from backend.core.database import SessionLocal
from backend.models.rss_feed import RSSFeed
from backend.models.rss_entry import RSSEntry
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_feed_entries(feed: RSSFeed, db: Session) -> int:
    """Fetch entries from a single feed"""
    try:
        logger.info(f"📥 Fetching: {feed.name}")

        # Fetch feed with proper headers to avoid bot detection
        parsed = feedparser.parse(
            feed.url,
            agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'
        )

        if parsed.bozo:  # Feed parse error
            logger.warning(f"⚠️  Parse warning for {feed.name}: {parsed.bozo_exception}")

        entries_added = 0

        # Process entries
        for entry in parsed.entries[:10]:  # Limit to latest 10 entries
            # Extract basic info
            title = entry.get('title', 'Untitled')
            link = entry.get('link', '')
            summary = entry.get('summary', entry.get('description', ''))

            # Check if entry already exists
            existing = db.query(RSSEntry).filter(
                RSSEntry.link == link
            ).first()

            if existing:
                continue

            # Parse published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])

            # Create entry
            new_entry = RSSEntry(
                feed_id=feed.id,
                title=title,
                link=link,
                summary=summary,
                content=summary,  # Use summary as content for now
                published_at=published_date,
                institution=feed.source,
                categories=[feed.category] if feed.category else []
            )

            db.add(new_entry)
            entries_added += 1

        db.commit()
        logger.info(f"✅ Added {entries_added} entries from {feed.name}")

        # Update feed stats
        feed.last_fetched_at = datetime.now()
        feed.total_entries += entries_added
        feed.fetch_success_count += 1
        db.commit()

        return entries_added

    except Exception as e:
        logger.error(f"❌ Error fetching {feed.name}: {str(e)}")
        feed.fetch_error_count += 1
        feed.last_error = str(e)
        feed.last_error_at = datetime.now()
        db.commit()
        return 0


async def main():
    """Fetch RSS entries from all active feeds"""
    db: Session = SessionLocal()

    try:
        logger.info("=" * 80)
        logger.info("📰 Fetching RSS Entries")
        logger.info("=" * 80)

        # Get all active feeds
        feeds = db.query(RSSFeed).filter(RSSFeed.is_active == True).all()
        logger.info(f"\n📡 Found {len(feeds)} active feeds")

        total_entries = 0

        for feed in feeds:
            entries_added = await fetch_feed_entries(feed, db)
            total_entries += entries_added

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ RSS FETCH COMPLETE")
        logger.info("=" * 80)
        logger.info(f"📊 Summary:")
        logger.info(f"  - Feeds processed: {len(feeds)}")
        logger.info(f"  - Total entries added: {total_entries}")

        logger.info("\n🎯 Next step:")
        logger.info("  Visit http://localhost:3000/my-eu-bubble to see your feed!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
