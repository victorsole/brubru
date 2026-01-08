"""
Import LEG_2025-11 Archive into eu_laws Table

This script indexes the 71K EU law documents from the LEG_2025-11 Formex XML archive
into the Supabase eu_laws table.

Usage:
    python -m backend.scripts.import_leg_archive [--limit N] [--dry-run]

Options:
    --limit N    Only process N documents (for testing)
    --dry-run    Parse but don't insert into database
    --verbose    Show detailed progress
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.parsers.formex_parser import FormexParser, ParsedLaw
from backend.core.database import get_db, SessionLocal
from backend.models.eu_law import EULaw

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


def find_main_xml_files(archive_path: Path) -> list[tuple[str, Path]]:
    """
    Find all main XML files in the LEG archive.

    Returns list of (uuid, xml_path) tuples.
    Main files are those in fmx4/ directories that don't end with .doc.fmx.xml or .toc.fmx.xml
    """
    results = []

    for uuid_dir in archive_path.iterdir():
        if not uuid_dir.is_dir() or uuid_dir.name.startswith('.'):
            continue

        fmx4_dir = uuid_dir / 'fmx4'
        if not fmx4_dir.exists():
            continue

        uuid = uuid_dir.name

        # Find main XML file (usually the one with .000101. in the name or first page)
        xml_files = list(fmx4_dir.glob('*.xml'))

        # Filter out metadata files
        main_files = [
            f for f in xml_files
            if not f.name.endswith('.doc.fmx.xml')
            and not f.name.endswith('.toc.fmx.xml')
            and '.000101.' in f.name  # Main document is usually page 1
        ]

        # If no .000101. file, try to find the first page
        if not main_files:
            main_files = [
                f for f in xml_files
                if not f.name.endswith('.doc.fmx.xml')
                and not f.name.endswith('.toc.fmx.xml')
            ]
            # Sort to get the first page
            main_files.sort(key=lambda x: x.name)

        if main_files:
            results.append((uuid, main_files[0]))

    return results


def determine_policy_area(parsed: ParsedLaw) -> Optional[str]:
    """Determine policy area from document content."""
    title_lower = parsed.title.lower() if parsed.title else ""
    doc_type_lower = parsed.doc_type.lower() if parsed.doc_type else ""

    # Policy area keywords
    policy_keywords = {
        "Digital Policy and Digital Economy": [
            "artificial intelligence", "ai system", "digital", "data protection",
            "privacy", "cybersecurity", "electronic", "platform", "online"
        ],
        "Environment and Climate Action": [
            "environment", "climate", "emission", "carbon", "biodiversity",
            "sustainability", "waste", "recycling", "pollution", "green"
        ],
        "Economic and Financial Affairs": [
            "financial", "banking", "investment", "capital market", "insurance",
            "credit", "payment", "securities", "euro", "monetary"
        ],
        "Agriculture": [
            "agricultural", "farm", "food", "wine", "organic", "plant",
            "animal", "fisheries", "geographical indication"
        ],
        "Health and Food Safety": [
            "health", "medical", "pharmaceutical", "medicine", "clinical",
            "patient", "disease", "safety", "sanitary"
        ],
        "Transport": [
            "transport", "aviation", "maritime", "railway", "road",
            "vehicle", "driver", "traffic"
        ],
        "Migration and Home Affairs": [
            "migration", "asylum", "border", "visa", "refugee",
            "schengen", "frontex"
        ],
        "Competition and State Aid": [
            "competition", "antitrust", "merger", "state aid", "subsidy"
        ],
        "Employment and Social Affairs": [
            "employment", "worker", "labour", "social", "pension",
            "working time", "health and safety at work"
        ],
        "Energy": [
            "energy", "electricity", "gas", "renewable", "nuclear",
            "power", "grid"
        ],
        "Trade": [
            "trade", "customs", "tariff", "import", "export",
            "dumping", "safeguard"
        ],
    }

    combined_text = f"{title_lower} {doc_type_lower}"

    for policy_area, keywords in policy_keywords.items():
        for keyword in keywords:
            if keyword in combined_text:
                return policy_area

    return None


def is_primary_legislation(parsed: ParsedLaw) -> bool:
    """Determine if this is primary legislation (vs annex, ToC, etc.)."""
    doc_type_lower = parsed.doc_type.lower() if parsed.doc_type else ""

    # Primary types
    primary_keywords = [
        "regulation", "directive", "decision", "recommendation", "opinion"
    ]

    return any(kw in doc_type_lower for kw in primary_keywords)


def import_document(
    db,
    uuid: str,
    xml_path: Path,
    parser: FormexParser,
    dry_run: bool = False
) -> Optional[EULaw]:
    """
    Parse and import a single document.

    Returns EULaw object if successful, None if skipped/failed.
    """
    try:
        parsed = parser.parse_file(xml_path)

        # Skip if no title (likely not a valid legal document)
        if not parsed.title:
            logger.debug(f"Skipping {uuid}: no title")
            return None

        # Check if already exists (skip in dry-run mode)
        if not dry_run and db:
            existing = db.query(EULaw).filter(EULaw.uuid == uuid).first()
            if existing:
                logger.debug(f"Skipping {uuid}: already exists")
                return existing

        # Create EULaw object
        eu_law = EULaw(
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
            extra_metadata={
                "short_title": parsed.short_title,
                "language": parsed.language,
                "page_count": parsed.page_count,
                "eea_relevance": parsed.eea_relevance,
                "article_count": len(parsed.articles),
                "recital_count": len(parsed.recitals),
                "annex_count": len(parsed.annexes),
            }
        )

        if not dry_run:
            db.add(eu_law)
            db.commit()
            db.refresh(eu_law)

        return eu_law

    except Exception as e:
        logger.error(f"Error processing {uuid}: {e}")
        if not dry_run:
            db.rollback()
        return None


def main():
    parser = argparse.ArgumentParser(description='Import LEG_2025-11 archive into eu_laws table')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of documents to process')
    parser.add_argument('--dry-run', action='store_true', help='Parse but do not insert into database')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress')
    parser.add_argument('--archive-path', type=str, default='docs/LEG_2025-11',
                        help='Path to LEG archive directory')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Find archive path
    archive_path = Path(args.archive_path)
    if not archive_path.is_absolute():
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent
        archive_path = project_root / args.archive_path

    if not archive_path.exists():
        logger.error(f"Archive path not found: {archive_path}")
        sys.exit(1)

    logger.info(f"Scanning archive: {archive_path}")

    # Find all XML files
    xml_files = find_main_xml_files(archive_path)
    total_files = len(xml_files)
    logger.info(f"Found {total_files} documents to process")

    if args.limit:
        xml_files = xml_files[:args.limit]
        logger.info(f"Limited to {len(xml_files)} documents")

    # Initialize parser
    formex_parser = FormexParser()

    # Statistics
    stats = {
        "processed": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "by_policy": {},
        "by_type": {},
    }

    # Process documents
    start_time = datetime.now()

    if args.dry_run:
        logger.info("DRY RUN - no database changes will be made")
        db = None
    else:
        db = SessionLocal()

    try:
        for i, (uuid, xml_path) in enumerate(xml_files):
            if (i + 1) % 100 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total_files - i - 1) / rate if rate > 0 else 0
                logger.info(
                    f"Progress: {i + 1}/{len(xml_files)} ({rate:.1f}/s, ETA: {eta/60:.1f} min) - "
                    f"Imported: {stats['imported']}, Errors: {stats['errors']}"
                )

            stats["processed"] += 1

            result = import_document(db, uuid, xml_path, formex_parser, args.dry_run)

            if result:
                stats["imported"] += 1

                # Track by policy area
                policy = result.policy_area or "Unknown"
                stats["by_policy"][policy] = stats["by_policy"].get(policy, 0) + 1

                # Track by document type
                doc_type = result.doc_type or "Unknown"
                # Simplify doc type
                if "Regulation" in doc_type:
                    doc_type = "Regulation"
                elif "Directive" in doc_type:
                    doc_type = "Directive"
                elif "Decision" in doc_type:
                    doc_type = "Decision"
                stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1
            else:
                stats["skipped"] += 1

    finally:
        if db:
            db.close()

    # Print summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info("IMPORT COMPLETE")
    logger.info(f"Time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Imported: {stats['imported']}")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("")
    logger.info("By Policy Area:")
    for policy, count in sorted(stats["by_policy"].items(), key=lambda x: -x[1]):
        logger.info(f"  {policy}: {count}")
    logger.info("")
    logger.info("By Document Type:")
    for doc_type, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        logger.info(f"  {doc_type}: {count}")


if __name__ == "__main__":
    main()
