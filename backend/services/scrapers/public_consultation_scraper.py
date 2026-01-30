"""
Public Consultation Scraper.

Scrapes EC "Have Your Say" public consultations portal.
Portal URL: https://ec.europa.eu/info/law/better-regulation/have-your-say

Features:
- Inherits from BaseScraper for rate limiting, caching, retries
- Fetches open, closed, and outcome-published consultations
- Extracts documents and related legislation

Created: January 2026
"""

import logging
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Callable

from services.scrapers.base_scraper import BaseScraper, ScraperError
from services.api_clients.have_your_say_client import (
    HaveYourSayClient,
    get_have_your_say_client,
)
from schemas.scrapers.public_consultation_schemas import (
    ScrapedConsultationItem,
    ScrapedConsultationDetail,
    ScrapeConsultationsResult,
    ScrapeAllConsultationsResult,
    ConsultationStatus,
    ConsultationType,
)
from knowledge_base.ec_consultations import (
    HAVE_YOUR_SAY_BASE_URL,
    calculate_relevance_score,
    PolicyArea,
)

logger = logging.getLogger(__name__)


class PublicConsultationScraper(BaseScraper):
    """
    Scraper for EC Have Your Say public consultations.

    Inherits from BaseScraper for:
    - Rate limiting (3.0s delay for EC sites)
    - Caching (6h TTL)
    - Retry logic (exponential backoff)
    - Statistics tracking
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url=HAVE_YOUR_SAY_BASE_URL,
            name="PublicConsultations",
            rate_limit_delay=3.0,  # EC sites need slower rate
            cache_ttl=21600,       # 6 hours
            timeout=30,
            max_retries=3,
            user_agent="Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)",
            use_coordinator=True,
            **kwargs
        )
        self._client = get_have_your_say_client()

    # =========================================================================
    # Required Abstract Method Implementations
    # =========================================================================

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search consultations by keyword.

        Args:
            query: Search query string
            **kwargs: Additional filters (status, policy_area, limit)

        Returns:
            List of matching consultations as dicts
        """
        status = kwargs.get('status')
        policy_area = kwargs.get('policy_area')
        limit = kwargs.get('limit', 50)

        try:
            items = await self._client.search_consultations(
                query=query,
                status=status,
                policy_area=policy_area,
                limit=limit
            )
            return [item.model_dump() for item in items]

        except Exception as e:
            logger.error(f"[ERROR] Search failed: {e}")
            return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get a specific consultation by initiative ID.

        Args:
            document_id: Initiative ID

        Returns:
            Consultation data as dict
        """
        # First, search for the consultation to get its URL
        # Then fetch details
        try:
            # Try to find in open consultations first
            open_items = await self.get_open_consultations(limit=100)
            for item in open_items:
                if item.initiative_id == document_id:
                    detail = await self._client.get_consultation_detail(
                        document_id,
                        item.portal_url
                    )
                    if detail:
                        return detail.model_dump()
                    return item.model_dump()

            # Try closed
            closed_items = await self.get_closed_consultations(limit=100)
            for item in closed_items:
                if item.initiative_id == document_id:
                    detail = await self._client.get_consultation_detail(
                        document_id,
                        item.portal_url
                    )
                    if detail:
                        return detail.model_dump()
                    return item.model_dump()

            return {}

        except Exception as e:
            logger.error(f"[ERROR] get_document failed for {document_id}: {e}")
            return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent consultations.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of recent consultations
        """
        try:
            items = await self.get_open_consultations(limit=limit)
            return [item.model_dump() for item in items]

        except Exception as e:
            logger.error(f"[ERROR] get_latest_updates failed: {e}")
            return []

    # =========================================================================
    # Consultation-Specific Methods
    # =========================================================================

    async def get_open_consultations(
        self,
        page: int = 0,
        limit: int = 20,
        max_pages: int = 5
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch currently open consultations.

        Args:
            page: Starting page (0-indexed)
            limit: Items per page
            max_pages: Maximum pages to fetch

        Returns:
            List of open consultation items
        """
        all_items = []

        for p in range(page, page + max_pages):
            try:
                items = await self._client.get_open_consultations(page=p, limit=limit)

                if not items:
                    break

                all_items.extend(items)

                # Stop if we got fewer items than limit (last page)
                if len(items) < limit:
                    break

            except Exception as e:
                logger.error(f"[ERROR] Failed to fetch open consultations page {p}: {e}")
                break

        logger.info(f"[OK] Fetched {len(all_items)} open consultations")
        return all_items

    async def get_closed_consultations(
        self,
        page: int = 0,
        limit: int = 20,
        max_pages: int = 5
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch closed consultations awaiting outcome.

        Args:
            page: Starting page
            limit: Items per page
            max_pages: Maximum pages to fetch

        Returns:
            List of closed consultation items
        """
        all_items = []

        for p in range(page, page + max_pages):
            try:
                items = await self._client.get_closed_consultations(page=p, limit=limit)

                if not items:
                    break

                all_items.extend(items)

                if len(items) < limit:
                    break

            except Exception as e:
                logger.error(f"[ERROR] Failed to fetch closed consultations page {p}: {e}")
                break

        logger.info(f"[OK] Fetched {len(all_items)} closed consultations")
        return all_items

    async def get_consultations_with_outcome(
        self,
        page: int = 0,
        limit: int = 20,
        max_pages: int = 3
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch consultations with published outcomes.

        Args:
            page: Starting page
            limit: Items per page
            max_pages: Maximum pages to fetch

        Returns:
            List of consultations with outcomes
        """
        all_items = []

        for p in range(page, page + max_pages):
            try:
                items = await self._client.get_consultations_with_outcome(page=p, limit=limit)

                if not items:
                    break

                all_items.extend(items)

                if len(items) < limit:
                    break

            except Exception as e:
                logger.error(f"[ERROR] Failed to fetch outcome consultations page {p}: {e}")
                break

        logger.info(f"[OK] Fetched {len(all_items)} consultations with outcomes")
        return all_items

    async def get_consultation_detail(
        self,
        initiative_id: str,
        portal_url: Optional[str] = None
    ) -> Optional[ScrapedConsultationDetail]:
        """
        Fetch full details for a consultation.

        Args:
            initiative_id: EC initiative ID
            portal_url: Optional direct URL

        Returns:
            Detailed consultation data
        """
        return await self._client.get_consultation_detail(initiative_id, portal_url)

    async def get_all_consultations(
        self,
        max_pages_per_status: int = 5,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch all consultations across all statuses.

        Args:
            max_pages_per_status: Max pages to fetch per status
            progress_callback: Optional callback(current, total, message)

        Returns:
            Combined list of all consultations
        """
        all_items = []
        total_steps = 3

        if progress_callback:
            progress_callback(1, total_steps, "Fetching open consultations...")

        open_items = await self.get_open_consultations(max_pages=max_pages_per_status)
        all_items.extend(open_items)

        if progress_callback:
            progress_callback(2, total_steps, "Fetching closed consultations...")

        closed_items = await self.get_closed_consultations(max_pages=max_pages_per_status)
        all_items.extend(closed_items)

        if progress_callback:
            progress_callback(3, total_steps, "Fetching consultations with outcomes...")

        outcome_items = await self.get_consultations_with_outcome(max_pages=max_pages_per_status)
        all_items.extend(outcome_items)

        logger.info(f"[OK] Total consultations fetched: {len(all_items)}")
        return all_items

    async def scrape_all_with_stats(
        self,
        max_pages_per_status: int = 5,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> ScrapeAllConsultationsResult:
        """
        Scrape all consultations and return detailed statistics.

        Args:
            max_pages_per_status: Max pages per status
            progress_callback: Optional progress callback

        Returns:
            ScrapeAllConsultationsResult with detailed statistics
        """
        start_time = datetime.now()
        results_by_status = {}

        # Open consultations
        open_start = datetime.now()
        if progress_callback:
            progress_callback(1, 3, "Scraping open consultations...")

        try:
            open_items = await self.get_open_consultations(max_pages=max_pages_per_status)
            open_result = ScrapeConsultationsResult(
                status=ConsultationStatus.OPEN,
                items_found=len(open_items),
                pages_scraped=max_pages_per_status,
                scraped_at=datetime.now(),
                duration_seconds=(datetime.now() - open_start).total_seconds()
            )
        except Exception as e:
            open_items = []
            open_result = ScrapeConsultationsResult(
                status=ConsultationStatus.OPEN,
                items_found=0,
                pages_scraped=0,
                errors=[str(e)],
                scraped_at=datetime.now(),
                duration_seconds=(datetime.now() - open_start).total_seconds()
            )

        results_by_status[ConsultationStatus.OPEN.value] = open_result

        # Closed consultations
        closed_start = datetime.now()
        if progress_callback:
            progress_callback(2, 3, "Scraping closed consultations...")

        try:
            closed_items = await self.get_closed_consultations(max_pages=max_pages_per_status)
            closed_result = ScrapeConsultationsResult(
                status=ConsultationStatus.CLOSED,
                items_found=len(closed_items),
                pages_scraped=max_pages_per_status,
                scraped_at=datetime.now(),
                duration_seconds=(datetime.now() - closed_start).total_seconds()
            )
        except Exception as e:
            closed_items = []
            closed_result = ScrapeConsultationsResult(
                status=ConsultationStatus.CLOSED,
                items_found=0,
                pages_scraped=0,
                errors=[str(e)],
                scraped_at=datetime.now(),
                duration_seconds=(datetime.now() - closed_start).total_seconds()
            )

        results_by_status[ConsultationStatus.CLOSED.value] = closed_result

        # Outcome consultations
        outcome_start = datetime.now()
        if progress_callback:
            progress_callback(3, 3, "Scraping outcome consultations...")

        try:
            outcome_items = await self.get_consultations_with_outcome(max_pages=max_pages_per_status)
            outcome_result = ScrapeConsultationsResult(
                status=ConsultationStatus.OUTCOME_PUBLISHED,
                items_found=len(outcome_items),
                pages_scraped=max_pages_per_status,
                scraped_at=datetime.now(),
                duration_seconds=(datetime.now() - outcome_start).total_seconds()
            )
        except Exception as e:
            outcome_items = []
            outcome_result = ScrapeConsultationsResult(
                status=ConsultationStatus.OUTCOME_PUBLISHED,
                items_found=0,
                pages_scraped=0,
                errors=[str(e)],
                scraped_at=datetime.now(),
                duration_seconds=(datetime.now() - outcome_start).total_seconds()
            )

        results_by_status[ConsultationStatus.OUTCOME_PUBLISHED.value] = outcome_result

        total_items = len(open_items) + len(closed_items) + len(outcome_items)

        return ScrapeAllConsultationsResult(
            total_items=total_items,
            open_count=len(open_items),
            closed_count=len(closed_items),
            outcome_count=len(outcome_items),
            results_by_status=results_by_status,
            scraped_at=datetime.now(),
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    async def get_consultations_closing_soon(
        self,
        days: int = 7
    ) -> List[ScrapedConsultationItem]:
        """
        Get consultations closing within specified days.

        Args:
            days: Number of days (default 7)

        Returns:
            List of consultations closing soon, sorted by deadline
        """
        open_items = await self.get_open_consultations(max_pages=10)

        today = date.today()
        closing_soon = []

        for item in open_items:
            if item.end_date:
                days_remaining = (item.end_date - today).days
                if 0 <= days_remaining <= days:
                    closing_soon.append(item)

        # Sort by deadline (earliest first)
        closing_soon.sort(key=lambda x: x.end_date or date.max)

        logger.info(f"[OK] Found {len(closing_soon)} consultations closing in {days} days")
        return closing_soon

    async def get_consultations_by_policy_area(
        self,
        policy_area: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[ScrapedConsultationItem]:
        """
        Get consultations filtered by policy area.

        Args:
            policy_area: Policy area code
            status: Optional status filter
            limit: Maximum items

        Returns:
            List of matching consultations
        """
        # Fetch all and filter
        if status == 'open':
            items = await self.get_open_consultations(max_pages=10)
        elif status == 'closed':
            items = await self.get_closed_consultations(max_pages=10)
        else:
            items = await self.get_all_consultations(max_pages_per_status=5)

        # Filter by policy area
        filtered = [
            item for item in items
            if policy_area.lower() in [p.lower() for p in item.policy_areas]
        ]

        return filtered[:limit]

    async def get_consultations_by_dg(
        self,
        dg_code: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[ScrapedConsultationItem]:
        """
        Get consultations by responsible DG.

        Args:
            dg_code: DG code (e.g., GROW, CNECT)
            status: Optional status filter
            limit: Maximum items

        Returns:
            List of matching consultations
        """
        if status == 'open':
            items = await self.get_open_consultations(max_pages=10)
        elif status == 'closed':
            items = await self.get_closed_consultations(max_pages=10)
        else:
            items = await self.get_all_consultations(max_pages_per_status=5)

        # Filter by DG
        filtered = [
            item for item in items
            if item.dg_responsible and item.dg_responsible.upper() == dg_code.upper()
        ]

        return filtered[:limit]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def calculate_relevance(self, item: ScrapedConsultationItem) -> int:
        """
        Calculate relevance score for a consultation.

        Args:
            item: Consultation item

        Returns:
            Score from 0-100
        """
        # Get primary policy area
        policy_area = PolicyArea.OTHER
        if item.policy_areas:
            try:
                policy_area = PolicyArea(item.policy_areas[0])
            except ValueError:
                pass

        # Calculate days remaining
        days_remaining = None
        if item.end_date:
            days_remaining = (item.end_date - date.today()).days

        return calculate_relevance_score(
            item.consultation_type,
            policy_area,
            days_remaining
        )


# Singleton instance
_scraper: Optional[PublicConsultationScraper] = None


def get_public_consultation_scraper() -> PublicConsultationScraper:
    """Get or create singleton scraper instance."""
    global _scraper
    if _scraper is None:
        _scraper = PublicConsultationScraper()
    return _scraper
