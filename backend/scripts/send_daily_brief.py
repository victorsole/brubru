"""
Send Daily Brief Email to All Subscribers

Usage:
    python3.12 scripts/send_daily_brief.py              # Preview (dry run)
    python3.12 scripts/send_daily_brief.py --send        # Send to all subscribers
    python3.12 scripts/send_daily_brief.py --send --extra-file path/to/emails.txt
    python3.12 scripts/send_daily_brief.py --list        # List all subscriber emails
"""

import argparse
import os
import re
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal


def _load_extra_recipients(file_path: str) -> list:
    """Extract email addresses from a file (txt with one per line, or .md with emails inline)."""
    if not os.path.exists(file_path):
        print(f"  [WARN] Extra recipients file not found: {file_path}")
        return []

    with open(file_path, 'r') as f:
        content = f.read()

    emails = set(re.findall(r'[\w.+-]+@[\w.-]+\.\w+', content))

    # Filter out format patterns and generic/institutional addresses
    skip_locals = {'first', 'last', 'flast', 'firstname', 'firstinitial', 'lastinitial'}
    skip_exact = {
        'hello@beresol.eu', 'victor@hellobo.eu',
        'reception@efpia.eu', 'info@medtecheurope.org', 'info@cocir.org',
        'communications@acea.auto', 'mediacentre@ebf.eu', 'gsmaeurope@gsma.com',
        'team@europeancorrespondent.com',
    }
    # Skip generic EP committee press emails
    skip_exact.update({e for e in emails if '-press@europarl' in e or 'presse-' in e or 'prensa-' in e or 'stampaIT@' in e})

    real = []
    for e in sorted(emails):
        if e in skip_exact:
            continue
        local = e.split('@')[0].lower()
        if any(p in local for p in skip_locals):
            continue
        if local == 'fl':
            continue
        real.append(e)

    return real


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


def preview(db, extra_recipients=None):
    """Show what would be sent."""
    from models.daily_brief import DailyBrief
    from services.daily_brief_email import _get_all_recipient_emails
    from datetime import date

    today = date.today().isoformat()
    items = (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority.asc())
        .limit(10)
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
    extra_new = set(extra_recipients or []) - registered - preusers
    total = len(registered) + len(preusers) + len(extra_new)
    print(f"  Would send to {total} recipient(s): {len(registered)} users, {len(preusers)} pre-users, {len(extra_new)} extra")
    print(f"  Run with --send to deliver\n")


def send(db, brubru_news=None, extra_recipients=None):
    """Send the daily brief to all subscribers."""
    from services.daily_brief_email import send_daily_brief_batch

    result = send_daily_brief_batch(db, brubru_news=brubru_news, extra_recipients=extra_recipients)
    print(f"\n  Daily Brief Send Results:")
    print(f"  Sent: {result.get('sent', 0)}")
    print(f"  Failed: {result.get('failed', 0)}")
    print(f"  Registered users: {result.get('registered_users', 0)}")
    print(f"  Pre-users: {result.get('pre_users', 0)}")
    print(f"  Extra recipients: {result.get('extra_recipients', 0)}")
    print(f"  Total recipients: {result.get('total_recipients', 0)}")

    if result.get("error"):
        print(f"  Error: {result['error']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Send daily brief emails")
    parser.add_argument("--send", action="store_true", help="Send to all subscribers")
    parser.add_argument("--list", action="store_true", help="List all subscriber emails")
    parser.add_argument("--news", nargs="+", metavar="ITEM",
                        help="Brubru product news items to include in the email")
    parser.add_argument("--extra-file", metavar="PATH",
                        help="File with additional recipient emails (txt or md)")
    parser.add_argument("--extra", nargs="+", metavar="EMAIL",
                        help="Additional recipient email addresses")
    args = parser.parse_args()

    # Collect extra recipients
    extra = list(args.extra or [])
    if args.extra_file:
        extra.extend(_load_extra_recipients(args.extra_file))
    extra = extra if extra else None

    db = SessionLocal()
    try:
        if args.list:
            list_subscribers(db)
        elif args.send:
            send(db, brubru_news=args.news, extra_recipients=extra)
        else:
            preview(db, extra_recipients=extra)
    finally:
        db.close()


if __name__ == "__main__":
    main()
