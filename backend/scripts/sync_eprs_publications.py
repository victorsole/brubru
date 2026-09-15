#!/usr/bin/env python3
"""
Sync EPRS Publications to Database

CLI script to sync European Parliament Research Service publications
from RSS feeds to the PostgreSQL database.

EPRS data is chatbot-only -- no dedicated UI. The context builder
queries this table to inject plain-language explainers into AI context.

Usage:
    # Basic sync (last 14 days, metadata only)
    python scripts/sync_eprs_publications.py

    # Sync last 30 days
    python scripts/sync_eprs_publications.py --days 30

    # Sync with full PDF extraction + ChromaDB indexing (slower)
    python scripts/sync_eprs_publications.py --enrich --days 7 --limit 20

    # Update existing records
    python scripts/sync_eprs_publications.py --update-existing

    # Show database stats
    python scripts/sync_eprs_publications.py --stats

    # Verbose output
    python scripts/sync_eprs_publications.py --verbose

    # Backfill an explicit window (dates inclusive)
    python scripts/sync_eprs_publications.py --since 2026-07-21 --until 2026-09-15

Sources (15 Sep 2026): EP Think Tank portal RSS with the search's date/type
filters -> on a WAF status or unparseable body, the HTML listing -> Playwright
rendering of that listing; plus the epthinktank.eu blog feed.

Exit codes:
    0  every source fetched, every item processed
    1  at least one error (a walled/unparseable source, an upsert or commit failure)
    2  nothing could be fetched from ANY source

Created: February 2026
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.eprs_sync_service import EPRSSyncService


EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_NOTHING_FETCHED = 2


def exit_code_for(stats: dict) -> int:
    """A walled source must never exit 0. 'Skipped' is not evidence of health."""
    if stats.get('nothing_fetched'):
        return EXIT_NOTHING_FETCHED
    if stats.get('errors'):
        return EXIT_ERRORS
    return EXIT_OK


def _date_arg(value: str) -> datetime:
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}")


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


async def main():
    parser = argparse.ArgumentParser(
        description='Sync EPRS publications from RSS feeds to database'
    )
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=14,
        help='Fetch publications from last N days (default: 14)'
    )
    parser.add_argument(
        '--since',
        type=_date_arg,
        help='Start of the window, YYYY-MM-DD (overrides --days)'
    )
    parser.add_argument(
        '--until',
        type=_date_arg,
        help='End of the window, YYYY-MM-DD (default: today)'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=200,
        help='Maximum publications per type to process (default: 200)'
    )
    parser.add_argument(
        '--enrich', '-e',
        action='store_true',
        help='Enable full PDF extraction + ChromaDB indexing (slower)'
    )
    parser.add_argument(
        '--update-existing', '-u',
        action='store_true',
        help='Update publications that already exist in the database'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics and exit'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    sync = EPRSSyncService(enable_pdf_extraction=args.enrich)
    code = EXIT_OK

    try:
        # Stats mode
        if args.stats:
            stats = sync.get_stats()
            print("\n[INFO] EPRS Publications Database Statistics:")
            print(f"  Total publications: {stats['total']}")
            print(f"  With full text:     {stats['with_full_text']}")
            print(f"  Without full text:  {stats['without_full_text']}")
            print(f"\n  By type:")
            for pub_type, count in stats['by_type'].items():
                print(f"    {pub_type}: {count}")
            return EXIT_OK

        # Enriched sync mode
        if args.enrich:
            result = await sync.sync_with_enrichment(
                days=args.days,
                limit=args.limit,
                verbose=True
            )
        else:
            # Standard metadata-only sync
            result = await sync.sync_all(
                days=args.days,
                limit=args.limit,
                skip_existing=not args.update_existing,
                verbose=True,
                since=args.since,
                until=args.until,
            )
        code = exit_code_for(result)
        if code == EXIT_NOTHING_FETCHED:
            print("\n[ERROR] Nothing could be fetched from any EPRS source; the table was not updated.")
        elif code == EXIT_ERRORS:
            print(f"\n[ERROR] EPRS sync finished with {result['errors']} error(s); see details above.")

    except KeyboardInterrupt:
        print("\n[STOP] Sync interrupted by user")
        code = EXIT_ERRORS
    except Exception as e:
        print(f"\n[ERROR] Sync failed: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        code = EXIT_ERRORS
    finally:
        await sync.close()
    return code


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
