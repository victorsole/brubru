"""
Extract Requirements for Law Cluster

Runs the requirement extraction pipeline on all laws in a specified cluster.

Usage:
    python backend/scripts/extract_requirements_for_cluster.py --cluster "FinTech Startup Compliance"
    python backend/scripts/extract_requirements_for_cluster.py --cluster-id 15
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy.orm import Session
from backend.core.database import engine, SessionLocal
from backend.models.eu_law import LawCluster, ClusterLaw, EULaw
from backend.services.compliance.requirement_extractor import RequirementExtractor


def get_cluster(db: Session, cluster_id: int = None, cluster_name: str = None) -> LawCluster:
    """Get cluster by ID or name"""
    if cluster_id:
        cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
    elif cluster_name:
        cluster = db.query(LawCluster).filter(LawCluster.name == cluster_name).first()
    else:
        raise ValueError("Must provide either cluster_id or cluster_name")

    if not cluster:
        raise ValueError(f"Cluster not found: {cluster_id or cluster_name}")

    return cluster


def get_cluster_laws(db: Session, cluster_id: int) -> list[EULaw]:
    """Get all laws in a cluster"""
    cluster_law_ids = db.query(ClusterLaw.law_id).filter(
        ClusterLaw.cluster_id == cluster_id
    ).all()

    law_ids = [cl[0] for cl in cluster_law_ids]

    laws = db.query(EULaw).filter(EULaw.id.in_(law_ids)).all()

    return laws


def extract_requirements_for_cluster(
    cluster_name: str = None,
    cluster_id: int = None,
    limit: int = None,
    model: str = 'gpt-4'
):
    """
    Extract requirements for all laws in a cluster.

    Args:
        cluster_name: Name of the cluster
        cluster_id: ID of the cluster
        limit: Limit number of laws to process (for testing)
        model: Model to use (gpt-4, saul-7b, llama-3.1-8b, mistral-7b)
    """
    db = SessionLocal()

    try:
        # Get cluster
        print("=" * 70)
        print("Requirement Extraction for Law Cluster")
        print("=" * 70)

        cluster = get_cluster(db, cluster_id=cluster_id, cluster_name=cluster_name)
        print(f"\nCluster: {cluster.name} (ID: {cluster.id})")
        print(f"Policy Area: {cluster.policy_area}")
        print(f"Applicability: {cluster.applicability}")
        print(f"Model: {model}")

        # Get laws in cluster
        laws = get_cluster_laws(db, cluster.id)
        print(f"\nLaws in cluster: {len(laws)}")

        if limit:
            laws = laws[:limit]
            print(f"Processing limited to: {limit} laws")

        if not laws:
            print("No laws found in this cluster.")
            return

        # Initialize extractor with specified model
        extractor = RequirementExtractor(db, model=model)

        # Process each law
        total_requirements = 0
        total_processed = 0
        failed_laws = []

        print("\n" + "-" * 70)
        print("Extracting requirements...")
        print("-" * 70)

        for i, law in enumerate(laws, 1):
            try:
                print(f"\n[{i}/{len(laws)}] Processing: {law.celex or law.uuid}")
                print(f"  Title: {law.title[:80]}...")

                # Extract requirements using the correct method
                requirements = extractor.extract_requirements_from_law(law, cluster.id)
                print(f"  Found {len(requirements)} potential requirements")

                if requirements:
                    # Save to database
                    for req in requirements:
                        db.add(req)
                    db.commit()
                    print(f"  ✓ Saved {len(requirements)} requirements")
                    total_requirements += len(requirements)
                else:
                    print(f"  No requirements extracted")

                total_processed += 1

            except Exception as e:
                print(f"  ✗ Error: {e}")
                failed_laws.append((law.celex or law.uuid, str(e)))
                db.rollback()  # Rollback on error

        # Summary
        print("\n" + "=" * 70)
        print("Extraction Summary")
        print("=" * 70)
        print(f"Cluster: {cluster.name}")
        print(f"Total laws processed: {total_processed}/{len(laws)}")
        print(f"Total requirements extracted: {total_requirements}")
        print(f"Failed laws: {len(failed_laws)}")

        if failed_laws:
            print("\nFailed laws:")
            for celex, error in failed_laws[:10]:  # Show first 10
                print(f"  - {celex}: {error[:100]}")

        print("\n✓ Requirement extraction completed!")

        # Show sample requirements
        if total_requirements > 0:
            from backend.models.eu_law import LawRequirement

            print("\nSample requirements:")
            sample_reqs = db.query(EULaw, LawRequirement).join(
                LawRequirement, EULaw.id == LawRequirement.law_id
            ).filter(
                EULaw.id.in_([law.id for law in laws])
            ).limit(3).all()

            for i, (law, req) in enumerate(sample_reqs, 1):
                print(f"\n{i}. {law.celex} - {req.article}")
                print(f"   {req.requirement_text[:150]}...")
                print(f"   Criticality: {req.criticality}")

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        raise

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Extract requirements from law cluster')
    parser.add_argument('--cluster', '-c', help='Cluster name')
    parser.add_argument('--cluster-id', '-i', type=int, help='Cluster ID')
    parser.add_argument('--limit', '-l', type=int, help='Limit number of laws to process')
    parser.add_argument('--model', '-m', default='gpt-4',
                        choices=['gpt-4', 'saul-7b', 'llama-3.1-8b', 'mistral-7b'],
                        help='Model to use for extraction (default: gpt-4)')
    parser.add_argument('--list-clusters', action='store_true', help='List available clusters')

    args = parser.parse_args()

    if args.list_clusters:
        # List all clusters
        db = SessionLocal()
        clusters = db.query(LawCluster).all()
        print("\nAvailable clusters:")
        print("-" * 70)
        for cluster in clusters:
            num_laws = db.query(ClusterLaw).filter(ClusterLaw.cluster_id == cluster.id).count()
            print(f"{cluster.id:3d}. {cluster.name}")
            print(f"      Policy: {cluster.policy_area} | Laws: {num_laws}")
        db.close()
        return 0

    if not args.cluster and not args.cluster_id:
        parser.error("Must provide either --cluster or --cluster-id (or use --list-clusters)")

    extract_requirements_for_cluster(
        cluster_name=args.cluster,
        cluster_id=args.cluster_id,
        limit=args.limit,
        model=args.model
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
