"""
Email Scheduler

Sends weekly re-engagement emails to inactive users via APScheduler.

Schedule (Monday 09:00 UTC):
- Welcome-back email to a user whose last presence (last_seen_at, else last_login)
  fell 7 to 14 days ago: one email per lapse, not one every Monday for ever.
- First-time welcome to a user created in the last 7 days who has never logged in.

Rules added 16 Oct 2026 (the job had no switch, no dedup and no record):
- REENGAGEMENT_EMAILS_ENABLED=false turns it off (default on).
- Never mails our own or seeded accounts, nor unclaimed pre-provisioned shells
  (same rule as scripts/user_activity_report.INTERNAL_USER_SQL): until then it
  matched 127 accounts every week, prospects we had not contacted included.
- Every run writes a sync_runs row (source_key reengagement_emails), sent or not.
- The scheduler itself starts only on Railway (main.py, in_app_schedulers_enabled).
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from core.database import SessionLocal

logger = logging.getLogger(__name__)

SOURCE_KEY = "reengagement_emails"
LAPSE_DAYS = 7        # a user counts as lapsed after 7 days without presence
WINDOW_DAYS = 7       # ...and is mailed only during the week after that (once)


def reengagement_recipients(db, now: datetime | None = None) -> dict:
    """The two recipient lists, read from the database. No email is sent here.

    Returns {"welcome_back": [(email, name, days_since)], "first_time": [(email, name)]}.
    """
    from scripts.user_activity_report import INTERNAL_USER_SQL
    from services.notifications.notification_email import is_synthetic

    now = now or datetime.now(timezone.utc)
    lapse_end = now - timedelta(days=LAPSE_DAYS)
    lapse_start = lapse_end - timedelta(days=WINDOW_DAYS)
    seen = "COALESCE(u.last_seen_at, u.last_login)"
    base = (f"u.is_active IS TRUE AND u.email IS NOT NULL AND u.email <> '' "
            f"AND NOT {INTERNAL_USER_SQL}")
    back = db.execute(text(
        f"SELECT u.email, u.full_name, {seen} AS seen FROM users u "
        f"WHERE {base} AND {seen} >= :a AND {seen} < :b ORDER BY u.email"),
        {"a": lapse_start, "b": lapse_end}).fetchall()
    first = db.execute(text(
        f"SELECT u.email, u.full_name FROM users u "
        f"WHERE {base} AND u.last_login IS NULL AND u.last_seen_at IS NULL "
        f"AND u.created_at >= :a ORDER BY u.email"),
        {"a": now - timedelta(days=WINDOW_DAYS)}).fetchall()

    def name(email, full_name):
        return full_name or email.split("@")[0]

    return {
        "welcome_back": [(r.email, name(r.email, r.full_name), (now - r.seen).days)
                         for r in back if not is_synthetic(r.email)],
        "first_time": [(r.email, name(r.email, r.full_name))
                       for r in first if not is_synthetic(r.email)],
    }


def _send_reengagement_emails():
    """
    Background job: send re-engagement emails to lapsed users.
    Runs in its own DB session and always leaves a sync_runs row.
    """
    from services.email_service import (
        get_email_service,
        build_welcome_back_email,
        build_first_time_welcome_email,
    )
    from services.sync.freshness import record_run

    started = datetime.now(timezone.utc)
    logger.info("[EMAIL-SCHEDULER] Starting weekly re-engagement run")
    db = SessionLocal()
    try:
        if os.getenv("REENGAGEMENT_EMAILS_ENABLED", "true").strip().lower() in ("false", "0", "no"):
            record_run(db, source_key=SOURCE_KEY, tier="email", status="skipped", items_added=0,
                       error="DISABLED (REENGAGEMENT_EMAILS_ENABLED=false)", started_at=started)
            return
        email_service = get_email_service()
        if not email_service.is_configured:
            logger.warning("[EMAIL-SCHEDULER] SMTP not configured, skipping")
            record_run(db, source_key=SOURCE_KEY, tier="email", status="skipped", items_added=0,
                       error="SMTP not configured", started_at=started)
            return

        lists = reengagement_recipients(db)
        sent = failed = 0
        for email, name, days_since in lists["welcome_back"]:
            data = build_welcome_back_email(user_name=name, days_since_login=days_since)
            if email_service.send(to=email, **data):
                sent += 1
            else:
                failed += 1
        for email, name in lists["first_time"]:
            data = build_first_time_welcome_email(user_name=name)
            if email_service.send(to=email, **data):
                sent += 1
            else:
                failed += 1

        summary = (f"welcome_back={len(lists['welcome_back'])} first_time={len(lists['first_time'])} "
                   f"sent={sent} failed={failed}")
        logger.info(f"[EMAIL-SCHEDULER] Weekly run complete: {summary}")
        record_run(db, source_key=SOURCE_KEY, tier="email",
                   status="failed" if failed and not sent else ("degraded" if failed else "success"),
                   items_added=sent, error=summary, started_at=started)
    except Exception as e:
        logger.error(f"[EMAIL-SCHEDULER] Error during weekly run: {e}")
        try:
            db.rollback()
            record_run(db, source_key=SOURCE_KEY, tier="email", status="failed", items_added=0,
                       error=f"{type(e).__name__}: {e}"[:500], started_at=started)
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Singleton scheduler
# ---------------------------------------------------------------------------

_email_scheduler: AsyncIOScheduler | None = None


def start_email_scheduler():
    """Start the email scheduler (called from app lifespan)."""
    global _email_scheduler

    if _email_scheduler is not None:
        logger.warning("[EMAIL-SCHEDULER] Already running")
        return

    _email_scheduler = AsyncIOScheduler()

    # Every Monday at 09:00 UTC
    _email_scheduler.add_job(
        _send_reengagement_emails,
    # timezone pinned explicitly (10 Sep 2026). A bare `hour=` resolves against
    # the scheduler's default timezone, which is the HOST's local zone, while
    # this file has always documented and logged UTC. Production is a
    # python:3.11-slim container with no TZ set, so it is UTC and this was
    # accidentally correct there; on any other host it silently shifts.
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC"),
        id="weekly_reengagement_email",
        name="Weekly Re-engagement Emails",
        replace_existing=True,
        max_instances=1,
    )

    _email_scheduler.start()
    logger.info("[EMAIL-SCHEDULER] Started (runs every Monday 09:00 UTC)")


def stop_email_scheduler():
    """Stop the email scheduler (called from app lifespan)."""
    global _email_scheduler

    if _email_scheduler:
        _email_scheduler.shutdown(wait=False)
        _email_scheduler = None
        logger.info("[EMAIL-SCHEDULER] Stopped")
