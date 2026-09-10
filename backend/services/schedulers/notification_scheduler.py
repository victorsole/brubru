"""Deliver the notifications Brubru already promised.

WHY THIS EXISTS (U3, 10 September 2026)
---------------------------------------
Tracking is a promise of future notification. On 10 September the `notifications`
table held 103 rows, all of one type, **all for a single recipient**, none read,
and none created since **18 June 2026 -- 84 days**. 70 accounts held tracked items;
69 had never received anything.

The cause was not a bug in either producer. Both work. **Neither had a scheduler.**

  * `CarriageStatusNotifier` (25 Aug 2026) has a CLI wrapper,
    `scripts/notify_carriage_status.py`, and a test suite, and no caller in the
    running application at all.
  * `services.alerts.saved_search_runner.run_all` is reachable only from
    `api/alerts.py`, a manual endpoint. Its last invocation is the 18 June date
    on every one of those 103 rows: somebody hit the endpoint once.

Three schedulers start in `main.py` (RSS, email, amendment sync). Notification
delivery was not one of them, so the feature shipped, was tested, and then simply
never ran.

WHAT THIS DELIVERS TODAY, STATED HONESTLY
-----------------------------------------
Scheduling this does not conjure notifications. Measured on 10 September, a dry
run of the carriage notifier examined 647 tracks and would create **0**: 529 have
a baseline and none of their files has moved, 118 have no baseline yet. The value
is that the next status change reaches the user instead of being lost.

The saved-search side currently has **4 active subscriptions, all belonging to
one seeded test account**. So this scheduler will, for now, mostly deliver to a
fixture. That is a reason to be careful reading the numbers it produces -- never a
reason to leave real accounts unnotified when their files move.

RUNS OFF THE EVENT LOOP, DELIBERATELY
-------------------------------------
Both producers do synchronous database work. `main.py` documents that the RSS
scheduler runs sync fetches on the event loop, blocks the single worker and wedges
the API -- which is why that one is OFF by default. This scheduler does not repeat
that: every job body is handed to `asyncio.to_thread`.

SILENCE IS NOT SUCCESS
----------------------
Each run logs what was PERSISTED, not what was attempted, and a failing producer
is logged at ERROR with its exception type. One producer failing must not stop the
other from running.
"""

from __future__ import annotations

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_notification_scheduler: AsyncIOScheduler | None = None

# UTC, and the timezone is passed to CronTrigger EXPLICITLY. APScheduler
# otherwise resolves a bare `hour=` against the scheduler's default timezone,
# which is the machine's local zone: the first test run of this file scheduled
# 06:00 as 06:00+02:00 while the docstring and the log line both said UTC. It
# would have been right on a UTC container and wrong everywhere else, which is
# luck rather than design.
#
# Early enough that a European user sees the night's movements when they open
# Brubru, late enough that the nightly carriage sweep has finished writing.
_CARRIAGE_HOUR = 6
_SAVED_SEARCH_HOUR = 7


def _run_carriage_notifier() -> dict:
    """Synchronous body; always called via asyncio.to_thread."""
    from core.database import SessionLocal
    from services.notifications.carriage_status_notifier import CarriageStatusNotifier

    db = SessionLocal()
    try:
        run = CarriageStatusNotifier(db).run()
        # Count what was persisted, never what was attempted.
        logger.info("[NOTIFY-SCHED] carriage: %s", run.summary())
        for err in run.errors:
            logger.error("[NOTIFY-SCHED] carriage track failed: %s", err)
        return {"created": run.created, "ok": run.ok, "errors": len(run.errors)}
    finally:
        db.close()


def _run_saved_searches() -> dict:
    from services.alerts.saved_search_runner import run_all

    summary = run_all()
    logger.info(
        "[NOTIFY-SCHED] saved searches: subscriptions_run=%s notifications_created=%s",
        summary.get("subscriptions_run"), summary.get("notifications_created"),
    )
    # A scope nobody implemented is a silent hole in a promise, so it is
    # surfaced at ERROR rather than left in a per-subscription warning.
    unknown = summary.get("unknown_scopes") or {}
    if unknown:
        logger.error(
            "[NOTIFY-SCHED] %d subscribed scope(s) have no handler and delivered "
            "nothing: %s", len(unknown), ", ".join(sorted(unknown)),
        )
    return summary


async def _carriage_job() -> None:
    try:
        await asyncio.to_thread(_run_carriage_notifier)
    except Exception as exc:  # noqa: BLE001 -- one producer must not kill the other
        logger.error("[NOTIFY-SCHED] carriage notifier failed: %s: %s",
                     type(exc).__name__, exc, exc_info=True)


async def _saved_search_job() -> None:
    try:
        await asyncio.to_thread(_run_saved_searches)
    except Exception as exc:  # noqa: BLE001
        logger.error("[NOTIFY-SCHED] saved-search runner failed: %s: %s",
                     type(exc).__name__, exc, exc_info=True)


def start_notification_scheduler() -> None:
    """Start daily notification delivery (called from the app lifespan).

    Opt OUT with ENABLE_NOTIFICATION_SCHEDULER=false. It defaults to ON: the
    whole defect being fixed here is delivery that never ran, and a delivery
    system that is off by default is the same outcome with a different cause.
    """
    global _notification_scheduler

    if os.getenv("ENABLE_NOTIFICATION_SCHEDULER", "true").lower() == "false":
        logger.info("[NOTIFY-SCHED] disabled by ENABLE_NOTIFICATION_SCHEDULER=false")
        return

    if _notification_scheduler is not None:
        logger.warning("[NOTIFY-SCHED] already running")
        return

    _notification_scheduler = AsyncIOScheduler()
    _notification_scheduler.add_job(
        _carriage_job,
        trigger=CronTrigger(hour=_CARRIAGE_HOUR, minute=0, timezone="UTC"),
        id="carriage_status_notifications",
        name="Carriage status notifications",
        replace_existing=True,
        max_instances=1,
        coalesce=True,          # a missed run catches up once, never N times
        misfire_grace_time=3600,
    )
    _notification_scheduler.add_job(
        _saved_search_job,
        trigger=CronTrigger(hour=_SAVED_SEARCH_HOUR, minute=0, timezone="UTC"),
        id="saved_search_notifications",
        name="Saved search alerts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    _notification_scheduler.start()
    logger.info(
        "[NOTIFY-SCHED] started (carriage %02d:00 UTC, saved searches %02d:00 UTC)",
        _CARRIAGE_HOUR, _SAVED_SEARCH_HOUR,
    )


def stop_notification_scheduler() -> None:
    """Stop delivery. Always clears the singleton, even if shutdown raises.

    `AsyncIOScheduler.shutdown()` schedules its own teardown on the event loop it
    was started with, so calling it after that loop has closed raises. If the
    exception escaped, the module-level singleton would stay set and the next
    `start()` would decline as "already running" -- leaving a scheduler that is
    referenced, dead, and silently delivering nothing. That is the shape of the
    bug this whole module exists to fix, so it is contained here rather than
    relying on the caller's try/except.
    """
    global _notification_scheduler
    if not _notification_scheduler:
        return
    try:
        _notification_scheduler.shutdown(wait=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[NOTIFY-SCHED] shutdown raised (%s); clearing anyway: %s",
                       type(exc).__name__, exc)
    finally:
        _notification_scheduler = None
        logger.info("[NOTIFY-SCHED] stopped")
