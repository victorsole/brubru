"""
Delta Import for EU Law Corpus Updates

Compares a new corpus directory against the existing eu_laws database,
inserting new laws, updating changed laws, and marking removed laws as repealed.

Usage:
    cd backend
    python3.12 -m backend.scripts.import_corpus_update --corpus-path /path/to/LEG_2026-06 [--dry-run] [--verbose] [--backup]
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw
from backend.services.parsers.formex_parser import FormexParser
from backend.scripts.import_leg_archive import (
    determine_policy_area,
    is_primary_legislation,
    find_main_xml_files,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

BATCH_SIZE = 500
PROGRESS_INTERVAL = 1000


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def detect_corpus_version(corpus_path: Path) -> str:
    """Auto-detect corpus version from directory name (e.g., LEG_2026-06)."""
    name = corpus_path.name
    if name.startswith("LEG_"):
        return name
    return f"LEG_{name}"


def create_backup_table(db, date_str: str, dry_run: bool = False):
    """Create a backup of the eu_laws table."""
    table_name = f"eu_laws_backup_{date_str}"
    if dry_run:
        logger.info(f"[INFO] DRY RUN: Would create backup table {table_name}")
        return
    logger.info(f"[INFO] Creating backup table: {table_name}")
    db.execute(
        __import__('sqlalchemy').text(
            f'CREATE TABLE IF NOT EXISTS "{table_name}" AS SELECT * FROM eu_laws'
        )
    )
    db.commit()
    logger.info(f"[OK] Backup table created: {table_name}")


def process_corpus(
    corpus_path: Path,
    corpus_version: str,
    dry_run: bool = False,
    verbose: bool = False,
    backup: bool = False,
):
    """Main delta import logic."""
    db = SessionLocal()
    formex_parser = FormexParser()

    stats = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "repealed": 0,
        "errors": 0,
    }

    try:
        # Backup if requested
        if backup:
            date_str = datetime.now().strftime("%Y%m%d")
            create_backup_table(db, date_str, dry_run)

        # Find all XML files in new corpus
        logger.info(f"[INFO] Scanning corpus: {corpus_path}")
        xml_files = find_main_xml_files(corpus_path)
        total_files = len(xml_files)
        logger.info(f"[INFO] Found {total_files} documents in new corpus")

        if total_files == 0:
            logger.error("[ERROR] No documents found in corpus. Check the path.")
            return stats

        # Collect new corpus UUIDs for repeal detection later
        new_corpus_uuids = set()

        # Load existing content hashes in bulk for fast lookup
        logger.info("[INFO] Loading existing content hashes from database...")
        existing_rows = db.query(EULaw.uuid, EULaw.content_hash).all()
        existing_hashes = {row.uuid: row.content_hash for row in existing_rows}
        logger.info(f"[INFO] Loaded {len(existing_hashes)} existing laws from database")

        start_time = time.time()
        pending_count = 0

        for i, (uuid, xml_path) in enumerate(xml_files):
            new_corpus_uuids.add(uuid)

            # Progress logging
            if (i + 1) % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = total_files - (i + 1)
                eta = remaining / rate if rate > 0 else 0
                logger.info(
                    f"[INFO] Progress: {i + 1}/{total_files} "
                    f"({rate:.1f}/s, ETA: {eta / 60:.1f} min) -- "
                    f"new={stats['new']}, updated={stats['updated']}, "
                    f"unchanged={stats['unchanged']}, errors={stats['errors']}"
                )

            try:
                # Compute hash of new file
                content_hash = compute_file_hash(xml_path)
                existing_hash = existing_hashes.get(uuid)

                if existing_hash is not None:
                    # UUID exists in DB
                    if existing_hash == content_hash:
                        # Unchanged
                        stats["unchanged"] += 1
                        if verbose:
                            logger.info(f"[INFO] SKIP (unchanged): {uuid}")
                        continue
                    else:
                        # Content changed -- update
                        parsed = formex_parser.parse_file(xml_path)
                        if not parsed.title:
                            stats["errors"] += 1
                            if verbose:
                                logger.warning(f"[WARN] No title after re-parse: {uuid}")
                            continue

                        if not dry_run:
                            law = db.query(EULaw).filter(EULaw.uuid == uuid).first()
                            if law:
                                law.celex = parsed.celex
                                law.doc_type = parsed.doc_type
                                law.title = parsed.title
                                law.date = parsed.date
                                law.oj_reference = parsed.oj_reference
                                law.policy_area = determine_policy_area(parsed)
                                law.is_primary_legislation = is_primary_legislation(parsed)
                                law.legal_basis = parsed.legal_basis if parsed.legal_basis else None
                                law.citations = parsed.citations if parsed.citations else None
                                law.xml_path = str(xml_path)
                                law.content_hash = content_hash
                                law.corpus_version = corpus_version
                                law.corpus_status = "active"
                                law.extra_metadata = {
                                    "short_title": parsed.short_title,
                                    "language": parsed.language,
                                    "page_count": parsed.page_count,
                                    "eea_relevance": parsed.eea_relevance,
                                    "article_count": len(parsed.articles),
                                    "recital_count": len(parsed.recitals),
                                    "annex_count": len(parsed.annexes),
                                }
                                pending_count += 1

                        stats["updated"] += 1
                        if verbose:
                            logger.info(f"[UPDATE] {uuid} ({parsed.celex or 'no CELEX'})")

                else:
                    # New law -- insert
                    parsed = formex_parser.parse_file(xml_path)
                    if not parsed.title:
                        stats["errors"] += 1
                        if verbose:
                            logger.warning(f"[WARN] No title for new doc: {uuid}")
                        continue

                    if not dry_run:
                        new_law = EULaw(
                            uuid=uuid,
                            celex=parsed.celex,
                            doc_type=parsed.doc_type,
                            title=parsed.title,
                            date=parsed.date,
                            oj_reference=parsed.oj_reference,
                            policy_area=determine_policy_area(parsed),
                            is_primary_legislation=is_primary_legislation(parsed),
                            legal_basis=parsed.legal_basis if parsed.legal_basis else None,
                            citations=parsed.citations if parsed.citations else None,
                            xml_path=str(xml_path),
                            content_hash=content_hash,
                            corpus_version=corpus_version,
                            corpus_status="active",
                            extra_metadata={
                                "short_title": parsed.short_title,
                                "language": parsed.language,
                                "page_count": parsed.page_count,
                                "eea_relevance": parsed.eea_relevance,
                                "article_count": len(parsed.articles),
                                "recital_count": len(parsed.recitals),
                                "annex_count": len(parsed.annexes),
                            },
                        )
                        db.add(new_law)
                        pending_count += 1

                    stats["new"] += 1
                    if verbose:
                        logger.info(f"[NEW] {uuid} ({parsed.celex or 'no CELEX'})")

                # Batch commit
                if not dry_run and pending_count >= BATCH_SIZE:
                    db.commit()
                    pending_count = 0

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[ERROR] {uuid}: {e}")
                if not dry_run:
                    db.rollback()
                    pending_count = 0

        # Final commit for remaining rows
        if not dry_run and pending_count > 0:
            db.commit()

        # Mark removed laws as repealed
        logger.info("[INFO] Checking for repealed laws (removed from new corpus)...")
        existing_uuids = set(existing_hashes.keys())
        removed_uuids = existing_uuids - new_corpus_uuids

        if removed_uuids:
            logger.info(f"[INFO] Found {len(removed_uuids)} laws not in new corpus")
            if not dry_run:
                batch = []
                for uuid in removed_uuids:
                    batch.append(uuid)
                    if len(batch) >= BATCH_SIZE:
                        db.query(EULaw).filter(
                            EULaw.uuid.in_(batch),
                            EULaw.corpus_status != "repealed",
                        ).update(
                            {"corpus_status": "repealed", "corpus_version": corpus_version},
                            synchronize_session="fetch",
                        )
                        db.commit()
                        batch = []
                if batch:
                    db.query(EULaw).filter(
                        EULaw.uuid.in_(batch),
                        EULaw.corpus_status != "repealed",
                    ).update(
                        {"corpus_status": "repealed", "corpus_version": corpus_version},
                        synchronize_session="fetch",
                    )
                    db.commit()

            stats["repealed"] = len(removed_uuids)
            if verbose:
                for uuid in list(removed_uuids)[:20]:
                    logger.info(f"[REPEAL] {uuid}")
                if len(removed_uuids) > 20:
                    logger.info(f"[REPEAL] ... and {len(removed_uuids) - 20} more")
        else:
            logger.info("[INFO] No laws removed from corpus")

    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Delta import for EU law corpus updates"
    )
    parser.add_argument(
        "--corpus-path", type=str, required=True,
        help="Path to new corpus directory (e.g., /path/to/LEG_2026-06)"
    )
    parser.add_argument(
        "--corpus-version", type=str, default=None,
        help="Corpus version label (default: auto-detect from directory name)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making DB changes"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show each file as it is processed"
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Create backup table before starting"
    )

    args = parser.parse_args()

    corpus_path = Path(args.corpus_path)
    if not corpus_path.is_absolute():
        project_root = Path(__file__).parent.parent.parent
        corpus_path = project_root / args.corpus_path

    if not corpus_path.exists():
        logger.error(f"[ERROR] Corpus path not found: {corpus_path}")
        sys.exit(1)

    corpus_version = args.corpus_version or detect_corpus_version(corpus_path)

    logger.info("=" * 60)
    logger.info("[INFO] EU Law Corpus Delta Import")
    logger.info(f"[INFO] Corpus path: {corpus_path}")
    logger.info(f"[INFO] Corpus version: {corpus_version}")
    if args.dry_run:
        logger.info("[INFO] DRY RUN -- no database changes will be made")
    if args.backup:
        logger.info("[INFO] Backup table will be created before import")
    logger.info("=" * 60)

    start_time = time.time()
    stats = process_corpus(
        corpus_path=corpus_path,
        corpus_version=corpus_version,
        dry_run=args.dry_run,
        verbose=args.verbose,
        backup=args.backup,
    )
    elapsed = time.time() - start_time

    logger.info("=" * 60)
    logger.info("[OK] DELTA IMPORT COMPLETE")
    logger.info(f"[INFO] Time: {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    logger.info(f"[NEW] New laws inserted: {stats['new']}")
    logger.info(f"[UPDATE] Laws updated: {stats['updated']}")
    logger.info(f"[INFO] Unchanged (skipped): {stats['unchanged']}")
    logger.info(f"[REPEAL] Laws marked repealed: {stats['repealed']}")
    logger.info(f"[ERROR] Errors: {stats['errors']}")
    total_processed = stats['new'] + stats['updated'] + stats['unchanged'] + stats['errors']
    logger.info(f"[INFO] Total files processed: {total_processed}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
