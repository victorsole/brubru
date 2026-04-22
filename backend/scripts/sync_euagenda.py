"""Sync third-party events from euagenda.eu into eu_calendar_events.

Usage:
    python3.12 scripts/sync_euagenda.py                        # default: 150 events with details
    python3.12 scripts/sync_euagenda.py --max 50 --no-details  # fast path, listing only
    python3.12 scripts/sync_euagenda.py --max 300              # larger batch
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Sync euagenda.eu events")
    parser.add_argument("--max", type=int, default=150,
                        help="Maximum events to process (default 150)")
    parser.add_argument("--no-details", dest="details", action="store_false",
                        help="Skip detail page fetches (faster, less data)")
    parser.set_defaults(details=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService

    service = EUCalendarSyncService()
    result = await service.sync_euagenda(
        max_events=args.max,
        include_details=args.details,
    )

    print("=" * 60)
    print("euagenda.eu sync result")
    print("=" * 60)
    print(f"  source:  {result.get('source')}")
    print(f"  added:   {result.get('added', 0)}")
    print(f"  updated: {result.get('updated', 0)}")
    print(f"  skipped: {result.get('skipped', 0)}")
    print(f"  errors:  {result.get('errors', 0)}")
    print(f"  time:    {result.get('elapsed_seconds', '?')}s")
    print("=" * 60)

    return 0 if result.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
