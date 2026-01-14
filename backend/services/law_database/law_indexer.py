"""
EU Law Indexer

Indexes EU laws from LEG_2025-11 directory into database and provides
search functionality for the chatbot context builder.

Main functions:
- index_all_laws(): Parse and index all 50k+ laws
- search_laws(): Semantic and text search
- get_law_by_celex(): Get specific law by CELEX
- classify_policy_area(): Map laws to policy taxonomy
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import or_, and_, desc, func
from sqlalchemy.orm import Session

from .xml_parser import get_xml_parser
from .policy_classifier import get_policy_classifier
from core.database import SessionLocal
from models.eu_law import EULaw, LawCluster, ClusterLaw
from knowledge_base.knowledge_loader import get_knowledge_loader

logger = logging.getLogger(__name__)


class EULawIndexer:
    """
    Index and search EU laws from LEG_2025-11.

    Provides fast access to 50k+ EU legal documents for:
    - Chatbot context injection
    - EU Law Comply compliance checking
    - Legal research
    """

    def __init__(
        self,
        leg_directory: str = "docs/LEG_2025-11",
        batch_size: int = 100,
        enable_policy_classification: bool = True
    ):
        """
        Initialize indexer.

        Args:
            leg_directory: Path to LEG_2025-11 directory
            batch_size: Number of laws to process in each batch
            enable_policy_classification: Automatically classify laws by policy area
        """
        self.leg_directory = Path(leg_directory)
        self.batch_size = batch_size
        self.enable_policy_classification = enable_policy_classification
        self.xml_parser = get_xml_parser()
        self.knowledge_loader = get_knowledge_loader()
        self.policy_classifier = get_policy_classifier() if enable_policy_classification else None

        # Load policy taxonomy for classification
        self.policy_areas = self._load_policy_taxonomy()

        logger.info(
            f"Initialized EULawIndexer: {self.leg_directory}, "
            f"policy classification {'enabled' if enable_policy_classification else 'disabled'}"
        )

    def _load_policy_taxonomy(self) -> Dict[str, Any]:
        """Load EU policy taxonomy from eu_policies.json"""
        try:
            policy_file = Path("backend/knowledge_base/institutions/eu_policies.json")
            if policy_file.exists():
                with open(policy_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            else:
                logger.warning("eu_policies.json not found, policy classification disabled")
                return {}
        except Exception as e:
            logger.error(f"Failed to load policy taxonomy: {str(e)}")
            return {}

    async def index_all_laws(
        self,
        resume_from: Optional[str] = None,
        max_laws: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Index all laws from LEG_2025-11 directory.

        This is a long-running operation that parses ~117k XML files
        from ~50k law directories.

        Args:
            resume_from: UUID to resume from (for interrupted indexing)
            max_laws: Maximum number of laws to index (for testing)

        Returns:
            Statistics about indexing operation
        """
        start_time = datetime.now()
        stats = {
            'total_directories': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        logger.info("Starting law indexing...")

        # Get all UUID directories
        uuid_dirs = sorted([d for d in self.leg_directory.iterdir() if d.is_dir()])
        stats['total_directories'] = len(uuid_dirs)

        logger.info(f"Found {len(uuid_dirs)} law directories")

        # Resume logic
        if resume_from:
            try:
                resume_idx = [d.name for d in uuid_dirs].index(resume_from)
                uuid_dirs = uuid_dirs[resume_idx:]
                logger.info(f"Resuming from {resume_from} ({len(uuid_dirs)} remaining)")
            except ValueError:
                logger.warning(f"Resume UUID {resume_from} not found, starting from beginning")

        # Limit for testing
        if max_laws:
            uuid_dirs = uuid_dirs[:max_laws]
            logger.info(f"Limited to {max_laws} laws for testing")

        # Process in batches
        batch = []
        db = SessionLocal()

        try:
            for uuid_dir in uuid_dirs:
                stats['processed'] += 1

                # Find XML file in fmx4 subdirectory
                xml_file = self._find_primary_xml(uuid_dir)

                if not xml_file:
                    logger.warning(f"No XML file found in {uuid_dir.name}")
                    stats['skipped'] += 1
                    continue

                # Check if already indexed
                existing = db.query(EULaw).filter(EULaw.uuid == uuid_dir.name).first()
                if existing:
                    logger.debug(f"Already indexed: {uuid_dir.name}")
                    stats['skipped'] += 1
                    continue

                # Parse XML
                metadata = self.xml_parser.parse_file(str(xml_file))

                if not metadata:
                    logger.warning(f"Failed to parse {xml_file}")
                    stats['failed'] += 1
                    stats['errors'].append({
                        'uuid': uuid_dir.name,
                        'error': 'XML parsing failed'
                    })
                    continue

                # Classify policy area
                policy_area = None
                if self.enable_policy_classification:
                    policy_area = self._classify_policy_area(metadata)

                # Determine if this is primary legislation or annex/technical doc
                doc_type = metadata.get('doc_type', 'Unknown')
                title = metadata['title']
                is_primary = self._is_primary_legislation(doc_type, title)

                # Create database record
                law = EULaw(
                    uuid=metadata['uuid'],
                    celex=metadata.get('celex'),
                    doc_type=doc_type,
                    title=title,
                    date=datetime.strptime(metadata['date'], '%Y-%m-%d').date() if metadata.get('date') else None,
                    oj_reference=metadata.get('oj_reference'),
                    policy_area=policy_area,
                    is_primary_legislation=is_primary,
                    legal_basis=metadata.get('legal_basis', []),
                    citations=metadata.get('citations', []),
                    subject_matter=metadata.get('subject_matter', []),
                    xml_path=metadata['xml_path'],
                    extra_metadata=metadata.get('metadata_extra', {})
                )

                batch.append(law)
                stats['successful'] += 1

                # Commit batch
                if len(batch) >= self.batch_size:
                    db.bulk_save_objects(batch)
                    db.commit()
                    logger.info(
                        f"Indexed batch: {stats['successful']}/{stats['processed']} "
                        f"({stats['successful']/stats['processed']*100:.1f}%)"
                    )
                    batch = []

                # Progress logging every 1000
                if stats['processed'] % 1000 == 0:
                    logger.info(
                        f"Progress: {stats['processed']}/{stats['total_directories']} "
                        f"({stats['processed']/stats['total_directories']*100:.1f}%) - "
                        f"{stats['successful']} successful, {stats['failed']} failed"
                    )

            # Commit remaining
            if batch:
                db.bulk_save_objects(batch)
                db.commit()
                logger.info(f"Committed final batch of {len(batch)} laws")

        except Exception as e:
            logger.error(f"Indexing failed: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        stats['duration_seconds'] = duration
        stats['laws_per_second'] = stats['successful'] / duration if duration > 0 else 0

        logger.info(
            f"Indexing complete: {stats['successful']} laws indexed in {duration:.1f}s "
            f"({stats['laws_per_second']:.1f} laws/sec)"
        )

        return stats

    def _find_primary_xml(self, uuid_dir: Path) -> Optional[Path]:
        """
        Find primary XML file in UUID directory.

        Structure: {UUID}/fmx4/{FILENAME}.xml
        Excludes .doc.xml files (those are document-specific versions)
        """
        fmx4_dir = uuid_dir / "fmx4"
        if not fmx4_dir.exists():
            return None

        # Find .xml files (not .doc.xml)
        xml_files = [
            f for f in fmx4_dir.glob("*.xml")
            if not f.name.endswith('.doc.xml')
        ]

        if xml_files:
            # Return first XML file
            return xml_files[0]

        return None

    def _classify_policy_area(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Classify law into one of the 33 EU policy areas using enhanced NLP classifier.

        Args:
            metadata: Parsed law metadata

        Returns:
            Policy area name or None
        """
        if not self.policy_classifier:
            return None

        # Use enhanced classifier
        policy_area, confidence = self.policy_classifier.classify_with_confidence(
            title=metadata.get('title', ''),
            doc_type=metadata.get('doc_type', ''),
            subject_matter=metadata.get('subject_matter', []),
            full_text=metadata.get('full_text', '')[:1000]  # First 1000 chars
        )

        if policy_area and confidence > 0.3:  # Minimum confidence threshold
            logger.debug(
                f"Classified as '{policy_area}' (confidence: {confidence:.2%})"
            )
            return policy_area

        return None

    def _is_primary_legislation(self, doc_type: str, title: str) -> bool:
        """
        Determine if a document is primary legislation or an annex/technical document.

        Args:
            doc_type: Document type from XML
            title: Document title

        Returns:
            True if primary legislation, False if annex/ToC/technical doc
        """
        # Check doc_type
        doc_type_lower = doc_type.lower() if doc_type else ''
        title_lower = title.lower() if title else ''

        # Non-primary indicators
        non_primary_indicators = [
            'annex',
            'official journal',
            'table of contents',
            'corrigendum',
            'erratum',
            'correction'
        ]

        # Check if it's a non-primary document
        for indicator in non_primary_indicators:
            if indicator in doc_type_lower or title_lower.startswith(indicator):
                return False

        # Everything else is considered primary legislation
        return True

    async def search_laws(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
        primary_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search laws by query and filters.

        Args:
            query: Search query (searches title, CELEX, subject matter)
            filters: Optional filters (policy_area, date_range, doc_type, include_annexes)
            limit: Maximum results
            offset: Pagination offset
            primary_only: If True, only search primary legislation (default: True)

        Returns:
            List of matching laws
        """
        db = SessionLocal()

        try:
            # Build query
            query_obj = db.query(EULaw)

            # Filter by primary legislation (skip annexes/ToCs by default)
            if primary_only and (not filters or filters.get('include_annexes') != True):
                query_obj = query_obj.filter(EULaw.is_primary_legislation == True)

            # Text search (simple ILIKE for now, can be upgraded to full-text search)
            if query:
                query_lower = f"%{query.lower()}%"
                query_obj = query_obj.filter(
                    or_(
                        EULaw.title.ilike(query_lower),
                        EULaw.celex.ilike(query_lower),
                        EULaw.doc_type.ilike(query_lower)
                    )
                )

            # Apply filters
            if filters:
                if 'policy_area' in filters:
                    query_obj = query_obj.filter(EULaw.policy_area == filters['policy_area'])

                if 'doc_type' in filters:
                    query_obj = query_obj.filter(EULaw.doc_type.ilike(f"%{filters['doc_type']}%"))

                if 'date_from' in filters:
                    query_obj = query_obj.filter(EULaw.date >= filters['date_from'])

                if 'date_to' in filters:
                    query_obj = query_obj.filter(EULaw.date <= filters['date_to'])

            # Order by date (newest first)
            query_obj = query_obj.order_by(desc(EULaw.date))

            # Pagination
            results = query_obj.offset(offset).limit(limit).all()

            # Convert to dict
            laws = [law.to_dict() for law in results]

            logger.debug(f"Search returned {len(laws)} laws for query: {query}")

            return laws

        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []
        finally:
            db.close()

    async def get_law_by_celex(self, celex: str) -> Optional[Dict[str, Any]]:
        """
        Get law by CELEX number.

        Args:
            celex: CELEX number (e.g., "32019D1194")

        Returns:
            Law metadata or None
        """
        db = SessionLocal()

        try:
            law = db.query(EULaw).filter(EULaw.celex == celex).first()

            if law:
                return law.to_dict()

            return None

        except Exception as e:
            logger.error(f"Failed to get law by CELEX {celex}: {str(e)}")
            return None
        finally:
            db.close()

    async def get_law_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get law by UUID.

        Args:
            uuid: UUID from directory name

        Returns:
            Law metadata or None
        """
        db = SessionLocal()

        try:
            law = db.query(EULaw).filter(EULaw.uuid == uuid).first()

            if law:
                return law.to_dict()

            return None

        except Exception as e:
            logger.error(f"Failed to get law by UUID {uuid}: {str(e)}")
            return None
        finally:
            db.close()

    async def get_law_full_text(self, uuid: str) -> str:
        """
        Get full text of law by parsing XML.

        Args:
            uuid: Law UUID

        Returns:
            Full text content
        """
        # Get law metadata
        law = await self.get_law_by_uuid(uuid)

        if not law:
            logger.warning(f"Law not found: {uuid}")
            return ""

        # Parse XML to get full text
        xml_path = law['xml_path']
        metadata = self.xml_parser.parse_file(xml_path)

        if metadata:
            return metadata.get('full_text', '')

        return ""

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get indexing statistics.

        Returns:
            Statistics about indexed laws
        """
        db = SessionLocal()

        try:
            stats = {
                'total_laws': db.query(EULaw).count(),
                'laws_with_celex': db.query(EULaw).filter(EULaw.celex.isnot(None)).count(),
                'by_policy_area': {},
                'by_doc_type': {},
                'date_range': {}
            }

            # Group by policy area
            policy_counts = db.query(
                EULaw.policy_area,
                func.count(EULaw.id)
            ).group_by(EULaw.policy_area).all()

            stats['by_policy_area'] = {
                policy or 'Unclassified': count
                for policy, count in policy_counts
            }

            # Group by doc type
            doc_type_counts = db.query(
                EULaw.doc_type,
                func.count(EULaw.id)
            ).group_by(EULaw.doc_type).order_by(desc(func.count(EULaw.id))).limit(10).all()

            stats['by_doc_type'] = {
                doc_type: count
                for doc_type, count in doc_type_counts
            }

            # Date range
            date_stats = db.query(
                func.min(EULaw.date),
                func.max(EULaw.date)
            ).first()

            if date_stats[0] and date_stats[1]:
                stats['date_range'] = {
                    'earliest': date_stats[0].isoformat(),
                    'latest': date_stats[1].isoformat()
                }

            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return {}
        finally:
            db.close()


# Global singleton
_indexer: Optional[EULawIndexer] = None


def get_law_indexer() -> EULawIndexer:
    """Get global law indexer instance"""
    global _indexer
    if _indexer is None:
        _indexer = EULawIndexer()
    return _indexer
