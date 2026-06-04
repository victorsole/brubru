"""
Migrate user_documents that are AUTHORED content disguised as document_type='uploaded'
into their proper editable types (analysis / note / strategy), so users can edit
the documents Brubru created in/for them.

Rule: a row is "authored" if both storage_document_id IS NULL and original_filename IS NULL.
Those rows have no real file behind them; their `content` is the source of truth and
should be editable in MEUB Documents.

The mapping below maps doc_metadata.original_document_type -> editable document_type.
For unmapped or missing orig_type, we default to 'note' (the most permissive editable
kind in the UI). Real file uploads (storage_document_id or original_filename set) are
NEVER touched.

Usage:
    cd backend && python3.12 scripts/migrate_authored_docs_to_editable.py            # dry-run
    cd backend && python3.12 scripts/migrate_authored_docs_to_editable.py --apply
    cd backend && python3.12 scripts/migrate_authored_docs_to_editable.py --apply --user-id <uuid>
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"))

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for n in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(n).setLevel(logging.WARNING)


# original_document_type (Brubru-internal kind tag) -> UI-editable document_type
ORIG_TO_EDITABLE: dict[str, str] = {
    # already-named primitives
    "analysis": "analysis",
    "note": "note",
    "strategy": "strategy",
    "amendment": "note",
    # Brubru-generated content
    "policy_summary": "note",
    "briefing_note": "note",
    "briefing": "note",
    "talking_points": "note",
    "mep_briefing": "note",
    "stakeholder_map": "note",
    "transcript": "note",
    "position_paper": "strategy",
    # external research / evidence dossiers
    "industry_dossier": "analysis",
    "evidence_base": "analysis",
    "commissioned_study": "analysis",
    "consultation_response": "strategy",
    "consultation_brief": "note",
    # anything else falls back to 'note'
}
DEFAULT_EDITABLE = "note"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Persist changes (default is dry-run).")
    ap.add_argument("--user-id", type=str, default=None, help="Restrict to one user (UUID).")
    ap.add_argument("--email", type=str, default=None, help="Restrict to one user (email).")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        params: dict[str, str] = {}
        where_user = ""
        if args.user_id:
            where_user = "AND ud.user_id = CAST(:uid AS uuid)"
            params["uid"] = args.user_id
        elif args.email:
            where_user = "AND ud.user_id = (SELECT id FROM users WHERE email = :email)"
            params["email"] = args.email

        rows = db.execute(text(f"""
            SELECT ud.id, ud.user_id, u.email, ud.title, ud.document_type,
                   ud.doc_metadata->>'original_document_type' AS orig_type,
                   LENGTH(COALESCE(ud.content,'')) AS content_len
            FROM user_documents ud
            JOIN users u ON u.id = ud.user_id
            WHERE ud.document_type = 'uploaded'
              AND ud.storage_document_id IS NULL
              AND ud.original_filename IS NULL
              {where_user}
            ORDER BY u.email, ud.created_at
        """), params).fetchall()

        if not rows:
            logger.info("No authored-but-uploaded documents found. Nothing to migrate.")
            return 0

        logger.info(f"Found {len(rows)} authored documents marked as 'uploaded':")
        plan: list[tuple] = []  # (id, email, title, new_type, orig_type)
        for r in rows:
            new_type = ORIG_TO_EDITABLE.get((r.orig_type or "").lower(), DEFAULT_EDITABLE)
            plan.append((str(r.id), r.email, r.title, new_type, r.orig_type or "(none)"))
            logger.info(
                f"  - [{r.email}] {r.title[:70]!s:70s}  orig={r.orig_type or '-':18s}-> {new_type}"
            )

        if not args.apply:
            logger.info(f"\n[dry-run] Would update {len(plan)} rows. Re-run with --apply.")
            return 0

        for doc_id, email, title, new_type, orig in plan:
            db.execute(text("""
                UPDATE user_documents
                SET document_type = :nt,
                    updated_at = NOW(),
                    doc_metadata = COALESCE(doc_metadata, '{}'::jsonb)
                                   || jsonb_build_object(
                                          'migrated_from', 'uploaded',
                                          'migrated_at', NOW()::text
                                      )
                WHERE id = CAST(:id AS uuid)
            """), {"id": doc_id, "nt": new_type})
        db.commit()
        logger.info(f"\nMigrated {len(plan)} documents.")
        return 0
    except Exception as exc:
        db.rollback()
        logger.error(f"Migration failed: {exc!r}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
