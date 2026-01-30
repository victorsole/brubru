#!/usr/bin/env python3
"""
Sync EC Public Consultations

CLI script to sync consultations from the EC "Have Your Say" portal.

Usage:
    # Sync all consultations
    python scripts/sync_consultations.py

    # Sync only open consultations
    python scripts/sync_consultations.py --status open

    # Sync closed consultations
    python scripts/sync_consultations.py --status closed

    # Sync consultations with outcomes
    python scripts/sync_consultations.py --status outcome

    # Control pagination
    python scripts/sync_consultations.py --max-pages 10

    # Dry run (test without database)
    python scripts/sync_consultations.py --dry-run

Created: January 2026
"""

import argparse
import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.consultation_sync_service import ConsultationSyncService
from services.scrapers.public_consultation_scraper import get_public_consultation_scraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def progress_callback(current: int, total: int, message: str):
    """Progress callback for sync operations."""
    print(f"[{current}/{total}] {message}")


async def run_sync(args):
    """Run the sync operation."""
    logger.info(f"[START] EC Public Consultations Sync")
    logger.info(f"[INFO] Status filter: {args.status or 'all'}")
    logger.info(f"[INFO] Max pages per status: {args.max_pages}")
    logger.info(f"[INFO] Skip existing: {args.skip_existing}")

    if args.dry_run:
        logger.info("[INFO] DRY RUN - No database changes will be made")
        # Just fetch and print, don't save
        scraper = get_public_consultation_scraper()

        if args.status == 'open':
            items = await scraper.get_open_consultations(max_pages=args.max_pages)
        elif args.status == 'closed':
            items = await scraper.get_closed_consultations(max_pages=args.max_pages)
        elif args.status == 'outcome':
            items = await scraper.get_consultations_with_outcome(max_pages=args.max_pages)
        else:
            items = await scraper.get_all_consultations(
                max_pages_per_status=args.max_pages,
                progress_callback=progress_callback
            )

        print(f"\n[OK] Found {len(items)} consultations")
        print("\nSample items:")
        for item in items[:5]:
            print(f"  - {item.initiative_id}: {item.title[:60]}...")
            print(f"    Type: {item.consultation_type}, Status: {item.status}")
            if item.end_date:
                print(f"    Deadline: {item.end_date}")
            print()

        return

    # Real sync
    service = ConsultationSyncService()

    if args.status == 'open':
        result = await service.sync_open(
            max_pages=args.max_pages,
            skip_existing=args.skip_existing
        )
    elif args.status == 'closed':
        result = await service.sync_closed(
            max_pages=args.max_pages,
            skip_existing=args.skip_existing
        )
    elif args.status == 'outcome':
        result = await service.sync_outcomes(max_pages=args.max_pages)
    else:
        result = await service.sync_all(
            max_pages_per_status=args.max_pages,
            skip_existing=args.skip_existing,
            progress_callback=progress_callback
        )

    # Print results
    print(f"\n{'='*50}")
    print("SYNC RESULTS")
    print(f"{'='*50}")
    print(f"Added:         {result['added']}")
    print(f"Updated:       {result['updated']}")
    print(f"Skipped:       {result['skipped']}")
    print(f"Errors:        {result['errors']}")
    print(f"Status changes: {result.get('status_changes', 0)}")
    print(f"{'='*50}")

    if result['errors'] > 0:
        logger.warning(f"[WARN] {result['errors']} errors occurred during sync")
        return 1

    logger.info("[OK] Sync completed successfully")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Sync EC Public Consultations from Have Your Say portal"
    )

    parser.add_argument(
        '--status',
        choices=['open', 'closed', 'outcome'],
        default=None,
        help="Filter by consultation status (default: all)"
    )

    parser.add_argument(
        '--max-pages',
        type=int,
        default=5,
        help="Maximum pages to fetch per status (default: 5)"
    )

    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help="Skip consultations that already exist (no update)"
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Test scraping without saving to database"
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        exit_code = asyncio.run(run_sync(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Sync cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"[ERROR] Sync failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
