"""Run the tender matcher, which has had no scheduler since it was written.

WHY THIS EXISTS (11 September 2026)
-----------------------------------
`auto_matching_enabled` is true. Tenders ingest daily and the corpus is fresh to
today. **29 active profiles are waiting.** And the newest row in `tender_matches`
was dated **22 June 2026, 81 days earlier**.

Nothing was broken. `TenderMatcher.match_all_users()` works. It simply had no
caller in the running application: the only triggers are
`POST /api/admin/tenders/run-matching` and `POST /api/tenderator/match`, both
admin-only and both manual. The last time anybody pressed the button was June.

This is the same defect as the notification scheduler fixed on 10 September in
`dec6006f` -- a feature that shipped, was tested, and then never ran -- and this
module follows that one deliberately, including its two hard-won details: an
explicit UTC timezone on the trigger, and a stop() that always clears the
singleton.

WHY THE MATCHER WAS MADE FASTER FIRST
-------------------------------------
Putting a cron in front of the matcher as it stood would have been a new
incident rather than a fix. Three compounding problems, all measured against
production on 11 September:

  1. One SELECT per (profile, tender) pair to test "does this match exist":
     29 x 8,522 = **247,138 round trips**, and it never got cheaper, because a
     pair scoring below the threshold creates no row and is re-queried forever.
  2. `DGGrowEnrichment.get_regulatory_risk_score()` called per PAIR, hitting the
     database each time, for an answer that depends only on the tender's CPV
     category and country -- **72 distinct answers**, recomputed a quarter of a
     million times.
  3. The tender query pulled every column, including `xml_content`: **150 MB for
     8,513 rows, 132 MB of it raw TED XML no scorer reads.** That made the query
     marginal against the 2 minute `statement_timeout` -- it completed once and
     then failed with `canceling statement due to statement timeout`.

After all three: a single profile went from **268 seconds to 22**, and a rerun
creates 0 and is idempotent.

WHAT THIS DELIVERS, STATED HONESTLY
-----------------------------------
The first production run will create a LARGE number of rows, because 81 days of
tenders have accumulated against 29 profiles that have matched none of them. That
is a real backlog landing at once, not a bug, but it should be expected rather
than discovered.

It also delivers those matches to a tab that cannot yet record whether anyone
looked: `is_viewed`, `is_saved`, `is_dismissed`, `is_applied` and `notified_at`
read 0 across all 902 matches ever created, because nothing in api/ or services/
assigns them. Matching without that writing path fills a list nobody is measured
against. Fixing it is a separate change and it is owed.
"""

from __future__ import annotations

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_tender_match_scheduler: AsyncIOScheduler | None = None

# UTC, passed to CronTrigger EXPLICITLY. A bare `hour=` resolves against the
# scheduler's default timezone, which is the host's local zone; three schedulers
# in this repo carried that bug until 10 September. Runs after the nightly TED
# ingest so the day's notices are matchable the same morning.
_MATCH_HOUR = 5


def _run_matcher() -> dict:
    """Synchronous body; always called via asyncio.to_thread.

    `match_all_users` is `async def` but every database call inside it is
    synchronous SQLAlchemy, so awaiting it on the event loop would block the
    single uvicorn worker for the length of the run. main.py already records
    that the RSS scheduler does exactly this and wedges the API, which is why
    that one is disabled. Hence its own loop, inside a thread.
    """
    from core.database import SessionLocal
    from services.tenders.matcher import TenderMatcher

    db = SessionLocal()
    try:
        matcher = TenderMatcher(db)
        created = asyncio.run(matcher.match_all_users())
        # Count what was PERSISTED. match_all_users commits and returns the
        # number of rows it added, not the number of pairs it considered.
        logger.info(
            "[TENDER-SCHED] created %s new match(es); %s distinct risk keys cached",
            created, len(matcher._risk_cache),
        )
        return {"created": created}
    finally:
        db.close()


async def _match_job() -> None:
    try:
        await asyncio.to_thread(_run_matcher)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[TENDER-SCHED] matcher failed: %s: %s", type(exc).__name__, exc, exc_info=True
        )


def start_tender_match_scheduler() -> None:
    """Start daily tender matching (called from the app lifespan).

    Opt OUT with ENABLE_TENDER_MATCH_SCHEDULER=false. Defaults to ON, for the
    same reason the notification scheduler does: the defect being fixed is a
    matcher that never ran, and a matcher that is off by default is that defect
    with a different cause.
    """
    global _tender_match_scheduler

    if os.getenv("ENABLE_TENDER_MATCH_SCHEDULER", "true").lower() == "false":
        logger.info("[TENDER-SCHED] disabled by ENABLE_TENDER_MATCH_SCHEDULER=false")
        return

    if _tender_match_scheduler is not None:
        logger.warning("[TENDER-SCHED] already running")
        return

    _tender_match_scheduler = AsyncIOScheduler()
    _tender_match_scheduler.add_job(
        _match_job,
        trigger=CronTrigger(hour=_MATCH_HOUR, minute=0, timezone="UTC"),
        id="tender_matching",
        name="Tender matching for active profiles",
        replace_existing=True,
        max_instances=1,        # a run can take minutes; never overlap itself
        coalesce=True,          # a missed run catches up once, never N times
        misfire_grace_time=3600,
    )
    _tender_match_scheduler.start()
    logger.info("[TENDER-SCHED] started (matching %02d:00 UTC daily)", _MATCH_HOUR)


def stop_tender_match_scheduler() -> None:
    """Stop matching. Always clears the singleton, even if shutdown raises.

    Same containment as the notification scheduler: if shutdown() raised after
    the loop closed, the singleton would stay set and the next start() would
    decline as "already running", leaving a referenced, dead scheduler matching
    nothing. That is the shape of the bug this module exists to fix.
    """
    global _tender_match_scheduler
    if not _tender_match_scheduler:
        return
    try:
        _tender_match_scheduler.shutdown(wait=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[TENDER-SCHED] shutdown raised (%s); clearing anyway: %s",
            type(exc).__name__, exc,
        )
    finally:
        _tender_match_scheduler = None
        logger.info("[TENDER-SCHED] stopped")
