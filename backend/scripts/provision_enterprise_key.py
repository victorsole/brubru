"""
Provision a new Enterprise-tier API key for a partner.

Used for first-class partner integrations (GovClipping, etc.). The key has
the `enterprise` rate-limit tier, which raises the per-key ceiling from
60/min (free) to 6000/min.

Usage:
    python3.12 backend/scripts/provision_enterprise_key.py \
        --user-id <uuid> --name "GovClipping production"

Or, to look up by email and create on the fly:
    python3.12 backend/scripts/provision_enterprise_key.py \
        --email jordi@govclipping.com --name "GovClipping production"

The plaintext key is printed ONCE. Hand it over via Signal (not email).
"""

import argparse
import sys
import uuid
from pathlib import Path

# Allow `python backend/scripts/...` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.user import User
from models.api_key import ApiKey


def parse_args():
    p = argparse.ArgumentParser(description="Provision an enterprise-tier API key.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--user-id", help="UUID of the existing user to attach the key to")
    g.add_argument("--email", help="Email of the user (looked up in users table)")
    p.add_argument("--name", required=True, help="Human label for the key (e.g. 'GovClipping production')")
    p.add_argument("--tier", default="enterprise", choices=["free", "pro", "enterprise"])
    p.add_argument("--commit", action="store_true", help="Actually write to DB (without it, dry-run)")
    return p.parse_args()


def main():
    args = parse_args()
    db: Session = SessionLocal()
    try:
        if args.user_id:
            user = db.query(User).filter(User.id == uuid.UUID(args.user_id)).first()
        else:
            user = db.query(User).filter(User.email == args.email).first()
        if not user:
            print(f"[ERROR] User not found by {'id' if args.user_id else 'email'}")
            sys.exit(2)

        plaintext, instance = ApiKey.generate(user_id=user.id, name=args.name)
        instance.api_tier = args.tier

        print(f"[INFO] Will provision key for: {user.email} ({user.id})")
        print(f"[INFO] Key name: {args.name}")
        print(f"[INFO] Tier: {args.tier}")
        print(f"[INFO] Prefix: ...{instance.key_prefix}")

        if not args.commit:
            print("\n[DRY-RUN] Pass --commit to actually write the key to DB.")
            print(f"[DRY-RUN] Plaintext that WOULD be issued: {plaintext}")
            sys.exit(0)

        db.add(instance)
        db.commit()
        db.refresh(instance)

        print()
        print("=" * 76)
        print("[OK] Enterprise key created")
        print("=" * 76)
        print(f"  user_id : {user.id}")
        print(f"  email   : {user.email}")
        print(f"  key id  : {instance.id}")
        print(f"  tier    : {instance.api_tier}")
        print(f"  PLAINTEXT (shown once — store safely):")
        print(f"     {plaintext}")
        print("=" * 76)
        print("[INFO] Hand over via Signal/secure channel. Email is not safe.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
