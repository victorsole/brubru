"""
EP Committee Draft Agenda Scraper.

Scrapes draft agenda metadata from EP committee latest-documents pages.
Does NOT parse PDF content -- cross-references with CommitteeWorkItem
records for procedure refs instead.

URL Patterns:
- All committees: https://www.europarl.europa.eu/committees/en/documents/latest-documents
- Per committee:  https://www.europarl.europa.eu/committees/en/{code}/documents/latest-documents

HTML structure (evostrap framework):
- Container: div.es_document
- Title:     h3.es_document-title a span.t-item
- Fragments: span.es_document-subtitle-fragment (date, doc_id, PE number)
- Committee: a.es_badge-committee
- PDF link:  a.es_document-subtitle-pdf
- DOC link:  a.es_document-subtitle-doc

Created: February 2026
"""

import re
import logging
from datetime import datetime, date as date_type
from typing import List, Optional, Dict, Any

from services.scrapers.base_scraper import BaseScraper
from schemas.scrapers.committee_agenda_schemas import ScrapedCommitteeAgenda
from knowledge_base.ep_committees import (
    EP_COMMITTEES,
    EP_COMMITTEE_BY_CODE,
    EP_COMMITTEE_CODES,
)

logger = logging.getLogger(__name__)


# Date patterns in titles: "Wednesday, 25 February 2026" or "Monday, 23 February 2026 - Tuesday, 24 February 2026"
DATE_PATTERN = re.compile(
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
    r'(\d{1,2})\s+'
    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
    r'(\d{4})'
)

MONTH_MAP = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4,
    'May': 5, 'June': 6, 'July': 7, 'August': 8,
    'September': 9, 'October': 10, 'November': 11, 'December': 12,
}

# PE number pattern: "PE784.460v02-00"
PE_PATTERN = re.compile(r'PE\d{3}\.\d{3}[a-zA-Z0-9\-]*')

# Date fragment pattern: "25-02-2026"
DATE_FRAGMENT_PATTERN = re.compile(r'^\d{2}-\d{2}-\d{4}$')

# Document ID pattern: "EMPL_OJ(2026)02-25_1"
DOC_ID_PATTERN = re.compile(r'^[A-Z]+_[A-Z]+\(\d{4}\)\d{2}-\d{2}_\d+$')


class CommitteeAgendaScraper(BaseScraper):
    """
    Scraper for EP Committee draft agenda documents.

    Only fetches metadata (title, date, PDF URL) from the latest-documents
    listing page. Does not download or parse PDF content.
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://www.europarl.europa.eu",
            name="EPCommitteeAgenda",
            rate_limit_delay=2.0,
            cache_ttl=43200,  # 12 hours
            timeout=30,
            max_retries=3,
            user_agent="Brubru/1.0 (EU Policy Assistant; https://brubru.beresol.eu)",
            **kwargs
        )

    # =========================================================================
    # Required Abstract Method Implementations
    # =========================================================================

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Not used for agenda scraping."""
        return []

    async def get_document(self, identifier: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Not used for agenda scraping."""
        return None

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return latest draft agendas as generic dicts."""
        agendas = await self.scrape_all_from_main_page()
        return [a.model_dump() for a in agendas[:limit]]

    # =========================================================================
    # Main Scraping Methods
    # =========================================================================

    async def scrape_all_from_main_page(self) -> List[ScrapedCommitteeAgenda]:
        """
        Scrape draft agendas from the main latest-documents page.
        This page lists documents from ALL committees, sorted by date.
        Most efficient: 1 request instead of 26.
        """
        url = f"{self.base_url}/committees/en/documents/latest-documents"

        try:
            soup = await self._fetch_and_parse(url)
            if not soup:
                return []

            agendas = self._extract_agendas_from_html(soup, url)
            logger.info(
                f"[OK] Main page: found {len(agendas)} draft agenda(s)"
            )
            return agendas

        except Exception as e:
            logger.error(f"[ERROR] Failed to scrape main latest-documents: {e}")
            return []

    async def scrape_committee_agendas(
        self,
        committee_code: str,
    ) -> List[ScrapedCommitteeAgenda]:
        """
        Scrape draft agenda metadata for a single committee.

        Args:
            committee_code: EP committee code (e.g. "LIBE", "ITRE")

        Returns:
            List of scraped agenda metadata
        """
        committee = EP_COMMITTEE_BY_CODE.get(committee_code.upper())
        if not committee:
            logger.warning(f"[WARN] Unknown committee code: {committee_code}")
            return []

        url = (
            f"{self.base_url}/committees/en/"
            f"{committee.url_path}/documents/latest-documents"
        )

        try:
            soup = await self._fetch_and_parse(url)
            if not soup:
                return []

            agendas = self._extract_agendas_from_html(soup, url)
            logger.info(
                f"[OK] {committee_code}: found {len(agendas)} draft agenda(s)"
            )
            return agendas

        except Exception as e:
            logger.error(f"[ERROR] Failed to scrape {committee_code} agendas: {e}")
            return []

    async def scrape_all_committees(
        self,
        committee_codes: Optional[List[str]] = None,
    ) -> List[ScrapedCommitteeAgenda]:
        """
        Scrape draft agendas. Uses main page by default (1 request for all).
        If specific committee_codes are provided, scrapes individual pages.

        Args:
            committee_codes: Optional list of codes to scrape.
                           If None, scrapes the main page (all committees).

        Returns:
            Combined list of all scraped agendas
        """
        if committee_codes:
            # Scrape individual committee pages
            all_agendas: List[ScrapedCommitteeAgenda] = []
            for code in committee_codes:
                try:
                    agendas = await self.scrape_committee_agendas(code)
                    all_agendas.extend(agendas)
                except Exception as e:
                    logger.warning(f"[WARN] Skipping {code}: {e}")
            logger.info(
                f"[OK] Scraped {len(all_agendas)} agendas from {len(committee_codes)} committees"
            )
            return all_agendas
        else:
            # Scrape main page (all committees in one request)
            return await self.scrape_all_from_main_page()

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _fetch_and_parse(self, url: str):
        """Fetch URL and return BeautifulSoup object."""
        from bs4 import BeautifulSoup

        html = await self._fetch(url)
        if not html:
            return None
        return BeautifulSoup(html, 'html.parser')

    def _extract_agendas_from_html(
        self,
        soup,
        source_url: str,
    ) -> List[ScrapedCommitteeAgenda]:
        """
        Extract draft agenda entries from EP latest-documents HTML.

        Uses the evostrap div.es_document card structure.
        """
        agendas: List[ScrapedCommitteeAgenda] = []
        now = datetime.now()

        # Find all document cards
        doc_cards = soup.select('div.es_document')

        if not doc_cards:
            logger.warning("[WARN] No div.es_document elements found on page")
            return []

        for card in doc_cards:
            # Get title text
            title_el = card.select_one('h3.es_document-title .t-item')
            if not title_el:
                continue

            title = title_el.get_text(strip=True)

            # Only process DRAFT AGENDA documents
            if 'DRAFT AGENDA' not in title.upper():
                continue

            # Extract committee code from badge
            committee_badge = card.select_one('a.es_badge-committee')
            if not committee_badge:
                continue
            committee_code = committee_badge.get_text(strip=True).upper()

            # Validate committee code
            if committee_code not in EP_COMMITTEE_CODES:
                # Could be a joint committee code (CJ21, CJ54) - skip
                continue

            # Parse meeting date from title
            meeting_date = self._parse_meeting_date(title)
            if not meeting_date:
                continue

            # Extract subtitle fragments (date, doc_id, PE number)
            fragments = card.select('span.es_document-subtitle-fragment')
            document_id = None
            pe_number = None

            for frag in fragments:
                frag_text = frag.get_text(strip=True)
                if DOC_ID_PATTERN.match(frag_text):
                    document_id = frag_text
                elif PE_PATTERN.match(frag_text):
                    pe_number = frag_text

            # Extract PDF and DOC URLs
            pdf_link = card.select_one('a.es_document-subtitle-pdf')
            pdf_url = pdf_link['href'] if pdf_link and pdf_link.get('href') else None

            doc_link = card.select_one('a.es_document-subtitle-doc')
            doc_url = doc_link['href'] if doc_link and doc_link.get('href') else None

            agendas.append(ScrapedCommitteeAgenda(
                committee_code=committee_code,
                meeting_date=meeting_date,
                title=title,
                document_id=document_id,
                pe_number=pe_number,
                pdf_url=pdf_url,
                doc_url=doc_url,
                source_url=source_url,
                scraped_at=now,
            ))

        return agendas

    def _parse_meeting_date(self, title: str) -> Optional[date_type]:
        """Parse the first meeting date from the agenda title."""
        match = DATE_PATTERN.search(title)
        if not match:
            return None

        day = int(match.group(1))
        month = MONTH_MAP.get(match.group(2), 0)
        year = int(match.group(3))

        if not month or year < 2020 or year > 2030:
            return None

        try:
            return date_type(year, month, day)
        except ValueError:
            return None
