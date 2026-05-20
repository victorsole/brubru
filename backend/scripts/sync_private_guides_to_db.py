"""
Sync local private_guides/{slug}/*.md files into the private_guides DB table.

The markdown files under backend/knowledge_base/private_guides/{slug}/ are
the local source of truth (gitignored). Production (Railway) cannot see
them in the deploy image, so this script UPSERTs them into Postgres where
the runtime loader reads them via SessionLocal.

Usage:
    # Sync a single slug:
    python3.12 backend/scripts/sync_private_guides_to_db.py ferrmed

    # Sync every slug folder present locally:
    python3.12 backend/scripts/sync_private_guides_to_db.py --all

    # Dry run (no DB writes):
    python3.12 backend/scripts/sync_private_guides_to_db.py ferrmed --dry-run

    # Wipe DB rows for a slug (e.g. after deleting a local file):
    python3.12 backend/scripts/sync_private_guides_to_db.py ferrmed --prune

The script reads .env via load_dotenv so DATABASE_URL is picked up when
invoked directly (CLAUDE.md hard rule: raw smtplib / raw DB scripts must
explicitly load .env).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

# Resolve project root and load .env (must precede any DB import).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sync-private-guides")

PRIVATE_GUIDES_DIR = _PROJECT_ROOT / "backend" / "knowledge_base" / "private_guides"


def _extract_title(content: str, fallback: str) -> str:
    first_line = content.lstrip().split("\n", 1)[0]
    return first_line.lstrip("# ").strip() or fallback


def _ordering_from_filename(filename: str) -> int:
    """`00_organisation.md` -> 0, `01_priority_files.md` -> 1, fallback 999."""
    stem = filename.split("_", 1)[0]
    try:
        return int(stem)
    except ValueError:
        return 999


def list_slugs() -> list[str]:
    if not PRIVATE_GUIDES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in PRIVATE_GUIDES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )


def sync_slug(slug: str, dry_run: bool = False, prune: bool = False) -> dict:
    slug_dir = PRIVATE_GUIDES_DIR / slug
    if not slug_dir.is_dir():
        raise FileNotFoundError(f"No slug folder: {slug_dir}")

    files = sorted(slug_dir.glob("*.md"))
    if not files:
        log.warning("No .md files in %s", slug_dir)
        return {"slug": slug, "files": 0, "upserted": 0, "deleted": 0}

    upserted = 0
    deleted = 0
    seen_filenames: list[str] = []

    db = SessionLocal()
    try:
        for md_file in files:
            content = md_file.read_text(encoding="utf-8")
            title = _extract_title(content, md_file.stem)
            ordering = _ordering_from_filename(md_file.name)
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

            seen_filenames.append(md_file.name)
            log.info(
                "%s/%s | %d chars | ordering=%d",
                slug,
                md_file.name,
                len(content),
                ordering,
            )

            if dry_run:
                continue

            db.execute(
                text(
                    """
                    INSERT INTO private_guides
                        (slug, filename, title, content, ordering,
                         source_path, source_hash, last_synced_at, updated_at)
                    VALUES
                        (:slug, :filename, :title, :content, :ordering,
                         :source_path, :source_hash, NOW(), NOW())
                    ON CONFLICT (slug, filename) DO UPDATE
                       SET title          = EXCLUDED.title,
                           content        = EXCLUDED.content,
                           ordering       = EXCLUDED.ordering,
                           source_path    = EXCLUDED.source_path,
                           source_hash    = EXCLUDED.source_hash,
                           last_synced_at = NOW(),
                           updated_at     = NOW()
                    """
                ),
                {
                    "slug": slug,
                    "filename": md_file.name,
                    "title": title,
                    "content": content,
                    "ordering": ordering,
                    "source_path": str(md_file.relative_to(_PROJECT_ROOT)),
                    "source_hash": sha,
                },
            )
            upserted += 1

        if prune and not dry_run:
            # Delete DB rows for files that no longer exist on disk.
            result = db.execute(
                text(
                    """
                    DELETE FROM private_guides
                    WHERE slug = :slug
                      AND filename <> ALL(:keep)
                    RETURNING filename
                    """
                ),
                {"slug": slug, "keep": seen_filenames},
            )
            deleted_rows = result.fetchall()
            deleted = len(deleted_rows)
            for r in deleted_rows:
                log.info("  pruned: %s/%s", slug, r[0])

        if not dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "slug": slug,
        "files": len(files),
        "upserted": upserted,
        "deleted": deleted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync private guides disk -> DB")
    parser.add_argument("slug", nargs="?", help="Slug to sync (omit with --all)")
    parser.add_argument("--all", action="store_true", help="Sync every slug folder")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, no writes")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete DB rows for files no longer on disk",
    )
    args = parser.parse_args()

    if args.all and args.slug:
        parser.error("Use either <slug> or --all, not both")
    if not args.all and not args.slug:
        parser.error("Provide a slug or --all")

    slugs = list_slugs() if args.all else [args.slug]
    if not slugs:
        log.error("No slug folders found under %s", PRIVATE_GUIDES_DIR)
        return 1

    summary = []
    for slug in slugs:
        try:
            summary.append(sync_slug(slug, dry_run=args.dry_run, prune=args.prune))
        except Exception as e:
            log.error("Sync failed for slug=%s: %s", slug, e)
            return 2

    log.info("Summary (dry_run=%s, prune=%s):", args.dry_run, args.prune)
    for s in summary:
        log.info(
            "  %s -> %d files / %d upserted / %d deleted",
            s["slug"], s["files"], s["upserted"], s["deleted"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
