"""
Reclassify Unclassified Primary Legislation

Uses enhanced NLP analysis with full text to classify laws that were
initially marked as "Unclassified" but are actually primary legislation.

Strategy:
1. Focus on primary legislation only (skip annexes)
2. Use full text analysis (not just title)
3. Use subject matter keywords
4. Lower confidence threshold for borderline cases

Usage:
    python -m backend.scripts.reclassify_unclassified
    python -m backend.scripts.reclassify_unclassified --limit 100
    python -m backend.scripts.reclassify_unclassified --min-confidence 0.2
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw
from backend.services.law_database.policy_classifier import get_policy_classifier
from backend.services.law_database.xml_parser import get_xml_parser


async def main():
    """Main reclassification function"""
    parser = argparse.ArgumentParser(
        description="Reclassify unclassified primary legislation using full text analysis"
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of laws to reclassify (for testing)'
    )

    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.2,
        help='Minimum confidence threshold (default: 0.2, lower than normal 0.3)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for database commits (default: 100)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("RECLASSIFY UNCLASSIFIED PRIMARY LEGISLATION")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Min confidence: {args.min_confidence}")
    print(f"Batch size: {args.batch_size}")

    # Initialize services
    classifier = get_policy_classifier()
    xml_parser = get_xml_parser()

    db = SessionLocal()

    try:
        # Get unclassified primary legislation
        query = db.query(EULaw).filter(
            EULaw.policy_area.is_(None),
            EULaw.is_primary_legislation == True
        )

        if args.limit:
            query = query.limit(args.limit)
            print(f"⚠️  LIMITED MODE: Processing only {args.limit} laws")

        unclassified_laws = query.all()

        print(f"\n📊 Found {len(unclassified_laws):,} unclassified primary laws")

        if len(unclassified_laws) == 0:
            print("✅ No unclassified laws to process!")
            return

        # Statistics
        stats = {
            'processed': 0,
            'classified': 0,
            'still_unclassified': 0,
            'by_policy': {}
        }

        start_time = datetime.now()

        print("\n🔄 Starting reclassification...")
        print("=" * 80)

        batch_updates = []

        for i, law in enumerate(unclassified_laws, 1):
            stats['processed'] += 1

            try:
                # Parse XML to get full text
                metadata = xml_parser.parse_file(law.xml_path)

                if not metadata:
                    stats['still_unclassified'] += 1
                    continue

                # Extract full text (first 5000 chars for performance)
                full_text = metadata.get('full_text', '')[:5000]

                # Use enhanced classifier with full text
                policy_area, confidence = classifier.classify_with_confidence(
                    title=law.title,
                    doc_type=law.doc_type or '',
                    subject_matter=law.subject_matter or [],
                    full_text=full_text
                )

                if policy_area and confidence >= args.min_confidence:
                    # Update law
                    law.policy_area = policy_area
                    stats['classified'] += 1
                    stats['by_policy'][policy_area] = stats['by_policy'].get(policy_area, 0) + 1

                    if stats['classified'] % 10 == 0:
                        print(f"   ✅ Classified: {law.celex or law.uuid[:8]} → {policy_area} (confidence: {confidence:.2%})")
                else:
                    stats['still_unclassified'] += 1

                # Batch commit
                if stats['processed'] % args.batch_size == 0:
                    db.commit()
                    print(f"\n📊 Progress: {stats['processed']}/{len(unclassified_laws)} ({stats['processed']/len(unclassified_laws)*100:.1f}%)")
                    print(f"   Classified: {stats['classified']}, Still unclassified: {stats['still_unclassified']}")

            except Exception as e:
                print(f"   ⚠️  Error processing {law.uuid}: {str(e)}")
                stats['still_unclassified'] += 1
                continue

        # Final commit
        db.commit()

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        print("\n" + "=" * 80)
        print("RECLASSIFICATION COMPLETE!")
        print("=" * 80)

        print(f"\n📊 RESULTS:")
        print(f"   Total processed: {stats['processed']:,}")
        print(f"   Successfully classified: {stats['classified']:,} ({stats['classified']/stats['processed']*100:.1f}%)")
        print(f"   Still unclassified: {stats['still_unclassified']:,} ({stats['still_unclassified']/stats['processed']*100:.1f}%)")

        print(f"\n⏱️  Duration: {duration:.1f}s ({stats['processed']/duration:.1f} laws/sec)")

        if stats['by_policy']:
            print(f"\n📂 New Classifications by Policy Area:")
            sorted_policies = sorted(stats['by_policy'].items(), key=lambda x: x[1], reverse=True)
            for policy, count in sorted_policies[:15]:
                print(f"   {policy}: {count:,}")

        # Get updated database stats
        print("\n" + "=" * 80)
        print("UPDATED DATABASE STATISTICS")
        print("=" * 80)

        primary_laws = db.query(EULaw).filter(EULaw.is_primary_legislation == True).count()
        classified_primary = db.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.policy_area.isnot(None)
        ).count()
        unclassified_primary = primary_laws - classified_primary

        print(f"\n📊 Primary Legislation:")
        print(f"   Total: {primary_laws:,}")
        print(f"   Classified: {classified_primary:,} ({classified_primary/primary_laws*100:.1f}%)")
        print(f"   Unclassified: {unclassified_primary:,} ({unclassified_primary/primary_laws*100:.1f}%)")

        print("\n✅ Reclassification completed successfully!")

    except Exception as e:
        print(f"\n❌ Reclassification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
