"""
Seed the public sandbox API key.

Idempotent: if an active row with is_sandbox=TRUE already exists, the script
prints its prefix and exits without minting a new one. Otherwise it mints a
new key, owned by the admin user, with the read-only scopes published in the
docs Try-It panel.

The plaintext is printed ONCE to stdout. The intended workflow is:

    1. Run this script in a one-off Railway shell (or locally against prod DB).
    2. Copy the plaintext into the project's .env as BRUBRU_SANDBOX_KEY.
    3. Frontend /api/docs Try-It buttons read VITE_BRUBRU_SANDBOX_KEY at build
       time. Postman public-sandbox examples use the same value.
    4. The shared sandbox is rate-limited via api_sandbox_pool in Phase B
       (100 calls/day global, 10/IP/day).

Usage:
    cd backend && python3.12 scripts/seed_sandbox_api_key.py
    cd backend && python3.12 scripts/seed_sandbox_api_key.py --rotate   # revoke + new

Notes:
    - The owning user is the first admin (role='admin') in the users table. If
      that lookup fails the script aborts; pass --owner-email to override.
    - There is a unique partial index on api_keys(is_sandbox) WHERE is_sandbox
      AND revoked_at IS NULL — so at most one active sandbox key can exist.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend/ to sys.path so we can import models/* when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.database import SessionLocal  # noqa: E402
from models.api_key import ApiKey       # noqa: E402
from models.user import User            # noqa: E402

# Scopes the sandbox key is permitted to use. All read:* scopes — the sandbox
# is meant to let evaluators try every retrieval-style endpoint.
SANDBOX_SCOPES = [
    "read:laws",
    "read:procedures",
    "read:calendar",
    "read:ep",
    "read:commission",
    "read:council",
    "read:knowledge",
    "read:publications",
]


def _resolve_owner(db: Session, owner_email: str | None) -> User:
    if owner_email:
        u = db.query(User).filter(User.email == owner_email).first()
        if u is None:
            raise SystemExit(f"[seed_sandbox] owner email not found: {owner_email}")
        return u
    u = (
        db.query(User)
        .filter(User.role == "admin")
        .order_by(User.created_at.asc())
        .first()
    )
    if u is None:
        raise SystemExit(
            "[seed_sandbox] no admin user found. Pass --owner-email <admin@example.com>."
        )
    return u


def _find_existing_sandbox(db: Session) -> ApiKey | None:
    return (
        db.query(ApiKey)
        .filter(and_(ApiKey.is_sandbox.is_(True), ApiKey.revoked_at.is_(None)))
        .first()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the public sandbox API key.")
    parser.add_argument(
        "--owner-email",
        default=None,
        help="Owner email override. Defaults to the earliest user with role='admin'.",
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Revoke any existing sandbox key first, then mint a new one.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = _find_existing_sandbox(db)
        if existing is not None and not args.rotate:
            print(
                f"[seed_sandbox] active sandbox key already exists "
                f"(id={existing.id}, prefix=brubru_live_…{existing.key_prefix}). "
                f"Use --rotate to revoke and mint a new one."
            )
            return 0

        if existing is not None and args.rotate:
            existing.revoked_at = datetime.now(timezone.utc)
            db.commit()
            print(f"[seed_sandbox] revoked previous sandbox key {existing.id}")

        owner = _resolve_owner(db, args.owner_email)
        plaintext, api_key = ApiKey.generate(
            user_id=owner.id,
            name="Public Sandbox",
            scopes=SANDBOX_SCOPES,
            expires_in_days=None,  # sandbox never expires; rotate manually if needed
            is_sandbox=True,
        )
        # Sandbox stays on the free rate-limit tier; the per-day cap is enforced
        # separately in Phase B via the api_sandbox_pool DB counter.
        api_key.api_tier = "free"
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        print()
        print("=" * 72)
        print("Sandbox API key minted. STORE THIS PLAINTEXT — it will not be shown again.")
        print("=" * 72)
        print(f"  id:          {api_key.id}")
        print(f"  owner:       {owner.email}")
        print(f"  scopes:      {SANDBOX_SCOPES}")
        print(f"  is_sandbox:  TRUE")
        print(f"  expires_at:  never")
        print()
        print(f"  PLAINTEXT:   {plaintext}")
        print()
        print("Next steps:")
        print("  1. Add to backend .env:  BRUBRU_SANDBOX_KEY=<plaintext>")
        print("  2. Add to frontend .env: VITE_BRUBRU_SANDBOX_KEY=<plaintext>")
        print("  3. Postman public-sandbox examples use the same value.")
        print("=" * 72)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
