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


def list_subscribers(db):
    """List all daily brief recipients (registered users + pre-user captures)."""
    from services.daily_brief_email import _get_all_recipient_emails

    registered, preusers = _get_all_recipient_emails(db)

    print(f"\n  Daily Brief Recipients ({len(registered) + len(preusers)} total):\n")

    if registered:
        print(f"  Registered users ({len(registered)}):")
        for i, email in enumerate(sorted(registered), 1):
            print(f"    {i}. {email}")

    if preusers:
        print(f"\n  Pre-user captures ({len(preusers)}):")
        for i, email in enumerate(sorted(preusers), 1):
            print(f"    {i}. {email}")

    if not registered and not preusers:
        print("  [INFO] No subscribers yet")
    print()


def preview(db):
    """Show what would be sent."""
    from models.daily_brief import DailyBrief
    from services.daily_brief_email import _get_all_recipient_emails
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

    registered, preusers = _get_all_recipient_emails(db)
    total = len(registered) + len(preusers)
    print(f"  Would send to {total} recipient(s): {len(registered)} users, {len(preusers)} pre-users")
    print(f"  Run with --send to deliver\n")


def send(db):
    """Send the daily brief to all subscribers."""
    from services.daily_brief_email import send_daily_brief_batch

    result = send_daily_brief_batch(db)
    print(f"\n  Daily Brief Send Results:")
    print(f"  Sent: {result.get('sent', 0)}")
    print(f"  Failed: {result.get('failed', 0)}")
    print(f"  Registered users: {result.get('registered_users', 0)}")
    print(f"  Pre-users: {result.get('pre_users', 0)}")
    print(f"  Total recipients: {result.get('total_recipients', 0)}")

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
