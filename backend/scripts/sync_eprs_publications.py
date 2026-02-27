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

Created: February 2026
"""

import asyncio
import argparse
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.eprs_sync_service import EPRSSyncService


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
            return

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
                verbose=True
            )

    except KeyboardInterrupt:
        print("\n[STOP] Sync interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Sync failed: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        await sync.close()


if __name__ == '__main__':
    asyncio.run(main())
