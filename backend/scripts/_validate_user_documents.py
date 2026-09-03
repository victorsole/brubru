"""
Reusable smoke-test helper for any script that inserts into user_documents.

Call `validate_user_documents_for(db, user_id)` at the end of every seed /
populate / migration script that touches `user_documents`. The helper round-
trips every one of the user's rows through `UserDocumentResponse` exactly as
`/api/documents` would, and raises if any row would 500 the API.

This is the runtime backstop. The structural backstop is migration 080
(`backend/migrations/080_user_documents_defaults_and_checks.sql`), which puts
DB-side defaults on view_count/version/is_private/is_featured/include_in_ai_context
and a CHECK constraint on document_type. Both layers must remain in place.

History of why this exists:
  - May 2026 (Guido Maria Valletta): rows with document_type='mep_letter' /
    'commission_email' passed DB (VARCHAR(50), no CHECK), then Pydantic 500'd
    /api/documents and the React tree white-screened with no error boundary.
  - 21 May 2026 (Joan Maria Piqué): rows with view_count=NULL because raw
    INSERT bypassed the ORM default `Column(Integer, default=0)`. Same
    response-time 500, same white screen.

Both are now refused at the DB layer by migration 080. This helper exists so
that even if a future migration is reverted, a seed script will fail loudly
in dev before reaching production.

Memory: memory/feedback_raw_insert_orm_defaults.md
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class UserDocumentValidationError(RuntimeError):
    """Raised when one or more user_documents rows fail Pydantic round-trip.

    The seed script should NOT commit if this raises. Surfacing it as a hard
    error preserves the "fail loudly in dev, never in prod" contract.
    """


def validate_user_documents_for(db, user_id: str) -> int:
    """Round-trip every user_documents row for `user_id` through
    UserDocumentResponse. Returns the count of validated rows. Raises
    UserDocumentValidationError if any row fails.

    Args:
        db: an open SQLAlchemy Session (e.g. SessionLocal()).
        user_id: the UUID (as string or UUID) of the user whose docs to check.

    Idempotent and read-only. Safe to call any number of times.
    """
    # Import inside the function so this module has no hard import-time deps;
    # callers do not need to fiddle with sys.path before importing the helper.
    from models.user_document import UserDocument
    from schemas.user_document_schemas import UserDocumentResponse

    docs = db.query(UserDocument).filter(UserDocument.user_id == user_id).all()

    fails = []
    for d in docs:
        try:
            # Both validate AND serialize. Some Pydantic failures only surface
            # at JSON serialization, not at validate (rare but real).
            UserDocumentResponse.model_validate(d).model_dump_json()
        except Exception as e:
            fails.append((str(d.id), d.document_type, type(e).__name__, str(e)[:300]))

    if not fails:
        logger.info(f"[OK] user_documents validation: {len(docs)} rows pass for user {user_id}")
        return len(docs)

    # Build a structured error so the seed script's stack trace is readable.
    lines = [
        f"{len(fails)} of {len(docs)} user_documents rows fail Pydantic round-trip for user {user_id}.",
        "These rows would 500 /api/documents and white-screen the My EU Bubble.",
        "DO NOT commit the seed transaction until each row is fixed.",
        "",
    ]
    for doc_id, doc_type, err_type, err_msg in fails:
        lines.append(f"  doc={doc_id[:8]} type='{doc_type}' {err_type}: {err_msg}")
    raise UserDocumentValidationError("\n".join(lines))


def validate_all_user_documents(db) -> tuple[int, int]:
    """Round-trip EVERY user_documents row in the platform. Useful for a CI
    health check or a one-off audit. Returns (passed, failed). Does not raise.

    Prints a per-user PASS/FAIL summary to logger.info / logger.error.
    """
    from sqlalchemy import text
    from models.user_document import UserDocument
    from schemas.user_document_schemas import UserDocumentResponse

    emails = db.execute(text("""
        SELECT u.email, u.id::text AS uid
        FROM users u
        WHERE EXISTS (SELECT 1 FROM user_documents ud WHERE ud.user_id = u.id)
        ORDER BY u.email
    """)).fetchall()

    total_pass = total_fail = 0
    for row in emails:
        docs = db.query(UserDocument).filter(UserDocument.user_id == row.uid).all()
        ok = fail = 0
        for d in docs:
            try:
                UserDocumentResponse.model_validate(d).model_dump_json()
                ok += 1
            except Exception:
                fail += 1
        total_pass += ok
        total_fail += fail
        if fail:
            logger.error(f"[FAIL] {row.email}: {ok}/{len(docs)} pass, {fail} fail")
        else:
            logger.info(f"[PASS] {row.email}: {len(docs)} docs")
    return total_pass, total_fail


def _cli():
    """`python3.12 scripts/_validate_user_documents.py` runs a platform-wide
    audit and exits non-zero on any failure."""
    sys.path.insert(0, f"{_REPO_ROOT}/backend")
    sys.path.insert(0, _REPO_ROOT)
    from dotenv import load_dotenv
    load_dotenv(f"{_REPO_ROOT}/.env")
    from core.database import SessionLocal, engine

    engine.echo = False
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    db = SessionLocal()
    try:
        ok, fail = validate_all_user_documents(db)
        print(f"\n[summary] {ok} PASS / {fail} FAIL")
        sys.exit(1 if fail else 0)
    finally:
        db.close()


if __name__ == "__main__":
    _cli()
