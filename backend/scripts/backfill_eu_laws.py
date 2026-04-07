"""
Backfill derived fields in eu_laws table.

Populates celex_year/type/number from CELEX string and computes content_hash
from XML files for delta detection during corpus updates.

Usage:
    cd backend
    python3.12 -m backend.scripts.backfill_eu_laws [--dry-run] [--limit N] [--skip-hash]
"""

import argparse
import hashlib
import logging
import re
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

CELEX_PATTERN = re.compile(r"^3\d{4}[A-Z]\d{4,}$")
BATCH_SIZE = 500


def parse_celex(celex: str) -> dict | None:
    """Parse CELEX string into year, type, number components."""
    if not celex or not CELEX_PATTERN.match(celex):
        return None
    return {
        "celex_year": int(celex[1:5]),
        "celex_type": celex[5],
        "celex_number": int(celex[6:]),
    }


PROJECT_ROOT = Path(__file__).parent.parent.parent


def compute_content_hash(xml_path: str) -> str | None:
    """Compute SHA-256 hash of XML file content."""
    path = Path(xml_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return None
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception as e:
        log.warning("[WARN] Failed to read %s: %s", xml_path, e)
        return None


def main():
    parser = argparse.ArgumentParser(description="Backfill derived fields in eu_laws table")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes")
    parser.add_argument("--limit", type=int, default=0, help="Process only N rows (0 = all)")
    parser.add_argument("--skip-hash", action="store_true", help="Skip content hash computation")
    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Count total rows
        query = db.query(EULaw)
        if args.limit > 0:
            query = query.limit(args.limit)
        rows = query.all()
        total = len(rows)

        log.info("[INFO] Found %d rows to process (dry_run=%s, skip_hash=%s)", total, args.dry_run, args.skip_hash)

        celex_parsed = 0
        hash_computed = 0
        celex_skipped = 0
        hash_skipped = 0
        corpus_set = 0
        errors = 0
        dirty_count = 0
        start_time = time.time()

        for i, law in enumerate(rows):
            dirty = False

            # 1. Parse CELEX into components
            if law.celex and law.celex_year is None:
                parsed = parse_celex(law.celex)
                if parsed:
                    law.celex_year = parsed["celex_year"]
                    law.celex_type = parsed["celex_type"]
                    law.celex_number = parsed["celex_number"]
                    celex_parsed += 1
                    dirty = True
                else:
                    log.warning("[WARN] Invalid CELEX format: '%s' (id=%d)", law.celex, law.id)
                    celex_skipped += 1
            elif not law.celex:
                celex_skipped += 1

            # 2. Compute content hash
            if not args.skip_hash and law.content_hash is None:
                if law.xml_path:
                    file_hash = compute_content_hash(law.xml_path)
                    if file_hash:
                        law.content_hash = file_hash
                        hash_computed += 1
                        dirty = True
                    else:
                        hash_skipped += 1
                else:
                    hash_skipped += 1
            elif args.skip_hash:
                pass  # intentionally skipping

            # 3. Set corpus defaults
            if law.corpus_version is None:
                law.corpus_version = "LEG_2025-11"
                corpus_set += 1
                dirty = True
            if law.corpus_status is None:
                law.corpus_status = "active"
                corpus_set += 1
                dirty = True

            if dirty:
                dirty_count += 1

            # Batch commit every BATCH_SIZE rows
            if (i + 1) % BATCH_SIZE == 0 and not args.dry_run:
                try:
                    db.commit()
                except Exception as e:
                    log.error("[ERROR] Batch commit failed at row %d: %s", i + 1, e)
                    db.rollback()
                    errors += 1

            # Progress logging every 1000 rows
            if (i + 1) % 1000 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - i - 1) / rate if rate > 0 else 0
                log.info(
                    "[INFO] Progress: %d/%d (%.1f%%) | %.0f rows/sec | ETA: %.0fs",
                    i + 1, total, (i + 1) / total * 100, rate, remaining,
                )

        # Final commit
        if not args.dry_run:
            try:
                db.commit()
            except Exception as e:
                log.error("[ERROR] Final commit failed: %s", e)
                db.rollback()
                errors += 1

        elapsed = time.time() - start_time
        log.info("[OK] Backfill complete in %.1fs", elapsed)
        log.info("[INFO] Summary:")
        log.info("  CELEX parsed:    %d", celex_parsed)
        log.info("  CELEX skipped:   %d", celex_skipped)
        log.info("  Hashes computed: %d", hash_computed)
        log.info("  Hashes skipped:  %d", hash_skipped)
        log.info("  Corpus defaults: %d", corpus_set)
        log.info("  Rows modified:   %d", dirty_count)
        log.info("  Errors:          %d", errors)
        if args.dry_run:
            log.info("  [DRY RUN] No changes written to database")

    finally:
        db.close()


if __name__ == "__main__":
    main()
