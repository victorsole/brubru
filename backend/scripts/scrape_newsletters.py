#!/usr/bin/env python3
"""
EC Newsletter Scraper Script

Command-line tool to scrape European Commission newsletters.

Usage:
    # Initialize newsletter sources in database
    python -m backend.scripts.scrape_newsletters --init

    # Scrape Tier 1 newsletters only
    python -m backend.scripts.scrape_newsletters --tier tier1

    # Scrape all newsletters
    python -m backend.scripts.scrape_newsletters --all

    # Update newsletters due for refresh
    python -m backend.scripts.scrape_newsletters --update

    # Get recent newsletters
    python -m backend.scripts.scrape_newsletters --recent --days 7
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.scrapers.newsletter_orchestrator import (
    NewsletterOrchestrator,
    initialize_newsletter_sources,
    scrape_tier1_newsletters,
    scrape_all_newsletters_full,
    update_newsletters,
)
from backend.core.database import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('newsletter_scraper.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description='EC Newsletter Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize newsletter sources in database'
    )

    parser.add_argument(
        '--tier',
        choices=['tier1', 'tier2', 'tier3'],
        help='Scrape specific tier only'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Scrape all newsletters (all tiers)'
    )

    parser.add_argument(
        '--update',
        action='store_true',
        help='Update newsletters due for refresh'
    )

    parser.add_argument(
        '--recent',
        action='store_true',
        help='Show recent newsletter items'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to look back (for --recent)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum items per newsletter to scrape'
    )

    parser.add_argument(
        '--force-update',
        action='store_true',
        help='Force update existing sources when initializing'
    )

    args = parser.parse_args()

    # Initialize sources
    if args.init:
        logger.info("Initializing newsletter sources...")
        await initialize_newsletter_sources(force_update=args.force_update)
        print("\n✅ Newsletter sources initialized successfully!")
        return

    # Scrape specific tier
    if args.tier:
        logger.info(f"Scraping {args.tier} newsletters...")
        db = SessionLocal()
        try:
            orchestrator = NewsletterOrchestrator()
            result = await orchestrator.scrape_all_newsletters(
                db,
                tier=args.tier,
                limit_per_newsletter=args.limit
            )
            print(f"\n✅ Scraping complete!")
            print(f"   Sources scraped: {result['sources_scraped']}")
            print(f"   Items found: {result['total_scraped']}")
            print(f"   New items saved: {result['total_saved']}")
        finally:
            db.close()
        return

    # Scrape all newsletters
    if args.all:
        logger.info("Scraping all newsletters...")
        result = await scrape_all_newsletters_full()
        print(f"\n✅ Full scraping complete!")
        print(f"   Sources scraped: {result['sources_scraped']}")
        print(f"   Items found: {result['total_scraped']}")
        print(f"   New items saved: {result['total_saved']}")
        return

    # Update newsletters
    if args.update:
        logger.info("Updating newsletters due for refresh...")
        result = await update_newsletters()
        if result:
            print(f"\n✅ Update complete!")
            print(f"   Sources updated: {result['sources_updated']}")
            print(f"   Items found: {result['total_scraped']}")
            print(f"   New items saved: {result['total_saved']}")
        else:
            print("\nℹ️  No newsletters due for update")
        return

    # Show recent newsletters
    if args.recent:
        logger.info(f"Fetching recent newsletters (last {args.days} days)...")
        db = SessionLocal()
        try:
            orchestrator = NewsletterOrchestrator()
            newsletters = orchestrator.get_recent_newsletters(
                db,
                days=args.days,
                limit=50
            )

            print(f"\n📰 Recent Newsletters (last {args.days} days): {len(newsletters)} items\n")
            print("-" * 80)

            for item in newsletters:
                print(f"\n{item.title}")
                print(f"   Source: {item.source.newsletter_name} ({item.source.dg_name})")
                print(f"   Date: {item.publication_date.strftime('%Y-%m-%d %H:%M')}")
                if item.summary:
                    print(f"   Summary: {item.summary[:100]}...")
                if item.original_url:
                    print(f"   URL: {item.original_url}")
                print(f"   Topics: {', '.join(item.topics) if item.topics else 'None'}")

            print("\n" + "-" * 80)
            print(f"Total: {len(newsletters)} items")

        finally:
            db.close()
        return

    # No arguments provided
    parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
