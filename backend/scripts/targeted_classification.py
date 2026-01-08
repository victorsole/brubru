"""
Targeted Classification for Specific Categories

Classifies remaining unclassified laws based on user-identified patterns:
1. Chemical regulations/prohibitions
2. Medical/health issues (diseases, viruses, bacteria)
3. Geographical indications
4. Member State allocations

Usage:
    python -m backend.scripts.targeted_classification
    python -m backend.scripts.targeted_classification --dry-run
    python -m backend.scripts.targeted_classification --limit 100
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from collections import Counter
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw


class TargetedClassifier:
    """Classifier for specific user-identified categories"""

    def __init__(self):
        self.db = SessionLocal()

        # Category keyword mappings
        self.category_rules = {
            'chemicals': {
                'policy_area': 'Environment',
                'keywords': [
                    # Chemical substances
                    'chemical', 'substance', 'compound', 'agent',
                    # Actions on chemicals
                    'prohibit', 'prohibiting', 'restriction', 'ban', 'banning',
                    'regulate', 'regulating', 'control',
                    # Chemical properties
                    'hazardous', 'toxic', 'dangerous', 'harmful',
                    # Chemical identifiers
                    'cas number', 'cas no',
                    # Specific chemical categories
                    'pesticide', 'biocide', 'preservative',
                    'additive', 'colorant', 'flavoring',
                    # Chemical regulation frameworks
                    'reach', 'clp regulation',
                ],
                'title_patterns': [
                    r'\bchemical\b',
                    r'\bsubstance\b',
                    r'\bprohibit\w*\b.*\bsubstance',
                    r'\brestrict\w*\b.*\bchemical',
                    r'\bban\w*\b.*\buse',
                ],
                'min_matches': 1  # Require only 1 match for chemicals
            },

            'medical': {
                'policy_area': 'Public Health',
                'keywords': [
                    # Diseases
                    'disease', 'illness', 'malady', 'infection', 'epidemic', 'pandemic',
                    # Pathogens
                    'virus', 'bacteria', 'bacterial', 'viral', 'pathogen',
                    'microorganism', 'microbe',
                    # Specific medical terms
                    'influenza', 'avian', 'swine flu', 'foot-and-mouth',
                    'salmonella', 'listeria', 'e. coli', 'bse', 'tse',
                    # Medical actions
                    'vaccination', 'immunisation', 'prophylaxis',
                    'treatment', 'therapy', 'diagnosis',
                    # Animal health (often in food safety context)
                    'animal health', 'veterinary', 'zoonotic', 'zoonosis',
                ],
                'title_patterns': [
                    r'\bdisease\b',
                    r'\bvirus\b',
                    r'\bbacteri(a|al)\b',
                    r'\binfection\b',
                    r'\banimal health\b',
                    r'\bveterinary\b',
                ],
                'min_matches': 1
            },

            'geographical_indications': {
                'policy_area': 'Agriculture',
                'keywords': [
                    # GI terminology
                    'geographical indication', 'geographic indication',
                    'protected designation of origin', 'protected geographical indication',
                    'traditional speciality guaranteed',
                    # Abbreviations
                    'pdo', 'pgi', 'tsg',
                    # GI actions
                    'registration of the name', 'registration of',
                    'name in the register',
                    # Origin terminology
                    'designation of origin', 'origin of', 'appellation',
                ],
                'title_patterns': [
                    r'\bgeographic\w*\s+indication\b',
                    r'\bprotected\s+designation\b',
                    r'\bprotected\s+geographical\b',
                    r'\bpdo\b',
                    r'\bpgi\b',
                    r'\bregistration\s+of\s+(the\s+)?name\b',
                    r'\bdesignation\s+of\s+origin\b',
                ],
                'min_matches': 1
            },

            'member_state_allocations': {
                'policy_area': 'Budget',
                'keywords': [
                    # Allocation terminology
                    'allocation', 'allocate', 'allocating', 'quota',
                    'distribution', 'distribute', 'distributing',
                    'apportionment', 'apportioning',
                    # Financial terms
                    'funding', 'financial assistance', 'grant',
                    'appropriation', 'budget',
                    # Member State references
                    'member state', 'member states',
                    # Specific country indicators (when combined with allocation)
                    'to belgium', 'to germany', 'to france', 'to italy',
                    'to spain', 'to poland', 'to netherlands',
                ],
                'title_patterns': [
                    r'\ballocation\b.*\bmember state\b',
                    r'\bmember state\b.*\ballocation\b',
                    r'\bquota\b.*\bmember state\b',
                    r'\bdistribut\w+\b.*\bmember state\b',
                    r'\ballocation\b.*\b(to|for)\s+[A-Z][a-z]+\b',  # "allocation to Belgium"
                    r'\bgranting\b.*\bmember state\b',
                ],
                'min_matches': 2  # Require 2 matches to avoid false positives
            },
        }

    def classify_law(self, law: EULaw) -> Tuple[Optional[str], str]:
        """
        Classify a law based on targeted category rules.

        Returns:
            (policy_area, category_name) or (None, 'none')
        """
        # Combine all text for analysis
        text_to_analyze = ' '.join(filter(None, [
            law.title or '',
            law.doc_type or '',
            ' '.join(law.subject_matter or []),
        ])).lower()

        # Try each category
        for category_name, rules in self.category_rules.items():
            matches = 0

            # Check keywords
            for keyword in rules['keywords']:
                if keyword.lower() in text_to_analyze:
                    matches += 1

            # Check title patterns (bonus weight)
            if law.title:
                title_lower = law.title.lower()
                for pattern in rules['title_patterns']:
                    if re.search(pattern, title_lower, re.IGNORECASE):
                        matches += 2  # Patterns count double

            # If enough matches, classify
            if matches >= rules['min_matches']:
                return rules['policy_area'], category_name

        return None, 'none'

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main classification function"""
    parser = argparse.ArgumentParser(
        description="Targeted classification for specific categories"
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be classified without committing'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum laws to process (for testing)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for commits (default: 100)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("TARGETED CLASSIFICATION FOR SPECIFIC CATEGORIES")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be committed")

    # Initialize classifier
    print("\n🚀 Initializing targeted classifier...")
    classifier = TargetedClassifier()

    try:
        # Get unclassified primary laws
        query = classifier.db.query(EULaw).filter(
            EULaw.policy_area.is_(None),
            EULaw.is_primary_legislation == True
        )

        if args.limit:
            query = query.limit(args.limit)
            print(f"⚠️  LIMITED MODE: Processing only {args.limit} laws")

        unclassified = query.all()
        total = len(unclassified)

        print(f"\n📊 Found {total:,} unclassified primary laws")

        if total == 0:
            print("✅ No unclassified laws!")
            return

        # Statistics
        stats = {
            'processed': 0,
            'classified': 0,
            'still_unclassified': 0,
            'by_category': Counter(),
            'by_policy': Counter()
        }

        start_time = datetime.now()

        print("\n🔄 Starting classification...")
        print("=" * 80)

        for i, law in enumerate(unclassified, 1):
            stats['processed'] += 1

            # Try to classify
            policy, category = classifier.classify_law(law)

            if policy:
                if not args.dry_run:
                    law.policy_area = policy

                stats['classified'] += 1
                stats['by_category'][category] += 1
                stats['by_policy'][policy] += 1

                # Show examples
                if stats['classified'] <= 20 or stats['classified'] % 50 == 0:
                    print(f"   ✅ [{category:20s}] {law.celex or law.uuid[:8]:20s} → {policy}")
                    print(f"      Title: {law.title[:80] if law.title else 'N/A'}...")
            else:
                stats['still_unclassified'] += 1

            # Batch commit
            if not args.dry_run and stats['processed'] % args.batch_size == 0:
                classifier.db.commit()
                pct = stats['processed'] / total * 100
                print(f"\n📊 Progress: {stats['processed']:,}/{total:,} ({pct:.1f}%) - Classified: {stats['classified']:,}, Failed: {stats['still_unclassified']:,}")

        # Final commit
        if not args.dry_run:
            classifier.db.commit()

        # Results
        duration = (datetime.now() - start_time).total_seconds()

        print("\n" + "=" * 80)
        print("CLASSIFICATION COMPLETE!")
        print("=" * 80)

        print(f"\n📊 RESULTS:")
        print(f"   Total processed: {stats['processed']:,}")
        print(f"   Successfully classified: {stats['classified']:,} ({stats['classified']/stats['processed']*100:.1f}%)")
        print(f"   Still unclassified: {stats['still_unclassified']:,} ({stats['still_unclassified']/stats['processed']*100:.1f}%)")

        print(f"\n⏱️  Duration: {duration:.1f}s ({stats['processed']/duration:.1f} laws/sec)")

        if stats['by_category']:
            print(f"\n📂 Classifications by Category:")
            for category, count in stats['by_category'].most_common():
                print(f"   {category:30s}: {count:,}")

        if stats['by_policy']:
            print(f"\n🏛️  Classifications by Policy Area:")
            for policy, count in stats['by_policy'].most_common():
                print(f"   {policy}: {count:,}")

        # Updated database stats (only if not dry run)
        if not args.dry_run:
            print("\n" + "=" * 80)
            print("FINAL DATABASE STATISTICS")
            print("=" * 80)

            primary_total = classifier.db.query(EULaw).filter(EULaw.is_primary_legislation == True).count()
            classified_primary = classifier.db.query(EULaw).filter(
                EULaw.is_primary_legislation == True,
                EULaw.policy_area.isnot(None)
            ).count()
            unclassified_primary = primary_total - classified_primary

            print(f"\n📊 Primary Legislation:")
            print(f"   Total: {primary_total:,}")
            print(f"   Classified: {classified_primary:,} ({classified_primary/primary_total*100:.1f}%)")
            print(f"   Unclassified: {unclassified_primary:,} ({unclassified_primary/primary_total*100:.1f}%)")

        print("\n✅ Targeted classification completed!")

        if args.dry_run:
            print("\n💡 This was a dry run. Run without --dry-run to commit changes.")

    except Exception as e:
        print(f"\n❌ Classification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        classifier.db.rollback()
        sys.exit(1)
    finally:
        classifier.close()


if __name__ == "__main__":
    main()
