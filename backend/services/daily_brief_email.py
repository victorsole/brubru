"""
Daily Brief Email Service

Sends the EU daily brief to subscribers:
1. Welcome email (immediate, on subscription)
2. Daily digest (batch, after /news --save)

Style rules:
- No em-dashes or "--", use colons and commas
- Real hyperlinks to real sources
- Every email gently drives users back to Brubru
"""

import logging
from datetime import date
from typing import List, Optional

from services.email_service import EmailService

logger = logging.getLogger(__name__)

BRUBRU_URL = "https://brubru.beresol.eu"
BRUBRU_CHAT_URL = f"{BRUBRU_URL}/chat"
BRUBRU_SIGNUP_URL = f"{BRUBRU_URL}/signup"
BRUBRU_LOGO = f"{BRUBRU_URL}/assets/brubru_mainlogo.png"


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
    brubru_link = f"{BRUBRU_CHAT_URL}?q={suggested_query}" if suggested_query else BRUBRU_CHAT_URL

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


def _build_brief_email_html(
    headlines: List[dict],
    brief_date: str,
    is_welcome: bool = False,
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
        intro = f"""
        <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 8px 0;">
          Welcome to the Brubru Daily Brief. Every morning, we scan 44 EU institutional
          news portals and bring you the top headlines that matter for Brussels professionals.
        </p>
        <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
          Here is your first brief:
        </p>"""
    else:
        intro = f"""
        <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
          Good morning. Here is what is happening in Brussels today:
        </p>"""

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
      <p style="font-size: 13px; color: #6b7280; line-height: 1.5; margin: 0 0 12px 0;">
        Brubru tracks {_feature_line(is_welcome)}
      </p>
      <a href="{BRUBRU_SIGNUP_URL}" style="font-size: 13px; color: #0693e3; text-decoration: underline;">
        Sign up free, no credit card required
      </a>
    </div>

    <!-- Footer -->
    <div style="text-align: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
      <p style="font-size: 11px; color: #9ca3af; margin: 0;">
        Brubru by <a href="https://beresol.eu" style="color: #9ca3af;">Beresol</a> &middot; Brussels, Belgium
      </p>
      <p style="font-size: 11px; color: #9ca3af; margin: 4px 0 0 0;">
        You subscribed to this brief via <a href="{BRUBRU_URL}" style="color: #9ca3af;">brubru.beresol.eu</a>
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


def send_welcome_brief(email: str, db_session) -> bool:
    """Send the welcome email with today's brief. Called on email capture."""
    from models.daily_brief import DailyBrief

    # Fetch today's headlines
    today = date.today().isoformat()
    items = (
        db_session.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority.asc())
        .limit(5)
        .all()
    )

    if not items:
        # Try yesterday
        from datetime import timedelta
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
        logger.warning("[EMAIL] No daily brief headlines found, skipping welcome email")
        return False

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

    html = _build_brief_email_html(headlines, brief_date, is_welcome=True)

    service = EmailService()
    return service.send(
        to=email,
        subject=f"Welcome to Brubru: your first EU Daily Brief",
        html_body=html,
    )


def send_daily_brief_batch(db_session) -> dict:
    """Send today's brief to all captured emails. Called from /news routine."""
    from models.daily_brief import DailyBrief
    from models.pre_user_event import PreUserEvent
    from sqlalchemy import func

    # Get today's headlines
    today = date.today().isoformat()
    items = (
        db_session.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority.asc())
        .limit(5)
        .all()
    )

    if not items:
        return {"sent": 0, "error": "No headlines for today"}

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

    html = _build_brief_email_html(headlines, today, is_welcome=False)

    # Get all unique captured emails
    rows = (
        db_session.query(
            func.distinct(PreUserEvent.event_metadata["email"].astext)
        )
        .filter(PreUserEvent.event_type == "email_captured")
        .all()
    )
    emails = [r[0] for r in rows if r[0]]

    if not emails:
        return {"sent": 0, "error": "No subscribers yet"}

    service = EmailService()
    sent = 0
    failed = 0

    for email in emails:
        try:
            success = service.send(
                to=email,
                subject=f"Brubru Daily Brief: {today}",
                html_body=html,
            )
            if success:
                sent += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"[WARN] Failed to send brief to {email[:3]}***: {e}")
            failed += 1

    logger.info(f"[OK] Daily brief sent to {sent}/{len(emails)} subscribers")
    return {"sent": sent, "failed": failed, "total_subscribers": len(emails)}
