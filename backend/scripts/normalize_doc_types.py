"""
Normalize doc_type values in eu_laws table.

Maps ~150 raw doc_type values into 10 clean categories in doc_type_normalized column.

Usage:
    cd backend
    python3.12 -m backend.scripts.normalize_doc_types [--dry-run] [--verbose]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import update, func, text
from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Normalization rules in priority order (first match wins).
# Each entry: (normalized_category, list_of_ILIKE_patterns)
NORMALIZATION_RULES = [
    ("Regulation",        ["%regulation%"]),
    ("Directive",         ["%directive%"]),
    ("Decision",          ["%decision%"]),
    ("Recommendation",    ["%recommendation%"]),
    ("Opinion",           ["%opinion%"]),
    ("Agreement",         ["%agreement%", "%convention%"]),
    ("Corrigendum",       ["%corrigendum%", "%erratum%", "%correction%"]),
    ("Annex",             ["annex%"]),
    ("Table of Contents", ["%official journal%", "%table of contents%"]),
]


def show_current_distribution(db):
    """Show top 30 raw doc_type values by frequency."""
    logger.info("[INFO] Current doc_type distribution (top 30):")
    logger.info("-" * 70)

    results = db.execute(
        text("""
            SELECT doc_type, COUNT(*) as cnt
            FROM eu_laws
            GROUP BY doc_type
            ORDER BY cnt DESC
            LIMIT 30
        """)
    ).fetchall()

    for row in results:
        logger.info(f"  {row.cnt:>6}  {row.doc_type}")

    total = db.execute(text("SELECT COUNT(*) FROM eu_laws")).scalar()
    distinct = db.execute(text("SELECT COUNT(DISTINCT doc_type) FROM eu_laws")).scalar()
    logger.info("-" * 70)
    logger.info(f"[INFO] Total rows: {total}, Distinct doc_type values: {distinct}")
    logger.info("")


def normalize(db, dry_run: bool = False, verbose: bool = False):
    """Apply normalization rules in priority order."""
    logger.info("[INFO] Applying normalization rules...")
    logger.info("")

    # Track which rows have already been categorized so earlier rules take priority.
    # We do this by only updating rows where doc_type_normalized IS NULL,
    # setting it progressively per category.

    # First, clear existing values so we can re-run idempotently
    clear_stmt = update(EULaw).values(doc_type_normalized=None)
    if verbose:
        logger.info(f"[INFO] Clearing existing doc_type_normalized values")
    db.execute(clear_stmt)

    total_updated = 0

    for category, patterns in NORMALIZATION_RULES:
        # Build OR condition: doc_type ILIKE pattern1 OR doc_type ILIKE pattern2 ...
        # Only update rows not yet categorized (doc_type_normalized IS NULL)
        conditions = " OR ".join(f"doc_type ILIKE :p{i}" for i in range(len(patterns)))
        params = {f"p{i}": pat for i, pat in enumerate(patterns)}

        sql = text(f"""
            UPDATE eu_laws
            SET doc_type_normalized = :category
            WHERE doc_type_normalized IS NULL
              AND ({conditions})
        """)
        params["category"] = category

        if verbose:
            logger.info(f"[INFO] SQL: UPDATE eu_laws SET doc_type_normalized = '{category}' "
                        f"WHERE doc_type_normalized IS NULL AND ({conditions})")
            logger.info(f"       Patterns: {patterns}")

        result = db.execute(sql, params)
        count = result.rowcount
        total_updated += count
        logger.info(f"[OK]   {category:<20s} -> {count:>6} rows updated")

    # Apply "Other" to everything still NULL
    other_sql = text("""
        UPDATE eu_laws
        SET doc_type_normalized = 'Other'
        WHERE doc_type_normalized IS NULL
    """)
    if verbose:
        logger.info("[INFO] SQL: UPDATE eu_laws SET doc_type_normalized = 'Other' "
                    "WHERE doc_type_normalized IS NULL")
    result = db.execute(other_sql)
    other_count = result.rowcount
    total_updated += other_count
    logger.info(f"[OK]   {'Other':<20s} -> {other_count:>6} rows updated")

    logger.info("")
    logger.info(f"[INFO] Total rows updated: {total_updated}")
    logger.info("")

    return total_updated


def show_final_distribution(db):
    """Show normalized distribution."""
    logger.info("[INFO] Final doc_type_normalized distribution:")
    logger.info("-" * 50)

    results = db.execute(
        text("""
            SELECT doc_type_normalized, COUNT(*) as cnt
            FROM eu_laws
            GROUP BY doc_type_normalized
            ORDER BY cnt DESC
        """)
    ).fetchall()

    for row in results:
        logger.info(f"  {row.cnt:>6}  {row.doc_type_normalized}")

    logger.info("-" * 50)
    logger.info("")


def main():
    parser = argparse.ArgumentParser(description="Normalize doc_type values in eu_laws table")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without committing")
    parser.add_argument("--verbose", action="store_true",
                        help="Show every UPDATE SQL statement")
    args = parser.parse_args()

    db = SessionLocal()

    try:
        show_current_distribution(db)
        normalize(db, dry_run=args.dry_run, verbose=args.verbose)
        show_final_distribution(db)

        if args.dry_run:
            logger.info("[INFO] DRY RUN -- rolling back all changes")
            db.rollback()
        else:
            db.commit()
            logger.info("[OK] All changes committed")

    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
