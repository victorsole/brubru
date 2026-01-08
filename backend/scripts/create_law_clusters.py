"""
Create Curated Law Packages (Clusters)

Automatically identifies and creates clusters for major EU legislative packages:
- GDPR Package (Data Protection)
- DSA/DMA Package (Digital Services/Markets)
- AI Act Package
- Green Deal Package
- Banking Union Package
- And more...

Usage:
    python -m backend.scripts.create_law_clusters
    python -m backend.scripts.create_law_clusters --package gdpr
    python -m backend.scripts.create_law_clusters --dry-run
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw, LawCluster, ClusterLaw
from sqlalchemy import or_


# Major EU Law Packages
LAW_PACKAGES = {
    'gdpr': {
        'name': 'GDPR Package (Data Protection)',
        'primary_celex': '32016R0679',  # GDPR
        'description': 'General Data Protection Regulation and implementing acts covering personal data protection in the EU',
        'applicability': 'Companies processing personal data of EU residents, public authorities, data processors',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['data protection', 'gdpr', 'personal data', 'privacy', '2016/679'],
        'date_from': 2016
    },

    'dsa': {
        'name': 'Digital Services Act Package',
        'primary_celex': '32022R2065',  # DSA
        'description': 'Digital Services Act regulating online intermediaries and platforms in the EU',
        'applicability': 'Online platforms, intermediary services, very large online platforms (VLOPs)',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['digital services', 'platform', 'intermediary', '2022/2065', 'online content'],
        'date_from': 2020
    },

    'dma': {
        'name': 'Digital Markets Act Package',
        'primary_celex': '32022R1925',  # DMA
        'description': 'Digital Markets Act establishing rules for digital gatekeepers',
        'applicability': 'Large digital platforms designated as gatekeepers, core platform services',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['digital markets', 'gatekeeper', '2022/1925', 'core platform services'],
        'date_from': 2020
    },

    'ai_act': {
        'name': 'AI Act Package',
        'primary_celex': '32024R1689',  # AI Act (if indexed)
        'description': 'Artificial Intelligence Act regulating AI systems in the EU',
        'applicability': 'AI system providers, deployers, distributors, importers',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['artificial intelligence', 'ai system', 'machine learning', 'high-risk ai'],
        'date_from': 2021
    },

    'nis2': {
        'name': 'NIS2 Directive (Cybersecurity)',
        'primary_celex': '32022L2555',  # NIS2
        'description': 'Network and Information Security Directive establishing cybersecurity requirements',
        'applicability': 'Essential and important entities, digital infrastructure operators',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['cybersecurity', 'network security', 'nis2', '2022/2555', 'cyber threat'],
        'date_from': 2020
    },

    'green_deal': {
        'name': 'European Green Deal Package',
        'primary_celex': None,  # Collection of laws, no single primary
        'description': 'Comprehensive package of climate and environmental legislation',
        'applicability': 'All sectors: energy, transport, industry, agriculture',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['green deal', 'climate neutral', 'fit for 55', 'emissions reduction', 'renewable energy'],
        'date_from': 2019
    },

    'banking_union': {
        'name': 'Banking Union Package',
        'primary_celex': '32013R1024',  # SSM Regulation
        'description': 'Single Supervisory Mechanism and banking supervision framework',
        'applicability': 'Banks, credit institutions, financial supervisors',
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': ['banking union', 'ssm', 'srm', 'prudential supervision', '1024/2013'],
        'date_from': 2012
    },

    'capital_markets_union': {
        'name': 'Capital Markets Union Package',
        'primary_celex': None,
        'description': 'Framework for integrated EU capital markets',
        'applicability': 'Investment firms, fund managers, securities markets',
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': ['capital markets union', 'mifid', 'prospectus', 'securities'],
        'date_from': 2015
    },

    'circular_economy': {
        'name': 'Circular Economy Package',
        'primary_celex': None,
        'description': 'Waste reduction, recycling, and circular economy legislation',
        'applicability': 'Manufacturers, waste management, product design',
        'policy_area': 'Environment',
        'priority_level': 'medium',
        'keywords': ['circular economy', 'waste', 'recycling', 'ecodesign', 'sustainable product'],
        'date_from': 2015
    },

    'farm_to_fork': {
        'name': 'Farm to Fork Strategy Package',
        'primary_celex': None,
        'description': 'Sustainable food system legislation',
        'applicability': 'Food producers, distributors, agricultural sector',
        'policy_area': 'Agriculture',
        'priority_level': 'medium',
        'keywords': ['farm to fork', 'sustainable food', 'pesticide reduction', 'organic farming'],
        'date_from': 2020
    },

    'migration_pact': {
        'name': 'Migration and Asylum Pact',
        'primary_celex': None,
        'description': 'Comprehensive migration and asylum framework',
        'applicability': 'Member states, border agencies, asylum authorities',
        'policy_area': 'Migration and Home Affairs',
        'priority_level': 'high',
        'keywords': ['migration', 'asylum', 'border', 'schengen', 'refugee'],
        'date_from': 2020
    },

    # =========================================================================
    # STARTUP-FOCUSED COMPLIANCE PACKAGES (LEG_2025-11)
    # =========================================================================

    'fintech_startup': {
        'name': 'FinTech Startup Compliance',
        'primary_celex': '32015L2366',  # PSD2 (Payment Services Directive 2)
        'description': 'Essential compliance package for FinTech startups: payment services, e-money, crypto-assets, and data protection',
        'applicability': 'FinTech startups, payment service providers, crypto exchanges, digital wallets, neobanks',
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': ['payment services', 'psd2', 'e-money', 'mica', 'crypto-asset', 'digital finance', 'open banking', 'strong customer authentication'],
        'date_from': 2015,
        'startup_focused': True,
        'affordability': 'Essential for startups seeking payment licenses or handling transactions'
    },

    'healthtech_startup': {
        'name': 'HealthTech Startup Compliance',
        'primary_celex': '32017R0745',  # MDR (Medical Device Regulation)
        'description': 'Medical device and health data compliance for HealthTech startups',
        'applicability': 'HealthTech startups, medical device manufacturers, digital health apps, telemedicine platforms',
        'policy_area': 'Health',
        'priority_level': 'high',
        'keywords': ['medical device', 'mdr', 'ivdr', 'in vitro diagnostic', 'health data', 'clinical trial', 'ce marking', 'medical app'],
        'date_from': 2017,
        'startup_focused': True,
        'affordability': 'Critical for market access - avoid costly regulatory mistakes'
    },

    'mobility_startup': {
        'name': 'Mobility & Transport Startup Compliance',
        'primary_celex': '32014L0094',  # Alternative Fuels Infrastructure Directive
        'description': 'Compliance for mobility startups: alternative fuels, autonomous vehicles, shared mobility',
        'applicability': 'Mobility startups, EV charging networks, micromobility, autonomous vehicle developers, ride-sharing platforms',
        'policy_area': 'Transport',
        'priority_level': 'high',
        'keywords': ['alternative fuel', 'electric vehicle', 'charging infrastructure', 'autonomous vehicle', 'mobility service', 'type approval', 'vehicle homologation'],
        'date_from': 2014,
        'startup_focused': True,
        'affordability': 'Navigate complex transport regulations before costly prototyping'
    },

    'climate_startup': {
        'name': 'Climate Tech Startup Compliance',
        'primary_celex': '32003L0087',  # EU ETS Directive
        'description': 'Carbon markets, emissions trading, and CBAM compliance for climate startups',
        'applicability': 'Climate tech startups, carbon credit platforms, emission reduction technology, green hydrogen, CCUS',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['emissions trading', 'ets', 'carbon border adjustment', 'cbam', 'carbon credit', 'emission allowance', 'carbon pricing', 'climate neutral'],
        'date_from': 2003,
        'startup_focused': True,
        'affordability': 'Understand carbon markets and avoid CBAM penalties'
    },

    'cleantech_startup': {
        'name': 'CleanTech Startup Funding & Compliance',
        'primary_celex': '32021R1119',  # European Climate Law
        'description': 'Green Deal compliance and funding opportunities for CleanTech startups',
        'applicability': 'CleanTech startups, renewable energy, energy efficiency, green hydrogen, sustainable materials',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['renewable energy', 'energy efficiency', 'green hydrogen', 'clean technology', 'innovation fund', 'just transition', 'renewable energy directive'],
        'date_from': 2019,
        'startup_focused': True,
        'affordability': 'Identify Green Deal funding + ensure compliance with energy regulations'
    },

    'ai_ml_startup': {
        'name': 'AI/ML Startup Compliance',
        'primary_celex': '32024R1689',  # AI Act
        'description': 'AI Act compliance for machine learning startups and AI system providers',
        'applicability': 'AI/ML startups, algorithm developers, predictive analytics, computer vision, NLP, generative AI',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['artificial intelligence', 'ai act', 'high-risk ai', 'machine learning', 'foundation model', 'general purpose ai', 'ai system', 'algorithmic transparency'],
        'date_from': 2021,
        'startup_focused': True,
        'affordability': 'Navigate AI Act before product launch - avoid €35M penalties'
    },

    'ecommerce_startup': {
        'name': 'E-commerce & Platform Startup Compliance',
        'primary_celex': '32022R2065',  # DSA
        'description': 'Essential compliance for e-commerce platforms, marketplaces, and online services',
        'applicability': 'E-commerce startups, online marketplaces, platform economy, SaaS providers',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['digital services', 'e-commerce', 'marketplace', 'consumer protection', 'distance selling', 'online platform', 'intermediary service'],
        'date_from': 2020,
        'startup_focused': True,
        'affordability': 'Avoid DSA content moderation fines + consumer protection disputes'
    },

    'circular_economy_startup': {
        'name': 'Circular Economy Startup Compliance (EPR)',
        'primary_celex': '32008L0098',  # Waste Framework Directive
        'description': 'Extended Producer Responsibility (EPR) and circular economy compliance',
        'applicability': 'Circular economy startups, product-as-service, reuse platforms, waste management, packaging producers',
        'policy_area': 'Environment',
        'priority_level': 'medium',
        'keywords': ['extended producer responsibility', 'epr', 'packaging waste', 'circular economy', 'waste management', 'recycling', 'eco-design', 'right to repair'],
        'date_from': 2008,
        'startup_focused': True,
        'affordability': 'Understand EPR obligations before scaling across EU markets'
    },

    'food_agtech_startup': {
        'name': 'Food & AgTech Startup Compliance',
        'primary_celex': '32002R0178',  # General Food Law
        'description': 'Food safety, novel foods, and agricultural technology compliance',
        'applicability': 'FoodTech startups, AgTech innovators, alternative proteins, vertical farming, food delivery platforms',
        'policy_area': 'Food Safety',
        'priority_level': 'high',
        'keywords': ['food safety', 'novel food', 'food contact material', 'agricultural technology', 'plant protection', 'food labeling', 'traceability'],
        'date_from': 2002,
        'startup_focused': True,
        'affordability': 'Navigate complex food regulations and novel food approvals'
    },

    'saas_b2b_startup': {
        'name': 'SaaS & B2B Startup Compliance',
        'primary_celex': '32016R0679',  # GDPR
        'description': 'Data protection, security, and B2B software compliance essentials',
        'applicability': 'SaaS startups, B2B software, cloud services, enterprise software, data processors',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['gdpr', 'data protection', 'cloud computing', 'data processor', 'data processing agreement', 'cybersecurity', 'nis2'],
        'date_from': 2016,
        'startup_focused': True,
        'affordability': 'Essential GDPR + NIS2 compliance without expensive DPO hiring'
    },
}


class ClusterCreator:
    """Creates law clusters from package definitions"""

    def __init__(self, dry_run=False):
        self.db = SessionLocal()
        self.dry_run = dry_run
        self.stats = {
            'clusters_created': 0,
            'laws_added': 0,
            'packages_processed': 0
        }

    def find_primary_law(self, celex: str) -> Optional[EULaw]:
        """Find primary law by CELEX"""
        if not celex:
            return None

        return self.db.query(EULaw).filter(
            EULaw.celex == celex
        ).first()

    def find_related_laws_by_citation(self, primary_law: EULaw, max_depth=2) -> List[Tuple[EULaw, str]]:
        """
        Find laws related through citations.

        Returns list of (law, relationship_type) tuples
        """
        related = []

        if not primary_law or not primary_law.celex:
            return related

        # Find laws that cite this law
        # Use PostgreSQL array overlap operator
        from sqlalchemy.dialects.postgresql import array
        implementing_laws = self.db.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.legal_basis.isnot(None),
            EULaw.legal_basis.op('&&')(array([primary_law.celex]))
        ).all()

        for law in implementing_laws:
            # Determine relationship type from doc_type
            doc_type_lower = (law.doc_type or '').lower()
            if 'implementing' in doc_type_lower:
                relationship = 'implementing'
            elif 'delegated' in doc_type_lower:
                relationship = 'delegated'
            elif 'amending' in doc_type_lower:
                relationship = 'amending'
            else:
                relationship = 'related'

            related.append((law, relationship))

        # Find laws cited by this law
        if primary_law.citations:
            for citation in primary_law.citations[:10]:  # Limit to first 10
                cited_law = self.db.query(EULaw).filter(
                    EULaw.celex == citation,
                    EULaw.is_primary_legislation == True
                ).first()

                if cited_law:
                    related.append((cited_law, 'cited'))

        return related

    def find_related_laws_by_keywords(self, keywords: List[str], date_from: int, limit=50) -> List[EULaw]:
        """Find laws by keyword search in title and subject matter"""
        # Build OR conditions for keywords
        conditions = []
        for keyword in keywords:
            conditions.append(EULaw.title.ilike(f'%{keyword}%'))

        laws = self.db.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.date >= datetime(date_from, 1, 1).date(),
            or_(*conditions)
        ).limit(limit).all()

        return laws

    def create_cluster(self, package_key: str, package_def: Dict) -> Optional[int]:
        """Create a law cluster from package definition"""

        print(f"\n{'='*80}")
        print(f"📦 Creating cluster: {package_def['name']}")
        print(f"{'='*80}")

        # Check if cluster already exists
        existing = self.db.query(LawCluster).filter(
            LawCluster.name == package_def['name']
        ).first()

        if existing:
            print(f"⚠️  Cluster already exists (ID: {existing.id})")
            if not self.dry_run:
                # Delete existing and recreate
                self.db.query(ClusterLaw).filter(
                    ClusterLaw.cluster_id == existing.id
                ).delete()
                self.db.query(LawCluster).filter(
                    LawCluster.id == existing.id
                ).delete()
                self.db.commit()
                print(f"   Deleted existing cluster to recreate")

        # Find primary law
        primary_law = None
        primary_law_id = None

        if package_def['primary_celex']:
            primary_law = self.find_primary_law(package_def['primary_celex'])
            if primary_law:
                primary_law_id = primary_law.id
                print(f"✅ Found primary law: {primary_law.celex}")
                print(f"   {primary_law.title[:80]}...")
            else:
                print(f"⚠️  Primary law {package_def['primary_celex']} not found in database")

        # Create cluster
        if not self.dry_run:
            cluster = LawCluster(
                name=package_def['name'],
                primary_law_id=primary_law_id,
                description=package_def['description'],
                applicability=package_def['applicability'],
                policy_area=package_def['policy_area'],
                priority_level=package_def['priority_level']
            )
            self.db.add(cluster)
            self.db.flush()  # Get cluster.id
            cluster_id = cluster.id
            print(f"✅ Created cluster (ID: {cluster_id})")
        else:
            cluster_id = -1  # Dummy ID for dry run
            print(f"🔍 DRY RUN: Would create cluster")

        # Find and add related laws
        laws_to_add = []

        # 1. Add primary law
        if primary_law:
            laws_to_add.append((primary_law, 'primary'))

        # 2. Find laws by citation network
        if primary_law:
            print(f"\n🔗 Finding related laws by citation network...")
            related_by_citation = self.find_related_laws_by_citation(primary_law)
            print(f"   Found {len(related_by_citation)} laws via citations")
            laws_to_add.extend(related_by_citation)

        # 3. Find laws by keywords
        print(f"\n🔍 Finding related laws by keywords: {', '.join(package_def['keywords'][:3])}...")
        related_by_keywords = self.find_related_laws_by_keywords(
            package_def['keywords'],
            package_def['date_from'],
            limit=50
        )
        print(f"   Found {len(related_by_keywords)} laws via keywords")

        # Add keyword matches as 'related'
        for law in related_by_keywords:
            # Don't add if already in list
            if not any(l.id == law.id for l, _ in laws_to_add):
                laws_to_add.append((law, 'related'))

        # Remove duplicates (keep first occurrence)
        seen_ids = set()
        unique_laws = []
        for law, rel_type in laws_to_add:
            if law.id not in seen_ids:
                seen_ids.add(law.id)
                unique_laws.append((law, rel_type))

        print(f"\n📊 Total unique laws to add: {len(unique_laws)}")

        # Add to cluster
        if not self.dry_run:
            for law, relationship_type in unique_laws[:100]:  # Limit to 100 laws per cluster
                cluster_law = ClusterLaw(
                    cluster_id=cluster_id,
                    law_id=law.id,
                    relationship_type=relationship_type
                )
                self.db.add(cluster_law)

            self.db.commit()
            print(f"✅ Added {len(unique_laws[:100])} laws to cluster")
        else:
            print(f"🔍 DRY RUN: Would add {len(unique_laws[:100])} laws")

        # Show sample laws
        print(f"\n📝 Sample laws in cluster:")
        for i, (law, rel_type) in enumerate(unique_laws[:10], 1):
            print(f"   {i:2d}. [{rel_type:12s}] {law.celex or law.uuid[:8]:20s}")
            print(f"       {law.title[:75]}...")

        self.stats['clusters_created'] += 1
        self.stats['laws_added'] += len(unique_laws[:100])

        return cluster_id

    def create_all_clusters(self, package_filter: Optional[str] = None):
        """Create all defined clusters"""

        packages_to_process = LAW_PACKAGES

        if package_filter:
            if package_filter in LAW_PACKAGES:
                packages_to_process = {package_filter: LAW_PACKAGES[package_filter]}
            else:
                print(f"❌ Unknown package: {package_filter}")
                print(f"Available packages: {', '.join(LAW_PACKAGES.keys())}")
                return

        print(f"🚀 Creating {len(packages_to_process)} law clusters...")

        for package_key, package_def in packages_to_process.items():
            try:
                self.create_cluster(package_key, package_def)
                self.stats['packages_processed'] += 1
            except Exception as e:
                print(f"\n❌ Failed to create cluster {package_key}: {str(e)}")
                import traceback
                traceback.print_exc()

    def show_statistics(self):
        """Display final statistics"""
        print(f"\n{'='*80}")
        print(f"CLUSTER CREATION COMPLETE")
        print(f"{'='*80}")
        print(f"\n📊 STATISTICS:")
        print(f"   Packages processed: {self.stats['packages_processed']}")
        print(f"   Clusters created: {self.stats['clusters_created']}")
        print(f"   Total laws added: {self.stats['laws_added']}")

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Create curated law packages (clusters)"
    )

    parser.add_argument(
        '--package',
        type=str,
        help=f'Create only specific package. Options: {", ".join(LAW_PACKAGES.keys())}'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without committing'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("CREATE CURATED LAW PACKAGES")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be committed")

    creator = ClusterCreator(dry_run=args.dry_run)

    try:
        creator.create_all_clusters(package_filter=args.package)
        creator.show_statistics()

        if not args.dry_run:
            print(f"\n✅ Clusters created successfully!")
            print(f"\n💡 View clusters:")
            print(f"   SELECT * FROM law_clusters;")
            print(f"   SELECT cluster_id, COUNT(*) FROM cluster_laws GROUP BY cluster_id;")
        else:
            print(f"\n💡 This was a dry run. Run without --dry-run to commit changes.")

    except Exception as e:
        print(f"\n❌ Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        creator.close()


if __name__ == "__main__":
    main()
