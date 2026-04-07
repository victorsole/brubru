"""
Fix Missing CELEX Numbers in eu_laws Table

Re-parses XML files to extract document numbers and constructs proper CELEX identifiers.
CELEX format: 3{year}{type_code}{number_padded_to_4}

Usage:
    cd backend
    python3.12 -m backend.scripts.fix_celex_numbers [--dry-run] [--limit N] [--verbose]
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw


# ---------------------------------------------------------------------------
# Type-code mapping from doc_type column
# ---------------------------------------------------------------------------

SKIP_PATTERNS = [
    "annex",
    "official journal",
    "table of contents",
    "corrigendum",
]

TYPE_CODE_MAP = [
    ("regulation", "R"),
    ("directive", "L"),
    ("decision", "D"),
    ("recommendation", "H"),
    ("agreement", "X"),
]

DEFAULT_TYPE_CODE = "R"  # regulations are most common


def should_skip(doc_type: str | None, title: str | None) -> bool:
    """Return True if this document type should not receive a CELEX."""
    combined = ((doc_type or "") + " " + (title or "")).lower()
    return any(p in combined for p in SKIP_PATTERNS)


def determine_type_code(doc_type: str | None) -> str:
    """Map the doc_type column to a single-char CELEX type code."""
    if not doc_type:
        return DEFAULT_TYPE_CODE
    dt_lower = doc_type.lower()
    for keyword, code in TYPE_CODE_MAP:
        if keyword in dt_lower:
            return code
    return DEFAULT_TYPE_CODE


# ---------------------------------------------------------------------------
# XML extraction of NO.DOC
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent


def extract_from_xml(xml_path: str) -> tuple[str | None, str | None]:
    """
    Parse XML to extract year and document number from <NO.DOC>.

    Returns (year, number) as strings, or (None, None) on failure.
    """
    path = Path(xml_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return None, None

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError):
        return None, None

    # Search for NO.DOC anywhere in the tree
    for no_doc in root.iter("NO.DOC"):
        year_el = no_doc.find("YEAR")
        num_el = no_doc.find("NO.CURRENT")
        if year_el is not None and num_el is not None:
            year = (year_el.text or "").strip()
            number = (num_el.text or "").strip()
            if year and number:
                return year, number

    return None, None


# ---------------------------------------------------------------------------
# Title-based fallback regex
# ---------------------------------------------------------------------------

# Matches patterns like (EU) 2024/1689, (EC) No 1308/2013, (EU) No 2024/1689
TITLE_PATTERN = re.compile(
    r"\((?:EU|EC|EEC|Euratom)\)\s*(?:No\s+)?(\d{4})/(\d+)",
    re.IGNORECASE,
)

# Also matches reversed format: No 1308/2013 (where year could be second)
TITLE_PATTERN_ALT = re.compile(
    r"(?:No|Nr\.?)\s+(\d+)/(\d{4})",
    re.IGNORECASE,
)


def extract_from_title(title: str | None) -> tuple[str | None, str | None]:
    """
    Regex fallback: extract year and number from the title string.

    Returns (year, number) as strings, or (None, None).
    """
    if not title:
        return None, None

    # Primary pattern: (EU) 2024/1689
    m = TITLE_PATTERN.search(title)
    if m:
        return m.group(1), m.group(2)

    # Alt pattern: No 1308/2013 (number/year)
    m = TITLE_PATTERN_ALT.search(title)
    if m:
        number, year = m.group(1), m.group(2)
        return year, number

    return None, None


# ---------------------------------------------------------------------------
# CELEX construction
# ---------------------------------------------------------------------------

def build_celex(year: str, type_code: str, number: str) -> str | None:
    """Construct a CELEX string: 3{year}{type_code}{number.zfill(4)}."""
    if not year or not number:
        return None
    # Validate year is 4 digits
    if not re.match(r"^\d{4}$", year):
        return None
    # Validate number is numeric
    if not number.isdigit():
        return None
    return f"3{year}{type_code}{number.zfill(4)}"


# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fix missing CELEX numbers in eu_laws table")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no database changes")
    parser.add_argument("--limit", type=int, default=0, help="Process only N documents (0 = all)")
    parser.add_argument("--verbose", action="store_true", help="Show each CELEX constructed")
    args = parser.parse_args()

    db = SessionLocal()

    try:
        # Query all laws without CELEX
        query = db.query(EULaw).filter(EULaw.celex.is_(None))
        total_null = query.count()
        print(f"[INFO] Found {total_null} eu_laws rows with celex IS NULL")

        if args.limit > 0:
            laws = query.limit(args.limit).all()
            print(f"[INFO] Processing {len(laws)} (limited to {args.limit})")
        else:
            laws = query.all()
            print(f"[INFO] Processing all {len(laws)} rows")

        # Pre-load existing CELEX values for duplicate detection
        existing_celex = set()
        for (c,) in db.query(EULaw.celex).filter(EULaw.celex.isnot(None)).all():
            existing_celex.add(c)
        print(f"[INFO] {len(existing_celex)} existing CELEX values loaded for duplicate check")

        # Counters
        fixed = 0
        skipped = 0
        errors = 0
        file_not_found = 0
        duplicates = 0
        type_distribution = Counter()
        source_distribution = Counter()  # xml vs title vs failed
        pending_updates = []

        for i, law in enumerate(laws, 1):
            # Skip annexes, ToCs, corrigenda
            if should_skip(law.doc_type, law.title):
                skipped += 1
                if args.verbose:
                    print(f"  [SKIP] id={law.id} doc_type={law.doc_type}")
                continue

            type_code = determine_type_code(law.doc_type)

            # Strategy 1: Parse XML
            year, number = extract_from_xml(law.xml_path)
            source = "xml"

            if year is None:
                # Check if file existed
                check_path = Path(law.xml_path)
                if not check_path.is_absolute():
                    check_path = PROJECT_ROOT / check_path
                if not check_path.exists():
                    file_not_found += 1

                # Strategy 2: Regex on title
                year, number = extract_from_title(law.title)
                source = "title"

            if year is None:
                errors += 1
                if args.verbose:
                    print(f"  [ERROR] id={law.id} -- could not extract year/number")
                    print(f"          xml_path={law.xml_path}")
                    print(f"          title={law.title[:100] if law.title else '(none)'}")
                continue

            celex = build_celex(year, type_code, number)
            if not celex:
                errors += 1
                if args.verbose:
                    print(f"  [ERROR] id={law.id} -- invalid celex components year={year} num={number}")
                continue

            # Duplicate check
            if celex in existing_celex:
                duplicates += 1
                if args.verbose:
                    print(f"  [WARN] id={law.id} -- duplicate CELEX {celex} (already exists)")
                # Still assign it -- duplicates can happen (e.g. different language versions)
                # but we warn about it

            if args.verbose:
                print(f"  [OK] id={law.id} celex={celex} (from {source})")

            # Stage the update
            law.celex = celex
            law.celex_year = int(year)
            law.celex_type = type_code
            law.celex_number = int(number)

            existing_celex.add(celex)
            type_distribution[type_code] += 1
            source_distribution[source] += 1
            fixed += 1

            # Batch commit every 500
            if not args.dry_run and fixed % 500 == 0:
                db.commit()
                print(f"[INFO] Committed batch -- {fixed} fixed so far ({i}/{len(laws)} processed)")

        # Final commit
        if not args.dry_run and fixed > 0:
            db.commit()
            print(f"[INFO] Final commit done")
        elif args.dry_run:
            db.rollback()
            print(f"[INFO] Dry run -- no changes written to database")

        # Summary
        print("")
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Total NULL celex rows:    {total_null}")
        print(f"  Processed:                {len(laws)}")
        print(f"  Fixed:                    {fixed}")
        print(f"  Skipped (annex/ToC/etc):  {skipped}")
        print(f"  Errors (no data found):   {errors}")
        print(f"  File not found on disk:   {file_not_found}")
        print(f"  Duplicate CELEX warnings: {duplicates}")
        print("")
        print("  Type code distribution:")
        for code in sorted(type_distribution.keys()):
            label = {"R": "Regulation", "L": "Directive", "D": "Decision", "H": "Recommendation", "X": "Other"}
            print(f"    {code} ({label.get(code, '?')}): {type_distribution[code]}")
        print("")
        print("  Source distribution:")
        for src, count in source_distribution.most_common():
            print(f"    {src}: {count}")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
