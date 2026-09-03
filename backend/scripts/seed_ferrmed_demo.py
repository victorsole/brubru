"""
Seed FerrMed demo user + pre-loaded tracked files.

Prepares the user for Victor's pitch on Tuesday 19 May 2026.

What it does:
1. Creates user bureau@ferrmed.com (blue tier, organisation=FERRMED ASBL).
2. Searches legislative_carriages for FerrMed-relevant files (TEN-T, ERTMS,
   rail freight, military mobility, combined transport, CEF, Eurovignette,
   intermodal, modal shift, etc.).
3. Inserts user_carriage_tracks rows so the new user's My EU Bubble opens
   onto real, relevant content from the first click.

Usage:
    # Dry run (default) — prints what it would do, no DB writes:
    python3.12 -m backend.scripts.seed_ferrmed_demo

    # Apply — creates user + tracks:
    python3.12 -m backend.scripts.seed_ferrmed_demo --apply

Idempotent: re-runs skip the user create and skip already-tracked carriages.
"""

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import sys
import argparse
import logging
from typing import List

sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, f"{_REPO_ROOT}/backend")

from passlib.context import CryptContext
from sqlalchemy import text

from core.database import SessionLocal  # noqa: E402
from models.user import User  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Silence SQLAlchemy SQL echo locally (settings.DEBUG=True is dev-only).
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


FERRMED_USER = {
    "email": "bureau@ferrmed.com",
    "full_name": "Ferrmed",
    "organization": "FERRMED ASBL",
    "password": "FerrmedBrubru2026",
    "subscription_tier": "blue",
    "policy_interests": ["Transport"],
    "sectors": [
        "rail-freight",
        "intermodal-logistics",
        "ten-t-corridors",
        "ertms-signalling",
        "military-mobility-dual-use",
        "rolling-stock",
    ],
    "country": "BE",
    "timezone": "Europe/Brussels",
    "language": "en",
    "role_title": "Permanent Delegation in Brussels",
}


# Explicit picks. Each entry resolves to one legislative_carriages row by
# either OEIL ref (preferred) or exact title fragment (fallback for entries
# with NULL OEIL). Curated 18 May 2026 from live DB inspection.
TARGET_FILES = [
    # 1. Current rail-specific INI — high-speed rail (TRAN, 2026)
    {"oeil": "2026/2003(INI)",      "label": "Connecting Europe Through High-Speed Rail (INI 2026)"},
    # 2. Live COD on capacity allocation — FerrMed's #1 operational topic
    {"oeil": "2023/0271(COD)",      "label": "Improving use of rail infrastructure capacity"},
    # 3. Rail safety topical (Tempi anniversary resolution, 2026)
    {"oeil": "2026/2647(RSP)",      "label": "Tempi accident: rail transport safety in the EU"},
    # 4. International carriage by rail — OTIF revision (TRAN, 2026)
    {"oeil": "COM(2026)0163",       "label": "OTIF: revision of International Carriage by Rail"},
    # 5. ECI on fast/affordable rail (TRAN)
    {"oeil": "C(2026)2014",         "label": "ECI: Fast, convenient, affordable rail"},
    # 6. HGV CO2 classes with trailers — modal-shift driver (TRAN)
    {"oeil": "2023/0134(COD)",      "label": "CO2 emission class of heavy-duty vehicles with trailers"},
    # 7. CountEmissionsEU — modal-shift transparency
    {"oeil": "2023/0266(COD)",      "label": "CountEmissionsEU: Measuring emissions from transport services"},
    # 8. TEN-T streamlining (completed but anchor file for FerrMed)
    {"oeil": "2018/0138(COD)",      "label": "TEN-T streamlining (Directive 2021/1187)"},
    # 9. Combined Transport directive (intermodal framework, by title)
    {"oeil": None,                   "title_like": "%directive on common rules for combined transport of goods%",
     "label": "Combined Transport directive revision"},
    # 10. Inland Waterway Transport fitness check (intermodal interface, by SWD ref)
    {"oeil": "SWD(2026)0027",       "label": "Inland Waterway Transport — market access fitness check"},
]


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_ferrmed_user(db, apply: bool) -> str:
    """Return the user id (existing or newly created)."""
    existing = db.query(User).filter(User.email == FERRMED_USER["email"]).first()
    if existing:
        logger.info(f"  [SKIP] User {FERRMED_USER['email']} already exists (id={existing.id})")
        return str(existing.id)

    if not apply:
        logger.info(f"  [DRY] Would CREATE user {FERRMED_USER['email']} ({FERRMED_USER['organization']}, blue tier)")
        return ""

    new_user = User(
        email=FERRMED_USER["email"],
        full_name=FERRMED_USER["full_name"],
        organization=FERRMED_USER["organization"],
        password_hash=get_password_hash(FERRMED_USER["password"]),
        subscription_tier=FERRMED_USER["subscription_tier"],
        policy_interests=FERRMED_USER["policy_interests"],
        sectors=FERRMED_USER["sectors"],
        country=FERRMED_USER["country"],
        timezone=FERRMED_USER["timezone"],
        language=FERRMED_USER["language"],
        role_title=FERRMED_USER["role_title"],
        is_active=True,
        is_verified=True,
        is_trainer=False,
    )
    db.add(new_user)
    db.flush()
    logger.info(f"  [OK]  CREATE user {FERRMED_USER['email']} (id={new_user.id}, BLUE tier)")
    return str(new_user.id)


def find_carriage(db, target: dict) -> dict | None:
    """Resolve a TARGET_FILES entry to one legislative_carriages row."""
    if target.get("oeil"):
        sql = text(
            """
            SELECT id::text AS id, title, oeil_procedure_ref,
                   current_status::text AS current_status,
                   COALESCE(lead_committee, '') AS lead_committee
            FROM legislative_carriages
            WHERE oeil_procedure_ref = :ref
            LIMIT 1
            """
        )
        row = db.execute(sql, {"ref": target["oeil"]}).mappings().first()
        if row:
            return dict(row)
    if target.get("title_like"):
        sql = text(
            """
            SELECT id::text AS id, title, oeil_procedure_ref,
                   current_status::text AS current_status,
                   COALESCE(lead_committee, '') AS lead_committee
            FROM legislative_carriages
            WHERE title ILIKE :p
            ORDER BY last_updated DESC NULLS LAST
            LIMIT 1
            """
        )
        row = db.execute(sql, {"p": target["title_like"]}).mappings().first()
        if row:
            return dict(row)
    return None


def seed_tracks(db, user_id: str, apply: bool) -> int:
    """Find and insert user_carriage_tracks for FerrMed. Return inserted count."""
    selected = []
    missing = []

    for target in TARGET_FILES:
        row = find_carriage(db, target)
        if not row:
            missing.append(target)
            logger.info(f"  [MISS] {target['label']}  (key: {target.get('oeil') or target.get('title_like')})")
            continue
        oeil = row["oeil_procedure_ref"] or "(no OEIL)"
        status = row["current_status"]
        cmt = row["lead_committee"] or "?"
        logger.info(f"  [ OK ] {target['label']}")
        logger.info(f"          {row['title'][:90]}")
        logger.info(f"          OEIL: {oeil}  status: {status}  cmt: {cmt}")
        selected.append(row)

    if not selected:
        logger.warning("\n  [WARN] No carriages matched any keyword group — DB may be empty for transport.")
        return 0

    if not user_id:
        logger.info(f"\n  [DRY] Would insert {len(selected)} user_carriage_tracks rows for FerrMed.")
        return 0

    # Live table lacks a UNIQUE(user_id, carriage_id) constraint (migration drift),
    # so we can't use ON CONFLICT. Pre-check existence per row, then insert.
    inserted = 0
    skipped = 0
    check_sql = text(
        "SELECT 1 FROM user_carriage_tracks WHERE user_id=:u AND carriage_id=CAST(:c AS uuid) LIMIT 1"
    )
    insert_sql = text(
        """
        INSERT INTO user_carriage_tracks (id, user_id, carriage_id, tracked_since,
                                          notify_on_status_change, notify_on_blocking,
                                          notify_on_new_documents)
        VALUES (gen_random_uuid(), :u, CAST(:c AS uuid), NOW(), TRUE, TRUE, TRUE)
        """
    )
    for r in selected:
        exists = db.execute(check_sql, {"u": user_id, "c": r["id"]}).first()
        if exists:
            skipped += 1
            continue
        db.execute(insert_sql, {"u": user_id, "c": r["id"]})
        inserted += 1

    if apply:
        logger.info(f"\n  [OK]  Inserted {inserted} new user_carriage_tracks rows ({skipped} already existed).")
    return inserted


def seed_text_adopted_tracks(db, user_id: str, apply: bool) -> int:
    """
    Pre-track the Texts Adopted that already match FerrMed's interests so the
    Texts Adopted sub-tab opens to real content. Picks adopted texts by
    (a) procedure_ref matching a tracked carriage, (b) transport-relevant
    title keyword.
    """
    # Find the most relevant adopted texts. Procedure ref priority, then keyword.
    proc_refs = [t.get("oeil") for t in TARGET_FILES if t.get("oeil")]
    candidates = []
    if proc_refs:
        rows = db.execute(
            text(
                """
                SELECT id::text AS id, ta_reference, title, procedure_ref, adoption_date
                FROM texts_adopted
                WHERE procedure_ref = ANY(:refs)
                ORDER BY adoption_date DESC NULLS LAST
                """
            ),
            {"refs": proc_refs},
        ).mappings().all()
        candidates.extend(dict(r) for r in rows)

    # Broaden with transport-relevant title keywords (limit so we don't dump everything).
    keyword_rows = db.execute(
        text(
            """
            SELECT id::text AS id, ta_reference, title, procedure_ref, adoption_date
            FROM texts_adopted
            WHERE (title ILIKE '%rail%' OR title ILIKE '%TEN-T%' OR title ILIKE '%transport%'
                   OR title ILIKE '%intermodal%' OR title ILIKE '%mobility%' OR title ILIKE '%CEF%')
            ORDER BY adoption_date DESC NULLS LAST
            LIMIT 5
            """
        )
    ).mappings().all()
    seen_ids = {c["id"] for c in candidates}
    for r in keyword_rows:
        if r["id"] not in seen_ids:
            candidates.append(dict(r))
            seen_ids.add(r["id"])

    if not candidates:
        logger.info("  [WARN] No adopted texts matched. Texts Adopted tab will stay empty.")
        return 0

    logger.info(f"  Selected {len(candidates)} adopted texts:")
    for c in candidates:
        logger.info(f"    - [{c['adoption_date']}] {c['ta_reference']}  {c['title'][:70]}")

    if not user_id:
        logger.info(f"\n  [DRY] Would insert {len(candidates)} user_text_adopted_tracks rows.")
        return 0

    check_sql = text(
        "SELECT 1 FROM user_text_adopted_tracks WHERE user_id=:u AND text_adopted_id=CAST(:t AS uuid) LIMIT 1"
    )
    insert_sql = text(
        """
        INSERT INTO user_text_adopted_tracks (id, user_id, text_adopted_id, tracked_since)
        VALUES (gen_random_uuid(), :u, CAST(:t AS uuid), NOW())
        """
    )
    inserted = 0
    skipped = 0
    for c in candidates:
        if db.execute(check_sql, {"u": user_id, "t": c["id"]}).first():
            skipped += 1
            continue
        db.execute(insert_sql, {"u": user_id, "t": c["id"]})
        inserted += 1

    if apply:
        logger.info(f"\n  [OK]  Inserted {inserted} new user_text_adopted_tracks ({skipped} already existed).")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Seed FerrMed demo user + tracked files.")
    parser.add_argument("--apply", action="store_true", help="Actually write to DB. Default is dry-run.")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN (use --apply to write)"
    logger.info("=" * 80)
    logger.info(f"FerrMed demo seed — {mode}")
    logger.info("=" * 80)

    db = SessionLocal()
    try:
        logger.info("\n[1/3] User")
        user_id = create_ferrmed_user(db, apply=args.apply)
        if args.apply:
            db.commit()  # commit user first so a tracks failure can't undo it
            logger.info("  [OK]  User committed.")

        logger.info("\n[2/3] Tracked files (My EU Bubble - Legislative Tracker)")
        seed_tracks(db, user_id=user_id, apply=args.apply)

        logger.info("\n[3/3] Tracked adopted texts (My EU Bubble - Texts Adopted)")
        seed_text_adopted_tracks(db, user_id=user_id, apply=args.apply)

        if args.apply:
            db.commit()
            logger.info("\n[OK] Committed.")
        else:
            db.rollback()
            logger.info("\n[DRY] Rolled back (no changes written).")
    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
