"""
EPRS Sync Service

Syncs European Parliament Research Service publications from RSS feeds
to the PostgreSQL database. Optionally enriches with full PDF text
extraction and indexes into ChromaDB for semantic search.

EPRS data is chatbot-only -- the context builder queries this table
to inject plain-language explainers alongside EUR-Lex and OEIL data.

Usage:
    from services.scrapers.eprs_sync_service import EPRSSyncService

    sync = EPRSSyncService()
    result = await sync.sync_all(days=14)
    print(f"Added: {result['added']}, Updated: {result['updated']}")

CLI:
    python scripts/sync_eprs_publications.py --days 14
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.database import SessionLocal
from models.eprs_publication import EPRSPublication, EPRSPublicationTypeEnum
from services.scrapers.think_tank_scraper import ThinkTankScraper
from schemas.scrapers.scraper_schemas import (
    EPRSPublication as EPRSPublicationSchema,
    EPRSPublicationType,
)

logger = logging.getLogger(__name__)


# RSS publication type string to enum mapping
RSS_TYPE_TO_ENUM = {
    'at a glance': EPRSPublicationTypeEnum.AT_A_GLANCE,
    'at-a-glance': EPRSPublicationTypeEnum.AT_A_GLANCE,
    'briefing': EPRSPublicationTypeEnum.BRIEFING,
    'briefings': EPRSPublicationTypeEnum.BRIEFING,
    'in-depth analysis': EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS,
    'in depth analysis': EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS,
    'study': EPRSPublicationTypeEnum.STUDY,
    'studies': EPRSPublicationTypeEnum.STUDY,
    'blog post': EPRSPublicationTypeEnum.BLOG_POST,
}


def _detect_publication_type(
    categories: List[str],
    title: str = "",
    url: str = ""
) -> EPRSPublicationTypeEnum:
    """Detect publication type from RSS categories, title, or URL."""
    # Check categories first
    for cat in categories:
        cat_lower = cat.lower().strip()
        if cat_lower in RSS_TYPE_TO_ENUM:
            return RSS_TYPE_TO_ENUM[cat_lower]

    # Check URL patterns
    url_lower = url.lower()
    if '/ata/' in url_lower or 'at-a-glance' in url_lower:
        return EPRSPublicationTypeEnum.AT_A_GLANCE
    if '/bri/' in url_lower or '/briefing' in url_lower:
        return EPRSPublicationTypeEnum.BRIEFING
    if '/ida/' in url_lower or 'in-depth' in url_lower:
        return EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS
    if '/stu/' in url_lower or '/study' in url_lower or '/studies' in url_lower:
        return EPRSPublicationTypeEnum.STUDY

    # Check title patterns
    title_lower = title.lower()
    if 'at a glance' in title_lower:
        return EPRSPublicationTypeEnum.AT_A_GLANCE
    if 'in-depth analysis' in title_lower:
        return EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS

    return EPRSPublicationTypeEnum.OTHER


def _extract_publication_id(url: str, title: str = "") -> str:
    """
    Extract or generate a stable publication ID from URL.

    EPRS IDs follow pattern: EPRS_BRI(2024)762322
    URLs contain PE numbers in the path.
    """
    # Try to extract PE number from URL
    # Pattern: /RegData/etudes/BREF/2024/762322/
    pe_match = re.search(r'/(\d{6,})/', url)
    if pe_match:
        pe_number = pe_match.group(1)

        # Detect type code from URL
        type_codes = {
            '/ATAG/': 'ATA', '/BREF/': 'BRI', '/IDAN/': 'IDA',
            '/STUD/': 'STU', '/BRIE/': 'BRI',
        }
        type_code = 'BRI'  # default
        for path_segment, code in type_codes.items():
            if path_segment in url:
                type_code = code
                break

        # Extract year
        year_match = re.search(r'/(\d{4})/' + pe_number, url)
        year = year_match.group(1) if year_match else str(datetime.now().year)

        return f"EPRS_{type_code}({year}){pe_number}"

    # Try epthinktank.eu slug-based ID
    slug_match = re.search(r'epthinktank\.eu/\d{4}/\d{2}/\d{2}/(.+?)/?$', url)
    if slug_match:
        return f"EPRS_BLOG_{slug_match.group(1)[:60]}"

    # Fallback: hash of URL
    import hashlib
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"EPRS_UNK_{url_hash}"


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various date formats from RSS feeds."""
    if not date_str:
        return None

    formats = [
        '%a, %d %b %Y %H:%M:%S %z',   # RSS standard
        '%Y-%m-%dT%H:%M:%S%z',         # ISO 8601
        '%Y-%m-%dT%H:%M:%S',           # ISO without TZ
        '%Y-%m-%d %H:%M:%S',           # Simple datetime
        '%Y-%m-%d',                     # Date only
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

    return None


def _extract_celex_numbers(text: str) -> List[str]:
    """Extract CELEX numbers from text (e.g. 32024R1689)."""
    if not text:
        return []
    # CELEX pattern: digit + 4-digit year + letter + number
    pattern = r'\b([0-9][0-9]{4}[A-Z][0-9]{1,6})\b'
    return list(set(re.findall(pattern, text)))


def _extract_procedure_refs(text: str) -> List[str]:
    """Extract OEIL procedure references (e.g. 2021/0106(COD))."""
    if not text:
        return []
    pattern = r'\b(\d{4}/\d{3,4}\([A-Z]{3}\))\b'
    return list(set(re.findall(pattern, text)))


class EPRSSyncService:
    """
    Service to sync EPRS publications from RSS feeds to PostgreSQL.

    Pipeline:
    1. Fetch publications from ThinkTankScraper (RSS feeds)
    2. Detect publication type, extract IDs
    3. Upsert into eprs_publications table
    4. Optionally: download PDFs, extract text, index in ChromaDB
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        enable_pdf_extraction: bool = False
    ):
        """
        Initialize the sync service.

        Args:
            db: Optional database session
            enable_pdf_extraction: Download PDFs and extract full text
        """
        self.scraper = ThinkTankScraper(
            enable_full_extraction=enable_pdf_extraction
        )
        self.enable_pdf_extraction = enable_pdf_extraction
        self._db = db
        self._owns_db = db is None

    @property
    def db(self) -> Session:
        """Get or create database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    async def sync_all(
        self,
        days: int = 14,
        limit: int = 200,
        skip_existing: bool = True,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Sync all EPRS publication types from RSS feeds.

        Args:
            days: Fetch publications from last N days
            limit: Maximum publications to process per type
            skip_existing: Skip publications already in the database
            verbose: Print progress to stdout

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        logger.info(f"[START] EPRS sync: Fetching RSS feeds (last {days} days)...")
        if verbose:
            print(f"[START] EPRS sync: Fetching publications from last {days} days...")

        hours = days * 24
        stats = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': [],
            'by_type': {},
        }

        # Fetch all publication types
        publication_types = [
            ('briefings', self.scraper.get_briefings),
            ('at_a_glance', self.scraper.get_at_a_glance),
            ('in_depth_analysis', self.scraper.get_in_depth_analysis),
            ('studies', self.scraper.get_studies),
        ]

        all_publications = []

        for type_name, fetch_fn in publication_types:
            try:
                if verbose:
                    print(f"  [INFO] Fetching {type_name}...")

                pubs = await fetch_fn(hours=hours)
                pubs = pubs[:limit]

                if verbose:
                    print(f"  [OK] Found {len(pubs)} {type_name}")

                for pub in pubs:
                    pub['_source_type'] = type_name

                all_publications.extend(pubs)
                stats['by_type'][type_name] = len(pubs)

            except Exception as e:
                logger.error(f"Failed to fetch {type_name}: {str(e)}")
                stats['errors'] += 1
                stats['error_details'].append(f"Fetch {type_name}: {str(e)}")

        if verbose:
            print(f"  [INFO] Total publications fetched: {len(all_publications)}")

        # Also fetch the general feed to catch anything missed
        try:
            general_pubs = await self.scraper.rss_client.get_latest_publications(
                days=days
            )
            # Only add publications not already in the type-specific lists
            existing_links = {p.get('link', '') for p in all_publications}
            new_general = [
                p for p in general_pubs
                if p.get('link', '') not in existing_links
            ]
            if new_general:
                for pub in new_general:
                    pub['_source_type'] = 'general'
                all_publications.extend(new_general[:limit])
                stats['by_type']['general'] = len(new_general[:limit])

                if verbose:
                    print(f"  [OK] Found {len(new_general[:limit])} additional from general feed")

        except Exception as e:
            logger.warning(f"General feed fetch failed (non-fatal): {str(e)}")

        # Process and upsert each publication
        for pub_data in all_publications:
            try:
                result = self._upsert_publication(
                    pub_data,
                    skip_existing=skip_existing
                )

                if result == 'added':
                    stats['added'] += 1
                elif result == 'updated':
                    stats['updated'] += 1
                elif result == 'skipped':
                    stats['skipped'] += 1

            except Exception as e:
                stats['errors'] += 1
                title = pub_data.get('title', 'Unknown')[:50]
                stats['error_details'].append(f"{title}: {str(e)}")
                logger.error(f"Failed to upsert publication: {str(e)}")

        # Commit all changes
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to commit: {str(e)}")
            self.db.rollback()
            stats['errors'] += 1
            stats['error_details'].append(f"Commit failed: {str(e)}")

        logger.info(
            f"[OK] EPRS sync complete: "
            f"{stats['added']} added, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        if verbose:
            print(f"\n[OK] EPRS sync complete:")
            print(f"  Added:   {stats['added']}")
            print(f"  Updated: {stats['updated']}")
            print(f"  Skipped: {stats['skipped']}")
            print(f"  Errors:  {stats['errors']}")
            if stats['error_details']:
                print(f"\n  Error details:")
                for err in stats['error_details'][:10]:
                    print(f"    - {err}")

        return stats

    async def sync_with_enrichment(
        self,
        days: int = 7,
        limit: int = 20,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Sync publications with full PDF extraction and ChromaDB indexing.

        Slower but produces full-text content for semantic search.

        Args:
            days: Fetch publications from last N days
            limit: Maximum publications to process
            verbose: Print progress

        Returns:
            Summary dict
        """
        if not self.enable_pdf_extraction:
            raise ValueError(
                "PDF extraction not enabled. "
                "Initialize with enable_pdf_extraction=True"
            )

        logger.info(f"[START] EPRS enriched sync (last {days} days, limit {limit})")
        if verbose:
            print(f"[START] EPRS enriched sync (last {days} days, limit {limit})")

        stats = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'enriched': 0,
            'indexed': 0,
            'errors': 0,
            'error_details': [],
        }

        try:
            # Get enriched publications (with PDF extraction)
            enriched_results = await self.scraper.get_latest_publications_enriched(
                hours=days * 24,
                limit=limit
            )

            if verbose:
                print(f"  [OK] Enriched {len(enriched_results)} publications")

            for result in enriched_results:
                pub = result.publication
                try:
                    # Upsert with full text
                    upsert_result = self._upsert_enriched_publication(pub)

                    if upsert_result == 'added':
                        stats['added'] += 1
                        stats['enriched'] += 1
                    elif upsert_result == 'updated':
                        stats['updated'] += 1
                        stats['enriched'] += 1
                    elif upsert_result == 'skipped':
                        stats['skipped'] += 1

                    if verbose:
                        print(
                            f"  [{upsert_result.upper()}] {pub.title[:60]} "
                            f"({pub.word_count or 0} words)"
                        )

                except Exception as e:
                    stats['errors'] += 1
                    stats['error_details'].append(f"{pub.title[:40]}: {str(e)}")
                    logger.error(f"Failed to upsert enriched pub: {str(e)}")

            # Index into ChromaDB
            try:
                from services.indexing.eprs_indexer import get_eprs_indexer
                indexer = get_eprs_indexer()
                publications = [r.publication for r in enriched_results]
                index_result = await indexer.index_publications(publications)
                stats['indexed'] = index_result.get('success', 0)

                if verbose:
                    print(
                        f"  [OK] ChromaDB: indexed {stats['indexed']} publications, "
                        f"{index_result.get('total_chunks', 0)} chunks"
                    )

            except Exception as e:
                logger.warning(f"ChromaDB indexing failed (non-fatal): {str(e)}")
                if verbose:
                    print(f"  [WARN] ChromaDB indexing failed: {str(e)}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Enriched sync failed: {str(e)}")
            self.db.rollback()
            stats['errors'] += 1
            stats['error_details'].append(f"Enriched sync: {str(e)}")

        if verbose:
            print(f"\n[OK] Enriched sync complete:")
            print(f"  Added:    {stats['added']}")
            print(f"  Updated:  {stats['updated']}")
            print(f"  Enriched: {stats['enriched']}")
            print(f"  Indexed:  {stats['indexed']}")
            print(f"  Errors:   {stats['errors']}")

        return stats

    def _upsert_publication(
        self,
        pub_data: Dict[str, Any],
        skip_existing: bool = True
    ) -> str:
        """
        Upsert a single publication from RSS data.

        Args:
            pub_data: RSS entry dict with title, link, summary, categories, etc.
            skip_existing: Skip if already in database

        Returns:
            'added', 'updated', or 'skipped'
        """
        link = pub_data.get('link', '')
        title = pub_data.get('title', '')
        categories = pub_data.get('categories', [])
        summary = pub_data.get('summary', '')

        # Generate stable publication ID
        publication_id = _extract_publication_id(link, title)

        # Check if exists
        existing = self.db.query(EPRSPublication).filter(
            EPRSPublication.publication_id == publication_id
        ).first()

        if existing:
            if skip_existing:
                return 'skipped'

            # Update metadata
            existing.title = title
            existing.summary = summary or existing.summary
            existing.categories = categories or existing.categories
            existing.last_updated = datetime.now()
            return 'updated'

        # Detect type
        source_type = pub_data.get('_source_type', '')
        pub_type = _detect_publication_type(categories, title, link)

        # Override with source type if available
        source_type_map = {
            'briefings': EPRSPublicationTypeEnum.BRIEFING,
            'at_a_glance': EPRSPublicationTypeEnum.AT_A_GLANCE,
            'in_depth_analysis': EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS,
            'studies': EPRSPublicationTypeEnum.STUDY,
        }
        if source_type in source_type_map:
            pub_type = source_type_map[source_type]

        # Parse date
        pub_date = _parse_date(pub_data.get('published'))

        # Extract cross-references from summary text
        search_text = f"{title} {summary}"
        celex_numbers = _extract_celex_numbers(search_text)
        procedure_refs = _extract_procedure_refs(search_text)

        # Extract authors
        authors = []
        if pub_data.get('author'):
            if isinstance(pub_data['author'], str):
                authors = [pub_data['author']]
            elif isinstance(pub_data['author'], list):
                authors = pub_data['author']

        # Create new record
        new_pub = EPRSPublication(
            id=uuid.uuid4(),
            publication_id=publication_id,
            title=title,
            publication_type=pub_type.value,
            html_url=link,
            pdf_url=pub_data.get('pdf_url') or self._extract_pdf_url(pub_data),
            authors=authors,
            publication_date=pub_date,
            summary=summary[:2000] if summary else None,
            policy_areas=self._extract_policy_areas(categories),
            committees=self._extract_committees(categories),
            related_celex_numbers=celex_numbers,
            related_procedures=procedure_refs,
            categories=categories,
            has_full_text=False,
            first_seen=datetime.now(),
            last_updated=datetime.now(),
            scraped_at=datetime.now(),
        )

        self.db.add(new_pub)
        return 'added'

    def _upsert_enriched_publication(
        self,
        pub: EPRSPublicationSchema
    ) -> str:
        """
        Upsert an enriched publication (with full text from PDF).

        Args:
            pub: EPRSPublication Pydantic schema from ThinkTankScraper

        Returns:
            'added', 'updated', or 'skipped'
        """
        # Check if exists
        existing = self.db.query(EPRSPublication).filter(
            EPRSPublication.publication_id == pub.publication_id
        ).first()

        if existing:
            # Update with enriched data
            if pub.full_text and not existing.has_full_text:
                existing.full_text = pub.full_text
                existing.word_count = pub.word_count
                existing.page_count = pub.page_count
                existing.has_full_text = pub.has_full_text
                existing.extraction_quality = pub.extraction_quality
                existing.related_celex_numbers = (
                    pub.related_celex_numbers or existing.related_celex_numbers
                )
                existing.related_procedures = (
                    pub.related_procedures or existing.related_procedures
                )
                existing.last_updated = datetime.now()
                return 'updated'
            return 'skipped'

        # Map Pydantic type to SQLAlchemy enum
        type_map = {
            EPRSPublicationType.AT_A_GLANCE: EPRSPublicationTypeEnum.AT_A_GLANCE,
            EPRSPublicationType.BRIEFING: EPRSPublicationTypeEnum.BRIEFING,
            EPRSPublicationType.IN_DEPTH_ANALYSIS: EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS,
            EPRSPublicationType.STUDY: EPRSPublicationTypeEnum.STUDY,
            EPRSPublicationType.BLOG_POST: EPRSPublicationTypeEnum.BLOG_POST,
            EPRSPublicationType.OTHER: EPRSPublicationTypeEnum.OTHER,
        }
        pub_type = type_map.get(pub.publication_type, EPRSPublicationTypeEnum.OTHER)

        new_pub = EPRSPublication(
            id=uuid.uuid4(),
            publication_id=pub.publication_id,
            title=pub.title,
            publication_type=pub_type.value,
            html_url=str(pub.html_url) if pub.html_url else None,
            pdf_url=str(pub.pdf_url) if pub.pdf_url else None,
            authors=pub.authors or [],
            publication_date=pub.publication_date,
            summary=pub.summary,
            full_text=pub.full_text,
            word_count=pub.word_count,
            page_count=pub.page_count,
            policy_areas=pub.policy_areas or [],
            committees=pub.committees or [],
            related_celex_numbers=pub.related_celex_numbers or [],
            related_procedures=pub.related_procedures or [],
            categories=pub.categories or [],
            extraction_quality=pub.extraction_quality,
            has_full_text=pub.has_full_text,
            first_seen=datetime.now(),
            last_updated=datetime.now(),
            scraped_at=datetime.now(),
        )

        self.db.add(new_pub)
        return 'added'

    def _extract_pdf_url(self, pub_data: Dict[str, Any]) -> Optional[str]:
        """Try to extract PDF URL from RSS entry enclosures or links."""
        # Check enclosures
        enclosures = pub_data.get('enclosures', [])
        for enc in enclosures:
            if isinstance(enc, dict) and 'href' in enc:
                if enc['href'].endswith('.pdf'):
                    return enc['href']
            elif isinstance(enc, str) and enc.endswith('.pdf'):
                return enc

        # Check links
        links = pub_data.get('links', [])
        for link in links:
            if isinstance(link, dict):
                href = link.get('href', '')
                if href.endswith('.pdf'):
                    return href

        return None

    def _extract_policy_areas(self, categories: List[str]) -> List[str]:
        """Extract policy area tags from RSS categories."""
        policy_keywords = {
            'digital', 'environment', 'transport', 'energy', 'health',
            'agriculture', 'trade', 'security', 'defence', 'migration',
            'economy', 'finance', 'internal market', 'competition',
            'education', 'culture', 'fisheries', 'regional', 'social',
            'foreign affairs', 'justice', 'consumer', 'industry',
            'research', 'space', 'climate', 'biodiversity',
        }

        areas = []
        for cat in categories:
            cat_lower = cat.lower()
            for keyword in policy_keywords:
                if keyword in cat_lower:
                    areas.append(cat)
                    break

        return areas

    def _extract_committees(self, categories: List[str]) -> List[str]:
        """Extract EP committee codes from RSS categories."""
        committee_codes = {
            'AFET', 'DEVE', 'INTA', 'BUDG', 'CONT', 'ECON', 'EMPL',
            'ENVI', 'ITRE', 'IMCO', 'TRAN', 'REGI', 'AGRI', 'PECH',
            'CULT', 'JURI', 'LIBE', 'AFCO', 'FEMM', 'PETI', 'DROI',
            'SEDE', 'FISC', 'BECA', 'AIDA', 'COVI', 'INGE',
        }

        committees = []
        for cat in categories:
            cat_upper = cat.upper().strip()
            if cat_upper in committee_codes:
                committees.append(cat_upper)

        return committees

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics for EPRS publications."""
        from sqlalchemy import func

        total = self.db.query(func.count(EPRSPublication.id)).scalar() or 0
        with_text = self.db.query(func.count(EPRSPublication.id)).filter(
            EPRSPublication.has_full_text == True
        ).scalar() or 0

        by_type = {}
        type_counts = self.db.query(
            EPRSPublication.publication_type,
            func.count(EPRSPublication.id)
        ).group_by(EPRSPublication.publication_type).all()
        for pub_type, count in type_counts:
            by_type[pub_type] = count

        return {
            'total': total,
            'with_full_text': with_text,
            'without_full_text': total - with_text,
            'by_type': by_type,
        }

    async def close(self):
        """Close connections."""
        await self.scraper.close()
        if self._owns_db and self._db:
            self._db.close()
