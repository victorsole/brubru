"""
Brubru Health Check

Usage:
    python3.12 scripts/healthcheck.py          # Run all checks
    python3.12 scripts/healthcheck.py --quick   # Skip external API checks

Checks: database, AI providers, scrapers, daily brief, EU calendar,
knowledge base, Railway backend.
"""

import argparse
import os
import sys
import urllib.request
import json
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"
import logging
logging.disable(logging.INFO)

RAILWAY_URL = "https://brubru-production.up.railway.app"
STALE_THRESHOLD_HOURS = 48


def _check(name: str, fn, results: list):
    """Run a check function and record the result."""
    try:
        ok, detail = fn()
        status = "OK" if ok else "WARN"
    except Exception as e:
        ok = False
        status = "FAIL"
        detail = str(e)[:120]
    results.append({"name": name, "status": status, "detail": detail})


def check_database():
    """Verify database connection and basic query."""
    from core.database import SessionLocal
    from models.user import User

    db = SessionLocal()
    try:
        count = db.query(User).count()
        return True, f"{count} users"
    finally:
        db.close()


def check_daily_brief():
    """Check headlines exist for today."""
    from core.database import SessionLocal
    from models.daily_brief import DailyBrief

    db = SessionLocal()
    try:
        today = date.today().isoformat()
        count = db.query(DailyBrief).filter(DailyBrief.brief_date == today).count()
        if count == 0:
            return False, "No headlines for today"
        return True, f"{count} headlines"
    finally:
        db.close()


def check_eu_calendar():
    """Check events exist for the next 7 days."""
    from core.database import SessionLocal
    from models.eu_calendar import EUCalendarEvent

    db = SessionLocal()
    try:
        today = date.today()
        week_ahead = today + timedelta(days=7)
        count = (
            db.query(EUCalendarEvent)
            .filter(EUCalendarEvent.start_date >= today)
            .filter(EUCalendarEvent.start_date <= week_ahead)
            .count()
        )
        if count == 0:
            return False, "No events in next 7 days"
        return True, f"{count} events next 7 days"
    finally:
        db.close()


def check_knowledge_base():
    """Verify guides load and trigger count."""
    from knowledge_base.knowledge_loader import get_knowledge_loader, GUIDE_KEYWORD_TRIGGERS

    loader = get_knowledge_loader()
    guides = loader.list_guides()
    trigger_count = len(GUIDE_KEYWORD_TRIGGERS)

    if len(guides) < 50:
        return False, f"Only {len(guides)} guides (expected 50+)"
    if trigger_count < 1000:
        return False, f"Only {trigger_count} triggers (expected 1000+)"
    return True, f"{len(guides)} guides, {trigger_count} triggers"


def check_scrapers():
    """Check last scrape timestamps are not stale."""
    from core.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # Check daily_briefs for latest date
        row = db.execute(text("SELECT MAX(brief_date) FROM daily_briefs")).fetchone()
        if not row or not row[0]:
            return False, "No daily brief data at all"

        latest = row[0]
        if isinstance(latest, str):
            latest = date.fromisoformat(latest)

        days_old = (date.today() - latest).days
        if days_old > 2:
            return False, f"Latest brief is {days_old} days old ({latest})"
        return True, f"Latest brief: {latest}"
    finally:
        db.close()


def check_railway():
    """Verify Railway backend responds."""
    try:
        req = urllib.request.Request(
            f"{RAILWAY_URL}/docs",
            headers={"User-Agent": "Brubru healthcheck"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 400:
                return True, f"HTTP {resp.status}"
            return False, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)[:80]


def check_ai_claude():
    """Verify Claude API key is set and API responds."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return False, "ANTHROPIC_API_KEY not set"

    try:
        data = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"HTTP {resp.status}"
    except Exception as e:
        code = getattr(e, 'code', None)
        if code == 429:
            return True, "Rate limited (API key works)"
        return False, str(e)[:80]


def check_ai_mistral():
    """Verify Mistral API key is set."""
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        return False, "MISTRAL_API_KEY not set"
    return True, "Key set"


def main():
    parser = argparse.ArgumentParser(description="Brubru health check")
    parser.add_argument("--quick", action="store_true",
                        help="Skip external API checks (Railway, AI providers)")
    args = parser.parse_args()

    results = []

    # Local checks (always run)
    _check("Database", check_database, results)
    _check("Daily Brief", check_daily_brief, results)
    _check("EU Calendar", check_eu_calendar, results)
    _check("Knowledge Base", check_knowledge_base, results)
    _check("Scrapers", check_scrapers, results)

    # External checks (skip with --quick)
    if not args.quick:
        _check("Railway Backend", check_railway, results)
        _check("Claude API", check_ai_claude, results)
        _check("Mistral API", check_ai_mistral, results)

    # Print results
    print(f"\n  Brubru Health Check -- {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    max_name = max(len(r["name"]) for r in results)
    ok_count = 0
    for r in results:
        icon = "[OK]  " if r["status"] == "OK" else "[WARN]" if r["status"] == "WARN" else "[FAIL]"
        print(f"  {icon} {r['name']:<{max_name}}  {r['detail']}")
        if r["status"] == "OK":
            ok_count += 1

    total = len(results)
    print(f"\n  {ok_count}/{total} checks passed.")

    if ok_count < total:
        failed = [r for r in results if r["status"] != "OK"]
        print(f"  Issues: {', '.join(r['name'] for r in failed)}")
    print()

    return 0 if ok_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
