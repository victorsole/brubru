"""
Clean a user's My Documents (user_documents) and/or drafted Amendments (amendments).

Scoped strictly to one email's user_id. Dry-run by default; writes a full JSON
backup of every row before deleting anything, so "start from scratch" is reversible.

Usage:
    # Preview documents (no writes):
    python3.12 -m backend.scripts.clean_user_documents --email victor@hellobo.eu

    # Delete documents:
    python3.12 -m backend.scripts.clean_user_documents --email victor@hellobo.eu --apply

    # Preview / delete amendments:
    python3.12 -m backend.scripts.clean_user_documents --email victor@hellobo.eu --target amendments
    python3.12 -m backend.scripts.clean_user_documents --email victor@hellobo.eu --target amendments --apply

Notes:
    - Connects to whatever DATABASE_URL/Supabase the backend .env points at (prod).
    - For uploaded docs with a storage_document_id, it also asks the document storage
      layer to delete the on-disk file. When run locally, that targets the LOCAL
      filesystem, not Railway's, so prod disk files may be left orphaned (harmless;
      the DB row is what feeds the app + AI context).
    - The amendments target only touches the user-scoped `amendments` table. It never
      touches `amendment_documents` / `mep_amendments`, which are shared scraped EP data.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from sqlalchemy import inspect

from core.database import SessionLocal
from models.user import User
from models.user_document import UserDocument
from models.amendment import Amendment

BACKUP_DIR = Path(__file__).resolve().parent / "_backups"


def _row_to_dict(row) -> dict:
    """Serialise every column on the row (UUID/datetime -> str)."""
    out = {}
    for col in inspect(row).mapper.column_attrs:
        value = getattr(row, col.key)
        if isinstance(value, (datetime,)):
            value = value.isoformat()
        elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
            value = str(value)
        out[col.key] = value
    return out


def _label_document(d: UserDocument) -> str:
    disk = f" [file:{d.storage_document_id}]" if d.storage_document_id else ""
    return f"{d.document_type:9} | {d.title[:70]}{disk}"


def _label_amendment(a: Amendment) -> str:
    ref = a.procedure_reference or a.document_filename or "-"
    return f"{a.amendment_type:12} | {a.position_text[:50]:50} | {ref}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean a user's documents or amendments.")
    parser.add_argument("--email", required=True, help="User email to clean.")
    parser.add_argument(
        "--target",
        choices=["documents", "amendments"],
        default="documents",
        help="Which table to clean (default: documents).",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete (default is dry-run).")
    args = parser.parse_args()

    if args.target == "amendments":
        model, label_fn, noun = Amendment, _label_amendment, "amendment"
    else:
        model, label_fn, noun = UserDocument, _label_document, "document"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            print(f"[ERROR] No user found for {args.email}")
            return

        rows = (
            db.query(model)
            .filter(model.user_id == user.id)
            .order_by(model.created_at.desc())
            .all()
        )

        print(f"[INFO] User {args.email} ({user.id}) has {len(rows)} {noun}(s).")
        for r in rows:
            print(f"  - {label_fn(r)}")

        if not rows:
            print("[OK] Nothing to clean.")
            return

        # Always write a backup first.
        BACKUP_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = BACKUP_DIR / f"{args.target}_{args.email.replace('@', '_at_')}_{stamp}.json"
        backup_path.write_text(
            json.dumps([_row_to_dict(r) for r in rows], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[OK] Backup of {len(rows)} row(s) written to {backup_path}")

        if not args.apply:
            print("[DRY-RUN] No rows deleted. Re-run with --apply to delete.")
            return

        deleted = 0
        for r in rows:
            if args.target == "documents" and r.document_type == "uploaded" and r.storage_document_id:
                try:
                    from services.storage.document_storage import get_document_storage
                    get_document_storage().delete_document(r.storage_document_id)
                    print(f"  [file] removed on-disk storage {r.storage_document_id}")
                except Exception as storage_err:
                    print(f"  [warn] could not remove on-disk file {r.storage_document_id}: {storage_err}")
            db.delete(r)
            deleted += 1

        db.commit()
        print(f"[OK] Deleted {deleted} {noun}(s) for {args.email}. {args.target.capitalize()} now empty.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
