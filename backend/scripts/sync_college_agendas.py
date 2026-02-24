"""
Sync Commission College Published Agendas (OJ Documents).

Fetches published "Ordre du Jour" documents from the EC Register of
Commission Documents and enriches existing calendar events with
agenda metadata (location, meeting number, document links).

Usage:
    python scripts/sync_college_agendas.py [--days-back 90] [--year 2026] [--verbose]

Created: February 2026
"""

import argparse
import asyncio
import logging
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.college_oj_sync_service import CollegeOJSyncService


def main():
    parser = argparse.ArgumentParser(
        description="Sync Commission College published agendas (OJ documents)"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=90,
        help="How many days back to scan for agendas (default: 90)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Year for OJ references (default: 2026)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"[START] Syncing Commission College agendas")
    print(f"  Days back: {args.days_back}")
    print(f"  Year: {args.year}")
    print()

    service = CollegeOJSyncService()
    result = asyncio.run(
        service.sync_college_agendas(
            days_back=args.days_back,
            year=args.year,
            verbose=args.verbose,
        )
    )

    print()
    print(f"[DONE] Results:")
    print(f"  Updated:  {result['updated']}")
    print(f"  Skipped:  {result['skipped']}")
    print(f"  Errors:   {result['errors']}")
    print(f"  Duration: {result.get('duration_seconds', '?')}s")


if __name__ == "__main__":
    main()
