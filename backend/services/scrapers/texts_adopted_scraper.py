"""
EP Texts Adopted Scraper.

Scrapes adopted texts from the European Parliament via:
1. RSS feed (ongoing updates) - primary source
2. TOC pages (historical backfill) - per plenary session date
3. Individual text pages (detail enrichment) - optional

URL Patterns:
- RSS: https://www.europarl.europa.eu/rss/doc/texts-adopted/en.xml
- TOC: https://www.europarl.europa.eu/doceo/document/TA-{term}-YYYY-MM-DD-TOC_EN.html
- Text: https://www.europarl.europa.eu/doceo/document/TA-{term}-YYYY-NNNN_EN.html

Created: February 2026
"""

import re
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any, Callable

from services.scrapers.base_scraper import BaseScraper, ScraperError
from schemas.scrapers.texts_adopted_schemas import (
    ScrapedTextAdopted,
    ScrapedTextAdoptedDetail,
    TextType,
    ScrapeResult,
    ScrapeAllResult,
    PARLIAMENTARY_TERMS,
)

logger = logging.getLogger(__name__)


class TextsAdoptedScraper(BaseScraper):
    """
    Scraper for EP Texts Adopted.

    Inherits from BaseScraper for:
    - Rate limiting (2.0s delay, coordinated with other EP scrapers)
    - Caching (24h TTL)
    - Retry logic (exponential backoff)
    - Statistics tracking
    """

    RSS_URL = "https://www.europarl.europa.eu/rss/doc/texts-adopted/en.xml"

    # Regex patterns
    TA_REF_PATTERN = re.compile(r'P(\d+)_TA\((\d{4})\)(\d+)')
    PROCEDURE_REF_PATTERN = re.compile(r'\d{4}/\d{4}\([A-Z]{3,4}\)')
    MEP_ID_PATTERN = re.compile(r'/meps/en/(\d+)')
    CELEX_PATTERN = re.compile(r'[35]\d{4}[A-Z]\d{4}')

    # Term to prefix mapping for URLs
    TERM_PREFIXES = {
        10: "TA-10",
        9: "TA-9",
        8: "TA-8",
        7: "TA-7",
        6: "TA-6",
        5: "TA-5",
        4: "TA-4",
    }

    # europarl.europa.eu answers a plain HTTP fetch with an HTTP 202 and a
    # near-empty JS shell -- 2,431 bytes and ZERO links on the texts-adopted
    # index, 0 bytes on a doceo TOC. Nothing raises, so `get_plenary_dates`
    # found no dates and reported "0 plenary dates" as a fact about the
    # Parliament rather than about our own fetch. That is why `texts_adopted`
    # holds only what the RSS feed carried and the corpus opens on 20 Jan 2026,
    # making the 26 November 2025 resolution on protecting minors online
    # invisible to every search.
    #
    # Anything smaller than this is treated as a FETCH FAILURE and retried
    # through a real browser, per `feedback_waf_walled_use_playwright`.
    _MIN_PLAUSIBLE_BYTES = 5000

    async def _fetch(self, url: str, *args, **kwargs):  # type: ignore[override]
        """Plain fetch, falling back to a real browser on a JS shell.

        Raises when neither path yields a plausible page, so an empty corpus can
        never again be mistaken for an empty Parliament.
        """
        html = None
        try:
            html = await super()._fetch(url, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- fall through to the browser
            logger.debug("[texts-adopted] plain fetch failed for %s: %s", url, exc)

        if html and len(html) >= self._MIN_PLAUSIBLE_BYTES:
            return html

        import asyncio as _asyncio
        from services.scrapers.waf_browser_fetcher import fetch_one

        got = len(html or "")
        logger.info("[texts-adopted] %s returned %d bytes -- rendering with a browser",
                    url, got)
        # fetch_one drives Playwright's SYNC api, which raises on the event loop.
        res = await _asyncio.to_thread(fetch_one, url, expand_accordions=True,
                                       strip_chrome=False)
        rendered = getattr(res, "html", None) or ""
        if len(rendered) < self._MIN_PLAUSIBLE_BYTES:
            raise RuntimeError(
                f"{url} returned {got} bytes plain and {len(rendered)} rendered -- "
                "treat as a FETCH FAILURE, never as 'no texts adopted'"
            )
        return rendered

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://www.europarl.europa.eu",
            name="EPTextsAdopted",
            rate_limit_delay=2.0,
            cache_ttl=86400,  # 24 hours
            timeout=30,
            max_retries=3,
            user_agent="Brubru/1.0 (EU Policy Assistant; https://brubru.beresol.eu)",
            **kwargs
        )

    # =========================================================================
    # Required Abstract Method Implementations
    # =========================================================================

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search adopted texts by keyword via RSS."""
        limit = kwargs.get('limit', 50)
        items = await self.fetch_rss()

        query_lower = query.lower()
        results = []
        for item in items:
            if query_lower in item.title.lower() or (
                item.description and query_lower in item.description.lower()
            ):
                results.append(item.model_dump())
                if len(results) >= limit:
                    break

        return results

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get an adopted text by TA reference."""
        items = await self.fetch_rss()
        for item in items:
            if item.ta_reference == document_id:
                return item.model_dump()
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest adopted texts from RSS feed."""
        items = await self.fetch_rss()
        return [item.model_dump() for item in items[:limit]]

    # =========================================================================
    # RSS Feed Methods
    # =========================================================================

    async def fetch_rss(self) -> List[ScrapedTextAdopted]:
        """
        Fetch and parse the Texts Adopted RSS feed.

        Returns:
            List of scraped adopted texts from RSS
        """
        try:
            xml_content = await self._fetch(
                self.RSS_URL,
                headers={'Accept': 'application/rss+xml, application/xml, text/xml'},
                use_cache=True
            )

            return self._parse_rss(xml_content)

        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch RSS feed: {e}")
            raise ScraperError(f"Failed to fetch RSS feed: {e}") from e

    def _parse_rss(self, xml_content: str) -> List[ScrapedTextAdopted]:
        """Parse RSS XML content into ScrapedTextAdopted items."""
        items = []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"[ERROR] Failed to parse RSS XML: {e}")
            return items

        channel = root.find('channel')
        if channel is None:
            logger.warning("[WARN] No channel element found in RSS")
            return items

        for item_elem in channel.findall('item'):
            try:
                parsed = self._parse_rss_item(item_elem)
                if parsed:
                    items.append(parsed)
            except Exception as e:
                title = item_elem.findtext('title', 'unknown')
                logger.debug(f"Error parsing RSS item '{title[:60]}': {e}")
                continue

        logger.info(f"[OK] Parsed {len(items)} items from RSS feed")
        return items

    def _parse_rss_item(self, item_elem) -> Optional[ScrapedTextAdopted]:
        """Parse a single RSS <item> element."""
        title_raw = item_elem.findtext('title', '').strip()
        link = item_elem.findtext('link', '').strip()
        description_raw = item_elem.findtext('description', '').strip()
        pub_date_str = item_elem.findtext('pubDate', '').strip()
        category = item_elem.findtext('category', '').strip()
        guid = item_elem.findtext('guid', '').strip()

        if not title_raw or not link:
            return None

        # Skip corrigenda - they're corrections, not adopted texts
        if category.lower() == 'corrigendum' or 'COR' in guid:
            return None

        # Extract TA reference from title
        ta_ref_match = self.TA_REF_PATTERN.search(title_raw)
        if not ta_ref_match:
            return None

        term_num = int(ta_ref_match.group(1))
        year = ta_ref_match.group(2)
        seq = ta_ref_match.group(3)
        ta_reference = f"P{term_num}_TA({year}){seq}"

        # Clean title: remove "Text adopted - " prefix and TA ref suffix
        title = title_raw
        title = re.sub(r'^Text adopted\s*-\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*P\d+_TA\(\d{4}\)\d+.*$', '', title)
        title = title.strip()

        # Extract procedure reference from description
        procedure_ref = None
        if description_raw:
            proc_match = self.PROCEDURE_REF_PATTERN.search(description_raw)
            if proc_match:
                procedure_ref = proc_match.group(0)

        # Clean description (remove HTML entities and source attribution)
        description = re.sub(r'<[^>]+>', '', description_raw)
        description = re.sub(r'&lt;.*?&gt;', '', description)
        description = re.sub(r'\s*Source\s*:.*$', '', description, flags=re.DOTALL)
        description = description.strip() or None

        # Parse date
        adoption_date = datetime.now()
        if pub_date_str:
            try:
                adoption_date = parsedate_to_datetime(pub_date_str)
            except (ValueError, TypeError):
                pass

        # Classify text type
        text_type = self._classify_text_type(title_raw, description_raw)

        return ScrapedTextAdopted(
            ta_reference=ta_reference,
            title=title,
            description=description,
            text_type=text_type,
            procedure_ref=procedure_ref,
            adoption_date=adoption_date,
            source_url=link,
            full_text_url=link if link.endswith('.html') else None,
            pdf_url=link if link.endswith('.pdf') else None,
            parliamentary_term=term_num,
            scraped_at=datetime.now(),
        )

    def _classify_text_type(self, title: str, description: str) -> TextType:
        """Classify the type of adopted text from its title and a SHORT description.

        WARNING: never pass a full document here. This is a substring test, and
        `elif 'decision' in combined` fires on any text that mentions the word
        anywhere -- so over a 20,000-character resolution it confidently returns
        DECISION. Measured 27 Aug 2026: 7 of 8 sampled resolutions were
        misclassified that way. The description is therefore truncated.

        Note also what this CANNOT do. The 437 rows backfilled from plenary TOC
        pages have no description at all -- the TOC carries only a title, and the
        document page's own header reads "Texts adopted - <title> - <date>" with
        no type marker. They stay OTHER, which here means UNCLASSIFIED, not
        "some other kind of text". Guessing from body text would mislabel them.
        """
        # A title plus a short lead is enough to classify; a whole document is not.
        combined = f"{title} {(description or '')[:300]}".lower()

        if 'legislative resolution' in combined:
            return TextType.LEGISLATIVE_RESOLUTION
        elif 'decision' in combined:
            return TextType.DECISION
        elif 'recommendation' in combined:
            return TextType.RECOMMENDATION
        elif 'resolution' in combined:
            return TextType.RESOLUTION
        else:
            return TextType.OTHER

    # =========================================================================
    # TOC Page Methods (Historical Backfill)
    # =========================================================================

    async def scrape_toc_page(
        self,
        date_str: str,
        term: int = 10
    ) -> List[ScrapedTextAdopted]:
        """
        Scrape a daily TOC (Table of Contents) page for adopted texts.

        Args:
            date_str: Date string in YYYY-MM-DD format
            term: Parliamentary term number (default: 10)

        Returns:
            List of scraped adopted texts from this plenary date
        """
        prefix = self.TERM_PREFIXES.get(term, f"TA-{term}")
        url = f"{self.base_url}/doceo/document/{prefix}-{date_str}-TOC_EN.html"

        try:
            html = await self._fetch(url, use_cache=True)
            return self._parse_toc_page(html, date_str, term, url)
        except ScraperError as e:
            if "HTTP 404" in str(e):
                logger.debug(f"No TOC page for {date_str} (term {term})")
                return []
            raise

    def _parse_toc_page(
        self,
        html: str,
        date_str: str,
        term: int,
        source_url: str
    ) -> List[ScrapedTextAdopted]:
        """Parse a TOC page HTML and extract adopted text items."""
        soup = self._parse_html(html)
        items = []

        # Parse adoption date
        try:
            adoption_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            adoption_date = datetime.now()

        prefix = self.TERM_PREFIXES.get(term, f"TA-{term}")

        # Find all links to adopted texts
        # Pattern: /doceo/document/TA-{term}-YYYY-NNNN_EN.html
        ta_pattern = re.compile(rf'{re.escape(prefix)}-\d{{4}}-\d{{4}}')

        for link in soup.select(f'a[href*="{prefix}"]'):
            href = link.get('href', '')
            title = link.get_text(strip=True)

            if not title or not href:
                continue

            # Skip TOC links and non-text links
            if 'TOC' in href or href.endswith('.pdf'):
                continue

            # Extract TA reference from URL
            ta_match = re.search(rf'{re.escape(prefix)}-(\d{{4}})-(\d{{4}})', href)
            if not ta_match:
                continue

            year = ta_match.group(1)
            seq = ta_match.group(2)
            ta_reference = f"P{term}_TA({year}){seq}"

            full_url = self._make_absolute_url(href)

            # Try to extract procedure reference from title
            procedure_ref = None
            proc_match = self.PROCEDURE_REF_PATTERN.search(title)
            if proc_match:
                procedure_ref = proc_match.group(0)

            # Classify text type from title
            text_type = self._classify_text_type(title, '')

            items.append(ScrapedTextAdopted(
                ta_reference=ta_reference,
                title=title,
                text_type=text_type,
                procedure_ref=procedure_ref,
                adoption_date=adoption_date,
                source_url=source_url,
                full_text_url=full_url,
                parliamentary_term=term,
                scraped_at=datetime.now(),
            ))

        logger.info(f"[OK] Parsed {len(items)} texts from TOC page {date_str}")
        return items

    async def get_plenary_dates(self, term: int = 10) -> List[str]:
        """
        Get all available plenary session dates for a given term.

        Scrapes the main Texts Adopted index page to find all plenary dates.

        Args:
            term: Parliamentary term number

        Returns:
            List of date strings in YYYY-MM-DD format, sorted descending
        """
        url = f"{self.base_url}/plenary/en/texts-adopted.html"

        try:
            html = await self._fetch(url, use_cache=True)
            soup = self._parse_html(html)

            prefix = self.TERM_PREFIXES.get(term, f"TA-{term}")
            dates = set()

            # Find all TOC links with dates
            toc_pattern = re.compile(
                rf'{re.escape(prefix)}-(\d{{4}}-\d{{2}}-\d{{2}})-TOC'
            )

            for link in soup.select('a[href]'):
                href = link.get('href', '')
                match = toc_pattern.search(href)
                if match:
                    dates.add(match.group(1))

            sorted_dates = sorted(dates, reverse=True)
            logger.info(f"[OK] Found {len(sorted_dates)} plenary dates for term {term}")
            return sorted_dates

        except Exception as e:
            logger.error(f"[ERROR] Failed to get plenary dates: {e}")
            return []

    async def scrape_term(
        self,
        term: int = 10,
        max_dates: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[ScrapedTextAdopted]:
        """
        Scrape all adopted texts from a parliamentary term.

        Args:
            term: Parliamentary term number
            max_dates: Maximum number of plenary dates to scrape (None = all)
            progress_callback: Optional callback(current, total, message)

        Returns:
            List of all scraped adopted texts for this term
        """
        if term not in PARLIAMENTARY_TERMS:
            raise ValueError(f"Invalid parliamentary term: {term}. Valid: {list(PARLIAMENTARY_TERMS.keys())}")

        dates = await self.get_plenary_dates(term)

        if max_dates:
            dates = dates[:max_dates]

        all_items = []
        total = len(dates)

        for i, date_str in enumerate(dates):
            if progress_callback:
                progress_callback(i + 1, total, f"Scraping term {term}: {date_str}")

            try:
                items = await self.scrape_toc_page(date_str, term)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[ERROR] Failed to scrape TOC for {date_str}: {e}")
                continue

        logger.info(f"[OK] Scraped {len(all_items)} texts from term {term} ({total} dates)")
        return all_items

    # =========================================================================
    # Detail Page Methods (Optional Enrichment)
    # =========================================================================

    async def scrape_text_detail(
        self,
        ta_reference: str,
        full_text_url: Optional[str] = None
    ) -> Optional[ScrapedTextAdoptedDetail]:
        """
        Scrape the detail page of an individual adopted text.

        Args:
            ta_reference: TA reference (e.g., P10_TA(2025)0042)
            full_text_url: URL to the text page (constructed from reference if not provided)

        Returns:
            ScrapedTextAdoptedDetail with full content, or None if failed
        """
        if not full_text_url:
            # Construct URL from reference
            ta_match = self.TA_REF_PATTERN.match(ta_reference)
            if not ta_match:
                return None
            term = ta_match.group(1)
            year = ta_match.group(2)
            seq = ta_match.group(3)
            full_text_url = (
                f"{self.base_url}/doceo/document/"
                f"TA-{term}-{year}-{seq}_EN.html"
            )

        try:
            html = await self._fetch(full_text_url, use_cache=True)
            return self._parse_detail_page(html, ta_reference, full_text_url)
        except Exception as e:
            logger.error(f"[ERROR] Failed to scrape detail for {ta_reference}: {e}")
            return None

    def _parse_detail_page(
        self,
        html: str,
        ta_reference: str,
        source_url: str
    ) -> Optional[ScrapedTextAdoptedDetail]:
        """Parse an individual text detail page."""
        soup = self._parse_html(html)

        # Extract title
        title_elem = soup.select_one('h1, .ep_name, .doc-title, title')
        title = title_elem.get_text(strip=True) if title_elem else ta_reference

        # Extract full text.
        #
        # `.ep_content`, `.doc-content` and `#TextesAdoptes` are ALL DEAD on
        # current doceo markup -- verified against live pages, none of the three
        # matches anything. The page is table-based: the document body lives in
        # `tr.contents`. Because a failed selector returned None without
        # complaint, `full_text` has been silently NULL for every adopted text
        # this scraper fetched, and the API served a synthesised body instead.
        #
        # Ordered: legacy selectors first (older cached pages may still use
        # them), then the current one. Whichever yields the MOST text wins,
        # rather than whichever matches first -- `table.doc_box_header` matches
        # on these pages but returns only the ~200-char header.
        full_text = None
        _best = 0
        for _sel in ('.ep_content', '.doc-content', '#TextesAdoptes',
                     'tr.contents', 'table.doc_box_header'):
            _el = soup.select_one(_sel)
            if not _el:
                continue
            _txt = _el.get_text(separator='\n', strip=True)
            if len(_txt) > _best:
                full_text, _best = _txt, len(_txt)
        if not full_text:
            # Loud, not silent: a body we could not find is a parser problem and
            # must not be indistinguishable from a document with no text.
            logger.warning(
                "[texts-adopted] no content container matched for %s (%d bytes of "
                "html) -- the doceo markup may have changed again", ta_reference, len(html)
            )

        # Extract procedure reference
        page_text = soup.get_text()
        procedure_ref = None
        proc_match = self.PROCEDURE_REF_PATTERN.search(page_text)
        if proc_match:
            procedure_ref = proc_match.group(0)

        # Extract committees
        committees = []
        for link in soup.select('a[href*="/committees/"]'):
            code = link.get_text(strip=True).upper()
            if len(code) <= 5 and code.isalpha():
                committees.append(code)
        committees = list(set(committees))

        # Extract rapporteur
        rapporteur_name = None
        rapporteur_mep_id = None
        mep_link = soup.select_one('a[href*="/meps/"]')
        if mep_link:
            rapporteur_name = mep_link.get_text(strip=True)
            href = mep_link.get('href', '')
            id_match = self.MEP_ID_PATTERN.search(href)
            if id_match:
                rapporteur_mep_id = id_match.group(1)

        # Extract CELEX number
        celex_number = None
        celex_match = self.CELEX_PATTERN.search(page_text)
        if celex_match:
            celex_number = celex_match.group(0)

        # Extract PDF link
        pdf_url = None
        pdf_link = soup.select_one('a[href$=".pdf"]')
        if pdf_link:
            pdf_url = self._make_absolute_url(pdf_link.get('href', ''))

        # Classify text type
        text_type = self._classify_text_type(title, full_text or '')

        # Parse TA reference for term info
        ta_match = self.TA_REF_PATTERN.match(ta_reference)
        term = int(ta_match.group(1)) if ta_match else 10

        return ScrapedTextAdoptedDetail(
            ta_reference=ta_reference,
            title=title,
            text_type=text_type,
            procedure_ref=procedure_ref,
            adoption_date=datetime.now(),  # Will be overridden by caller
            source_url=source_url,
            full_text_url=source_url,
            pdf_url=pdf_url,
            parliamentary_term=term,
            full_text=full_text,
            committees=committees,
            rapporteur_name=rapporteur_name,
            rapporteur_mep_id=rapporteur_mep_id,
            celex_number=celex_number,
            scraped_at=datetime.now(),
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def validate_ta_reference(ref: str) -> bool:
        """Validate a TA reference format."""
        return bool(TextsAdoptedScraper.TA_REF_PATTERN.match(ref))

    @staticmethod
    def ta_ref_to_url(ta_reference: str) -> Optional[str]:
        """Convert a TA reference to its EP document URL."""
        match = TextsAdoptedScraper.TA_REF_PATTERN.match(ta_reference)
        if not match:
            return None
        term = match.group(1)
        year = match.group(2)
        seq = match.group(3)
        return (
            f"https://www.europarl.europa.eu/doceo/document/"
            f"TA-{term}-{year}-{seq}_EN.html"
        )
