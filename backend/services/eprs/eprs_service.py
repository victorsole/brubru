"""
EPRS Unified Service

Coordinates all EPRS (European Parliament Research Service) components:
- RSS feeds (new publications)
- CELLAR/SPARQL (historical archive)
- PDF extraction and enrichment
- Vector database indexing
- Explainer matching for legislation
- "EU Legislation in Progress" curated list

This is the single entry point for all EPRS functionality in Brubru.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from services.scrapers.think_tank_scraper import ThinkTankScraper
from services.api_clients.eprs_archive_client import EPRSArchiveClient, EPRSPublicationType
from services.indexing.eprs_indexer import EPRSIndexer, get_eprs_indexer
from services.matching.eprs_matcher import EPRSMatcher, get_eprs_matcher
from schemas.scrapers.scraper_schemas import EPRSPublication

logger = logging.getLogger(__name__)


class EPRSService:
    """
    Unified EPRS Service - coordinates all EPRS components.

    Architecture:
    ```
    Data Sources          Processing           Consumption
    ════════════          ══════════           ═══════════

    ThinkTankScraper ─┐
      (RSS + PDF)     │
                      ├──→ EPRSIndexer ──→ EPRSMatcher
    EPRSArchiveClient ┤    (ChromaDB)       (Find explainers)
      (CELLAR)        │
                      │
    LegislationIn ────┘
      Progress
      (Curated list)
    ```

    Usage:
        service = EPRSService()

        # Find explainers for legislation
        result = await service.find_explainers(
            procedure_ref="2021/0106(COD)",
            celex="32024R1689"
        )

        # Index recent publications
        stats = await service.index_recent_publications(days=7)

        # Get curated legislation in progress
        procedures = await service.get_legislation_in_progress()

        # Search EPRS publications
        results = await service.search("artificial intelligence regulation")
    """

    def __init__(
        self,
        enable_pdf_extraction: bool = True,
        cache_ttl_seconds: int = 3600
    ):
        """
        Initialize unified EPRS service.

        Args:
            enable_pdf_extraction: Enable PDF download and text extraction
            cache_ttl_seconds: Cache TTL for matcher results
        """
        # Initialize components
        self.scraper = ThinkTankScraper(enable_full_extraction=enable_pdf_extraction)
        self.archive_client = EPRSArchiveClient()
        self.indexer = get_eprs_indexer()
        self.matcher = get_eprs_matcher()

        # Lazy-load legislation in progress scraper
        self._lip_scraper = None

        self._cache_ttl = cache_ttl_seconds

        logger.info(
            "Initialized EPRSService "
            f"(pdf_extraction={enable_pdf_extraction})"
        )

    @property
    def legislation_in_progress_scraper(self):
        """Lazy-load the LegislationInProgressScraper."""
        if self._lip_scraper is None:
            from .legislation_in_progress_scraper import LegislationInProgressScraper
            self._lip_scraper = LegislationInProgressScraper()
        return self._lip_scraper

    # =========================================================================
    # EXPLAINER MATCHING (Primary use case)
    # =========================================================================

    async def find_explainers(
        self,
        procedure_ref: Optional[str] = None,
        celex: Optional[str] = None,
        title: Optional[str] = None,
        max_results: int = 3
    ) -> Dict[str, Any]:
        """
        Find EPRS explainer briefings for legislation.

        This is the primary method for the Legislative Train enricher.
        Searches for EPRS publications that explain the given legislation.

        Args:
            procedure_ref: OEIL procedure reference (e.g., "2021/0106(COD)")
            celex: CELEX number (e.g., "32024R1689")
            title: Legislation title for semantic matching
            max_results: Maximum explainers to return

        Returns:
            Dict with:
                - explainers: List of matching EPRS briefings
                - match_strategy: How matches were found
                - confidence: Match confidence (0-1)

        Example:
            result = await service.find_explainers(
                procedure_ref="2021/0106(COD)",
                celex="32024R1689",
                title="Artificial Intelligence Act"
            )
            # result['explainers'] contains EPRS briefings about AI Act
        """
        logger.info(
            f"Finding EPRS explainers "
            f"(procedure={procedure_ref}, celex={celex})"
        )

        return await self.matcher.auto_match_legislation(
            celex=celex,
            procedure_ref=procedure_ref,
            title=title,
            max_results=max_results
        )

    async def find_explainers_for_procedure(
        self,
        procedure_ref: str,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find EPRS explainers for a specific procedure.

        Args:
            procedure_ref: Procedure reference (e.g., "2021/0106(COD)")
            max_results: Maximum results

        Returns:
            List of matching EPRS briefings
        """
        return await self.matcher.find_explainers_for_procedure(
            procedure_ref=procedure_ref,
            max_results=max_results,
            prefer_at_a_glance=True
        )

    async def find_explainers_for_celex(
        self,
        celex: str,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find EPRS explainers for a specific CELEX number.

        Args:
            celex: CELEX number (e.g., "32024R1689")
            max_results: Maximum results

        Returns:
            List of matching EPRS briefings
        """
        return await self.matcher.find_explainers_for_celex(
            celex=celex,
            max_results=max_results
        )

    # =========================================================================
    # SEARCH
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        publication_type: Optional[str] = None,
        policy_area: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search EPRS publications.

        Searches the indexed vector database for relevant publications.

        Args:
            query: Search query
            limit: Maximum results
            publication_type: Filter by type (briefing, study, at_a_glance, etc.)
            policy_area: Filter by policy area

        Returns:
            List of matching publications with text and metadata
        """
        filters = {}
        if publication_type:
            filters['publication_type'] = publication_type
        if policy_area:
            filters['policy_areas'] = policy_area

        return await self.indexer.search(
            query=query,
            limit=limit,
            filters=filters if filters else None
        )

    # =========================================================================
    # INDEXING
    # =========================================================================

    async def index_recent_publications(
        self,
        days: int = 7,
        publication_type: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Fetch and index recent EPRS publications.

        Gets publications from RSS feeds, extracts PDF content,
        and indexes them into the vector database.

        Args:
            days: Fetch publications from last N days
            publication_type: Filter by type (briefings, studies, etc.)
            limit: Maximum publications to process

        Returns:
            Indexing statistics
        """
        logger.info(
            f"Indexing recent EPRS publications "
            f"(days={days}, type={publication_type}, limit={limit})"
        )

        try:
            # Fetch and enrich publications from RSS
            enriched_results = await self.scraper.get_latest_publications_enriched(
                hours=days * 24,
                limit=limit,
                publication_type=publication_type
            )

            if not enriched_results:
                return {
                    'success': True,
                    'publications_fetched': 0,
                    'publications_indexed': 0,
                    'total_chunks': 0,
                    'errors': []
                }

            # Extract publications from results
            publications = [r.publication for r in enriched_results]

            # Index into vector database
            index_result = await self.indexer.index_publications(publications)

            return {
                'success': True,
                'publications_fetched': len(enriched_results),
                'publications_indexed': index_result['success'],
                'total_chunks': index_result['total_chunks'],
                'skipped': index_result['skipped'],
                'errors': index_result['errors']
            }

        except Exception as e:
            logger.error(f"Failed to index recent publications: {str(e)}")
            return {
                'success': False,
                'publications_fetched': 0,
                'publications_indexed': 0,
                'total_chunks': 0,
                'errors': [str(e)]
            }

    async def index_from_archive(
        self,
        year_from: int,
        year_to: Optional[int] = None,
        publication_type: Optional[EPRSPublicationType] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Index EPRS publications from CELLAR archive.

        Uses SPARQL queries to fetch historical publications
        and indexes them into the vector database.

        Args:
            year_from: Start year (e.g., 2020)
            year_to: End year (defaults to current year)
            publication_type: Filter by type
            limit: Maximum publications to fetch

        Returns:
            Indexing statistics
        """
        year_to = year_to or datetime.now().year

        logger.info(
            f"Indexing EPRS archive "
            f"(years={year_from}-{year_to}, type={publication_type}, limit={limit})"
        )

        try:
            # Fetch from CELLAR
            archive_pubs = await self.archive_client.get_eprs_publications(
                year_from=year_from,
                year_to=year_to,
                publication_type=publication_type,
                limit=limit
            )

            if not archive_pubs:
                return {
                    'success': True,
                    'publications_fetched': 0,
                    'publications_indexed': 0,
                    'message': 'No publications found in archive'
                }

            # Convert archive format to EPRSPublication objects
            # Note: Archive publications may need PDF download for full content
            indexed_count = 0
            errors = []

            for pub_data in archive_pubs:
                try:
                    # If publication has a URL, try to enrich it
                    if pub_data.get('url'):
                        result = await self.scraper.get_publication_with_full_content(
                            publication_url=pub_data.get('url'),
                            title=pub_data.get('title')
                        )

                        # Index the enriched publication
                        index_result = await self.indexer.index_publication(
                            result.publication
                        )

                        if index_result['success']:
                            indexed_count += 1
                        else:
                            errors.extend(index_result['errors'])

                except Exception as e:
                    errors.append(f"Failed to process {pub_data.get('title', 'unknown')}: {str(e)}")
                    continue

            return {
                'success': True,
                'publications_fetched': len(archive_pubs),
                'publications_indexed': indexed_count,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Failed to index from archive: {str(e)}")
            return {
                'success': False,
                'publications_fetched': 0,
                'publications_indexed': 0,
                'errors': [str(e)]
            }

    # =========================================================================
    # LEGISLATION IN PROGRESS
    # =========================================================================

    async def get_legislation_in_progress(
        self,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get curated "EU Legislation in Progress" procedures.

        Scrapes epthinktank.eu for the curated list of ~181 active
        legislative procedures with EPRS coverage.

        Args:
            force_refresh: Force re-scrape even if cached

        Returns:
            List of procedure references with metadata:
                - procedure_ref: "2021/0106(COD)"
                - title: Procedure title
                - eprs_url: Link to EPRS coverage
                - policy_area: Policy area if available
        """
        return await self.legislation_in_progress_scraper.get_procedures(
            force_refresh=force_refresh
        )

    async def get_legislation_in_progress_by_policy_area(
        self,
        policy_area: str
    ) -> List[Dict[str, Any]]:
        """
        Get legislation in progress filtered by policy area.

        Args:
            policy_area: Policy area to filter by

        Returns:
            Filtered list of procedures
        """
        return await self.legislation_in_progress_scraper.get_procedures_by_policy_area(
            policy_area=policy_area
        )

    async def sync_legislation_in_progress(self) -> Dict[str, Any]:
        """
        Sync "EU Legislation in Progress" with the database.

        Fetches the curated list and creates/updates carriages
        in the legislative_carriages table with source='oeil_direct'.

        Returns:
            Sync statistics
        """
        return await self.legislation_in_progress_scraper.sync_to_database()

    # =========================================================================
    # PUBLICATION FEEDS
    # =========================================================================

    async def get_latest_briefings(
        self,
        days: int = 14
    ) -> List[Dict[str, Any]]:
        """Get latest EPRS briefings."""
        return await self.scraper.get_briefings(hours=days * 24)

    async def get_latest_at_a_glance(
        self,
        days: int = 14
    ) -> List[Dict[str, Any]]:
        """Get latest 'At a Glance' summaries."""
        return await self.scraper.get_at_a_glance(hours=days * 24)

    async def get_latest_studies(
        self,
        days: int = 60
    ) -> List[Dict[str, Any]]:
        """Get latest EP studies."""
        return await self.scraper.get_studies(hours=days * 24)

    async def get_latest_in_depth_analysis(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get latest in-depth analysis documents."""
        return await self.scraper.get_in_depth_analysis(hours=days * 24)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about indexed EPRS publications.

        Returns:
            Statistics including total chunks, unique publications, etc.
        """
        return self.indexer.get_stats()

    async def get_archive_stats(
        self,
        year_from: int = 2009
    ) -> Dict[str, Any]:
        """
        Get statistics about EPRS publications in CELLAR archive.

        Args:
            year_from: Count from this year

        Returns:
            Archive statistics
        """
        count = await self.archive_client.count_eprs_publications(
            year_from=year_from
        )

        years = await self.archive_client.get_eprs_publication_years()

        return {
            'total_publications': count,
            'years_available': years,
            'earliest_year': min(years) if years else None,
            'latest_year': max(years) if years else None
        }

    # =========================================================================
    # CLEANUP
    # =========================================================================

    async def close(self):
        """Close all client connections."""
        await self.scraper.close()
        await self.archive_client.close()
        if self._lip_scraper:
            await self._lip_scraper.close()
        logger.info("Closed EPRSService connections")

    def clear_cache(self):
        """Clear all caches."""
        self.matcher.clear_cache()
        if self._lip_scraper:
            self._lip_scraper.clear_cache()
        logger.info("Cleared EPRSService caches")


# Global singleton
_eprs_service: Optional[EPRSService] = None


def get_eprs_service(
    enable_pdf_extraction: bool = True
) -> EPRSService:
    """
    Get global EPRS service instance.

    Args:
        enable_pdf_extraction: Enable PDF download and extraction

    Returns:
        EPRSService instance
    """
    global _eprs_service

    if _eprs_service is None:
        _eprs_service = EPRSService(
            enable_pdf_extraction=enable_pdf_extraction
        )

    return _eprs_service
