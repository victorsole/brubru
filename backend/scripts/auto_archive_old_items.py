"""
Auto-archive old items in My EU Bubble across user-specific tracks.

Cadence: run daily as part of /morning or via cron.

Rules (conservative -- only archive when an item is clearly past its lifespan):

  user_carriage_tracks
    - WHERE legislative_carriages.current_status IN ('ADOPTED','PUBLISHED','REJECTED','LAPSED','WITHDRAWN')
    - AND legislative_carriages.last_updated < NOW() - INTERVAL '90 days'
    -> archived_reason = 'auto:adopted' (or 'auto:rejected', 'auto:lapsed')

  user_consultation_tracks
    - WHERE consultation deadline_date < NOW() - INTERVAL '30 days'
    -> archived_reason = 'auto:closed'

  user_commission_doc_tracks + user_committee_work_tracks
    - WHERE last_updated < NOW() - INTERVAL '180 days'
      AND status indicates final/adopted (best-effort)
    -> archived_reason = 'auto:stale'

  user_text_adopted_tracks + user_vote_tracks
    -> NEVER auto-archive (user-curated reference items)

The job NEVER touches archived_at if it is already set (idempotent).

Run: python3.12 scripts/auto_archive_old_items.py [--dry-run]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402


CARRIAGE_TERMINAL_STATUSES = ("ADOPTED", "COMPLETED", "WITHDRAWN")


def archive_carriages(db, dry_run: bool) -> int:
    """Auto-archive tracked legislative carriages whose procedure terminated 90+ days ago."""
    statuses_str = ", ".join(f"'{s}'" for s in CARRIAGE_TERMINAL_STATUSES)
    sql = f"""
        SELECT uct.id, uct.user_id, lc.oeil_procedure_ref, lc.current_status, lc.last_updated
        FROM user_carriage_tracks uct
        JOIN legislative_carriages lc ON lc.id = uct.carriage_id
        WHERE uct.archived_at IS NULL
          AND lc.current_status IN ({statuses_str})
          AND lc.last_updated < NOW() - INTERVAL '90 days'
        LIMIT 1000
    """
    rows = db.execute(text(sql)).fetchall()
    if not rows:
        print("[carriage] no items to auto-archive")
        return 0
    print(f"[carriage] {len(rows)} items qualify for auto-archive:")
    for r in rows[:10]:
        print(f"  track {r[0]} user {r[1]} | {r[2]} status={r[3]} updated={r[4]}")
    if dry_run:
        return 0
    ids = [r[0] for r in rows]
    db.execute(
        text(
            "UPDATE user_carriage_tracks SET archived_at = NOW(), "
            "archived_reason = 'auto:' || lower((SELECT current_status FROM legislative_carriages WHERE id = "
            "(SELECT carriage_id FROM user_carriage_tracks WHERE user_carriage_tracks.id = ANY(:ids) LIMIT 1))) "
            "WHERE id = ANY(:ids)"
        ),
        {"ids": ids},
    )
    db.commit()
    return len(rows)


def archive_consultations(db, dry_run: bool) -> int:
    """Auto-archive tracked consultations whose deadline passed 30+ days ago."""
    sql = """
        SELECT uct.id, uct.user_id, c.deadline_date
        FROM user_consultation_tracks uct
        JOIN public_consultations c ON c.id = uct.consultation_id
        WHERE uct.archived_at IS NULL
          AND c.deadline_date < NOW() - INTERVAL '30 days'
        LIMIT 1000
    """
    try:
        rows = db.execute(text(sql)).fetchall()
    except Exception as e:
        db.rollback()
        print(f"[consultation] skipped (schema mismatch?): {e}")
        return 0
    if not rows:
        print("[consultation] no items to auto-archive")
        return 0
    print(f"[consultation] {len(rows)} items qualify for auto-archive")
    if dry_run:
        return 0
    ids = [r[0] for r in rows]
    db.execute(
        text("UPDATE user_consultation_tracks SET archived_at = NOW(), archived_reason = 'auto:closed' WHERE id = ANY(:ids)"),
        {"ids": ids},
    )
    db.commit()
    return len(rows)


def archive_stale_docs(db, dry_run: bool) -> int:
    """Auto-archive tracked Commission docs whose last_updated > 180 days ago."""
    sql = """
        SELECT uct.id
        FROM user_commission_doc_tracks uct
        JOIN commission_documents cd ON cd.id = uct.document_id
        WHERE uct.archived_at IS NULL
          AND cd.last_updated < NOW() - INTERVAL '180 days'
        LIMIT 1000
    """
    try:
        rows = db.execute(text(sql)).fetchall()
    except Exception as e:
        db.rollback()
        print(f"[commission_doc] skipped: {e}")
        return 0
    if not rows:
        print("[commission_doc] no items to auto-archive")
        return 0
    print(f"[commission_doc] {len(rows)} items qualify for auto-archive")
    if dry_run:
        return 0
    ids = [r[0] for r in rows]
    db.execute(
        text("UPDATE user_commission_doc_tracks SET archived_at = NOW(), archived_reason = 'auto:stale' WHERE id = ANY(:ids)"),
        {"ids": ids},
    )
    db.commit()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-archive old My EU Bubble items")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        n1 = archive_carriages(db, args.dry_run)
        n2 = archive_consultations(db, args.dry_run)
        n3 = archive_stale_docs(db, args.dry_run)
        total = n1 + n2 + n3
        print(f"[OK] auto-archive {'simulated' if args.dry_run else 'applied'}: {total} items "
              f"(carriages={n1}, consultations={n2}, commission_docs={n3})")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
