"""
Send Daily Brief Email to All Subscribers

Usage:
    python3.12 scripts/send_daily_brief.py              # Preview (dry run)
    python3.12 scripts/send_daily_brief.py --send        # Send to all subscribers
    python3.12 scripts/send_daily_brief.py --list        # List all subscriber emails
"""

import argparse
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models.pre_user_event import PreUserEvent
from sqlalchemy import func


def list_subscribers(db):
    """List all captured emails."""
    rows = (
        db.query(
            PreUserEvent.event_metadata["email"].astext,
            func.min(PreUserEvent.created_at),
        )
        .filter(PreUserEvent.event_type == "email_captured")
        .group_by(PreUserEvent.event_metadata["email"].astext)
        .order_by(func.min(PreUserEvent.created_at))
        .all()
    )

    if not rows:
        print("[INFO] No subscribers yet")
        return

    print(f"\n  Daily Brief Subscribers ({len(rows)} total):\n")
    for i, (email, subscribed_at) in enumerate(rows, 1):
        print(f"  {i}. {email}  (since {subscribed_at.strftime('%Y-%m-%d %H:%M')})")
    print()


def preview(db):
    """Show what would be sent."""
    from models.daily_brief import DailyBrief
    from datetime import date

    today = date.today().isoformat()
    items = (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority.asc())
        .limit(5)
        .all()
    )

    if not items:
        print(f"[WARN] No headlines for {today}")
        return

    print(f"\n  Headlines for {today}:\n")
    for i, item in enumerate(items, 1):
        print(f"  {i}. [{item.category.upper()}] {item.headline}")
        print(f"     {item.url}")
    print()

    # Count subscribers
    count = (
        db.query(func.count(func.distinct(PreUserEvent.event_metadata["email"].astext)))
        .filter(PreUserEvent.event_type == "email_captured")
        .scalar()
    )
    print(f"  Would send to {count} subscriber(s)")
    print(f"  Run with --send to deliver\n")


def send(db):
    """Send the daily brief to all subscribers."""
    from services.daily_brief_email import send_daily_brief_batch

    result = send_daily_brief_batch(db)
    print(f"\n  Daily Brief Send Results:")
    print(f"  Sent: {result.get('sent', 0)}")
    print(f"  Failed: {result.get('failed', 0)}")
    print(f"  Total subscribers: {result.get('total_subscribers', 0)}")

    if result.get("error"):
        print(f"  Error: {result['error']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Send daily brief emails")
    parser.add_argument("--send", action="store_true", help="Send to all subscribers")
    parser.add_argument("--list", action="store_true", help="List all subscriber emails")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.list:
            list_subscribers(db)
        elif args.send:
            send(db)
        else:
            preview(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
