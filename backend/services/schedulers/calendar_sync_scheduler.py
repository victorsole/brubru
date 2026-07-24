"""
EU Calendar Sync Scheduler

Daily sync of the My EU Bubble calendar from all sources (EP plenary + committee
agendas, Council configurations, EC College + tentative agendas, DG events, ...).

Schedule: Daily at 05:00 UTC (after the 04:00 amendment sync, low-traffic hours).

CRITICAL DESIGN NOTE
--------------------
`EUCalendarSyncService.sync_all()` is a SYNCHRONOUS method that also calls
`asyncio.run()` internally for the async sub-syncs (Council, committee/college
agendas). Running it directly inside this async job would (a) block the single
prod web worker's event loop for the whole scrape -- the exact event-loop
starvation that wedged prod on 2 Jul -- and (b) crash, because `asyncio.run()`
cannot be called from an already-running loop.

Both problems are solved by running the whole blocking call in a worker thread
via `asyncio.to_thread`: the event loop stays free, and the fresh thread has no
running loop so the nested `asyncio.run()` calls work. This is the same
"offload blocking sync to a thread" rule that keeps the RSS scheduler from
wedging the API.

Follows the same singleton pattern as amendment_sync_scheduler.py.

Created: 24 July 2026 (Council calendar had gone stale since 22 Feb 2026).
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_calendar_scheduler: AsyncIOScheduler | None = None


def _run_sync_blocking() -> dict:
    """
    Blocking full-calendar sync. MUST run in a worker thread (no running event
    loop) because sync_all() uses asyncio.run() internally. Manages its own DB
    sessions exactly like the CLI (scripts/sync_eu_calendar.py).
    """
    from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService

    service = EUCalendarSyncService()
    return service.sync_all()


async def _daily_calendar_sync():
    """Background job: refresh every calendar source. Never blocks the loop."""
    logger.info("[CALENDAR-SCHEDULER] Starting daily calendar sync")

    try:
        result = await asyncio.to_thread(_run_sync_blocking)
        logger.info(
            f"[OK] Daily calendar sync: "
            f"+{result.get('total_added', 0)} added, "
            f"~{result.get('total_updated', 0)} updated, "
            f"!{result.get('total_errors', 0)} errors"
        )
        for r in result.get("results", []):
            logger.info(
                f"[CALENDAR-SCHEDULER]   {r.get('source')}: "
                f"+{r.get('added', 0)} ~{r.get('updated', 0)} !{r.get('errors', 0)}"
            )
    except Exception as e:
        logger.error(f"[ERROR] Daily calendar sync failed: {e}")


def start_calendar_sync_scheduler():
    """Start the calendar sync scheduler (called from app lifespan)."""
    global _calendar_scheduler

    if _calendar_scheduler is not None:
        logger.warning("[CALENDAR-SCHEDULER] Already running")
        return

    _calendar_scheduler = AsyncIOScheduler()

    # Daily at 05:00 UTC (after the 04:00 amendment sync).
    _calendar_scheduler.add_job(
        _daily_calendar_sync,
        trigger=CronTrigger(hour=5, minute=0),
        id="daily_calendar_sync",
        name="Daily EU Calendar Sync",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,  # still run if the worker was busy at 05:00
    )

    _calendar_scheduler.start()
    logger.info("[CALENDAR-SCHEDULER] Started (runs daily at 05:00 UTC)")


def stop_calendar_sync_scheduler():
    """Stop the calendar sync scheduler (called from app lifespan)."""
    global _calendar_scheduler

    if _calendar_scheduler:
        _calendar_scheduler.shutdown(wait=False)
        _calendar_scheduler = None
        logger.info("[CALENDAR-SCHEDULER] Stopped")
