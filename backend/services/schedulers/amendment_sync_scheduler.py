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

    from datetime import datetime, timezone
    from services.sync.freshness import record_run

    db = SessionLocal()
    started = datetime.now(timezone.utc)
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
        # A run that discovered nothing is not a quiet day. EP Open Data answers 200
        # with an error in the body, which used to read as an empty page, so this job
        # stored nothing from 3 May to 28 Sep 2026 while logging success every night
        # and leaving no durable trace at all.
        if result.errors:
            status = "failed"
        elif result.documents_discovered == 0:
            status = "failed"
            result.errors.append("discovered 0 documents: the source is down or changed")
        elif result.documents_failed:
            status = "degraded"
        else:
            status = "success"
        record_run(
            db, source_key="ep_amendments", tier="warm", status=status,
            items_added=result.amendments_stored,
            error="; ".join(result.errors)[:2000] or None,
            started_at=started,
        )
    except Exception as e:
        logger.error(f"[ERROR] Daily amendment sync failed: {e}")
        record_run(db, source_key="ep_amendments", tier="warm", status="failed",
                   error=f"{type(e).__name__}: {e}", started_at=started)
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
    # timezone pinned explicitly (10 Sep 2026). A bare `hour=` resolves against
    # the scheduler's default timezone, which is the HOST's local zone, while
    # this file has always documented and logged UTC. Production is a
    # python:3.11-slim container with no TZ set, so it is UTC and this was
    # accidentally correct there; on any other host it silently shifts.
        trigger=CronTrigger(hour=4, minute=0, timezone="UTC"),
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
