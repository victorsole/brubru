"""
Send Daily Brief Email to All Subscribers

Usage:
    python3.12 scripts/send_daily_brief.py              # Preview (dry run)
    python3.12 scripts/send_daily_brief.py --test        # Send ONLY to hello@beresol.eu (TEST MODE)
    python3.12 scripts/send_daily_brief.py --send        # Send to all subscribers
    python3.12 scripts/send_daily_brief.py --send --extra-file path/to/emails.txt
    python3.12 scripts/send_daily_brief.py --list        # List all subscriber emails

IMPORTANT: Always run --test first and verify the email before running --send.
"""

import argparse
import os
import re
import sys
import urllib.request

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal


def _load_unsubscribed_extras() -> set:
    """Return set of emails explicitly unsubscribed via pre_user_events 'daily_brief_unsubscribe'.

    Honors unsubscribe requests for addresses fed via --extra / --extra-file
    that are not in the users table (and therefore not covered by
    User.preferences.daily_brief_unsubscribed).
    """
    try:
        from sqlalchemy import text as _text
        db = SessionLocal()
        rows = db.execute(_text(
            "SELECT LOWER(event_metadata->>'email') AS email "
            "FROM pre_user_events "
            "WHERE event_type IN ('daily_brief_unsubscribe', 'unsubscribe') "
            "AND event_metadata->>'email' IS NOT NULL"
        )).fetchall()
        db.close()
        return {r.email for r in rows if r.email}
    except Exception as e:
        print(f"  [WARN] Could not load unsubscribe list: {e}")
        return set()


def _load_extra_recipients(file_path: str) -> list:
    """Extract email addresses from a file (txt with one per line, or .md with emails inline)."""
    if not os.path.exists(file_path):
        print(f"  [WARN] Extra recipients file not found: {file_path}")
        return []

    with open(file_path, 'r') as f:
        content = f.read()

    emails = set(re.findall(r'[\w.+-]+@[\w.-]+\.\w+', content))
    unsubscribed = _load_unsubscribed_extras()

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
        if e.lower() in unsubscribed:
            continue
        local = e.split('@')[0].lower()
        if any(p in local for p in skip_locals):
            continue
        if local == 'fl':
            continue
        real.append(e)

    return real


def verify_headline_urls(db) -> bool:
    """Verify all headline URLs return HTTP 200. Blocks send if any fail."""
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
        print("  [WARN] No headlines found for today")
        return False

    print(f"\n  Verifying {len(items)} headline URLs...\n")
    all_ok = True
    for item in items:
        try:
            # Use GET (not HEAD) so servers that don't implement HEAD
            # (consilium subdomain returns 405; some EP pages too) still
            # return 200. We do not download the full body.
            req = urllib.request.Request(item.url, method='GET', headers={
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                resp.read(1024)  # consume minimal bytes, close connection
        except Exception as e:
            status = getattr(e, 'code', 0) or 0

        if 200 <= status < 400:
            print(f"  [OK]   {status} {item.url}")
        else:
            print(f"  [FAIL] {status} {item.url}")
            print(f"         Headline: {item.headline}")
            all_ok = False

    if not all_ok:
        print("\n  [ERROR] Some URLs failed verification. Fix them before sending.")
    else:
        print("\n  [OK] All URLs verified.")
    return all_ok


def send_test(db, brubru_news=None, feature_map=None):
    """Send the daily brief ONLY to hello@beresol.eu for testing."""
    from services.daily_brief_email import _fetch_headlines, _build_brief_email_html
    from services.email_service import EmailService

    headlines, brief_date = _fetch_headlines(db)
    if not headlines:
        print("  [WARN] No headlines found for today")
        return

    # Apply per-priority feature mappings if provided. Mirrors the production
    # send_daily_brief_batch() behaviour so the test email looks identical to
    # the real send. feature_map keys are 1-based positional indices.
    if feature_map:
        for i, h in enumerate(headlines, start=1):
            fm = feature_map.get(i) or feature_map.get(h.get("priority"))
            if fm:
                h["brubru_feature_label"] = fm.get("label")
                h["brubru_feature_url"] = fm.get("url")

    test_email = "hello@beresol.eu"
    html = _build_brief_email_html(
        headlines, brief_date, test_email,
        is_welcome=False, is_registered_user=True,
        brubru_news=brubru_news,
    )

    from datetime import date
    formatted = date.fromisoformat(brief_date).strftime("%d %B %Y")
    subject = f"[TEST] Brubru Daily EU Brief -- {formatted}"

    service = EmailService()
    success = service.send(to=test_email, subject=subject, html_body=html)
    if success:
        print(f"\n  [OK] Test email sent to {test_email}")
        print(f"  Check your inbox, then run --send to deliver to all subscribers.")
    else:
        print(f"\n  [ERROR] Failed to send test email to {test_email}")


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
    extra_new = set(extra_recipients or []) - registered - preusers
    total = len(registered) + len(preusers) + len(extra_new)
    print(f"  Would send to {total} recipient(s): {len(registered)} users, {len(preusers)} pre-users, {len(extra_new)} extra")
    print(f"  Run with --send to deliver\n")


def send(db, brubru_news=None, extra_recipients=None, skip_url_check=False,
         week_ahead=None, week_ahead_closing=None, feature_map=None):
    """Send the daily brief to all subscribers. Verifies URLs first."""
    from services.daily_brief_email import send_daily_brief_batch

    # GUARDRAIL: Verify all URLs before sending to real subscribers
    if not skip_url_check:
        urls_ok = verify_headline_urls(db)
        if not urls_ok:
            print("\n  [BLOCKED] Daily brief send blocked due to URL verification failures.")
            print("  Fix the URLs in the database, then retry.")
            print("  To skip this check (NOT recommended): --send --skip-url-check")
            return

    result = send_daily_brief_batch(db, brubru_news=brubru_news, extra_recipients=extra_recipients,
                                     week_ahead=week_ahead, week_ahead_closing=week_ahead_closing,
                                     feature_map=feature_map)
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
    parser.add_argument("--test", action="store_true",
                        help="Send ONLY to hello@beresol.eu (always do this first)")
    parser.add_argument("--send", action="store_true", help="Send to all subscribers")
    parser.add_argument("--verify-urls", action="store_true",
                        help="Only verify headline URLs, do not send")
    parser.add_argument("--skip-url-check", action="store_true",
                        help="Skip URL verification before --send (NOT recommended)")
    parser.add_argument("--list", action="store_true", help="List all subscriber emails")
    parser.add_argument("--news", nargs="+", metavar="ITEM",
                        help="Brubru product news items to include in the email")
    parser.add_argument("--week-ahead", nargs="+", metavar="ITEM",
                        help="Friday 'Week ahead' bullet items (HTML allowed)")
    parser.add_argument("--week-ahead-closing", metavar="TEXT",
                        help="Friday closing line (e.g. weekend wishes)")
    parser.add_argument("--extra-file", metavar="PATH",
                        help="File with additional recipient emails (txt or md)")
    parser.add_argument("--extra", nargs="+", metavar="EMAIL",
                        help="Additional recipient email addresses")
    parser.add_argument("--feature", action="append", metavar="INDEX:LABEL:URL", default=None,
                        help="Per-headline Brubru feature CTA. Format INDEX:LABEL:URL. INDEX is 1-based headline position. Repeat the flag once per headline. Example: --feature \"1:Open My Files:https://brubru.beresol.eu/my-eu-bubble?tab=my_files\" --feature \"2:Track this in Legislative Tracker:https://...\"")
    args = parser.parse_args()

    # Parse --feature flags into feature_map dict.
    # action="append" gives a flat list of strings, one per --feature occurrence.
    # (Earlier versions used nargs="+" which silently dropped earlier --feature
    # flags when the user repeated the option — only the last list survived.
    # action="append" makes "repeat the flag once per headline" the documented
    # ergonomic and correct usage.)
    feature_map = None
    if args.feature:
        feature_map = {}
        for spec in args.feature:
            parts = spec.split(":", 2)
            if len(parts) != 3:
                print(f"[WARN] Skipping malformed --feature spec: {spec} (expected INDEX:LABEL:URL)")
                continue
            try:
                idx = int(parts[0])
            except ValueError:
                print(f"[WARN] Skipping --feature with non-integer index: {spec}")
                continue
            feature_map[idx] = {"label": parts[1], "url": parts[2]}

    # Permanent extras: individually approved recipients who should always receive the brief
    PERMANENT_EXTRAS = [
        'silvia.gambino@europarl.europa.eu',
        'raquel.correadomenech@europarl.europa.eu',
    ]

    # Collect extra recipients
    extra = list(PERMANENT_EXTRAS)
    extra.extend(args.extra or [])
    if args.extra_file:
        extra.extend(_load_extra_recipients(args.extra_file))
    extra = extra if extra else None

    db = SessionLocal()
    try:
        if args.list:
            list_subscribers(db)
        elif args.verify_urls:
            verify_headline_urls(db)
        elif args.test:
            verify_headline_urls(db)
            send_test(db, brubru_news=args.news, feature_map=feature_map)
        elif args.send:
            send(db, brubru_news=args.news, extra_recipients=extra,
                 skip_url_check=args.skip_url_check,
                 week_ahead=args.week_ahead, week_ahead_closing=args.week_ahead_closing,
                 feature_map=feature_map)
        else:
            preview(db, extra_recipients=extra)
    finally:
        db.close()


if __name__ == "__main__":
    main()
