"""
EU Calendar Sync CLI Script.

Usage:
    python scripts/sync_eu_calendar.py [--source ep|council|commission] [--verbose]

Created: February 2026
"""

import argparse
import asyncio
import logging
import sys
import os

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService


def main():
    parser = argparse.ArgumentParser(description="Sync EU Calendar events")
    parser.add_argument(
        "--source",
        choices=["ep", "council", "commission", "all"],
        default="all",
        help="Source to sync (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year for EP calendar (default: 2025 + 2026)",
    )
    parser.add_argument(
        "--months-ahead",
        type=int,
        default=6,
        help="Months ahead for Council/Commission (default: 6)",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    print("[START] EU Calendar sync")
    service = EUCalendarSyncService()

    if args.source == "all":
        result = service.sync_all()
        print(f"\n[OK] Sync complete:")
        for r in result["results"]:
            print(f"  {r['source']}: +{r['added']} added, ~{r['updated']} updated, "
                  f"={r['skipped']} skipped, !{r['errors']} errors "
                  f"({r.get('duration_seconds', 0):.1f}s)")
        print(f"\n  Total: +{result['total_added']} added, "
              f"~{result['total_updated']} updated, "
              f"!{result['total_errors']} errors")

    elif args.source == "ep":
        years = [args.year] if args.year else [2025, 2026]
        for year in years:
            r = service.sync_ep_calendar(year)
            print(f"[OK] EP {year}: +{r['added']} added, ~{r['updated']} updated")

    elif args.source == "commission":
        r = service.sync_ec_college(args.months_ahead)
        print(f"[OK] EC College: +{r['added']} added, ~{r['updated']} updated")

    elif args.source == "council":
        async def _sync_council():
            return await service.sync_council_meetings(args.months_ahead)

        r = asyncio.run(_sync_council())
        print(f"[OK] Council: +{r['added']} added, ~{r['updated']} updated")

    print("[STOP] EU Calendar sync finished")


if __name__ == "__main__":
    main()
