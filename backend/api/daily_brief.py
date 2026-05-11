"""
Daily EU Brief API

Serves today's EU institutional headlines for the chat page Daily Brief.
Public endpoint (no auth required) -- pre-users need to see this.
"""

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.database import get_db
from models.daily_brief import DailyBrief

router = APIRouter(prefix="/api/daily-brief", tags=["daily-brief"])


class BriefItem(BaseModel):
    headline: str
    url: str
    source: str
    category: str
    snippet: Optional[str] = None
    suggested_query: Optional[str] = None

    model_config = {"from_attributes": True}


class DailyBriefResponse(BaseModel):
    date: str
    items: List[BriefItem]
    total: int


@router.get("", response_model=DailyBriefResponse)
def get_daily_brief(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Get today's EU institutional headlines.

    Falls back to yesterday if no items for today yet (scraper hasn't run).
    Public endpoint -- no auth required.
    """
    today = date.today()

    # Try today first
    items = (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority, DailyBrief.created_at)
        .limit(limit)
        .all()
    )

    brief_date = today

    # Fallback to yesterday if empty
    if not items:
        yesterday = today - timedelta(days=1)
        items = (
            db.query(DailyBrief)
            .filter(DailyBrief.brief_date == yesterday)
            .order_by(DailyBrief.priority, DailyBrief.created_at)
            .limit(limit)
            .all()
        )
        brief_date = yesterday

    # Fallback to most recent date with data
    if not items:
        latest = (
            db.query(DailyBrief.brief_date)
            .order_by(desc(DailyBrief.brief_date))
            .first()
        )
        if latest:
            brief_date = latest[0]
            items = (
                db.query(DailyBrief)
                .filter(DailyBrief.brief_date == brief_date)
                .order_by(DailyBrief.priority, DailyBrief.created_at)
                .limit(limit)
                .all()
            )

    return DailyBriefResponse(
        date=brief_date.isoformat(),
        items=[BriefItem.model_validate(item) for item in items],
        total=len(items),
    )


@router.get("/stats")
def get_brief_stats(db: Session = Depends(get_db)):
    """Knowledge base stats for the chat page badge."""
    from models.legislative_train import LegislativeCarriage

    total_files = db.query(LegislativeCarriage).count()

    # Count knowledge guides
    import os
    guides_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'guides')
    total_guides = len([f for f in os.listdir(guides_dir) if f.endswith('.md')]) if os.path.isdir(guides_dir) else 0

    # Latest brief date
    latest = (
        db.query(DailyBrief.brief_date)
        .order_by(desc(DailyBrief.brief_date))
        .first()
    )

    return {
        "total_guides": total_guides,
        "total_files": total_files,
        "last_trained": latest[0].isoformat() if latest else None,
    }


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_daily_brief(
    email: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Unsubscribe from the daily brief. Works for both registered users and pre-users.
    Returns a simple confirmation page.
    """
    from models.user import User
    from models.pre_user_event import PreUserEvent
    from sqlalchemy import text
    import uuid as _uuid
    from datetime import datetime as _dt

    unsubscribed = False

    # 1. Registered user path: flip preferences flag
    user = db.query(User).filter(User.email == email).first()
    if user:
        prefs = user.preferences or {}
        prefs["daily_brief_unsubscribed"] = True
        user.preferences = prefs
        db.commit()
        unsubscribed = True

    # 2. Pre-user captured email path: remove email_captured rows
    deleted = (
        db.query(PreUserEvent)
        .filter(
            PreUserEvent.event_type == "email_captured",
            PreUserEvent.event_metadata["email"].astext == email,
        )
        .delete(synchronize_session="fetch")
    )
    if deleted > 0:
        db.commit()
        unsubscribed = True

    # 3. EU Transparency Register path: mark org as unsubscribed
    try:
        eutr_updated = db.execute(
            text(
                "UPDATE transparency_register_orgs "
                "SET outreach_status = 'unsubscribed', updated_at = NOW() "
                "WHERE LOWER(contact_email) = LOWER(:e) "
                "  AND outreach_status != 'unsubscribed'"
            ),
            {"e": email},
        ).rowcount
        if eutr_updated:
            db.commit()
            unsubscribed = True
    except Exception:
        db.rollback()

    # 4. ALWAYS log a daily_brief_unsubscribe event, even if email was not
    # found in any of the three pools. This makes the recipient filter
    # in send pipelines authoritative on a single source of truth, and
    # prevents repeat sends to addresses that previously clicked unsubscribe.
    try:
        db.execute(
            text(
                "INSERT INTO pre_user_events "
                "(id, pre_user_id, event_type, event_metadata, created_at) "
                "VALUES (:id, NULL, 'daily_brief_unsubscribe', "
                ":metadata::jsonb, :ts)"
            ),
            {
                "id": str(_uuid.uuid4()),
                "metadata": '{"email": "' + email.replace('"', '') + '"}',
                "ts": _dt.utcnow(),
            },
        )
        db.commit()
        # If none of the three pools matched but the event log went through,
        # treat as a successful unsubscribe (right-to-object honoured at the
        # event-log layer; future sends filter by this event).
        unsubscribed = True
    except Exception:
        db.rollback()

    if unsubscribed:
        message = "You have been unsubscribed from the Brubru Brief."
        sub_message = "You will no longer receive Brubru Brief emails."
    else:
        message = "We could not unsubscribe this email address."
        sub_message = "If you are still receiving emails, please contact hello@beresol.eu."

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Unsubscribe</title></head>
<body style="margin: 0; padding: 0; background: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <div style="max-width: 480px; margin: 80px auto; text-align: center; padding: 32px;">
    <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" style="height: 40px; margin-bottom: 24px;" />
    <h1 style="font-size: 20px; color: #111827; margin: 0 0 12px 0;">{message}</h1>
    <p style="font-size: 15px; color: #6b7280; line-height: 1.5;">{sub_message}</p>
    <a href="https://brubru.beresol.eu" style="display: inline-block; margin-top: 24px; padding: 10px 24px; background: #0693e3; color: #ffffff; text-decoration: none; border-radius: 8px; font-size: 14px;">
      Go to Brubru
    </a>
  </div>
</body>
</html>"""
