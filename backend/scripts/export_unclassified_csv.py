"""
Export Unclassified Laws to CSV

Creates a CSV file with all remaining unclassified primary laws
for manual review and analysis.

Usage:
    python -m backend.scripts.export_unclassified_csv
    python -m backend.scripts.export_unclassified_csv --output custom_name.csv
"""

import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw


def analyze_why_unclassified(law: EULaw) -> str:
    """Analyze why a law might be unclassified"""
    reasons = []

    # Check what data is missing
    if not law.celex:
        reasons.append("No CELEX")
    if not law.subject_matter or len(law.subject_matter) == 0:
        reasons.append("No subject matter")
    if not law.legal_basis or len(law.legal_basis) == 0:
        reasons.append("No legal basis")
    if not law.citations or len(law.citations) == 0:
        reasons.append("No citations")
    if not law.doc_type or law.doc_type == "Unknown":
        reasons.append("Unknown doc type")

    # Check if title is very short (likely insufficient)
    if law.title and len(law.title) < 50:
        reasons.append("Very short title")

    # Check for generic indicators
    if law.doc_type:
        doc_type_lower = law.doc_type.lower()
        if any(word in doc_type_lower for word in ['amending', 'implementing', 'derogating']):
            reasons.append("Derivative legislation")

    # Check for procedural keywords
    if law.title:
        title_lower = law.title.lower()
        procedural_keywords = ['establishing', 'laying down', 'concerning the']
        if any(kw in title_lower for kw in procedural_keywords):
            reasons.append("Procedural/Generic wording")

    if not reasons:
        reasons.append("Insufficient distinctive content")

    return "; ".join(reasons)


def export_to_csv(output_file: str):
    """Export unclassified laws to CSV"""
    db = SessionLocal()

    try:
        # Get all unclassified primary laws
        unclassified = db.query(EULaw).filter(
            EULaw.policy_area.is_(None),
            EULaw.is_primary_legislation == True
        ).order_by(EULaw.date.desc()).all()

        total = len(unclassified)

        print(f"📊 Found {total:,} unclassified primary laws")
        print(f"📄 Exporting to: {output_file}")

        # Define CSV columns
        fieldnames = [
            'celex',
            'title',
            'doc_type',
            'date',
            'oj_reference',
            'has_legal_basis',
            'legal_basis_count',
            'legal_basis_sample',
            'has_citations',
            'citations_count',
            'citations_sample',
            'has_subject_matter',
            'subject_matter_count',
            'subject_matter_sample',
            'uuid',
            'xml_path',
            'likely_reason_unclassified'
        ]

        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for i, law in enumerate(unclassified, 1):
                # Prepare row data
                row = {
                    'celex': law.celex or '',
                    'title': law.title[:200] if law.title else '',  # Truncate long titles
                    'doc_type': law.doc_type or '',
                    'date': law.date.isoformat() if law.date else '',
                    'oj_reference': law.oj_reference or '',

                    # Legal basis
                    'has_legal_basis': 'Yes' if law.legal_basis and len(law.legal_basis) > 0 else 'No',
                    'legal_basis_count': len(law.legal_basis) if law.legal_basis else 0,
                    'legal_basis_sample': ', '.join(law.legal_basis[:3]) if law.legal_basis else '',

                    # Citations
                    'has_citations': 'Yes' if law.citations and len(law.citations) > 0 else 'No',
                    'citations_count': len(law.citations) if law.citations else 0,
                    'citations_sample': ', '.join(law.citations[:3]) if law.citations else '',

                    # Subject matter
                    'has_subject_matter': 'Yes' if law.subject_matter and len(law.subject_matter) > 0 else 'No',
                    'subject_matter_count': len(law.subject_matter) if law.subject_matter else 0,
                    'subject_matter_sample': ', '.join(law.subject_matter[:5]) if law.subject_matter else '',

                    # Metadata
                    'uuid': law.uuid,
                    'xml_path': law.xml_path,

                    # Analysis
                    'likely_reason_unclassified': analyze_why_unclassified(law)
                }

                writer.writerow(row)

                # Progress
                if i % 1000 == 0:
                    print(f"   Exported {i:,}/{total:,} ({i/total*100:.1f}%)")

        print(f"\n✅ Export complete!")
        print(f"   File: {output_file}")
        print(f"   Total rows: {total:,}")

        # Print summary statistics
        print(f"\n📊 SUMMARY STATISTICS:")

        # Count by missing data
        no_celex = sum(1 for law in unclassified if not law.celex)
        no_subject = sum(1 for law in unclassified if not law.subject_matter or len(law.subject_matter) == 0)
        no_basis = sum(1 for law in unclassified if not law.legal_basis or len(law.legal_basis) == 0)
        no_citations = sum(1 for law in unclassified if not law.citations or len(law.citations) == 0)

        print(f"   Missing CELEX: {no_celex:,} ({no_celex/total*100:.1f}%)")
        print(f"   Missing subject matter: {no_subject:,} ({no_subject/total*100:.1f}%)")
        print(f"   Missing legal basis: {no_basis:,} ({no_basis/total*100:.1f}%)")
        print(f"   Missing citations: {no_citations:,} ({no_citations/total*100:.1f}%)")

        # Count by document type
        from collections import Counter
        doc_types = Counter(law.doc_type for law in unclassified if law.doc_type)

        print(f"\n📝 TOP 10 DOCUMENT TYPES:")
        for doc_type, count in doc_types.most_common(10):
            print(f"   {doc_type[:60]:60s}: {count:,}")

        # Count by year
        years = Counter(law.date.year for law in unclassified if law.date)
        print(f"\n📅 TOP 10 YEARS:")
        for year, count in sorted(years.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {year}: {count:,}")

    except Exception as e:
        print(f"\n❌ Export failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def main():
    """Main export function"""
    parser = argparse.ArgumentParser(
        description="Export unclassified laws to CSV"
    )

    parser.add_argument(
        '--output',
        type=str,
        default=f'unclassified_laws_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        help='Output CSV filename'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("EXPORT UNCLASSIFIED LAWS TO CSV")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    export_to_csv(args.output)

    print(f"\n✅ CSV file ready for review!")
    print(f"\n💡 Next steps:")
    print(f"   1. Open {args.output} in Excel/Google Sheets")
    print(f"   2. Sort by 'likely_reason_unclassified' column")
    print(f"   3. Review patterns in unclassified laws")
    print(f"   4. Decide on classification strategy")


if __name__ == "__main__":
    main()
