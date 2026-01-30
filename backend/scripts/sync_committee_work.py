#!/usr/bin/env python3
"""
Sync EP Committee Work In Progress Data

CLI script to sync committee work items to the database.

Usage:
    # Sync all committees (default 5 pages each)
    python scripts/sync_committee_work.py

    # Sync specific committees
    python scripts/sync_committee_work.py --committees AFET LIBE ECON

    # Sync with more pages per committee
    python scripts/sync_committee_work.py --max-pages 10

    # Skip existing (don't update)
    python scripts/sync_committee_work.py --skip-existing

    # Verbose output
    python scripts/sync_committee_work.py --verbose

Created: January 2026
"""

import asyncio
import argparse
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.committee_work_sync_service import CommitteeWorkSyncService
from knowledge_base.ep_committees import EP_COMMITTEE_CODES


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def progress_callback(current: int, total: int, message: str):
    """Print progress updates"""
    percent = (current / total) * 100 if total > 0 else 0
    print(f"  [{current}/{total}] ({percent:.1f}%) {message}")


async def main():
    parser = argparse.ArgumentParser(
        description='Sync EP Committee Work in Progress data to database'
    )
    parser.add_argument(
        '--committees', '-c',
        nargs='+',
        help='Specific committee codes to sync (e.g., AFET LIBE ECON)',
        default=None
    )
    parser.add_argument(
        '--max-pages', '-p',
        type=int,
        default=5,
        help='Maximum pages to scrape per committee (default: 5)'
    )
    parser.add_argument(
        '--skip-existing', '-s',
        action='store_true',
        help='Skip items that already exist (no update)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--list-committees',
        action='store_true',
        help='List all available committee codes and exit'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Scrape but do not save to database'
    )

    args = parser.parse_args()

    # List committees option
    if args.list_committees:
        print("\nAvailable EP Committee Codes:\n")
        for code in sorted(EP_COMMITTEE_CODES):
            print(f"  {code}")
        print(f"\nTotal: {len(EP_COMMITTEE_CODES)} committees\n")
        return 0

    setup_logging(args.verbose)

    # Validate committee codes
    committees = None
    if args.committees:
        committees = [c.upper() for c in args.committees]
        invalid = [c for c in committees if c not in EP_COMMITTEE_CODES]
        if invalid:
            print(f"[ERROR] Invalid committee codes: {', '.join(invalid)}")
            print(f"Use --list-committees to see valid codes")
            return 1

    # Summary
    print("\n" + "=" * 60)
    print("EP Committee Work In Progress Sync")
    print("=" * 60)
    print(f"  Committees: {', '.join(committees) if committees else 'All (' + str(len(EP_COMMITTEE_CODES)) + ')'}")
    print(f"  Max pages per committee: {args.max_pages}")
    print(f"  Skip existing: {args.skip_existing}")
    print(f"  Dry run: {args.dry_run}")
    print("=" * 60 + "\n")

    if args.dry_run:
        print("[DRY RUN] Would sync with the above settings (no database changes)")
        # For dry run, just do a test scrape
        from services.scrapers.committee_work_scraper import CommitteeWorkInProgressScraper
        scraper = CommitteeWorkInProgressScraper()
        test_committee = committees[0] if committees else 'AFET'
        print(f"\n[DRY RUN] Testing scrape of {test_committee} (1 page)...")
        items = await scraper.scrape_committee(test_committee, max_pages=1)
        print(f"[DRY RUN] Would process {len(items)} items from {test_committee}")
        return 0

    # Run sync
    try:
        service = CommitteeWorkSyncService()
        result = await service.sync_all(
            max_pages_per_committee=args.max_pages,
            skip_existing=args.skip_existing,
            committees=committees,
            progress_callback=progress_callback if args.verbose else None
        )

        # Print results
        print("\n" + "=" * 60)
        print("Sync Results")
        print("=" * 60)
        print(f"  Added:          {result['added']}")
        print(f"  Updated:        {result['updated']}")
        print(f"  Skipped:        {result['skipped']}")
        print(f"  Status changes: {result.get('status_changes', 0)}")
        print(f"  Errors:         {result['errors']}")
        print("=" * 60 + "\n")

        # Show sample of items if verbose
        if args.verbose and result['items']:
            print("Sample items:")
            for item in result['items'][:5]:
                action = item.get('action', 'unknown')
                ref = item.get('procedure_ref', '')
                code = item.get('committee_code', '')
                print(f"  [{action.upper()}] {ref} ({code})")
            if len(result['items']) > 5:
                print(f"  ... and {len(result['items']) - 5} more")
            print()

        return 0 if result['errors'] == 0 else 1

    except Exception as e:
        print(f"\n[ERROR] Sync failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
