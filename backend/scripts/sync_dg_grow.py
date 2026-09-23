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

# The paid fallback's key (SCRAPEDO_API_KEY) is in the repo-root .env locally
# and in the environment on Railway; load it without overriding either.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=False)
except ImportError:  # pragma: no cover
    pass

from core.database import SessionLocal
from services.scrapers.dg_grow.dg_grow_sync_service import DGGrowSyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _record_tris(db, stats: dict, started) -> None:
    """One sync_runs row per TRIS run (23 Sep 2026).

    The job ran daily from the cron for six and a half months, re-read the same
    46 notifications, reported "0 new" every day and recorded nothing, so a
    dead feed looked like a quiet one. TRIS publishes most working days, so:
    nothing fetched is a failure, and a newest notification older than 7 days
    is degraded even when the run itself went fine.
    """
    from sqlalchemy import text
    from services.sync.freshness import record_run
    try:
        db.rollback()
    except Exception:  # noqa: BLE001
        pass
    newest_age = db.execute(text(
        "SELECT CURRENT_DATE - max(notification_date) FROM tris_notifications")).scalar()
    if stats.get("error"):
        status, err = "failed", stats["error"]
    elif not stats.get("synced"):
        status, err = "failed", "no TRIS notifications fetched"
    elif stats.get("throttled"):
        status, err = "degraded", (f"TRIS rate limited (429) after back-off; stopped at frontier "
                                   f"{stats.get('frontier_after')}, the next run resumes from there")
    elif stats.get("errors"):
        status, err = "degraded", f"{stats['errors']} notification(s) failed to write"
    elif newest_age is None or newest_age > 7:
        status, err = "degraded", f"newest TRIS notification is {newest_age} days old"
    else:
        status, err = "success", None
    if stats.get("paid_fetches") or stats.get("uncertain_ids"):
        note = (f"{stats.get('paid_fetches', 0)} page(s) via Scrape.do after a 429; "
                f"{stats.get('uncertain_ids', 0)} id(s) unreadable there (missing or failed, "
                f"re-read directly next run)")
        err = f"{err}; {note}" if err else note
    if not err and stats.get("frontier_before") == stats.get("frontier_after"):
        err = f"frontier unchanged at {stats.get('frontier_before')}"  # informative, not a failure
    record_run(db, source_key="tris", tier="daily", status=status,
               items_added=stats.get("new", 0), error=err, started_at=started)


def _record_simple(db, source_key: str, stats: dict, started) -> None:
    """sync_runs row for a list-page source: nothing fetched is a failure."""
    from services.sync.freshness import record_run
    try:
        db.rollback()
    except Exception:  # noqa: BLE001
        pass
    if stats.get("error"):
        status, err = "failed", stats["error"]
    elif not stats.get("synced"):
        status, err = "failed", "nothing fetched"
    elif stats.get("errors"):
        status, err = "degraded", f"{stats['errors']} row(s) failed to write"
    else:
        status, err = "success", None
    record_run(db, source_key=source_key, tier="daily", status=status,
               items_added=stats.get("new", 0), error=err, started_at=started)


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
            import datetime as _dt
            started = _dt.datetime.now(_dt.timezone.utc)
            try:
                stats = await service.sync_tris(days=args.days, country=args.country)
            except Exception as exc:
                _record_tris(db, {"error": f"{type(exc).__name__}: {exc}"[:500]}, started)
                raise
            if not args.country:
                _record_tris(db, stats, started)
        elif args.source == "tbt":
            import datetime as _dt
            started = _dt.datetime.now(_dt.timezone.utc)
            try:
                stats = await service.sync_tbt()
            except Exception as exc:
                _record_simple(db, "wto_tbt", {"error": f"{type(exc).__name__}: {exc}"[:500]}, started)
                raise
            _record_simple(db, "wto_tbt", stats, started)
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
