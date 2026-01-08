"""
Visualize Law Distribution and Clustering

Shows the distribution of indexed laws across:
1. Policy areas (classification-based clustering)
2. Document types
3. Time periods
4. Citation networks

Usage:
    python -m backend.scripts.visualize_law_distribution
    python -m backend.scripts.visualize_law_distribution --export-json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw
from sqlalchemy import func, desc


def get_policy_area_distribution(db):
    """Get distribution of laws by policy area"""
    results = db.query(
        EULaw.policy_area,
        func.count(EULaw.id).label('count')
    ).filter(
        EULaw.is_primary_legislation == True
    ).group_by(
        EULaw.policy_area
    ).order_by(
        desc('count')
    ).all()

    return [(policy or 'Unclassified', count) for policy, count in results]


def get_document_type_distribution(db, limit=20):
    """Get distribution of laws by document type"""
    results = db.query(
        EULaw.doc_type,
        func.count(EULaw.id).label('count')
    ).filter(
        EULaw.is_primary_legislation == True
    ).group_by(
        EULaw.doc_type
    ).order_by(
        desc('count')
    ).limit(limit).all()

    return [(doc_type or 'Unknown', count) for doc_type, count in results]


def get_yearly_distribution(db):
    """Get distribution of laws by year"""
    results = db.query(
        func.extract('year', EULaw.date).label('year'),
        func.count(EULaw.id).label('count')
    ).filter(
        EULaw.is_primary_legislation == True,
        EULaw.date.isnot(None)
    ).group_by(
        'year'
    ).order_by(
        'year'
    ).all()

    return [(int(year), count) for year, count in results]


def get_top_cited_laws(db, limit=20):
    """Get most cited laws based on citation frequency"""
    # This requires analyzing which laws are cited most often
    # We need to count how many times each CELEX appears in other laws' citations

    all_laws = db.query(EULaw).filter(
        EULaw.is_primary_legislation == True,
        EULaw.citations.isnot(None)
    ).all()

    citation_counts = Counter()
    for law in all_laws:
        if law.citations:
            for citation in law.citations:
                citation_counts[citation] += 1

    # Get details for most cited
    top_cited = []
    for citation, count in citation_counts.most_common(limit):
        # Try to find the law in our database
        cited_law = db.query(EULaw).filter(
            EULaw.celex == citation
        ).first()

        if cited_law:
            top_cited.append({
                'celex': citation,
                'title': cited_law.title[:80] + '...' if len(cited_law.title) > 80 else cited_law.title,
                'citation_count': count,
                'policy_area': cited_law.policy_area
            })
        else:
            top_cited.append({
                'celex': citation,
                'title': 'Not in database',
                'citation_count': count,
                'policy_area': None
            })

    return top_cited


def get_policy_area_growth(db):
    """Get yearly growth by policy area (top 10 policy areas only)"""
    # Get top 10 policy areas
    top_policies = db.query(
        EULaw.policy_area,
        func.count(EULaw.id).label('count')
    ).filter(
        EULaw.is_primary_legislation == True,
        EULaw.policy_area.isnot(None)
    ).group_by(
        EULaw.policy_area
    ).order_by(
        desc('count')
    ).limit(10).all()

    top_policy_names = [policy for policy, _ in top_policies]

    # Get yearly counts for each top policy
    growth_data = {}
    for policy_area in top_policy_names:
        results = db.query(
            func.extract('year', EULaw.date).label('year'),
            func.count(EULaw.id).label('count')
        ).filter(
            EULaw.is_primary_legislation == True,
            EULaw.policy_area == policy_area,
            EULaw.date.isnot(None)
        ).group_by(
            'year'
        ).order_by(
            'year'
        ).all()

        growth_data[policy_area] = [(int(year), count) for year, count in results]

    return growth_data


def get_related_laws_clusters(db, min_shared_citations=3, limit=10):
    """Find clusters of laws that cite similar sources"""
    # Get laws with citations
    laws_with_citations = db.query(EULaw).filter(
        EULaw.is_primary_legislation == True,
        EULaw.citations.isnot(None)
    ).all()

    # Build citation similarity
    law_citations = {}
    for law in laws_with_citations:
        if law.citations and len(law.citations) >= min_shared_citations:
            law_citations[law.celex or law.uuid] = set(law.citations)

    # Find clusters (laws with many shared citations)
    clusters = []
    processed = set()

    for law1_id, citations1 in law_citations.items():
        if law1_id in processed:
            continue

        cluster = [law1_id]
        for law2_id, citations2 in law_citations.items():
            if law1_id == law2_id or law2_id in processed:
                continue

            # Count shared citations
            shared = len(citations1 & citations2)
            if shared >= min_shared_citations:
                cluster.append(law2_id)
                processed.add(law2_id)

        if len(cluster) > 1:  # Only include clusters with multiple laws
            clusters.append(cluster)
            processed.add(law1_id)

        if len(clusters) >= limit:
            break

    return clusters


def print_horizontal_bar(label, value, max_value, width=50):
    """Print a horizontal bar chart"""
    bar_length = int((value / max_value) * width) if max_value > 0 else 0
    bar = '█' * bar_length
    percentage = (value / max_value * 100) if max_value > 0 else 0
    print(f"   {label[:40]:40s} {bar:50s} {value:5,} ({percentage:5.1f}%)")


def main():
    """Main visualization function"""
    parser = argparse.ArgumentParser(
        description="Visualize law distribution and clustering"
    )

    parser.add_argument(
        '--export-json',
        action='store_true',
        help='Export data as JSON file'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=f'law_distribution_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
        help='Output JSON filename'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("EU LAW DISTRIBUTION AND CLUSTERING VISUALIZATION")
    print("=" * 80)

    db = SessionLocal()

    try:
        # Get total stats
        total_laws = db.query(EULaw).count()
        primary_laws = db.query(EULaw).filter(EULaw.is_primary_legislation == True).count()
        classified = db.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.policy_area.isnot(None)
        ).count()

        print(f"\n📊 OVERALL STATISTICS")
        print(f"   Total laws indexed: {total_laws:,}")
        print(f"   Primary legislation: {primary_laws:,} ({primary_laws/total_laws*100:.1f}%)")
        print(f"   Classified: {classified:,} ({classified/primary_laws*100:.1f}%)")

        # 1. Policy Area Distribution
        print(f"\n📂 DISTRIBUTION BY POLICY AREA")
        print("=" * 80)

        policy_dist = get_policy_area_distribution(db)
        max_count = policy_dist[0][1] if policy_dist else 0

        for i, (policy, count) in enumerate(policy_dist[:25], 1):
            print_horizontal_bar(f"{i:2d}. {policy}", count, max_count)

        # 2. Document Type Distribution
        print(f"\n📝 DISTRIBUTION BY DOCUMENT TYPE (Top 20)")
        print("=" * 80)

        doc_type_dist = get_document_type_distribution(db, limit=20)
        max_count = doc_type_dist[0][1] if doc_type_dist else 0

        for i, (doc_type, count) in enumerate(doc_type_dist, 1):
            print_horizontal_bar(f"{i:2d}. {doc_type[:35]}", count, max_count)

        # 3. Yearly Distribution
        print(f"\n📅 DISTRIBUTION BY YEAR")
        print("=" * 80)

        yearly_dist = get_yearly_distribution(db)

        if yearly_dist:
            # Group into decades for visualization
            decade_counts = defaultdict(int)
            for year, count in yearly_dist:
                decade = (year // 10) * 10
                decade_counts[decade] += count

            max_count = max(decade_counts.values()) if decade_counts else 0

            for decade in sorted(decade_counts.keys()):
                count = decade_counts[decade]
                print_horizontal_bar(f"{decade}s", count, max_count)

        # 4. Most Cited Laws
        print(f"\n🔗 MOST CITED LAWS (Citation Network)")
        print("=" * 80)
        print("   Analyzing citation relationships...")

        top_cited = get_top_cited_laws(db, limit=15)

        if top_cited:
            max_citations = top_cited[0]['citation_count'] if top_cited else 0

            for i, law in enumerate(top_cited, 1):
                policy_tag = f"[{law['policy_area'][:20]}]" if law['policy_area'] else '[Unclassified]'
                print(f"   {i:2d}. {law['celex']:15s} - {law['citation_count']:3,} citations - {policy_tag}")
                print(f"       {law['title'][:75]}")
        else:
            print("   No citation data available")

        # 5. Policy Area Growth Over Time
        print(f"\n📈 POLICY AREA TRENDS (Top 5 Policy Areas)")
        print("=" * 80)

        growth_data = get_policy_area_growth(db)

        # Show only top 5 for readability
        for i, (policy, yearly_data) in enumerate(list(growth_data.items())[:5], 1):
            recent_years = [year for year, count in yearly_data if year >= 2010]
            if recent_years:
                total_recent = sum(count for year, count in yearly_data if year >= 2010)
                print(f"   {i}. {policy[:50]:50s}: {total_recent:,} laws since 2010")

        # Export to JSON if requested
        if args.export_json:
            export_data = {
                'generated_at': datetime.now().isoformat(),
                'statistics': {
                    'total_laws': total_laws,
                    'primary_laws': primary_laws,
                    'classified': classified,
                    'classification_rate': classified / primary_laws if primary_laws > 0 else 0
                },
                'policy_area_distribution': [
                    {'policy_area': policy, 'count': count}
                    for policy, count in policy_dist
                ],
                'document_type_distribution': [
                    {'doc_type': doc_type, 'count': count}
                    for doc_type, count in doc_type_dist
                ],
                'yearly_distribution': [
                    {'year': year, 'count': count}
                    for year, count in yearly_dist
                ],
                'top_cited_laws': top_cited,
                'policy_area_growth': growth_data
            }

            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"\n✅ Data exported to: {args.output}")

        print("\n" + "=" * 80)
        print("VISUALIZATION COMPLETE")
        print("=" * 80)

        print("\n💡 Next steps:")
        print("   - Create law clusters: Group related laws (e.g., 'GDPR Package')")
        print("   - Export with --export-json for external visualization")
        print("   - Analyze citation networks to find law relationships")

    except Exception as e:
        print(f"\n❌ Visualization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
