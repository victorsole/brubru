"""
DG GROW Database Sync Script

Syncs data from DG GROW databases (NANDO, TRIS, TBT, EMI) to PostgreSQL.

Usage:
    # Full sync (all sources)
    python scripts/sync_dg_grow.py

    # Specific sources
    python scripts/sync_dg_grow.py --source nando
    python scripts/sync_dg_grow.py --source tris --days 14
    python scripts/sync_dg_grow.py --source tbt
    python scripts/sync_dg_grow.py --source emi

    # Filter by country
    python scripts/sync_dg_grow.py --source nando --country BE
    python scripts/sync_dg_grow.py --source tris --country DK

    # Show current stats
    python scripts/sync_dg_grow.py --stats
"""

import asyncio
import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.database import SessionLocal
from services.scrapers.dg_grow.dg_grow_sync_service import DGGrowSyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Sync DG GROW databases")
    parser.add_argument("--source", choices=["nando", "tris", "tbt", "emi", "all"],
                        default="all", help="Data source to sync")
    parser.add_argument("--days", type=int, default=7,
                        help="Look back period for TRIS (default: 7)")
    parser.add_argument("--country", type=str, default=None,
                        help="Country filter (ISO alpha-2)")
    parser.add_argument("--stats", action="store_true",
                        help="Show current database stats and exit")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    db = SessionLocal()

    try:
        service = DGGrowSyncService(db)

        if args.stats:
            stats = service.get_stats()
            print("\n--- DG GROW Database Stats ---")
            for table, count in stats.items():
                print(f"  {table}: {count} records")
            print()
            return

        print(f"\n--- Syncing DG GROW: {args.source} ---")

        if args.source == "nando":
            stats = await service.sync_nando(country=args.country)
        elif args.source == "tris":
            stats = await service.sync_tris(days=args.days, country=args.country)
        elif args.source == "tbt":
            stats = await service.sync_tbt()
        elif args.source == "emi":
            stats = await service.sync_emi()
        else:
            stats = await service.sync_all()

        print(f"\nSync results: {stats}")
        print("\nCurrent database stats:")
        db_stats = service.get_stats()
        for table, count in db_stats.items():
            print(f"  {table}: {count} records")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
