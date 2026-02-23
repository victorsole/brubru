"""
Amendment Sync Scheduler

Daily incremental sync of EP amendment documents from the EP Open Data API.

Schedule: Daily at 04:00 UTC (low-traffic hours).
Fetches new AM/PR documents for the current year and parses their DOCX files.

Follows the same singleton pattern as rss_scheduler.py and email_scheduler.py.

Created: February 2026
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database import SessionLocal

logger = logging.getLogger(__name__)

_amendment_scheduler: AsyncIOScheduler | None = None


async def _daily_amendment_sync():
    """
    Background job: fetch new AM/PR/PA documents from EP Open Data API.
    Runs in its own DB session.
    """
    from services.scrapers.bulk_amendment_sync_service import BulkAmendmentSyncService

    logger.info("[AMENDMENT-SCHEDULER] Starting daily incremental sync")

    db = SessionLocal()
    try:
        service = BulkAmendmentSyncService(db=db)
        result = await service.sync_incremental()

        logger.info(
            f"[OK] Daily amendment sync: "
            f"{result.documents_parsed} docs parsed, "
            f"{result.amendments_stored} amendments stored, "
            f"{result.documents_skipped} skipped, "
            f"{result.documents_failed} failed "
            f"({result.duration_seconds}s)"
        )
    except Exception as e:
        logger.error(f"[ERROR] Daily amendment sync failed: {e}")
    finally:
        db.close()


def start_amendment_sync_scheduler():
    """Start the amendment sync scheduler (called from app lifespan)."""
    global _amendment_scheduler

    if _amendment_scheduler is not None:
        logger.warning("[AMENDMENT-SCHEDULER] Already running")
        return

    _amendment_scheduler = AsyncIOScheduler()

    # Daily at 04:00 UTC
    _amendment_scheduler.add_job(
        _daily_amendment_sync,
        trigger=CronTrigger(hour=4, minute=0),
        id="daily_amendment_sync",
        name="Daily EP Amendment Sync",
        replace_existing=True,
        max_instances=1,
    )

    _amendment_scheduler.start()
    logger.info("[AMENDMENT-SCHEDULER] Started (runs daily at 04:00 UTC)")


def stop_amendment_sync_scheduler():
    """Stop the amendment sync scheduler (called from app lifespan)."""
    global _amendment_scheduler

    if _amendment_scheduler:
        _amendment_scheduler.shutdown(wait=False)
        _amendment_scheduler = None
        logger.info("[AMENDMENT-SCHEDULER] Stopped")
