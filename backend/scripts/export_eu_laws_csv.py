"""
Export eu_laws table to CSV master file.

Usage:
    cd backend
    python3.12 -m backend.scripts.export_eu_laws_csv [--output PATH] [--primary-only]
"""

import argparse
import csv
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw


def export_eu_laws_csv(output_path: str, primary_only: bool = False):
    """Export eu_laws table to CSV."""
    db = SessionLocal()

    try:
        query = db.query(EULaw)

        if primary_only:
            query = query.filter(EULaw.is_primary_legislation == True)

        # Sort by date DESC (nulls last)
        query = query.order_by(EULaw.date.desc().nullslast())

        laws = query.all()
        print(f"[INFO] Queried {len(laws)} rows from eu_laws")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        columns = [
            "celex", "uuid", "doc_type_normalized", "title", "date",
            "policy_area", "celex_year", "celex_type",
            "is_primary_legislation", "oj_reference",
            "corpus_version", "corpus_status", "citation_count"
        ]

        rows_written = 0
        rows_with_celex = 0
        rows_with_policy_area = 0

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(columns)

            for law in laws:
                title_truncated = (law.title[:200] + "...") if law.title and len(law.title) > 200 else (law.title or "")
                citation_count = len(law.citations) if law.citations else 0

                writer.writerow([
                    law.celex or "",
                    law.uuid or "",
                    law.doc_type_normalized or "",
                    title_truncated,
                    law.date.isoformat() if law.date else "",
                    law.policy_area or "",
                    law.celex_year or "",
                    law.celex_type or "",
                    law.is_primary_legislation if law.is_primary_legislation is not None else "",
                    law.oj_reference or "",
                    law.corpus_version or "",
                    law.corpus_status or "",
                    citation_count,
                ])

                rows_written += 1
                if law.celex:
                    rows_with_celex += 1
                if law.policy_area:
                    rows_with_policy_area += 1

        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)

        print(f"[OK] Exported {rows_written} rows to {output_path}")
        print(f"[INFO] Rows with CELEX: {rows_with_celex} ({rows_with_celex * 100 // max(rows_written, 1)}%)")
        print(f"[INFO] Rows with policy area: {rows_with_policy_area} ({rows_with_policy_area * 100 // max(rows_written, 1)}%)")
        print(f"[INFO] File size: {file_size_mb:.2f} MB ({file_size:,} bytes)")

        if primary_only:
            print(f"[INFO] Filter: primary legislation only")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Export eu_laws table to CSV")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output CSV file path (default: data/eu_laws_master.csv)"
    )
    parser.add_argument(
        "--primary-only", action="store_true",
        help="Exclude annexes (is_primary_legislation = False)"
    )

    args = parser.parse_args()

    # Default output path relative to project root
    if args.output:
        output_path = args.output
    else:
        project_root = Path(__file__).parent.parent.parent
        output_path = str(project_root / "data" / "eu_laws_master.csv")

    print(f"[INFO] Exporting eu_laws to CSV...")
    print(f"[INFO] Output: {output_path}")

    export_eu_laws_csv(output_path, primary_only=args.primary_only)


if __name__ == "__main__":
    main()
