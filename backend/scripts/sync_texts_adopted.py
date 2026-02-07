"""
CLI script to sync EP Texts Adopted to the database.

Usage:
    # Sync from RSS feed (recent texts)
    python scripts/sync_texts_adopted.py --rss

    # Sync specific parliamentary term
    python scripts/sync_texts_adopted.py --term 10

    # Sync all terms (full historical backfill)
    python scripts/sync_texts_adopted.py --all-terms

    # Limit dates per term
    python scripts/sync_texts_adopted.py --term 10 --max-dates 5

    # Dry run (test without database)
    python scripts/sync_texts_adopted.py --rss --dry-run

Created: February 2026
"""

import asyncio
import argparse
import logging
import sys
import os
import time

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def progress_callback(current: int, total: int, message: str):
    """Print progress updates."""
    print(f"  [{current}/{total}] {message}")


async def run_rss_sync(dry_run: bool = False):
    """Sync from RSS feed."""
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

    scraper = TextsAdoptedScraper()
    items = await scraper.fetch_rss()

    print(f"\n[INFO] Fetched {len(items)} items from RSS feed")

    for item in items[:10]:
        print(f"  - {item.ta_reference}: {item.title[:80]}")
        if item.procedure_ref:
            print(f"    Procedure: {item.procedure_ref}")
        print(f"    Type: {item.text_type}, Date: {item.adoption_date.strftime('%Y-%m-%d')}")

    if len(items) > 10:
        print(f"  ... and {len(items) - 10} more")

    if dry_run:
        print("\n[DRY RUN] No database changes made")
        return

    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    service = TextsAdoptedSyncService()
    result = await service.sync_rss(skip_existing=False)

    print(f"\n[OK] RSS sync complete:")
    print(f"  Added: {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")


async def run_term_sync(term: int, max_dates: int = None, dry_run: bool = False):
    """Sync a specific parliamentary term."""
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

    scraper = TextsAdoptedScraper()

    print(f"\n[INFO] Getting plenary dates for term {term}...")
    dates = await scraper.get_plenary_dates(term)
    print(f"[INFO] Found {len(dates)} plenary dates")

    if max_dates:
        dates = dates[:max_dates]
        print(f"[INFO] Limited to {max_dates} dates")

    items = await scraper.scrape_term(
        term=term,
        max_dates=max_dates,
        progress_callback=progress_callback
    )

    print(f"\n[INFO] Scraped {len(items)} items from term {term}")

    # Show sample
    for item in items[:5]:
        print(f"  - {item.ta_reference}: {item.title[:80]}")

    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

    if dry_run:
        print("\n[DRY RUN] No database changes made")
        return

    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    service = TextsAdoptedSyncService()
    result = await service.sync_term(
        term=term,
        max_dates=max_dates,
        skip_existing=True,
        progress_callback=progress_callback
    )

    print(f"\n[OK] Term {term} sync complete:")
    print(f"  Added: {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")


async def run_all_terms_sync(max_dates: int = None, dry_run: bool = False):
    """Sync all parliamentary terms."""
    if dry_run:
        from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
        from schemas.scrapers.texts_adopted_schemas import PARLIAMENTARY_TERMS

        scraper = TextsAdoptedScraper()

        for term in sorted(PARLIAMENTARY_TERMS.keys(), reverse=True):
            print(f"\n--- Term {term} ({PARLIAMENTARY_TERMS[term]['years']}) ---")
            dates = await scraper.get_plenary_dates(term)
            print(f"  Plenary dates: {len(dates)}")
            if dates:
                print(f"  Latest: {dates[0]}, Earliest: {dates[-1]}")

        print("\n[DRY RUN] No database changes made")
        return

    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    service = TextsAdoptedSyncService()
    result = await service.sync_all(
        max_dates_per_term=max_dates,
        skip_existing=True,
        progress_callback=progress_callback
    )

    print(f"\n[OK] All terms sync complete:")
    print(f"  Terms synced: {result['terms_synced']}")
    print(f"  Added: {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")


def main():
    parser = argparse.ArgumentParser(description="Sync EP Texts Adopted to database")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--rss', action='store_true', help='Sync from RSS feed (recent texts)')
    group.add_argument('--term', type=int, choices=range(4, 11), help='Sync specific term (4-10)')
    group.add_argument('--all-terms', action='store_true', help='Sync all terms (historical backfill)')

    parser.add_argument('--max-dates', type=int, help='Max plenary dates to scrape per term')
    parser.add_argument('--dry-run', action='store_true', help='Test without database writes')

    args = parser.parse_args()

    start_time = time.time()

    if args.rss:
        print("[START] Syncing Texts Adopted from RSS feed...")
        asyncio.run(run_rss_sync(dry_run=args.dry_run))
    elif args.term:
        print(f"[START] Syncing Texts Adopted for term {args.term}...")
        asyncio.run(run_term_sync(args.term, max_dates=args.max_dates, dry_run=args.dry_run))
    elif args.all_terms:
        print("[START] Syncing Texts Adopted for ALL terms...")
        asyncio.run(run_all_terms_sync(max_dates=args.max_dates, dry_run=args.dry_run))

    duration = time.time() - start_time
    print(f"\n[DONE] Completed in {duration:.1f}s")


if __name__ == "__main__":
    main()
