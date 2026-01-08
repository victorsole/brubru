"""
AI-Powered Cluster Validation

Uses Claude to validate whether each law actually belongs in its assigned cluster.
Removes misclassified laws and optionally finds missing laws.

Usage:
    python -m backend.scripts.validate_clusters_ai
    python -m backend.scripts.validate_clusters_ai --cluster-id 2
    python -m backend.scripts.validate_clusters_ai --dry-run
    python -m backend.scripts.validate_clusters_ai --find-missing
"""

import asyncio
import json
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import anthropic
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.core.config import settings
from backend.models.eu_law import EULaw, LawCluster, ClusterLaw

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClusterValidator:
    """Validates law-cluster assignments using AI."""

    def __init__(self, db: Session, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.stats = {
            'clusters_processed': 0,
            'laws_validated': 0,
            'laws_removed': 0,
            'laws_kept': 0,
            'laws_added': 0
        }

    def validate_cluster(self, cluster_id: int, find_missing: bool = False) -> Dict[str, Any]:
        """
        Validate all laws in a cluster.

        Returns dict with validation results.
        """
        # Get cluster
        cluster = self.db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            logger.error(f"Cluster {cluster_id} not found")
            return None

        logger.info(f"\n{'='*80}")
        logger.info(f"VALIDATING CLUSTER {cluster.id}: {cluster.name}")
        logger.info(f"{'='*80}")
        logger.info(f"Description: {cluster.description}")
        logger.info(f"Applicability: {cluster.applicability}")

        # Get laws in cluster
        cluster_laws = self.db.query(ClusterLaw, EULaw).join(
            EULaw, ClusterLaw.law_id == EULaw.id
        ).filter(
            ClusterLaw.cluster_id == cluster_id
        ).all()

        logger.info(f"Laws to validate: {len(cluster_laws)}")

        # Batch validate laws (send multiple at once for efficiency)
        laws_to_validate = [(cl, law) for cl, law in cluster_laws]
        validation_results = self._batch_validate_laws(cluster, laws_to_validate)

        # Process results
        laws_to_keep = []
        laws_to_remove = []

        for (cl, law), is_valid, reason in validation_results:
            if is_valid:
                laws_to_keep.append((law, reason))
                self.stats['laws_kept'] += 1
            else:
                laws_to_remove.append((law, reason))
                self.stats['laws_removed'] += 1

        # Report results
        logger.info(f"\n📊 VALIDATION RESULTS:")
        logger.info(f"   ✅ Valid laws to keep: {len(laws_to_keep)}")
        logger.info(f"   ❌ Invalid laws to remove: {len(laws_to_remove)}")

        if laws_to_remove:
            logger.info(f"\n❌ LAWS TO REMOVE:")
            for law, reason in laws_to_remove[:20]:  # Show first 20
                logger.info(f"   - [{law.celex or 'No CELEX'}] {law.title[:60]}...")
                logger.info(f"     Reason: {reason}")

        # Apply changes
        if not self.dry_run and laws_to_remove:
            for law, reason in laws_to_remove:
                self.db.query(ClusterLaw).filter(
                    ClusterLaw.cluster_id == cluster_id,
                    ClusterLaw.law_id == law.id
                ).delete()
            self.db.commit()
            logger.info(f"\n✅ Removed {len(laws_to_remove)} invalid laws from cluster")

        # Find missing laws if requested
        missing_laws = []
        if find_missing:
            missing_laws = self._find_missing_laws(cluster)
            if missing_laws and not self.dry_run:
                for law, relationship in missing_laws:
                    existing = self.db.query(ClusterLaw).filter(
                        ClusterLaw.cluster_id == cluster_id,
                        ClusterLaw.law_id == law.id
                    ).first()
                    if not existing:
                        self.db.add(ClusterLaw(
                            cluster_id=cluster_id,
                            law_id=law.id,
                            relationship_type=relationship
                        ))
                        self.stats['laws_added'] += 1
                self.db.commit()
                logger.info(f"\n✅ Added {len(missing_laws)} missing laws to cluster")

        self.stats['clusters_processed'] += 1
        self.stats['laws_validated'] += len(cluster_laws)

        return {
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'original_count': len(cluster_laws),
            'valid_count': len(laws_to_keep),
            'removed_count': len(laws_to_remove),
            'added_count': len(missing_laws),
            'removed_laws': [(l.celex, l.title[:80], r) for l, r in laws_to_remove],
            'added_laws': [(l.celex, l.title[:80]) for l, _ in missing_laws]
        }

    def _batch_validate_laws(
        self,
        cluster: LawCluster,
        laws: List[Tuple[ClusterLaw, EULaw]]
    ) -> List[Tuple[Tuple[ClusterLaw, EULaw], bool, str]]:
        """
        Validate multiple laws at once using AI.

        Returns list of (law_tuple, is_valid, reason)
        """
        if not laws:
            return []

        # Build the validation prompt
        laws_text = []
        for i, (cl, law) in enumerate(laws, 1):
            laws_text.append(f"""
{i}. CELEX: {law.celex or 'None'}
   Title: {law.title}
   Doc Type: {law.doc_type or 'Unknown'}
   Policy Area: {law.policy_area or 'Unknown'}
""")

        prompt = f"""You are an EU legal expert. Validate whether each law belongs in this cluster.

CLUSTER DEFINITION:
- Name: {cluster.name}
- Description: {cluster.description}
- Applicability: {cluster.applicability}
- Policy Area: {cluster.policy_area}

LAWS TO VALIDATE:
{''.join(laws_text)}

For EACH law, determine:
1. Does it directly relate to {cluster.name}?
2. Would it apply to {cluster.applicability}?
3. Is it in the correct policy domain?

A law BELONGS if it:
- Is the main regulation/directive for this topic
- Is an implementing/delegated act of the main law
- Directly addresses the same regulatory subject matter
- Applies to the same regulated entities

A law does NOT BELONG if it:
- Only mentions a keyword by coincidence (e.g., "platform" in "Disability Platform" is not about digital platforms)
- Is from a completely different policy domain (e.g., CFSP/military decisions don't belong in digital policy clusters)
- Has no substantive connection to the cluster's regulatory scope

Return a JSON array with one object per law:
[
  {{"index": 1, "valid": true, "reason": "Main DSA regulation"}},
  {{"index": 2, "valid": false, "reason": "CFSP military decision, unrelated to digital services"}},
  ...
]

Be strict - only keep laws that genuinely belong. It's better to have fewer correct laws than many incorrect ones."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            results = json.loads(content.strip())

            # Map results back to laws
            validation_results = []
            for (cl, law), result in zip(laws, results):
                is_valid = result.get('valid', False)
                reason = result.get('reason', 'No reason provided')
                validation_results.append(((cl, law), is_valid, reason))

            return validation_results

        except Exception as e:
            logger.error(f"AI validation failed: {str(e)}")
            # On error, keep all laws (conservative approach)
            return [((cl, law), True, "Validation error - kept by default") for cl, law in laws]

    def _find_missing_laws(self, cluster: LawCluster) -> List[Tuple[EULaw, str]]:
        """
        Find laws that should be in the cluster but aren't.

        Uses AI to suggest missing laws based on cluster definition.
        """
        logger.info(f"\n🔍 Finding missing laws for cluster: {cluster.name}")

        # Get current law IDs in cluster
        current_law_ids = set(
            cl.law_id for cl in self.db.query(ClusterLaw).filter(
                ClusterLaw.cluster_id == cluster.id
            ).all()
        )

        # Search for candidate laws by policy area and keywords
        candidates = self._search_candidate_laws(cluster)

        # Filter out laws already in cluster
        new_candidates = [law for law in candidates if law.id not in current_law_ids]

        if not new_candidates:
            logger.info("   No new candidates found")
            return []

        logger.info(f"   Found {len(new_candidates)} candidate laws to evaluate")

        # Ask AI to identify which should be added
        prompt = f"""You are an EU legal expert. Identify which of these laws should be added to a cluster.

CLUSTER DEFINITION:
- Name: {cluster.name}
- Description: {cluster.description}
- Applicability: {cluster.applicability}
- Policy Area: {cluster.policy_area}

CANDIDATE LAWS:
"""
        for i, law in enumerate(new_candidates[:30], 1):  # Limit to 30
            prompt += f"""
{i}. CELEX: {law.celex or 'None'}
   Title: {law.title}
   Doc Type: {law.doc_type or 'Unknown'}
"""

        prompt += """

Return a JSON array of law indices that SHOULD be added to this cluster:
{"add": [1, 5, 12], "reasons": {"1": "Implementing act for main regulation", "5": "...", "12": "..."}}

Only include laws that clearly and directly relate to the cluster's regulatory scope.
Be selective - quality over quantity."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            indices_to_add = result.get('add', [])

            missing_laws = []
            for idx in indices_to_add:
                if 1 <= idx <= len(new_candidates):
                    law = new_candidates[idx - 1]
                    missing_laws.append((law, 'related'))
                    logger.info(f"   ➕ Add: [{law.celex}] {law.title[:60]}...")

            return missing_laws

        except Exception as e:
            logger.error(f"Failed to find missing laws: {str(e)}")
            return []

    def _search_candidate_laws(self, cluster: LawCluster) -> List[EULaw]:
        """Search for candidate laws that might belong to cluster."""
        # Build search based on cluster policy area
        query = self.db.query(EULaw).filter(
            EULaw.is_primary_legislation == True
        )

        # Filter by policy area if available
        if cluster.policy_area:
            query = query.filter(
                or_(
                    EULaw.policy_area.ilike(f'%{cluster.policy_area}%'),
                    EULaw.title.ilike(f'%{cluster.name.split()[0]}%')  # First word of cluster name
                )
            )

        return query.limit(100).all()


async def validate_all_clusters(
    cluster_id: Optional[int] = None,
    dry_run: bool = False,
    find_missing: bool = False
):
    """Validate all clusters or a specific one."""
    db = SessionLocal()
    validator = ClusterValidator(db, dry_run=dry_run)

    try:
        if cluster_id:
            clusters = db.query(LawCluster).filter(LawCluster.id == cluster_id).all()
        else:
            clusters = db.query(LawCluster).order_by(LawCluster.id).all()

        logger.info(f"Validating {len(clusters)} clusters")

        results = []
        for cluster in clusters:
            try:
                result = validator.validate_cluster(cluster.id, find_missing=find_missing)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Failed to validate cluster {cluster.name}: {e}")
                continue

        # Summary
        logger.info(f"\n{'='*80}")
        logger.info("VALIDATION COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"\n📊 OVERALL STATISTICS:")
        logger.info(f"   Clusters processed: {validator.stats['clusters_processed']}")
        logger.info(f"   Laws validated: {validator.stats['laws_validated']}")
        logger.info(f"   Laws kept: {validator.stats['laws_kept']}")
        logger.info(f"   Laws removed: {validator.stats['laws_removed']}")
        logger.info(f"   Laws added: {validator.stats['laws_added']}")

        if dry_run:
            logger.info(f"\n⚠️  DRY RUN - No changes were made")

        # Save results to file
        results_file = f"cluster_validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.utcnow().isoformat(),
                'dry_run': dry_run,
                'stats': validator.stats,
                'results': results
            }, f, indent=2)
        logger.info(f"\n📄 Results saved to: {results_file}")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="AI-powered cluster validation")
    parser.add_argument("--cluster-id", type=int, help="Validate only this cluster")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    parser.add_argument("--find-missing", action="store_true", help="Also find and add missing laws")
    args = parser.parse_args()

    asyncio.run(validate_all_clusters(
        cluster_id=args.cluster_id,
        dry_run=args.dry_run,
        find_missing=args.find_missing
    ))


if __name__ == "__main__":
    main()
