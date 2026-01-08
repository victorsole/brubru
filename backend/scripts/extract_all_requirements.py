"""
Extract Legal Requirements from All EU Law Clusters

This script:
1. Processes all 21 law clusters
2. Extracts legal requirements using AI (obligations, deadlines, entities)
3. Saves to backend/knowledge_base/requirements/ as JSON files
4. Also populates the database law_requirements table

Usage:
    python -m backend.scripts.extract_all_requirements

Options:
    --cluster-id N     Extract only cluster N
    --dry-run          Don't save to database, only generate files
    --force            Re-extract even if requirements exist
"""

import asyncio
import json
import logging
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base" / "requirements"
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)


class RequirementExtractor:
    """Extracts legal requirements from EU law text using AI."""

    def __init__(self, db: Session):
        from ..core.config import settings
        import anthropic
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def extract_from_cluster(
        self,
        cluster_id: int,
        force: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Extract all requirements for a cluster.

        Returns dict with cluster info and extracted requirements.
        """
        from ..models.eu_law import LawCluster, ClusterLaw, EULaw, LawRequirement

        # Get cluster
        cluster = self.db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            logger.error(f"Cluster {cluster_id} not found")
            return None

        logger.info(f"Processing cluster: {cluster.name}")

        # Check if requirements already exist
        existing_count = self.db.query(LawRequirement).filter(
            LawRequirement.cluster_id == cluster_id
        ).count()

        if existing_count > 0 and not force:
            logger.info(f"  Cluster already has {existing_count} requirements. Use --force to re-extract.")
            return self._load_existing_requirements(cluster)

        # Get laws in cluster
        cluster_laws = self.db.query(ClusterLaw, EULaw).join(
            EULaw, ClusterLaw.law_id == EULaw.id
        ).filter(
            ClusterLaw.cluster_id == cluster_id
        ).all()

        logger.info(f"  Found {len(cluster_laws)} laws in cluster")

        # Extract requirements from each law
        all_requirements = []
        for i, (cl, law) in enumerate(cluster_laws):
            logger.info(f"  [{i+1}/{len(cluster_laws)}] Processing: {law.celex or 'No CELEX'}")

            try:
                requirements = await self._extract_from_law(law, cluster)
                all_requirements.extend(requirements)
                logger.info(f"    Extracted {len(requirements)} requirements")
            except Exception as e:
                logger.error(f"    Error: {str(e)}")
                continue

        # Build result
        result = {
            "cluster_id": cluster.id,
            "cluster_name": cluster.name,
            "policy_area": cluster.policy_area,
            "description": cluster.description,
            "applicability": cluster.applicability,
            "extraction_date": datetime.utcnow().isoformat(),
            "total_laws": len(cluster_laws),
            "total_requirements": len(all_requirements),
            "requirements": all_requirements
        }

        # Save to file
        self._save_to_file(cluster, result)

        # Save to database (unless dry run)
        if not dry_run:
            self._save_to_database(cluster, all_requirements)

        return result

    async def _extract_from_law(
        self,
        law: "EULaw",
        cluster: "LawCluster"
    ) -> List[Dict[str, Any]]:
        """Extract requirements from a single law."""

        # Get law text (from XML or title/description)
        law_text = self._get_law_text(law)

        if not law_text or len(law_text) < 100:
            # No useful text, create basic requirement from title
            return self._create_basic_requirement(law, cluster)

        # Use AI to extract requirements
        prompt = f"""Extract all legal requirements/obligations from this EU law.

LAW DETAILS:
- CELEX: {law.celex or 'N/A'}
- Title: {law.title}
- Type: {law.doc_type or 'Unknown'}
- Policy Area: {cluster.policy_area}

LAW TEXT:
{law_text[:12000]}

EXTRACT:
For each requirement/obligation found, provide:
1. article: Article number (e.g., "Article 5", "Article 17(1)")
2. requirement_text: The specific obligation (what must be done)
3. applicable_entity: Who must comply (e.g., "data controllers", "online platforms", "member states")
4. criticality: "critical" (legally binding, penalties), "important" (should comply), or "recommended"
5. deadline_text: Any deadline mentioned (e.g., "within 72 hours", "by 1 January 2025")
6. keywords: Key terms for searching

Focus on:
- Obligations using "shall", "must", "required to", "obliged to"
- Prohibitions using "shall not", "must not", "prohibited"
- Rights that create obligations (e.g., "users have the right to..." creates obligation on platforms)

Return JSON array:
[
  {{
    "article": "Article X",
    "requirement_text": "...",
    "applicable_entity": "...",
    "criticality": "critical|important|recommended",
    "deadline_text": "...",
    "keywords": ["keyword1", "keyword2"]
  }}
]

If no clear requirements found, return empty array: []"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system="You are an EU legal expert extracting compliance requirements. Be thorough but precise. Only extract actual legal obligations, not general descriptions. Always respond with valid JSON only.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.content[0].text
            # Try to extract JSON from the response
            # Handle case where response might have markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            data = json.loads(content.strip())

            # Handle different response structures
            if isinstance(data, list):
                requirements = data
            elif isinstance(data, dict) and "requirements" in data:
                requirements = data["requirements"]
            else:
                requirements = []

            # Enrich with law metadata
            for req in requirements:
                req["law_id"] = law.id
                req["law_celex"] = law.celex
                req["law_title"] = law.title
                req["cluster_id"] = cluster.id

            return requirements

        except Exception as e:
            logger.error(f"AI extraction failed: {str(e)}")
            return self._create_basic_requirement(law, cluster)

    def _get_law_text(self, law: "EULaw") -> str:
        """Get text content from law (from XML file or database)."""
        # Try to read from XML file
        if law.xml_path:
            xml_path = Path(law.xml_path)
            if xml_path.exists():
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(xml_path)
                    root = tree.getroot()

                    # Extract text from all elements
                    texts = []
                    for elem in root.iter():
                        if elem.text and elem.text.strip():
                            texts.append(elem.text.strip())
                        if elem.tail and elem.tail.strip():
                            texts.append(elem.tail.strip())

                    return "\n".join(texts)
                except Exception as e:
                    logger.warning(f"Failed to parse XML {xml_path}: {e}")

        # Fallback to title + subject matter
        parts = [law.title]
        if law.subject_matter:
            parts.extend(law.subject_matter)
        return "\n".join(parts)

    def _create_basic_requirement(
        self,
        law: "EULaw",
        cluster: "LawCluster"
    ) -> List[Dict[str, Any]]:
        """Create a basic requirement entry when AI extraction fails."""
        return [{
            "article": "General",
            "requirement_text": f"Comply with {law.title}",
            "applicable_entity": cluster.applicability or "Relevant entities",
            "criticality": "important",
            "deadline_text": None,
            "keywords": (law.subject_matter or [])[:5],
            "law_id": law.id,
            "law_celex": law.celex,
            "law_title": law.title,
            "cluster_id": cluster.id
        }]

    def _load_existing_requirements(self, cluster: "LawCluster") -> Dict[str, Any]:
        """Load existing requirements from database."""
        from ..models.eu_law import LawRequirement, EULaw

        requirements = self.db.query(LawRequirement, EULaw).join(
            EULaw, LawRequirement.law_id == EULaw.id
        ).filter(
            LawRequirement.cluster_id == cluster.id
        ).all()

        req_list = []
        for req, law in requirements:
            req_list.append({
                "article": req.article,
                "requirement_text": req.requirement_text,
                "applicable_entity": req.applicable_entity,
                "criticality": req.criticality,
                "deadline_text": req.deadline.isoformat() if req.deadline else None,
                "keywords": req.extra_metadata.get("keywords", []) if req.extra_metadata else [],
                "law_id": law.id,
                "law_celex": law.celex,
                "law_title": law.title,
                "cluster_id": cluster.id
            })

        return {
            "cluster_id": cluster.id,
            "cluster_name": cluster.name,
            "policy_area": cluster.policy_area,
            "description": cluster.description,
            "applicability": cluster.applicability,
            "extraction_date": "existing",
            "total_laws": len(set(r["law_id"] for r in req_list)),
            "total_requirements": len(req_list),
            "requirements": req_list
        }

    def _save_to_file(self, cluster: "LawCluster", data: Dict[str, Any]):
        """Save extracted requirements to JSON file."""
        # Create safe filename
        safe_name = re.sub(r'[^\w\s-]', '', cluster.name).strip().replace(' ', '_').lower()
        filename = f"{cluster.id:02d}_{safe_name}.json"
        filepath = KNOWLEDGE_BASE_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"  Saved to {filepath}")

    def _save_to_database(self, cluster: "LawCluster", requirements: List[Dict[str, Any]]):
        """Save requirements to database."""
        from ..models.eu_law import LawRequirement
        from datetime import datetime

        # Delete existing requirements for this cluster
        self.db.query(LawRequirement).filter(
            LawRequirement.cluster_id == cluster.id
        ).delete()

        # Insert new requirements
        for req in requirements:
            # Truncate article to fit VARCHAR(100)
            article = req.get("article", "General")
            if article and len(article) > 100:
                article = article[:97] + "..."

            # Truncate applicable_entity to fit column
            applicable_entity = req.get("applicable_entity")
            if applicable_entity and len(applicable_entity) > 255:
                applicable_entity = applicable_entity[:252] + "..."

            db_req = LawRequirement(
                law_id=req.get("law_id"),
                cluster_id=cluster.id,
                article=article,
                requirement_text=req.get("requirement_text", ""),
                applicable_entity=applicable_entity,
                criticality=req.get("criticality", "important"),
                deadline=None,  # Would need to parse deadline_text
                extra_metadata={
                    "keywords": req.get("keywords", []),
                    "law_celex": req.get("law_celex"),
                    "law_title": req.get("law_title")
                }
            )
            self.db.add(db_req)

        try:
            self.db.commit()
            logger.info(f"  Saved {len(requirements)} requirements to database")
        except Exception as e:
            logger.error(f"  Database error: {str(e)}")
            self.db.rollback()


async def extract_all_clusters(
    cluster_id: Optional[int] = None,
    force: bool = False,
    dry_run: bool = False
):
    """Extract requirements from all clusters (or specific cluster)."""
    from ..core.database import SessionLocal
    from ..models.eu_law import LawCluster

    db = SessionLocal()
    extractor = RequirementExtractor(db)

    try:
        if cluster_id:
            clusters = db.query(LawCluster).filter(LawCluster.id == cluster_id).all()
        else:
            clusters = db.query(LawCluster).order_by(LawCluster.id).all()

        logger.info(f"Processing {len(clusters)} clusters")

        results = []
        for cluster in clusters:
            try:
                result = await extractor.extract_from_cluster(
                    cluster.id, force=force, dry_run=dry_run
                )
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Failed to process cluster {cluster.name}: {e}")
                continue

        # Summary
        total_requirements = sum(r["total_requirements"] for r in results)
        logger.info(f"\n{'='*60}")
        logger.info(f"EXTRACTION COMPLETE")
        logger.info(f"Clusters processed: {len(results)}")
        logger.info(f"Total requirements extracted: {total_requirements}")
        logger.info(f"Files saved to: {KNOWLEDGE_BASE_DIR}")
        logger.info(f"{'='*60}")

        # Create index file
        _create_index_file(results)

    finally:
        db.close()


def _create_index_file(results: List[Dict[str, Any]]):
    """Create an index file listing all clusters and their requirements."""
    index = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_clusters": len(results),
        "total_requirements": sum(r["total_requirements"] for r in results),
        "clusters": [
            {
                "id": r["cluster_id"],
                "name": r["cluster_name"],
                "policy_area": r["policy_area"],
                "laws": r["total_laws"],
                "requirements": r["total_requirements"],
                "file": f"{r['cluster_id']:02d}_{re.sub(r'[^w s-]', '', r['cluster_name']).strip().replace(' ', '_').lower()}.json"
            }
            for r in results
        ]
    }

    index_path = KNOWLEDGE_BASE_DIR / "_index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    logger.info(f"Created index file: {index_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract EU law requirements")
    parser.add_argument("--cluster-id", type=int, help="Extract only this cluster")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to database")
    parser.add_argument("--force", action="store_true", help="Re-extract existing requirements")
    args = parser.parse_args()

    asyncio.run(extract_all_clusters(
        cluster_id=args.cluster_id,
        force=args.force,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
