"""
One-off backfill: write pre_user_events rotation rows for the 32 EUTR orgs
that received the 11 May Brubru Brief transition issue but whose log INSERT
failed due to the :metadata::jsonb SQL syntax bug.

Reads emails from /tmp/eutr_already_sent.txt (one per line), looks up the
org metadata in transparency_register_orgs, and inserts the missing
pre_user_events rows with event_type='send_brubru_brief_eutr'.

Run once, then delete.
"""
import sys
import uuid as _uuid
from datetime import datetime as _dt
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.database import SessionLocal


def main():
    with open("/tmp/eutr_already_sent.txt") as f:
        emails = [line.strip() for line in f if line.strip()]
    print(f"Backfilling rotation rows for {len(emails)} EUTR orgs")

    db = SessionLocal()
    inserted = 0
    try:
        for email in emails:
            org = db.execute(
                text(
                    "SELECT name, policy_cluster FROM transparency_register_orgs "
                    "WHERE LOWER(contact_email) = LOWER(:e) LIMIT 1"
                ),
                {"e": email},
            ).fetchone()
            org_name = (org.name if org else "") or ""
            cluster = (org.policy_cluster if org else "") or ""

            metadata_json = (
                '{"email": "' + email.replace('"', '') + '",'
                ' "org_name": "' + org_name.replace('"', '') + '",'
                ' "policy_cluster": "' + cluster.replace('"', '') + '",'
                ' "issue": "transition_2026-05-11",'
                ' "backfilled": true}'
            )
            db.execute(
                text(
                    "INSERT INTO pre_user_events "
                    "(id, pre_user_id, event_type, ab_variant, event_metadata, created_at) "
                    "VALUES (:id, :pre_user_id, 'send_brubru_brief_eutr', 'A', "
                    "CAST(:metadata AS jsonb), :ts)"
                ),
                {
                    "id": str(_uuid.uuid4()),
                    "pre_user_id": str(_uuid.uuid4()),
                    "metadata": metadata_json,
                    "ts": _dt.utcnow(),
                },
            )
            inserted += 1
        db.commit()
        print(f"[OK] {inserted} rotation rows inserted")
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
