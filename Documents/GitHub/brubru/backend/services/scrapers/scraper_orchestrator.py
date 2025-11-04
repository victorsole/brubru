"""
Scraper Orchestrator

Coordinates all EU institutional scrapers, manages concurrent scraping,
and provides unified interface for data retrieval.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from .european_parliament_scraper import EuropeanParliamentScraper
from .european_commission_scraper import EuropeanCommissionScraper
from .council_scraper import CouncilScraper
from .eurlex_scraper import EURLexScraper
from .oeil_scraper import OEILScraper
from .legislative_train_scraper import LegislativeTrainScraper
from .law_tracker_scraper import LawTrackerScraper
from .who_is_who_scraper import WhoIsWhoScraper
from .assist_eu_scraper import AssistEUScraper
from .jrc_scraper import JRCScraper
from .think_tank_scraper import ThinkTankScraper
from .style_guide_scraper import StyleGuideScraper
from .iate_scraper import IATEScraper


class ScraperOrchestrator:
    """
    Orchestrates all EU institutional scrapers.

    Features:
    - Unified search across all sources
    - Parallel scraping with configurable concurrency
    - Aggregated results with source attribution
    - Centralized statistics and monitoring
    - Error handling and fallback strategies
    """

    def __init__(self, max_concurrent_scrapers: int = 5):
        """
        Initialize orchestrator with all scrapers.

        Args:
            max_concurrent_scrapers: Maximum number of scrapers to run in parallel
        """
        self.max_concurrent = max_concurrent_scrapers
        self.semaphore = asyncio.Semaphore(max_concurrent_scrapers)

        # Initialize all scrapers
        self.scrapers = {
            'european_parliament': EuropeanParliamentScraper(),
            'european_commission': EuropeanCommissionScraper(),
            'council': CouncilScraper(),
            'eurlex': EURLexScraper(),
            'oeil': OEILScraper(),
            'legislative_train': LegislativeTrainScraper(),
            'law_tracker': LawTrackerScraper(),
            'who_is_who': WhoIsWhoScraper(),
            'assist_eu': AssistEUScraper(),
            'jrc': JRCScraper(),
            'think_tank': ThinkTankScraper(),
            'style_guide': StyleGuideScraper(),
            'iate': IATEScraper(),
        }

    async def _scrape_with_semaphore(self, scraper_name: str, method: str, *args, **kwargs):
        """Execute scraper method with semaphore for concurrency control"""
        async with self.semaphore:
            try:
                scraper = self.scrapers[scraper_name]
                method_func = getattr(scraper, method)
                result = await method_func(*args, **kwargs)
                return {
                    'source': scraper_name,
                    'success': True,
                    'data': result,
                    'error': None
                }
            except Exception as e:
                return {
                    'source': scraper_name,
                    'success': False,
                    'data': None,
                    'error': str(e)
                }

    async def search_all_sources(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search across all (or selected) EU institutional sources.

        Args:
            query: Search query
            sources: List of source names to search (default: all)
            **kwargs: Additional search parameters

        Returns:
            Dictionary with results from each source
        """
        # Determine which sources to query
        target_sources = sources if sources else list(self.scrapers.keys())

        # Create search tasks for each source
        tasks = []
        for source in target_sources:
            if source in self.scrapers:
                task = self._scrape_with_semaphore(source, 'search', query, **kwargs)
                tasks.append(task)

        # Execute searches in parallel
        start_time = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        # Aggregate results
        aggregated = {
            'query': query,
            'total_sources': len(target_sources),
            'execution_time_ms': execution_time,
            'results': {}
        }

        for result in results:
            if isinstance(result, dict) and 'source' in result:
                aggregated['results'][result['source']] = result
            else:
                # Handle exceptions
                aggregated['results']['error'] = str(result)

        return aggregated

    async def get_document_from_source(
        self,
        source: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve document from specific source.

        Args:
            source: Source name (e.g., 'eurlex', 'oeil')
            document_id: Document identifier

        Returns:
            Document data

        Raises:
            ValueError: If source not found
        """
        if source not in self.scrapers:
            raise ValueError(f"Unknown source: {source}")

        return await self._scrape_with_semaphore(source, 'get_document', document_id)

    async def get_latest_updates_all(self, limit: int = 5) -> Dict[str, Any]:
        """
        Get latest updates from all sources.

        Args:
            limit: Number of updates per source

        Returns:
            Dictionary with latest updates from each source
        """
        tasks = []
        for source_name in self.scrapers.keys():
            task = self._scrape_with_semaphore(source_name, 'get_latest_updates', limit)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated = {
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }

        for result in results:
            if isinstance(result, dict) and 'source' in result:
                aggregated['sources'][result['source']] = result

        return aggregated

    async def search_meps(self, query: str, **kwargs) -> List[Any]:
        """Convenience method: Search MEPs"""
        scraper = self.scrapers['european_parliament']
        return await scraper.search_meps(query, **kwargs)

    async def get_legislation_by_celex(self, celex: str) -> Dict[str, Any]:
        """Convenience method: Get legislation by CELEX number"""
        scraper = self.scrapers['eurlex']
        doc = await scraper.get_document_by_celex(celex)
        return doc.dict()

    async def track_legislative_procedure(self, procedure_ref: str) -> Dict[str, Any]:
        """
        Track legislative procedure across multiple sources.

        Queries:
        - OEIL for procedure details
        - Legislative Train for visual timeline
        - Law Tracker for implementation status

        Args:
            procedure_ref: Procedure reference (e.g., '2021/0106(COD)')

        Returns:
            Comprehensive procedure information from multiple sources
        """
        tasks = [
            self._scrape_with_semaphore('oeil', 'get_procedure', procedure_ref),
            self._scrape_with_semaphore('legislative_train', 'get_procedure', procedure_ref),
            self._scrape_with_semaphore('law_tracker', 'get_procedure', procedure_ref),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            'procedure_reference': procedure_ref,
            'oeil_data': results[0] if len(results) > 0 else None,
            'legislative_train_data': results[1] if len(results) > 1 else None,
            'law_tracker_data': results[2] if len(results) > 2 else None,
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all scrapers"""
        stats = {}
        for name, scraper in self.scrapers.items():
            stats[name] = scraper.get_stats()

        return stats

    def clear_all_caches(self):
        """Clear cache for all scrapers"""
        for scraper in self.scrapers.values():
            scraper.clear_cache()
