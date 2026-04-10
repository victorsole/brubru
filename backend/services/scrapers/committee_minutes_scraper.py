"""
EP Committee Minutes Scraper.

Scrapes published meeting minutes from all 26 European Parliament committees.

URL pattern (per committee):
https://www.europarl.europa.eu/committees/en/{code}/meetings/minutes

General minutes page (all committees):
https://www.europarl.europa.eu/committees/en/meetings/minutes

HTML structure (April 2026):
  div.es_document
    div.es_document-header
      h3.es_document-title > span.t-item  ->  "MINUTES - Monday, 10 November 2025"
      div.es_document-subtitle (data-separator="-")
        span.es_document-subtitle-fragment  ->  publication date, doc ref, PE ref
        a.es_badge.es_badge-committee  ->  committee code
      div.es_document-subtitle (data-separator="|")
        a.es_document-subtitle-pdf  ->  PDF link
        a.es_document-subtitle-doc  ->  DOC link

Created: April 2026
"""

import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from bs4 import BeautifulSoup

from services.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Date patterns in minutes titles
# "Monday, 10 November 2025"
# "Monday, 10 November 2025 - Tuesday, 11 November 2025"
DATE_PATTERN = re.compile(
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
    r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})'
)

MONTH_MAP = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4,
    'May': 5, 'June': 6, 'July': 7, 'August': 8,
    'September': 9, 'October': 10, 'November': 11, 'December': 12,
}

# Publication date pattern: "31-03-2026"
PUB_DATE_PATTERN = re.compile(r'^(\d{2})-(\d{2})-(\d{4})$')


@dataclass
class ScrapedMinutesItem:
    """A single scraped minutes entry."""
    committee_code: str
    meeting_date: datetime
    meeting_date_end: Optional[datetime] = None
    title: str = ""
    pe_reference: Optional[str] = None
    document_reference: Optional[str] = None
    publication_date: Optional[datetime] = None
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    source_url: str = ""
    scraped_at: datetime = field(default_factory=datetime.utcnow)


class CommitteeMinutesScraper(BaseScraper):
    """Scraper for EP Committee meeting minutes."""

    BASE_URL = "https://www.europarl.europa.eu"

    def __init__(self, **kwargs):
        super().__init__(
            base_url=self.BASE_URL,
            name="EPCommitteeMinutes",
            rate_limit_delay=2.0,
            cache_ttl=86400,
            timeout=30,
            max_retries=3,
            user_agent="Brubru/1.0 (EU Policy Assistant; https://brubru.beresol.eu)",
            **kwargs
        )

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def scrape_all_minutes(self, max_pages: int = 5) -> List[ScrapedMinutesItem]:
        """Scrape the general minutes page (all committees combined)."""
        all_items = []
        url = f"{self.BASE_URL}/committees/en/meetings/minutes"

        for page in range(max_pages):
            page_url = f"{url}?page={page}" if page > 0 else url
            logger.info(f"[START] Scraping minutes page {page + 1}: {page_url}")

            try:
                html = await self._fetch_page(page_url)
                if not html:
                    break

                items = self._parse_minutes_page(html, page_url)
                if not items:
                    logger.info(f"[INFO] No items on page {page + 1}, stopping")
                    break

                all_items.extend(items)
                logger.info(f"[OK] Page {page + 1}: {len(items)} minutes entries")

            except Exception as e:
                logger.error(f"[ERROR] Failed to scrape page {page + 1}: {e}")
                break

        logger.info(f"[OK] Total minutes scraped: {len(all_items)}")
        return all_items

    async def scrape_committee_minutes(self, committee_code: str, max_pages: int = 3) -> List[ScrapedMinutesItem]:
        """Scrape minutes for a specific committee."""
        code = committee_code.lower()
        all_items = []

        for page in range(max_pages):
            url = f"{self.BASE_URL}/committees/en/{code}/meetings/minutes"
            if page > 0:
                url += f"?page={page}"

            try:
                html = await self._fetch_page(url)
                if not html:
                    break

                items = self._parse_minutes_page(html, url)
                if not items:
                    break

                all_items.extend(items)
            except Exception as e:
                logger.error(f"[ERROR] {committee_code} page {page + 1}: {e}")
                break

        return all_items

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting and caching."""
        try:
            return await self._fetch(url)
        except Exception as e:
            logger.error(f"[ERROR] Fetch failed: {url}: {e}")
            return None

    def _parse_minutes_page(self, html: str, source_url: str) -> List[ScrapedMinutesItem]:
        """Parse a minutes listing page and extract all entries."""
        soup = BeautifulSoup(html, 'html.parser')
        items = []

        for doc_div in soup.select('div.es_document'):
            try:
                item = self._parse_single_entry(doc_div, source_url)
                if item:
                    items.append(item)
            except Exception as e:
                logger.warning(f"[WARN] Failed to parse entry: {e}")
                continue

        return items

    def _parse_single_entry(self, doc_div, source_url: str) -> Optional[ScrapedMinutesItem]:
        """Parse a single div.es_document into a ScrapedMinutesItem."""
        # Title: h3.es_document-title > span.t-item
        title_el = doc_div.select_one('h3.es_document-title .t-item')
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if 'MINUTES' not in title.upper():
            return None

        # Parse meeting dates from title
        dates = DATE_PATTERN.findall(title)
        if not dates:
            return None

        day, month_name, year = dates[0]
        meeting_date = datetime(int(year), MONTH_MAP[month_name], int(day))

        meeting_date_end = None
        if len(dates) > 1:
            day2, month2, year2 = dates[1]
            meeting_date_end = datetime(int(year2), MONTH_MAP[month2], int(day2))

        # Subtitle fragments: publication date, document ref, PE ref
        pe_reference = None
        document_reference = None
        publication_date = None
        committee_code = None

        for frag in doc_div.select('span.es_document-subtitle-fragment'):
            text = frag.get_text(strip=True)
            if text.startswith('PE'):
                pe_reference = text
            elif '_PV(' in text or '_PV-' in text:
                document_reference = text
            else:
                m = PUB_DATE_PATTERN.match(text)
                if m:
                    publication_date = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))

        # Committee badge
        badge = doc_div.select_one('a.es_badge-committee')
        if badge:
            committee_code = badge.get_text(strip=True)

        # If no committee code found, try to extract from document_reference
        if not committee_code and document_reference:
            parts = document_reference.split('_')
            if parts:
                committee_code = parts[0]

        if not committee_code:
            return None

        # PDF and DOC links
        pdf_url = None
        doc_url = None

        pdf_link = doc_div.select_one('a.es_document-subtitle-pdf')
        if pdf_link and pdf_link.get('href'):
            pdf_url = pdf_link['href']
            if pdf_url.startswith('/'):
                pdf_url = f"{self.BASE_URL}{pdf_url}"

        doc_link = doc_div.select_one('a.es_document-subtitle-doc')
        if doc_link and doc_link.get('href'):
            doc_url = doc_link['href']
            if doc_url.startswith('/'):
                doc_url = f"{self.BASE_URL}{doc_url}"

        return ScrapedMinutesItem(
            committee_code=committee_code.upper(),
            meeting_date=meeting_date,
            meeting_date_end=meeting_date_end,
            title=title,
            pe_reference=pe_reference,
            document_reference=document_reference,
            publication_date=publication_date,
            pdf_url=pdf_url,
            doc_url=doc_url,
            source_url=source_url,
        )
