"""
Daily Brief Email Service

Sends the EU daily brief to subscribers:
1. Welcome email (immediate, on subscription)
2. Daily digest (batch, after /news --save)

Recipients: registered Brubru users + pre-user email captures.
Unsubscribe: users set preferences.daily_brief_unsubscribed = true,
             pre-users are removed from pre_user_events.

Style rules:
- No em-dashes or "--", use colons and commas
- Real hyperlinks to real sources
- Every email gently drives users back to Brubru
"""

import logging
import urllib.parse
from datetime import date
from typing import List, Optional

from services.email_service import EmailService

logger = logging.getLogger(__name__)

BRUBRU_URL = "https://brubru.beresol.eu"
BRUBRU_CHAT_URL = f"{BRUBRU_URL}/chat"
BRUBRU_SIGNUP_URL = f"{BRUBRU_URL}/signup"
BRUBRU_LOGO = f"{BRUBRU_URL}/assets/brubru_mainlogo.png"
API_URL = "https://brubru-production.up.railway.app"


def _category_label(cat: str) -> str:
    labels = {
        "ec": "European Commission",
        "ep": "European Parliament",
        "council": "Council of the EU",
        "ecb": "European Central Bank",
        "agencies": "EU Agencies",
        "cor": "Committee of the Regions",
        "eesc": "Economic and Social Committee",
    }
    return labels.get(cat, "EU Institutions")


def _build_headline_html(headline: str, url: str, source: str, category: str, suggested_query: Optional[str] = None) -> str:
    """Build a single headline row with source link and Brubru query link."""
    cat_label = _category_label(category)
    brubru_link = f"{BRUBRU_CHAT_URL}?q={urllib.parse.quote(suggested_query)}" if suggested_query else BRUBRU_CHAT_URL

    return f"""
    <tr>
      <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
        <a href="{url}" style="color: #111827; text-decoration: none; font-size: 15px; font-weight: 500; line-height: 1.4;">
          {headline}
        </a>
        <div style="margin-top: 4px; font-size: 12px; color: #9ca3af;">
          {cat_label} &middot;
          <a href="{url}" style="color: #6b7280; text-decoration: underline;">Source</a> &middot;
          <a href="{brubru_link}" style="color: #0693e3; text-decoration: underline;">Ask Brubru about this</a>
        </div>
      </td>
    </tr>"""


def _unsubscribe_url(email: str) -> str:
    """Build the unsubscribe URL for this email."""
    encoded = urllib.parse.quote(email)
    return f"{API_URL}/api/daily-brief/unsubscribe?email={encoded}"


def _build_brief_email_html(
    headlines: List[dict],
    brief_date: str,
    email: str,
    is_welcome: bool = False,
    is_registered_user: bool = False,
) -> str:
    """Build the full HTML email for the daily brief."""

    headline_rows = "\n".join(
        _build_headline_html(
            h["headline"], h["url"], h["source"], h["category"],
            h.get("suggested_query")
        )
        for h in headlines
    )

    # Format date nicely
    try:
        d = date.fromisoformat(brief_date)
        formatted_date = d.strftime("%A, %d %B %Y")
    except (ValueError, TypeError):
        formatted_date = brief_date or "Today"

    if is_welcome:
        intro = """
        <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 8px 0;">
          Welcome to the Brubru Daily Brief. Every morning, we scan 44 EU institutional
          news portals and bring you the top headlines that matter for Brussels professionals.
        </p>
        <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
          Here is your first brief:
        </p>"""
    else:
        intro = """
        <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
          Good morning. Here is what is happening in the EU bubble today:
        </p>"""

    # Registered users see "Log in" CTA, pre-users see "Sign up free"
    if is_registered_user:
        bottom_nudge = f"""
      <p style="font-size: 13px; color: #6b7280; line-height: 1.5; margin: 0 0 12px 0;">
        Brubru tracks {_feature_line(False)}
      </p>
      <a href="{BRUBRU_CHAT_URL}" style="font-size: 13px; color: #0693e3; text-decoration: underline;">
        Open Brubru
      </a>"""
    else:
        bottom_nudge = f"""
      <p style="font-size: 13px; color: #6b7280; line-height: 1.5; margin: 0 0 12px 0;">
        Brubru tracks {_feature_line(is_welcome)}
      </p>
      <a href="{BRUBRU_SIGNUP_URL}" style="font-size: 13px; color: #0693e3; text-decoration: underline;">
        Sign up free, no credit card required
      </a>"""

    unsub_link = _unsubscribe_url(email)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; background: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <div style="max-width: 560px; margin: 0 auto; padding: 32px 16px;">

    <!-- Header -->
    <div style="text-align: center; margin-bottom: 24px;">
      <a href="{BRUBRU_URL}">
        <img src="{BRUBRU_LOGO}" alt="Brubru" style="height: 40px; margin-bottom: 12px;" />
      </a>
      <h1 style="font-size: 20px; font-weight: 600; color: #111827; margin: 0 0 4px 0;">
        Daily EU Brief
      </h1>
      <p style="font-size: 13px; color: #9ca3af; margin: 0;">{formatted_date}</p>
    </div>

    <!-- Card -->
    <div style="background: #ffffff; border-radius: 12px; padding: 24px; border: 1px solid #e5e7eb;">
      {intro}

      <!-- Headlines -->
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
        {headline_rows}
      </table>

      <!-- CTA -->
      <div style="text-align: center; margin-top: 24px;">
        <a href="{BRUBRU_CHAT_URL}" style="display: inline-block; padding: 10px 24px; background: #0693e3; color: #ffffff; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 500;">
          Ask Brubru anything about EU policy
        </a>
      </div>
    </div>

    <!-- Features nudge -->
    <div style="text-align: center; margin-top: 20px; padding: 16px;">
      {bottom_nudge}
    </div>

    <!-- Footer -->
    <div style="text-align: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
      <p style="font-size: 11px; color: #9ca3af; margin: 0;">
        Brubru by <a href="https://beresol.eu" style="color: #9ca3af;">Beresol</a> &middot; Brussels, Belgium
      </p>
      <p style="margin: 12px 0 0 0;">
        <a href="{unsub_link}" style="display: inline-block; padding: 6px 16px; font-size: 12px; color: #6b7280; text-decoration: none; border: 1px solid #e5e7eb; border-radius: 6px;">
          Stop receiving this daily brief
        </a>
      </p>
    </div>

  </div>
</body>
</html>"""


def _feature_line(is_welcome: bool) -> str:
    features = [
        "500+ legislative files",
        "29 policy knowledge guides",
        "6 EU institutional calendars",
    ]
    if is_welcome:
        return (
            f"{features[0]}, {features[1]}, and {features[2]}. "
            "Use it to draft amendments, generate briefings, check compliance, and more."
        )
    return f"{features[0]}, {features[1]}, and {features[2]}."


def _fetch_headlines(db_session) -> tuple:
    """Fetch today's (or yesterday's) headlines. Returns (headlines_list, date_string)."""
    from models.daily_brief import DailyBrief
    from datetime import timedelta

    today = date.today().isoformat()
    items = (
        db_session.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority.asc())
        .limit(5)
        .all()
    )

    if not items:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        items = (
            db_session.query(DailyBrief)
            .filter(DailyBrief.brief_date == yesterday)
            .order_by(DailyBrief.priority.asc())
            .limit(5)
            .all()
        )
        brief_date = yesterday
    else:
        brief_date = today

    if not items:
        return [], ""

    headlines = [
        {
            "headline": item.headline,
            "url": item.url,
            "source": item.source,
            "category": item.category,
            "suggested_query": item.suggested_query,
        }
        for item in items
    ]
    return headlines, brief_date


def send_welcome_brief(email: str, db_session) -> bool:
    """Send the welcome email with today's brief. Called on email capture."""
    headlines, brief_date = _fetch_headlines(db_session)

    if not headlines:
        logger.warning("[EMAIL] No daily brief headlines found, skipping welcome email")
        return False

    html = _build_brief_email_html(headlines, brief_date, email, is_welcome=True)

    service = EmailService()
    return service.send(
        to=email,
        subject="Welcome to Brubru: your first EU Daily Brief",
        html_body=html,
    )


def _get_all_recipient_emails(db_session) -> tuple:
    """
    Get all daily brief recipients: registered users + pre-user captures.
    Excludes users who have unsubscribed (preferences.daily_brief_unsubscribed = true).
    Returns (list_of_email_strings, count_registered, count_preuser).
    """
    from models.user import User
    from models.pre_user_event import PreUserEvent
    from sqlalchemy import func

    # 1. Registered users who have NOT unsubscribed
    all_users = db_session.query(User.email, User.preferences).filter(User.email.isnot(None)).all()
    registered_emails = set()
    for email, prefs in all_users:
        if prefs and prefs.get("daily_brief_unsubscribed"):
            continue
        registered_emails.add(email)

    # 2. Pre-user captured emails
    preuser_rows = (
        db_session.query(
            func.distinct(PreUserEvent.event_metadata["email"].astext)
        )
        .filter(PreUserEvent.event_type == "email_captured")
        .all()
    )
    preuser_emails = {r[0] for r in preuser_rows if r[0]}

    # Remove pre-user emails that are already registered (avoid duplicates)
    preuser_only = preuser_emails - registered_emails

    return registered_emails, preuser_only


def send_daily_brief_batch(db_session) -> dict:
    """Send today's brief to all subscribers (users + pre-users). Called from /news routine."""
    headlines, brief_date = _fetch_headlines(db_session)

    if not headlines:
        return {"sent": 0, "error": "No headlines for today"}

    registered_emails, preuser_emails = _get_all_recipient_emails(db_session)
    all_emails = list(registered_emails) + list(preuser_emails)

    if not all_emails:
        return {"sent": 0, "error": "No subscribers yet"}

    service = EmailService()
    sent = 0
    failed = 0

    for email in all_emails:
        try:
            is_registered = email in registered_emails
            html = _build_brief_email_html(
                headlines, brief_date, email,
                is_welcome=False,
                is_registered_user=is_registered,
            )
            success = service.send(
                to=email,
                subject=f"Brubru Daily Brief: {brief_date}",
                html_body=html,
            )
            if success:
                sent += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"[WARN] Failed to send brief to {email[:3]}***: {e}")
            failed += 1

    logger.info(f"[OK] Daily brief sent to {sent}/{len(all_emails)} ({len(registered_emails)} users, {len(preuser_emails)} pre-users)")
    return {
        "sent": sent,
        "failed": failed,
        "registered_users": len(registered_emails),
        "pre_users": len(preuser_emails),
        "total_recipients": len(all_emails),
    }
