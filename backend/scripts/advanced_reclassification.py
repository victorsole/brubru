"""
Advanced Multi-Strategy Reclassification

Uses multiple strategies to classify the remaining 5,884 unclassified primary laws:

Strategy 1: CELEX Pattern Analysis - Infer policy from CELEX structure
Strategy 2: Legal Basis Inheritance - Inherit policy from parent/basis laws
Strategy 3: Citation Network Analysis - Infer from citing/cited laws
Strategy 4: Enhanced Full Text Analysis - Lower thresholds, more context
Strategy 5: Subject Matter Direct Mapping - Keyword → Policy direct rules
Strategy 6: Document Type Heuristics - Type-based policy inference

Usage:
    python -m backend.scripts.advanced_reclassification
    python -m backend.scripts.advanced_reclassification --strategies all
    python -m backend.scripts.advanced_reclassification --strategies celex,legal_basis
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw
from backend.services.law_database.policy_classifier import get_policy_classifier
from backend.services.law_database.xml_parser import get_xml_parser


class AdvancedClassifier:
    """Multi-strategy classifier for unclassified laws"""

    def __init__(self):
        self.db = SessionLocal()
        self.policy_classifier = get_policy_classifier()
        self.xml_parser = get_xml_parser()

        # Load all classified laws for reference
        self.classified_laws_cache = {}
        self._build_classification_cache()

    def _build_classification_cache(self):
        """Build cache of classified laws for quick lookups"""
        print("📚 Building classification cache...")

        classified = self.db.query(EULaw).filter(
            EULaw.policy_area.isnot(None),
            EULaw.is_primary_legislation == True
        ).all()

        for law in classified:
            # Index by CELEX
            if law.celex:
                self.classified_laws_cache[law.celex] = law.policy_area

            # Index by UUID
            self.classified_laws_cache[law.uuid] = law.policy_area

        print(f"   ✅ Cached {len(classified):,} classified laws")

    # ========== STRATEGY 1: CELEX Pattern Analysis ==========

    def classify_by_celex_pattern(self, law: EULaw) -> Optional[str]:
        """
        Infer policy area from CELEX number patterns.

        CELEX structure: [Sector][Year][Type][Sequential]
        Sector codes can indicate policy areas.
        """
        if not law.celex or len(law.celex) < 5:
            return None

        # CELEX sector mappings (first character)
        celex_sector_map = {
            '3': None,  # EU law (most common, not specific)
            '1': 'Trade and Economic Security',  # Treaties
            '2': 'Foreign and Security Policy',  # International agreements
            '4': 'Justice and Fundamental Rights',  # Court decisions
            '5': 'European Parliament',  # Parliamentary questions
            '6': 'Economic and Financial Affairs',  # National implementing measures
        }

        sector = law.celex[0]
        if sector in celex_sector_map and celex_sector_map[sector]:
            return celex_sector_map[sector]

        # Type-based inference (positions 5-6)
        if len(law.celex) >= 6:
            doc_code = law.celex[5:7]

            # Common document type patterns
            type_map = {
                'R': None,  # Regulation (too generic)
                'L': None,  # Directive (too generic)
                'D': None,  # Decision (too generic)
                'PC': 'Agriculture',  # Common agricultural policy
                'SC': 'Maritime Affairs and Fisheries',  # Common fisheries policy
            }

            if doc_code in type_map and type_map[doc_code]:
                return type_map[doc_code]

        return None

    # ========== STRATEGY 2: Legal Basis Inheritance ==========

    def classify_by_legal_basis(self, law: EULaw) -> Optional[str]:
        """
        Inherit policy area from legal basis laws.

        If this law is based on another law, it likely belongs to the same policy area.
        """
        if not law.legal_basis or len(law.legal_basis) == 0:
            return None

        # Extract CELEX/references from legal basis
        policy_votes = Counter()

        for basis in law.legal_basis[:5]:  # Check first 5 bases
            # Try to find this basis in our cache
            # Look for patterns like "Regulation 2016/679" or "32016R0679"

            # Try direct match
            if basis in self.classified_laws_cache:
                policy_votes[self.classified_laws_cache[basis]] += 1
                continue

            # Try to extract CELEX-like patterns
            import re
            celex_pattern = r'(\d{4,5}[RLDC]\d{4})'
            matches = re.findall(celex_pattern, basis.replace('/', ''))

            for match in matches:
                if match in self.classified_laws_cache:
                    policy_votes[self.classified_laws_cache[match]] += 1

        # Return most common policy area from legal bases
        if policy_votes:
            return policy_votes.most_common(1)[0][0]

        return None

    # ========== STRATEGY 3: Citation Network Analysis ==========

    def classify_by_citations(self, law: EULaw) -> Optional[str]:
        """
        Infer policy from laws that cite this law or are cited by this law.

        Laws that reference each other often belong to the same policy area.
        """
        policy_votes = Counter()

        # Check laws cited by this law
        if law.citations:
            for citation in law.citations[:10]:  # First 10 citations
                if citation in self.classified_laws_cache:
                    policy_votes[self.classified_laws_cache[citation]] += 1

        # Check laws that cite this law (reverse lookup)
        if law.celex:
            citing_laws = self.db.query(EULaw).filter(
                EULaw.policy_area.isnot(None),
                EULaw.citations.contains([law.celex])
            ).limit(10).all()

            for citing_law in citing_laws:
                policy_votes[citing_law.policy_area] += 1

        # Return most common policy
        if policy_votes:
            most_common_policy, count = policy_votes.most_common(1)[0]
            # Require at least 2 citations pointing to same policy
            if count >= 2:
                return most_common_policy

        return None

    # ========== STRATEGY 4: Enhanced Full Text Analysis ==========

    def classify_by_full_text(self, law: EULaw, min_confidence: float = 0.15) -> Optional[str]:
        """
        Use full text with very low confidence threshold.

        This is more aggressive than the standard classification.
        """
        try:
            # Parse XML for full text
            metadata = self.xml_parser.parse_file(law.xml_path)
            if not metadata:
                return None

            # Get more text (10,000 chars instead of 1,000)
            full_text = metadata.get('full_text', '')[:10000]

            if not full_text or len(full_text) < 100:
                return None

            # Classify with low threshold
            policy_area, confidence = self.policy_classifier.classify_with_confidence(
                title=law.title,
                doc_type=law.doc_type or '',
                subject_matter=law.subject_matter or [],
                full_text=full_text
            )

            if policy_area and confidence >= min_confidence:
                return policy_area

        except Exception as e:
            return None

        return None

    # ========== STRATEGY 5: Subject Matter Direct Mapping ==========

    def classify_by_subject_matter(self, law: EULaw) -> Optional[str]:
        """
        Direct mapping of subject matter keywords to policy areas.

        Some keywords are strong indicators of specific policy areas.
        """
        if not law.subject_matter:
            return None

        # Strong keyword → policy mappings
        keyword_map = {
            # Agriculture
            'agriculture': 'Agriculture',
            'farming': 'Agriculture',
            'agricultural': 'Agriculture',
            'crop': 'Agriculture',
            'livestock': 'Agriculture',

            # Fisheries
            'fish': 'Maritime Affairs and Fisheries',
            'fishing': 'Maritime Affairs and Fisheries',
            'fisheries': 'Maritime Affairs and Fisheries',
            'maritime': 'Maritime Affairs and Fisheries',

            # Environment
            'environment': 'Environment',
            'environmental': 'Environment',
            'pollution': 'Environment',
            'waste': 'Environment',

            # Climate
            'climate': 'Climate Action',
            'emissions': 'Climate Action',
            'greenhouse': 'Climate Action',

            # Energy
            'energy': 'Energy',
            'electricity': 'Energy',
            'renewable': 'Energy',

            # Digital
            'digital': 'Digital Policy and Digital Economy',
            'data': 'Digital Policy and Digital Economy',
            'cybersecurity': 'Digital Policy and Digital Economy',
            'internet': 'Digital Policy and Digital Economy',

            # Trade
            'trade': 'Trade and Economic Security',
            'customs': 'Trade and Economic Security',
            'import': 'Trade and Economic Security',
            'export': 'Trade and Economic Security',

            # Health
            'health': 'Public Health',
            'medical': 'Public Health',
            'pharmaceutical': 'Public Health',

            # Transport
            'transport': 'Transport',
            'aviation': 'Transport',
            'railway': 'Transport',
            'road': 'Transport',
        }

        # Score each policy by keyword matches
        policy_scores = Counter()

        for keyword in law.subject_matter:
            keyword_lower = keyword.lower()
            if keyword_lower in keyword_map:
                policy_scores[keyword_map[keyword_lower]] += 1

        # Return policy with most keyword matches (require at least 2)
        if policy_scores:
            most_common_policy, count = policy_scores.most_common(1)[0]
            if count >= 2:
                return most_common_policy

        return None

    # ========== STRATEGY 6: Document Type Heuristics ==========

    def classify_by_doc_type(self, law: EULaw) -> Optional[str]:
        """
        Infer policy from document type patterns.

        Certain document types tend to belong to specific policy areas.
        """
        if not law.doc_type:
            return None

        doc_type_lower = law.doc_type.lower()

        # Document type patterns
        type_patterns = {
            'state aid': 'Competition',
            'competition': 'Competition',
            'merger': 'Competition',

            'customs': 'Trade and Economic Security',
            'tariff': 'Trade and Economic Security',

            'food safety': 'Food Safety',
            'food': 'Food Safety',

            'veterinary': 'Food Safety',
            'animal health': 'Food Safety',

            'budget': 'Budget',
            'budgetary': 'Budget',

            'institutional': 'Institutional Affairs',
        }

        for pattern, policy in type_patterns.items():
            if pattern in doc_type_lower:
                return policy

        return None

    # ========== Main Classification Method ==========

    def classify_law(
        self,
        law: EULaw,
        strategies: List[str],
        min_confidence: float = 0.15
    ) -> tuple[Optional[str], str]:
        """
        Apply multiple strategies to classify a law.

        Returns:
            (policy_area, strategy_used)
        """
        # Try each strategy in order
        strategy_methods = {
            'legal_basis': self.classify_by_legal_basis,
            'citations': self.classify_by_citations,
            'subject_matter': self.classify_by_subject_matter,
            'doc_type': self.classify_by_doc_type,
            'celex': self.classify_by_celex_pattern,
            'full_text': lambda law: self.classify_by_full_text(law, min_confidence)
        }

        for strategy_name in strategies:
            if strategy_name not in strategy_methods:
                continue

            try:
                policy = strategy_methods[strategy_name](law)
                if policy:
                    return policy, strategy_name
            except Exception as e:
                continue

        return None, 'none'

    def close(self):
        """Close database connection"""
        self.db.close()


async def main():
    """Main reclassification function"""
    parser = argparse.ArgumentParser(
        description="Advanced multi-strategy reclassification"
    )

    parser.add_argument(
        '--strategies',
        type=str,
        default='legal_basis,citations,subject_matter,doc_type,full_text,celex',
        help='Comma-separated list of strategies to use (default: all)'
    )

    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.15,
        help='Minimum confidence for full text strategy (default: 0.15)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for commits (default: 100)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum laws to process (for testing)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("ADVANCED MULTI-STRATEGY RECLASSIFICATION")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Parse strategies
    strategies = [s.strip() for s in args.strategies.split(',')]
    print(f"\n🔧 Strategies enabled: {', '.join(strategies)}")
    print(f"   Min confidence (full text): {args.min_confidence}")

    # Initialize classifier
    print("\n🚀 Initializing advanced classifier...")
    classifier = AdvancedClassifier()

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
            'by_policy': Counter(),
            'by_strategy': Counter()
        }

        start_time = datetime.now()

        print("\n🔄 Starting classification...")
        print("=" * 80)

        for i, law in enumerate(unclassified, 1):
            stats['processed'] += 1

            # Try to classify
            policy, strategy = classifier.classify_law(law, strategies, args.min_confidence)

            if policy:
                law.policy_area = policy
                stats['classified'] += 1
                stats['by_policy'][policy] += 1
                stats['by_strategy'][strategy] += 1

                if stats['classified'] % 50 == 0:
                    print(f"   ✅ [{strategy:12s}] {law.celex or law.uuid[:8]:20s} → {policy}")
            else:
                stats['still_unclassified'] += 1

            # Batch commit
            if stats['processed'] % args.batch_size == 0:
                classifier.db.commit()
                pct = stats['processed'] / total * 100
                print(f"\n📊 Progress: {stats['processed']:,}/{total:,} ({pct:.1f}%) - Classified: {stats['classified']:,}, Failed: {stats['still_unclassified']:,}")

        # Final commit
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

        if stats['by_strategy']:
            print(f"\n🔧 Classifications by Strategy:")
            for strategy, count in stats['by_strategy'].most_common():
                print(f"   {strategy:15s}: {count:,}")

        if stats['by_policy']:
            print(f"\n📂 Top 15 Policy Areas:")
            for policy, count in stats['by_policy'].most_common(15):
                print(f"   {policy}: {count:,}")

        # Updated database stats
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

        print("\n✅ Advanced reclassification completed!")

    except Exception as e:
        print(f"\n❌ Classification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        classifier.db.rollback()
        sys.exit(1)
    finally:
        classifier.close()


if __name__ == "__main__":
    asyncio.run(main())
