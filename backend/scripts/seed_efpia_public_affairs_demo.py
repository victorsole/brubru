"""
Create the EFPIA demo account `public-affairs@efpia.eu` as an exact copy of
David Devant Cerezo's blue-tier setup, for the 28 May 2026 EFPIA pitch demo.

What it copies from david.devantcerezo@efpia.eu (server-side INSERT ... SELECT,
so no Python type round-tripping of JSONB/array columns):

  1. The user row     -> organization, role_title, country, timezone,
                         policy_interests, subscription_tier + expiry, and the
                         private_guide_slug (david-devant-efpia, already synced
                         to the private_guides table, 6 files). Identity columns
                         (email, name, password) are overridden; language is set
                         to English for the demo audience.
  2. user_carriage_tracks  -> all of David's tracked carriages.
  3. user_documents        -> all of David's MEUB Documents.

Idempotent: re-runs skip the user if it exists and skip already-copied
carriages (by carriage_id) and documents (by title).

Password: EFPIABrubru2026  (pbkdf2_sha256 via passlib, same as api/auth.py).

Usage:
    cd backend && python3.12 scripts/seed_efpia_public_affairs_demo.py            # dry-run
    cd backend && python3.12 scripts/seed_efpia_public_affairs_demo.py --apply    # write DB
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
from passlib.context import CryptContext

load_dotenv(f"{_REPO_ROOT}/.env")

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# Same scheme as backend/api/auth.py (pwd_context = pbkdf2_sha256).
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SOURCE_EMAIL = "david.devantcerezo@efpia.eu"

DEMO_EMAIL = "public-affairs@efpia.eu"
DEMO_PASSWORD = "EFPIABrubru2026"
DEMO_FULL_NAME = "EFPIA Public Affairs"
DEMO_FIRST_NAME = "EFPIA"
DEMO_PREFERRED_NAME = "EFPIA"
DEMO_LANGUAGE = "en"  # demo audience is English-speaking; David's own pref is 'ca'

# user_documents columns that must NOT be copied verbatim (overridden or reset).
DOC_SKIP_COLS = {"id", "user_id", "created_at", "updated_at", "parent_document_id"}


def doc_copy_cols(db) -> list[str]:
    rows = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='user_documents' "
            "ORDER BY ordinal_position"
        )
    ).all()
    return [r[0] for r in rows if r[0] not in DOC_SKIP_COLS]


def get_user_id(db, email: str) -> str | None:
    return db.execute(text("SELECT id::text FROM users WHERE email=:e"), {"e": email}).scalar()


def create_demo_user(db, apply: bool) -> None:
    existing = get_user_id(db, DEMO_EMAIL)
    if existing:
        logger.info(f"  [user] EXISTS {DEMO_EMAIL} (id={existing[:8]}) - skipping insert")
        # Make sure the guide pointer + tier are correct even on a re-run.
        if apply:
            db.execute(
                text(
                    "UPDATE users SET private_guide_slug=(SELECT private_guide_slug FROM users WHERE email=:src),"
                    " private_guide_status='ready', private_guide_updated_at=NOW(),"
                    " is_active=true, is_verified=true, updated_at=NOW() WHERE email=:e"
                ),
                {"src": SOURCE_EMAIL, "e": DEMO_EMAIL},
            )
        return

    pw_hash = pwd_context.hash(DEMO_PASSWORD)
    sql = text(
        """
        INSERT INTO users (
            id, email, password_hash, full_name, first_name, preferred_name,
            organization, role_title, country, language, timezone, policy_interests,
            subscription_tier, subscription_expires_at, is_active, is_verified,
            private_guide_slug, private_guide_status, private_guide_updated_at,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(), :email, :pwhash, :full_name, :first_name, :preferred_name,
            organization, role_title, country, :language, timezone, policy_interests,
            subscription_tier, subscription_expires_at, true, true,
            private_guide_slug, 'ready', NOW(),
            NOW(), NOW()
        FROM users WHERE email = :src
        """
    )
    params = {
        "email": DEMO_EMAIL,
        "pwhash": pw_hash,
        "full_name": DEMO_FULL_NAME,
        "first_name": DEMO_FIRST_NAME,
        "preferred_name": DEMO_PREFERRED_NAME,
        "language": DEMO_LANGUAGE,
        "src": SOURCE_EMAIL,
    }
    if apply:
        db.execute(sql, params)
        logger.info(f"  [user] CREATE {DEMO_EMAIL} (blue, copied from {SOURCE_EMAIL}, language={DEMO_LANGUAGE})")
    else:
        logger.info(f"  [user] WOULD CREATE {DEMO_EMAIL} (blue, copied from {SOURCE_EMAIL}, language={DEMO_LANGUAGE})")


def copy_carriages(db, apply: bool) -> None:
    src_id = get_user_id(db, SOURCE_EMAIL)
    n_src = db.execute(
        text("SELECT count(*) FROM user_carriage_tracks WHERE user_id=:u"), {"u": src_id}
    ).scalar()
    sql = text(
        """
        INSERT INTO user_carriage_tracks (
            id, user_id, carriage_id,
            notify_on_status_change, notify_on_blocking, notify_on_new_documents,
            tracked_since, last_notified_at, user_position, archived_at, archived_reason
        )
        SELECT
            gen_random_uuid(), (SELECT id FROM users WHERE email=:demo), carriage_id,
            notify_on_status_change, notify_on_blocking, notify_on_new_documents,
            NOW(), NULL, user_position, archived_at, archived_reason
        FROM user_carriage_tracks
        WHERE user_id = (SELECT id FROM users WHERE email=:src)
          AND carriage_id NOT IN (
              SELECT carriage_id FROM user_carriage_tracks
              WHERE user_id = (SELECT id FROM users WHERE email=:demo)
          )
        """
    )
    if apply:
        res = db.execute(sql, {"src": SOURCE_EMAIL, "demo": DEMO_EMAIL})
        logger.info(f"  [carriages] copied {res.rowcount} of {n_src} (skipped already-present)")
    else:
        logger.info(f"  [carriages] WOULD copy up to {n_src} carriage tracks")


def copy_documents(db, apply: bool) -> None:
    src_id = get_user_id(db, SOURCE_EMAIL)
    n_src = db.execute(
        text("SELECT count(*) FROM user_documents WHERE user_id=:u"), {"u": src_id}
    ).scalar()

    cols = doc_copy_cols(db)
    col_list = ", ".join(cols)
    sql = text(
        f"""
        INSERT INTO user_documents (id, user_id, {col_list}, parent_document_id, created_at, updated_at)
        SELECT gen_random_uuid(), (SELECT id FROM users WHERE email=:demo), {col_list}, NULL, NOW(), NOW()
        FROM user_documents
        WHERE user_id = (SELECT id FROM users WHERE email=:src)
          AND title NOT IN (
              SELECT title FROM user_documents WHERE user_id = (SELECT id FROM users WHERE email=:demo)
          )
        """
    )
    if apply:
        res = db.execute(sql, {"src": SOURCE_EMAIL, "demo": DEMO_EMAIL})
        logger.info(f"  [documents] copied {res.rowcount} of {n_src} (skipped same-title)")
    else:
        logger.info(f"  [documents] WOULD copy up to {n_src} documents ({len(cols)} columns each)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    args = ap.parse_args()
    apply = args.apply

    logger.info("=" * 78)
    logger.info(f"Seed EFPIA demo account {DEMO_EMAIL} (copy of {SOURCE_EMAIL}) - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        if not get_user_id(db, SOURCE_EMAIL):
            raise RuntimeError(f"Source user {SOURCE_EMAIL} not found - cannot copy.")

        create_demo_user(db, apply)
        db.flush()  # make the new user row visible to the copy SELECTs
        copy_carriages(db, apply)
        copy_documents(db, apply)

        if apply:
            demo_id = get_user_id(db, DEMO_EMAIL)
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, demo_id)
            logger.info(f"  [validate] {n} user_documents rows round-trip cleanly")
            db.commit()
            logger.info("\n[OK] committed.")
        else:
            db.rollback()
            logger.info("\n[OK] dry-run only. Re-run with --apply to commit.")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
