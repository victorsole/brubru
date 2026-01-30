"""
EP Committee Work In Progress Scraper.

Scrapes work-in-progress data from all 26 European Parliament committees.

URL Pattern:
https://www.europarl.europa.eu/committees/en/{code}/documents/work-in-progress?term=10&page={n}

Special case: TRAN committee uses different URL format (missing code in path).

Created: January 2026
"""

import asyncio
import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from bs4 import BeautifulSoup

from services.scrapers.base_scraper import BaseScraper, ScraperError
from schemas.scrapers.committee_work_schemas import (
    ScrapedCommitteeWorkItem,
    ScrapedCommitteeWorkDetail,
    ProcedureType,
    CommitteeRole,
    ScrapeResult,
    ScrapeAllResult,
)
from knowledge_base.ep_committees import (
    EP_COMMITTEES,
    EP_COMMITTEE_CODES,
    get_committee_url,
)

logger = logging.getLogger(__name__)


class CommitteeWorkInProgressScraper(BaseScraper):
    """
    Scraper for EP Committee 'Work in Progress' pages.

    Inherits from BaseScraper for:
    - Rate limiting (2.0s delay)
    - Caching (24h TTL)
    - Retry logic (exponential backoff)
    - Statistics tracking
    """

    # Procedure type to relevance score mapping
    RELEVANCE_SCORES = {
        ProcedureType.COD: 100,  # Ordinary legislative procedure
        ProcedureType.APP: 80,   # Consent procedure
        ProcedureType.CNS: 70,   # Consultation procedure
        ProcedureType.NLE: 50,   # Non-legislative
        ProcedureType.INI: 40,   # Own-initiative
    }

    # Regex patterns
    PROCEDURE_REF_PATTERN = re.compile(r'\d{4}/\d{4}\([A-Z]{3,4}\)')
    PROCEDURE_TYPE_PATTERN = re.compile(r'\(([A-Z]{3,4})\)')
    MEP_ID_PATTERN = re.compile(r'/meps/en/(\d+)')

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://www.europarl.europa.eu",
            name="EPCommitteeWork",
            rate_limit_delay=2.0,  # Match EP scraper pattern
            cache_ttl=86400,       # 24 hours
            timeout=30,
            max_retries=3,
            user_agent="Brubru/1.0 (EU Policy Assistant; https://brubru.beresol.eu)",
            **kwargs
        )

    # =========================================================================
    # Required Abstract Method Implementations
    # =========================================================================

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search committee work items by keyword.

        Args:
            query: Search query string
            **kwargs: Additional filters (committee_code, procedure_type, etc.)

        Returns:
            List of matching work items as dicts
        """
        committee_code = kwargs.get('committee_code')
        procedure_types = kwargs.get('procedure_types', [])
        limit = kwargs.get('limit', 50)

        results = []

        # If specific committee, search only that one
        if committee_code:
            committees_to_search = [committee_code.upper()]
        else:
            # Search all committees (limited to first page each for performance)
            committees_to_search = EP_COMMITTEE_CODES

        for code in committees_to_search:
            try:
                items = await self.scrape_committee(code, max_pages=1)

                # Filter by query
                query_lower = query.lower()
                for item in items:
                    if query_lower in item.title.lower():
                        # Filter by procedure type if specified
                        if procedure_types and item.procedure_type not in procedure_types:
                            continue
                        results.append(item.model_dump())

                        if len(results) >= limit:
                            return results

            except Exception as e:
                logger.warning(f"Error searching {code}: {str(e)}")
                continue

        return results

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get a specific work item by procedure reference.

        Args:
            document_id: Procedure reference (e.g., "2025/0580(CNS)")

        Returns:
            Work item details as dict
        """
        # Search across all committees for this procedure
        for code in EP_COMMITTEE_CODES:
            try:
                items = await self.scrape_committee(code, max_pages=3)

                for item in items:
                    if item.procedure_ref == document_id:
                        return item.model_dump()

            except Exception as e:
                logger.debug(f"Error checking {code}: {str(e)}")
                continue

        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent work items across all committees.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of recent work items
        """
        all_items = []

        # Fetch first page from each committee
        for code in EP_COMMITTEE_CODES:
            try:
                items = await self.scrape_committee(code, max_pages=1)
                all_items.extend(items)
            except Exception as e:
                logger.warning(f"Error fetching latest from {code}: {str(e)}")
                continue

        # Sort by scraped_at (most recent first)
        all_items.sort(key=lambda x: x.scraped_at, reverse=True)

        # Return as dicts
        return [item.model_dump() for item in all_items[:limit]]

    # =========================================================================
    # Committee-Specific Scraping Methods
    # =========================================================================

    async def scrape_committee(
        self,
        committee_code: str,
        max_pages: int = 10,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[ScrapedCommitteeWorkItem]:
        """
        Scrape all work items from a single committee.

        Args:
            committee_code: Committee code (e.g., "AFET", "LIBE")
            max_pages: Maximum pages to scrape (default: 10)
            progress_callback: Optional callback(current, total, message)

        Returns:
            List of scraped work items
        """
        committee_code = committee_code.upper()

        if committee_code not in EP_COMMITTEE_CODES:
            raise ValueError(f"Invalid committee code: {committee_code}")

        items = []
        page = 0

        while page < max_pages:
            try:
                url = get_committee_url(committee_code, page=page)

                if progress_callback:
                    progress_callback(
                        page + 1,
                        max_pages,
                        f"Scraping {committee_code} page {page + 1}"
                    )

                html = await self._fetch(url, use_cache=True)
                page_items = self._parse_work_list_page(html, committee_code, url)

                if not page_items:
                    # No more items, stop pagination
                    break

                items.extend(page_items)
                page += 1

                # Check if there's a next page
                if not self._has_next_page(html):
                    break

            except Exception as e:
                logger.error(f"Error scraping {committee_code} page {page}: {str(e)}")
                break

        logger.info(f"[OK] Scraped {len(items)} items from {committee_code}")
        return items

    async def scrape_all_committees(
        self,
        max_pages_per_committee: int = 5,
        committees: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[ScrapedCommitteeWorkItem]:
        """
        Scrape work items from all 26 committees.

        Args:
            max_pages_per_committee: Max pages per committee (default: 5)
            committees: Optional list of specific committee codes to scrape
            progress_callback: Optional callback(current, total, message)

        Returns:
            List of all scraped work items
        """
        committees_to_scrape = committees or EP_COMMITTEE_CODES
        all_items = []
        total = len(committees_to_scrape)

        for i, code in enumerate(committees_to_scrape):
            if progress_callback:
                progress_callback(i + 1, total, f"Scraping {code}...")

            try:
                items = await self.scrape_committee(
                    code,
                    max_pages=max_pages_per_committee
                )
                all_items.extend(items)

            except Exception as e:
                logger.error(f"[ERROR] Failed to scrape {code}: {str(e)}")
                continue

        logger.info(f"[OK] Total items scraped: {len(all_items)} from {total} committees")
        return all_items

    async def scrape_all_with_stats(
        self,
        max_pages_per_committee: int = 5,
        committees: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> ScrapeAllResult:
        """
        Scrape all committees and return detailed statistics.

        Args:
            max_pages_per_committee: Max pages per committee
            committees: Optional list of specific committee codes
            progress_callback: Optional progress callback

        Returns:
            ScrapeAllResult with detailed statistics
        """
        start_time = datetime.now()
        committees_to_scrape = committees or EP_COMMITTEE_CODES

        all_items = []
        results_by_committee = []
        committees_failed = []

        for i, code in enumerate(committees_to_scrape):
            if progress_callback:
                progress_callback(
                    i + 1,
                    len(committees_to_scrape),
                    f"Scraping {code}..."
                )

            committee_start = datetime.now()
            errors = []

            try:
                items = await self.scrape_committee(
                    code,
                    max_pages=max_pages_per_committee
                )
                all_items.extend(items)

                results_by_committee.append(ScrapeResult(
                    committee_code=code,
                    items_found=len(items),
                    pages_scraped=min(max_pages_per_committee, (len(items) // 20) + 1),
                    errors=errors,
                    scraped_at=datetime.now(),
                    duration_seconds=(datetime.now() - committee_start).total_seconds()
                ))

            except Exception as e:
                logger.error(f"[ERROR] Failed to scrape {code}: {str(e)}")
                committees_failed.append(code)
                errors.append(str(e))

                results_by_committee.append(ScrapeResult(
                    committee_code=code,
                    items_found=0,
                    pages_scraped=0,
                    errors=errors,
                    scraped_at=datetime.now(),
                    duration_seconds=(datetime.now() - committee_start).total_seconds()
                ))

        return ScrapeAllResult(
            total_items=len(all_items),
            committees_scraped=len(committees_to_scrape) - len(committees_failed),
            committees_failed=committees_failed,
            results_by_committee=results_by_committee,
            scraped_at=datetime.now(),
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )

    # =========================================================================
    # HTML Parsing Methods
    # =========================================================================

    def _parse_work_list_page(
        self,
        html: str,
        committee_code: str,
        source_url: str
    ) -> List[ScrapedCommitteeWorkItem]:
        """Parse a work-in-progress list page and extract items."""
        soup = BeautifulSoup(html, 'lxml')
        items = []

        # Find all procedure entries
        # The EP website typically uses specific class patterns for list items
        entries = soup.select('.erpl_document, .ep-result, .ep_content-list-item, [data-procedure]')

        if not entries:
            # Try alternative selectors
            entries = soup.select('.ep_content-list li, .erpl_product')

        if not entries:
            # Last resort: look for any element with procedure reference pattern
            entries = self._find_procedure_elements(soup)

        for entry in entries:
            try:
                item = self._parse_work_item(entry, committee_code, source_url)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing entry: {str(e)}")
                continue

        return items

    def _find_procedure_elements(self, soup: BeautifulSoup) -> List:
        """Find elements containing procedure references as fallback."""
        elements = []
        text_content = soup.get_text()

        # Find all procedure references in page
        refs = self.PROCEDURE_REF_PATTERN.findall(text_content)

        if refs:
            # Get parent elements for each reference
            for ref in refs:
                element = soup.find(string=re.compile(re.escape(ref)))
                if element:
                    parent = element.find_parent(['div', 'li', 'article', 'section'])
                    if parent and parent not in elements:
                        elements.append(parent)

        return elements

    def _parse_work_item(
        self,
        element,
        committee_code: str,
        source_url: str
    ) -> Optional[ScrapedCommitteeWorkItem]:
        """Parse a single work item element."""
        text_content = element.get_text(separator=' ', strip=True)

        # Extract procedure reference
        ref_match = self.PROCEDURE_REF_PATTERN.search(text_content)
        if not ref_match:
            return None

        procedure_ref = ref_match.group(0)

        # Extract procedure type
        procedure_type = self._extract_procedure_type(procedure_ref)

        # Extract title (usually in a heading or link)
        title = self._extract_title(element, procedure_ref)
        if not title:
            return None

        # Extract rapporteur
        rapporteur_name, rapporteur_mep_id = self._extract_rapporteur(element)

        # Extract status
        status = self._extract_status(element)

        # Extract committee role
        committee_role = self._extract_committee_role(element, text_content)

        # Extract URLs
        oeil_url = self._extract_oeil_url(element)
        ep_page_url = self._extract_ep_page_url(element)

        return ScrapedCommitteeWorkItem(
            procedure_ref=procedure_ref,
            committee_code=committee_code,
            title=title,
            procedure_type=procedure_type,
            committee_role=committee_role,
            rapporteur_name=rapporteur_name,
            rapporteur_mep_id=rapporteur_mep_id,
            status=status,
            oeil_url=oeil_url,
            ep_page_url=ep_page_url,
            source_url=source_url,
            scraped_at=datetime.now()
        )

    def _extract_procedure_type(self, procedure_ref: str) -> ProcedureType:
        """Extract procedure type from reference string."""
        match = self.PROCEDURE_TYPE_PATTERN.search(procedure_ref)
        if match:
            type_str = match.group(1)
            try:
                return ProcedureType(type_str)
            except ValueError:
                pass
        return ProcedureType.INI  # Default to lowest relevance

    def _extract_title(self, element, procedure_ref: str) -> Optional[str]:
        """Extract title from element."""
        # Try common title selectors
        title_selectors = [
            'h2', 'h3', 'h4',
            '.erpl_document-title',
            '.ep_title',
            'a[href*="oeil"]',
            '.procedure-title',
        ]

        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                # Clean up title (remove procedure ref if included)
                title = title.replace(procedure_ref, '').strip()
                if title and len(title) > 5:
                    return title

        # Fallback: get all text and clean it
        full_text = element.get_text(separator=' ', strip=True)
        # Remove procedure ref and common labels
        title = full_text.replace(procedure_ref, '')
        title = re.sub(r'(Rapporteur|Shadow|Committee|Lead|Opinion)[:]*', '', title)
        title = ' '.join(title.split())[:200]  # Limit length

        return title if len(title) > 5 else None

    def _extract_rapporteur(self, element) -> tuple:
        """Extract rapporteur name and MEP ID."""
        name = None
        mep_id = None

        # Look for MEP link
        mep_link = element.select_one('a[href*="/meps/"]')
        if mep_link:
            name = mep_link.get_text(strip=True)
            href = mep_link.get('href', '')
            id_match = self.MEP_ID_PATTERN.search(href)
            if id_match:
                mep_id = id_match.group(1)
            return name, mep_id

        # Look for rapporteur label
        text = element.get_text()
        rapp_match = re.search(r'Rapporteur[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        if rapp_match:
            name = rapp_match.group(1).strip()

        return name, mep_id

    def _extract_status(self, element) -> Optional[str]:
        """Extract status from element."""
        # Common status patterns
        status_selectors = [
            '.erpl_badge',
            '.ep_status',
            '.status',
            '[data-status]',
        ]

        for selector in status_selectors:
            status_elem = element.select_one(selector)
            if status_elem:
                return status_elem.get_text(strip=True)

        # Look for status keywords in text
        text = element.get_text().lower()
        status_keywords = [
            'in committee', 'awaiting', 'adopted', 'rejected',
            'withdrawn', 'pending', 'completed', 'tabled'
        ]

        for keyword in status_keywords:
            if keyword in text:
                return keyword.title()

        return None

    def _extract_committee_role(self, element, text: str) -> CommitteeRole:
        """Extract committee role from text."""
        text_lower = text.lower()

        if 'associated' in text_lower or 'opinion' in text_lower:
            return CommitteeRole.OPINION
        elif 'lead' in text_lower or 'responsible' in text_lower:
            return CommitteeRole.LEAD

        # Default to lead if not specified
        return CommitteeRole.LEAD

    def _extract_oeil_url(self, element) -> Optional[str]:
        """Extract OEIL URL from element."""
        oeil_link = element.select_one('a[href*="oeil.europarl"]')
        if oeil_link:
            return oeil_link.get('href')

        # Look for any link with procedure reference
        for link in element.select('a[href]'):
            href = link.get('href', '')
            if 'oeil' in href.lower() or 'procedure' in href.lower():
                return href

        return None

    def _extract_ep_page_url(self, element) -> Optional[str]:
        """Extract EP page URL from element."""
        # Look for document/procedure links
        for link in element.select('a[href]'):
            href = link.get('href', '')
            if 'europarl.europa.eu' in href and 'oeil' not in href:
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href

        return None

    def _has_next_page(self, html: str) -> bool:
        """Check if there's a next page."""
        soup = BeautifulSoup(html, 'lxml')

        # Look for pagination next button
        next_selectors = [
            '.ep_pagination-next:not(.disabled)',
            'a[rel="next"]',
            '.pagination .next:not(.disabled)',
            'a[aria-label="Next"]',
        ]

        for selector in next_selectors:
            if soup.select_one(selector):
                return True

        return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_relevance_score(self, procedure_type: ProcedureType) -> int:
        """Get relevance score for a procedure type."""
        return self.RELEVANCE_SCORES.get(procedure_type, 40)

    @staticmethod
    def validate_procedure_ref(ref: str) -> bool:
        """Validate a procedure reference format."""
        return bool(CommitteeWorkInProgressScraper.PROCEDURE_REF_PATTERN.match(ref))
