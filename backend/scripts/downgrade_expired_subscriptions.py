"""
Downgrade subscriptions whose expiry has passed.

Flips `subscription_tier` to 'white' for users where:
  - subscription_expires_at IS NOT NULL
  - subscription_expires_at < NOW()
  - subscription_tier != 'white' (skip already-downgraded)
  - stripe_subscription_id IS NULL (Stripe-managed subs roll over on their own
    via stripe_payment.py webhooks; this script only handles manually-granted
    complimentary tiers).

Designed to run as a daily Railway cron. Safe to run multiple times per day.

Usage:
    cd backend && python3.12 scripts/downgrade_expired_subscriptions.py            # dry-run
    cd backend && python3.12 scripts/downgrade_expired_subscriptions.py --apply    # write DB
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import logging
import sys

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(f"{_REPO_ROOT}/.env")

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id::text, email, full_name, subscription_tier, subscription_expires_at
            FROM users
            WHERE subscription_expires_at IS NOT NULL
              AND subscription_expires_at < NOW()
              AND subscription_tier != 'white'
              AND stripe_subscription_id IS NULL
            ORDER BY subscription_expires_at
        """)).fetchall()

        if not rows:
            logger.info("[OK] no expired subscriptions to downgrade")
            return

        logger.info(f"Found {len(rows)} expired non-Stripe subscriptions:")
        for r in rows:
            logger.info(f"  {r.email:<40} tier={r.subscription_tier:<6} expired={r.subscription_expires_at}")

        if not args.apply:
            logger.info("\nDry-run only. Re-run with --apply to commit.")
            return

        result = db.execute(text("""
            UPDATE users
            SET subscription_tier = 'white',
                updated_at = NOW()
            WHERE subscription_expires_at IS NOT NULL
              AND subscription_expires_at < NOW()
              AND subscription_tier != 'white'
              AND stripe_subscription_id IS NULL
        """))
        db.commit()
        logger.info(f"\n[OK] downgraded {result.rowcount} users to white tier")
    finally:
        db.close()


if __name__ == "__main__":
    main()
