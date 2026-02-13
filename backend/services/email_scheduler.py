"""
Email Scheduler

Sends weekly re-engagement emails to inactive users via APScheduler.

Schedule:
- Every Monday at 09:00 UTC: Welcome-back emails to users inactive 7+ days
- Every Monday at 09:00 UTC: First-time welcome to users who never logged in
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database import SessionLocal
from models.user import User

logger = logging.getLogger(__name__)


def _send_reengagement_emails():
    """
    Background job: send re-engagement emails to inactive users.
    Runs in its own DB session.
    """
    from services.email_service import (
        get_email_service,
        build_welcome_back_email,
        build_first_time_welcome_email,
    )

    logger.info("[EMAIL-SCHEDULER] Starting weekly re-engagement run")

    email_service = get_email_service()
    if not email_service.is_configured:
        logger.warning("[EMAIL-SCHEDULER] SMTP not configured, skipping")
        return

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)

        # Users who logged in before but not in the last 7 days
        inactive_users = db.query(User).filter(
            User.is_active == True,
            User.last_login != None,
            User.last_login < cutoff,
            User.email != None,
            User.role != 'admin',
        ).all()

        # Users who registered but never logged in
        never_logged_in = db.query(User).filter(
            User.is_active == True,
            User.last_login == None,
            User.email != None,
            User.role != 'admin',
        ).all()

        sent = 0
        failed = 0

        for user in inactive_users:
            days_since = (datetime.utcnow() - user.last_login).days
            name = user.full_name or user.email.split("@")[0]
            email_data = build_welcome_back_email(user_name=name, days_since_login=days_since)
            if email_service.send(to=user.email, **email_data):
                sent += 1
            else:
                failed += 1

        for user in never_logged_in:
            name = user.full_name or user.email.split("@")[0]
            email_data = build_first_time_welcome_email(user_name=name)
            if email_service.send(to=user.email, **email_data):
                sent += 1
            else:
                failed += 1

        logger.info(
            f"[EMAIL-SCHEDULER] Weekly run complete: "
            f"{sent} sent, {failed} failed "
            f"({len(inactive_users)} inactive, {len(never_logged_in)} never logged in)"
        )
    except Exception as e:
        logger.error(f"[EMAIL-SCHEDULER] Error during weekly run: {e}")
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
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
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
