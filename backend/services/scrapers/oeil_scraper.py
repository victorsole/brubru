"""
OEIL Legislative Observatory Scraper

PHASE 4 UPGRADE: Integrated with API clients
- XML export functionality (primary)
- RSS subscriptions for procedure tracking
- api.epdb.eu JSON dumps integration
- Web scraping as fallback

PHASE 5 UPGRADE: Full web scraping implementation
- Complete procedure page parsing (all 7 sections)
- MEP extraction with photos and political groups
- Document gateway parsing
- Timeline and forecast extraction

Scrapes EU legislative procedures, timelines, and status updates
"""

import asyncio
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import aiohttp
from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper, ScraperError, _extract_domain
from services.api_clients.oeil_client import OEILClient
from schemas.scrapers.oeil_schemas import (
    OEILProcedure, OEILBasicInfo, OEILKeyPlayers, OEILKeyEvents,
    OEILForecasts, OEILTechnicalInfo, OEILDocumentation, OEILAdditionalInfo,
    OEILMep, OEILCommittee, OEILDocument, OEILEvent, OEILForecast,
    OEILLegalBasis, OEILConsultativeBody, OEILNationalParliamentContribution
)

logger = logging.getLogger(__name__)


# Labels that appear on an OEIL procedure page. A value is the line AFTER a
# label, so a value that is itself a label means the extraction slipped and the
# field must stay empty rather than carry the label forward.
_OEIL_LABELS = frozenset({
    "Basic information", "Full procedure", "Status", "Subject", "Legal basis",
    "Other legal basis", "Committee dossier", "Stage reached in procedure",
    "Key players", "Committee responsible", "Rapporteur", "Appointed",
    "Shadow rapporteur", "Committee for opinion", "Key events", "Forecasts",
    "Technical information", "Documentation gateway", "Additional information",
    "Procedure reference", "Procedure type", "Procedure subtype", "Instrument",
    "Amendments and repeals", "Mandatory consultation of other institutions",
    "Document type", "Committee", "Ref", "Date", "Summary", "pdf",
})


def _oeil_lines(soup: BeautifulSoup) -> list:
    """Every visible line of an OEIL page, in order, blanks removed.

    OEIL renders as label line followed by value line. The page is
    server-rendered: the data IS in the HTML (verified 3 Sep 2026 against
    2023/0437(COD), where the raw response carries the committee, the
    rapporteur and the stage). An earlier reading called it a JS SPA; that was
    a bad text extraction, not a JS wall.
    """
    clone = BeautifulSoup(str(soup), "html.parser")
    for t in clone(["script", "style", "noscript"]):
        t.decompose()
    return [ln.strip() for ln in clone.get_text("\n", strip=True).split("\n") if ln.strip()]


def _value_after(lines: list, label: str) -> Optional[str]:
    """The line following `label`, or None when the next line is another label.

    Why this exists: `_parse_basic_info` used to read the LABEL as the value.
    It matched a "Stage reached" regex and then assigned group(0), the
    whole match, so every procedure came back with status
    "Stage reached in procedure" and title "Procedure File: <ref>". Both are the
    page furniture, not the data. Callers relying on OEIL for rapporteur
    identity were reading furniture.
    """
    try:
        i = lines.index(label)
    except ValueError:
        return None
    for candidate in lines[i + 1: i + 3]:
        if candidate in _OEIL_LABELS:
            continue
        return candidate
    return None


# ---------------------------------------------------------------------------
# Fetch classification (15 Sep 2026)
# ---------------------------------------------------------------------------
# What OEIL actually answers, measured 15 Sep 2026 with a Chrome/141 UA:
#
#   oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=...
#       -> 307, 164-byte nginx body, Location: the SAME path on
#          oeil.europarl.europa.eu. No cookie, no challenge script: a moved
#          host, not a WAF.
#   oeil.europarl.europa.eu/oeil/en/procedure-file?reference=...
#       -> 200, ~140 KB, server-rendered, every section in the HTML
#          (div#section1..8), including rapporteur, shadows, opinion
#          committees, key events and forecasts.
#
# So the plain HTTP route works and stays primary. The browser is kept for the
# day it stops working: a WAF status (202, 403), a redirect that leaves the
# OEIL procedure page, or a 200 that carries nothing parseable. Any of those
# without a usable browser result is a counted, raised error, never an empty
# procedure that the caller reads as "no events".

_OEIL_HOSTS = frozenset({"oeil.europarl.europa.eu", "oeil.secure.europarl.europa.eu"})
_WAF_STATUSES = frozenset({202, 403})


class OEILFetchError(ScraperError):
    """OEIL gave us nothing we could parse. Always counted by the caller."""

    def __init__(self, reference: str, reason: str, status: Optional[int] = None,
                 route: Optional[str] = None):
        self.reference = reference
        self.reason = reason
        self.status = status
        self.route = route
        super().__init__(f"OEIL {reference}: {reason}"
                         + (f" (HTTP {status})" if status is not None else "")
                         + (f" [route={route}]" if route else ""))


@dataclass
class OEILPage:
    reference: str
    url: str
    html: str
    route: str               # "http" or "browser"
    http_status: Optional[int]


def looks_like_procedure_page(html: Optional[str]) -> bool:
    """True when the HTML carries the OEIL procedure sections."""
    if not html or len(html) < 2000:
        return False
    return ('id="section1"' in html or "id='section1'" in html
            or ("Key players" in html and "Key events" in html))


def classify_oeil_response(status: Optional[int], body: Optional[str],
                           location: Optional[str] = None) -> str:
    """Decide what a raw OEIL HTTP answer means.

    Returns one of:
      "ok"        200 with the procedure sections present
      "redirect"  3xx to another OEIL procedure-file URL (follow it)
      "waf"       a WAF status, a redirect away from the procedure page, or a
                  200 carrying nothing parseable -> try the browser
      "not_found" 404: the reference does not exist on OEIL
      "error"     anything else (5xx, 429...): raise, the browser cannot help
    """
    if status == 200:
        return "ok" if looks_like_procedure_page(body) else "waf"
    if status in _WAF_STATUSES:
        return "waf"
    if status is not None and 300 <= status < 400:
        if location:
            p = urlparse(location)
            host_ok = (not p.netloc) or p.netloc.lower() in _OEIL_HOSTS
            if host_ok and "/procedure-file" in p.path and "reference=" in (p.query or ""):
                return "redirect"
        return "waf"
    if status == 404:
        return "not_found"
    return "error"


class _BrowserLane:
    """One headless browser, reused for every ref, confined to ONE thread.

    Playwright's sync API is thread-affine (greenlet), and it refuses to run
    inside a running asyncio loop, so every call -- launch, fetch, close -- is
    submitted to the same single-worker executor.
    """

    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oeil-browser")
        self._fetcher = None

    def _fetch_sync(self, url: str):
        if self._fetcher is None:
            from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
            f = WafBrowserFetcher(settle_ms=1500, networkidle_ms=8000)
            f.__enter__()
            self._fetcher = f
        return self._fetcher.fetch(url, expand_accordions=False, strip_chrome=False,
                                   wait_for_selector="#section3")

    async def fetch(self, url: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, self._fetch_sync, url)

    def _close_sync(self):
        if self._fetcher is not None:
            try:
                self._fetcher.__exit__(None, None, None)
            finally:
                self._fetcher = None

    async def close(self):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(self._pool, self._close_sync)
        finally:
            self._pool.shutdown(wait=False)


def _clean_group(raw: str) -> Tuple[str, Optional[str]]:
    """'CANFIN Pascal (Renew)' -> ('CANFIN Pascal', 'Renew').

    The old pattern only allowed capitals, '&' and '/', so Renew, PfE, The Left
    and Greens/EFA stayed glued to the surname.
    """
    m = re.search(r"\(([^()]{2,30})\)\s*$", raw)
    if m:
        return raw[:m.start()].strip(), m.group(1).strip()
    return raw.strip(), None


def _dmy(text: str) -> Optional[date]:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


class OEILScraper(BaseScraper):
    """
    Scraper for OEIL Legislative Observatory.

    PHASE 4 UPGRADE:
    - Primary: XML export functionality
    - RSS feeds for real-time procedure updates
    - Third-party: api.epdb.eu integration
    - Fallback: Web scraping

    PHASE 5 UPGRADE:
    - Full web scraping of procedure pages
    - All 7 sections extraction
    - MEP data with photos
    - Complete document gateway

    Key Features:
    - Legislative procedure tracking
    - Document status and timeline
    - RSS monitoring for updates
    - Committee opinions and amendments
    """

    # URL patterns. oeil.europarl.europa.eu is the canonical host: since at least
    # 15 Sep 2026 oeil.secure.* answers a 307 to it (see classify_oeil_response).
    PROCEDURE_URL = "https://oeil.europarl.europa.eu/oeil/en/procedure-file"
    PROCEDURE_URL_LEGACY = "https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do"
    MEP_URL_PATTERN = re.compile(r'/meps/en/(\d+)')
    DATE_PATTERN = re.compile(r'(\d{2})/(\d{2})/(\d{4})')

    def __init__(self, use_api: bool = True, allow_browser_fallback: bool = False, **kwargs):
        # use_api is consumed HERE and never forwarded. BaseScraper does not
        # accept it, so while it rode in **kwargs any caller writing the
        # apparently-harmless OEILScraper(use_api=True) got a TypeError -- and
        # the one caller that did, the on-demand OEIL fetch in the context
        # builder, lost its entire legislative-files block to the outer
        # handler (audit 17 Aug 2026).
        super().__init__(
            base_url="https://oeil.europarl.europa.eu/oeil/en",
            name="OEIL",
            rate_limit_delay=2.0,
            **kwargs
        )

        # PHASE 4: Initialize API client
        self.api_client = OEILClient()
        self.use_api = use_api

        # Procedure-page fetching: which route served each page, and how many
        # failed. Callers print this so "0 updated" can never hide "0 fetched".
        # The browser fallback is OPT-IN: batch jobs that close() the scraper
        # turn it on; request-path callers (chat context builder, API routes)
        # construct OEILScraper() per request without closing it, and must not
        # launch Chromium there. With it off a walled page still raises
        # OEILFetchError rather than returning an empty procedure.
        self.allow_browser_fallback = allow_browser_fallback
        self._browser: Optional[_BrowserLane] = None
        self.fetch_stats: Counter = Counter()

        logger.info("OEIL Scraper initialized with API client")

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search OEIL legislative procedures.

        PHASE 4: RSS feeds for search

        Args:
            query: Search query
            **kwargs: Additional parameters

        Returns:
            List of procedures
        """
        if self.use_api:
            try:
                logger.info(f"Searching OEIL procedures: {query}")
                # Would use RSS feeds or XML export
                procedures = await self.api_client.get_latest_procedures(hours=168)  # 1 week

                # Filter by query
                results = [p for p in procedures if query.lower() in p['title'].lower()]
                return results
            except Exception as e:
                logger.error(f"OEIL search failed: {str(e)}")

        return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get procedure document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document data
        """
        # Would use XML export or web scraping
        logger.info(f"Fetching OEIL document: {document_id}")
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest procedure updates via RSS.

        PHASE 4: RSS feeds

        Args:
            limit: Maximum results

        Returns:
            Latest updates
        """
        if self.use_api:
            try:
                logger.info("Fetching latest OEIL updates via RSS")
                procedures = await self.api_client.get_latest_procedures(hours=24)
                return procedures[:limit]
            except Exception as e:
                logger.error(f"RSS fetch failed: {str(e)}")

        return []

    async def get_procedure(self, procedure_ref: str) -> Dict[str, Any]:
        """
        Get specific legislative procedure by reference.

        PHASE 5: Now uses full web scraping implementation.

        Args:
            procedure_ref: Procedure reference (e.g., "2021/0106(COD)")

        Returns:
            Procedure data with timeline as dictionary
        """
        try:
            procedure = await self.get_procedure_full(procedure_ref)
            return procedure.model_dump()
        except Exception as e:
            logger.error(f"Failed to get procedure {procedure_ref}: {e}")
            return {"error": str(e), "reference": procedure_ref}

    async def get_procedures_by_type(
        self,
        procedure_type: str,
        hours: int = 168
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get procedures by type using RSS

        Args:
            procedure_type: Type (ordinary_legislative, consultation, consent, etc.)
            hours: Time window in hours

        Returns:
            List of procedures
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info(f"Fetching {procedure_type} procedures")
            procedures = await self.api_client.get_latest_procedures(
                hours=hours,
                procedure_type=procedure_type
            )
            return procedures
        except Exception as e:
            logger.error(f"Failed to fetch procedures: {str(e)}")
            return []

    async def export_procedures(
        self,
        date_from: datetime,
        date_to: Optional[datetime] = None
    ) -> Optional[str]:
        """
        PHASE 4: New method - Export procedure data as XML

        Args:
            date_from: Start date
            date_to: End date

        Returns:
            XML data
        """
        if not self.use_api:
            raise NotImplementedError("XML export requires API client")

        try:
            logger.info(f"Exporting OEIL data from {date_from}")
            xml_data = await self.api_client.export_procedure_data(date_from, date_to)
            return xml_data
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            return None

    async def close(self):
        """Close API client connections and the fallback browser, if launched."""
        if getattr(self, '_browser', None) is not None:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"OEIL: browser close failed: {type(e).__name__}: {e}")
            self._browser = None
        if hasattr(self, 'api_client'):
            await self.api_client.close()
            logger.info("Closed OEIL API client")

    # =========================================================================
    # PHASE 5: Full Procedure Web Scraping
    # =========================================================================

    async def get_procedure_full(self, procedure_ref: str) -> OEILProcedure:
        """
        Fetch and parse complete OEIL procedure page.

        Extracts all 7 sections:
        1. Basic Information
        2. Key Players
        3. Key Events
        4. Forecasts
        5. Technical Information
        6. Documentation Gateway
        7. Additional Information

        Args:
            procedure_ref: Procedure reference (e.g., "2024/0176(COD)")

        Returns:
            OEILProcedure with all sections populated

        Raises:
            ScraperError: On fetch or parse failure
        """
        procedure, _page = await self.get_procedure_with_page(procedure_ref)
        return procedure

    async def get_procedure_with_page(self, procedure_ref: str) -> Tuple[OEILProcedure, OEILPage]:
        """Fetch, parse and VALIDATE a procedure page; also return the raw page.

        Raises OEILFetchError when neither route yields a page with a title or
        a key event. It never returns an empty procedure: an empty result used
        to be indistinguishable from "OEIL lists no events", and the update
        script counted it as a skip, not an error.
        """
        logger.info(f"Fetching full procedure: {procedure_ref}")
        url = f"{self.PROCEDURE_URL}?reference={procedure_ref}"
        try:
            page = await self._fetch_procedure_page(procedure_ref, url)
            procedure = self.parse_procedure_html(page.html, procedure_ref, page.url)

            if not self._has_substance(procedure) and page.route == "http" \
                    and self.allow_browser_fallback:
                # A 200 that parses to nothing is the other face of a WAF.
                logger.warning(f"OEIL {procedure_ref}: HTTP 200 parsed to nothing; "
                               f"retrying through the browser")
                page = await self._browser_fetch(procedure_ref, url, page.http_status)
                procedure = self.parse_procedure_html(page.html, procedure_ref, page.url)

            if not self._has_substance(procedure):
                raise OEILFetchError(procedure_ref, "page parsed to no title and no key events",
                                     status=page.http_status, route=page.route)

            self.fetch_stats[f"ok_{page.route}"] += 1
            logger.info(f"Successfully parsed procedure {procedure_ref} via {page.route} "
                        f"({len(procedure.key_events.events)} events, "
                        f"{len(procedure.forecasts.forecasts)} forecasts)")
            return procedure, page

        except OEILFetchError as e:
            self.fetch_stats["failed"] += 1
            logger.error(f"[ERROR] {e}")
            raise
        except Exception as e:
            self.fetch_stats["failed"] += 1
            logger.error(f"Failed to parse procedure {procedure_ref}: {type(e).__name__}: {e}")
            raise ScraperError(f"Failed to parse procedure {procedure_ref}: {str(e)}") from e

    @staticmethod
    def _has_substance(procedure: OEILProcedure) -> bool:
        return bool(procedure.key_events.events or procedure.basic_info.title)

    def parse_procedure_html(self, html: str, procedure_ref: str, url: str) -> OEILProcedure:
        """Parse all 7 sections of an OEIL procedure page (no network)."""
        soup = self._parse_html(html)
        return OEILProcedure(
            source_url=url,
            basic_info=self._parse_basic_info(soup, procedure_ref),
            key_players=self._parse_key_players(soup),
            key_events=self._parse_key_events(soup),
            forecasts=self._parse_forecasts(soup),
            technical_info=self._parse_technical_info(soup, procedure_ref),
            documentation=self._parse_documentation(soup),
            additional_info=self._parse_additional_info(soup),
        )

    async def _http_get_no_redirect(self, url: str) -> Tuple[int, str, Optional[str]]:
        """One GET, redirects NOT followed, so the caller sees what OEIL said."""
        domain = _extract_domain(url)
        if self._coordinator:
            await self._coordinator.acquire(domain)
        else:
            await self._rate_limit()
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=headers, allow_redirects=False) as resp:
                    body = await resp.text(errors="replace")
                    self.stats['requests_made'] += 1
                    self.stats['total_bytes'] += len(body)
                    return resp.status, body, resp.headers.get('Location')
        finally:
            if self._coordinator:
                self._coordinator.release(domain)

    async def _fetch_procedure_page(self, procedure_ref: str, url: str) -> OEILPage:
        status: Optional[int] = None
        current = url
        for _hop in range(3):
            try:
                status, body, location = await self._http_get_no_redirect(current)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # One retry on transport failure; the browser would not help.
                logger.warning(f"OEIL {procedure_ref}: transport error {type(e).__name__}; retrying once")
                await asyncio.sleep(2.0)
                try:
                    status, body, location = await self._http_get_no_redirect(current)
                except (aiohttp.ClientError, asyncio.TimeoutError) as e2:
                    raise OEILFetchError(procedure_ref, f"transport error {type(e2).__name__}: {e2}",
                                         route="http") from e2

            verdict = classify_oeil_response(status, body, location)
            if verdict == "ok":
                return OEILPage(procedure_ref, current, body, "http", status)
            if verdict == "redirect":
                nxt = urljoin(current, location)
                logger.info(f"OEIL {procedure_ref}: HTTP {status} moved to {nxt}")
                current = nxt
                continue
            if verdict == "not_found":
                raise OEILFetchError(procedure_ref, "no such procedure on OEIL", status=status, route="http")
            if verdict == "waf":
                logger.warning(f"OEIL {procedure_ref}: HTTP {status} ({len(body or '')} bytes"
                               f"{', Location ' + location if location else ''}) looks walled; "
                               f"falling back to the browser")
                if not self.allow_browser_fallback:
                    raise OEILFetchError(procedure_ref, "walled response and browser fallback disabled",
                                         status=status, route="http")
                return await self._browser_fetch(procedure_ref, current, status)
            raise OEILFetchError(procedure_ref, "unexpected HTTP answer", status=status, route="http")
        raise OEILFetchError(procedure_ref, "too many redirects", status=status, route="http")

    async def _browser_fetch(self, procedure_ref: str, url: str, http_status: Optional[int]) -> OEILPage:
        self.fetch_stats["browser_attempts"] += 1
        try:
            if self._browser is None:
                self._browser = _BrowserLane()
            result = await self._browser.fetch(url)
        except ImportError as e:
            raise OEILFetchError(procedure_ref, f"browser fallback unavailable: {e}",
                                 status=http_status, route="browser") from e
        if result.error or not looks_like_procedure_page(result.html):
            raise OEILFetchError(
                procedure_ref,
                f"browser fallback got nothing parseable ({result.error or f'{len(result.html)} bytes of HTML'})",
                status=result.nav_status or http_status, route="browser")
        return OEILPage(procedure_ref, result.url, result.html, "browser", result.nav_status)

    # =========================================================================
    # Section Parsers
    # =========================================================================

    def _parse_basic_info(self, soup: BeautifulSoup, procedure_ref: str) -> OEILBasicInfo:
        """Parse Section 1: Basic Information - Direct search approach"""
        basic_info = OEILBasicInfo(reference=procedure_ref)

        try:
            # Line-based extraction FIRST (fixed 3 Sep 2026). OEIL renders
            # label-then-value, and the real procedure title is the line after
            # "Full procedure". The <title> tag is only ever
            # "Procedure File: <ref> | Legislative Observatory | ...", which is
            # the page furniture; taking it produced a title of
            # "Procedure File: 2023/0437(COD)" for every single procedure.
            lines = _oeil_lines(soup)
            real_title = _value_after(lines, "Full procedure")
            if real_title and len(real_title) > 10 and not real_title.startswith("20"):
                basic_info.title = real_title
            else:
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text(strip=True)
                    if '|' in title_text:
                        title_text = title_text.split('|')[0].strip()
                    if title_text and not title_text.startswith('20'):
                        basic_info.title = title_text

            # Search entire page text for key patterns
            page_text = soup.get_text()

            # Procedure type (COD, CNS, etc.)
            type_match = re.search(r'(COD|CNS|APP|BUD|NLE)\s*[-–:]\s*([A-Z][^\n]{10,80})', page_text)
            if type_match:
                basic_info.procedure_type_code = type_match.group(1)
                basic_info.procedure_type = f"{type_match.group(1)} - {type_match.group(2).strip()}"

            # Status: the line after the "Status" label, or after
            # "Stage reached in procedure" on the technical-information block.
            # The old code matched a regex and then assigned group(0) -- the
            # WHOLE match, label included -- so every procedure reported its
            # status as the literal string "Stage reached in procedure".
            status = (_value_after(lines, "Status")
                      or _value_after(lines, "Stage reached in procedure"))
            if status:
                basic_info.status = status

            # Subjects - look for subject/theme links anywhere in page
            subject_links = soup.find_all('a', href=re.compile(r'subject|theme|policy-area'))
            for link in subject_links:
                subject = link.get_text(strip=True)
                if subject and len(subject) > 3 and subject not in basic_info.subjects:
                    basic_info.subjects.append(subject)

            # Also look for list items containing subject codes like "3.40.01"
            for li in soup.find_all('li'):
                li_text = li.get_text(strip=True)
                if re.match(r'\d+\.\d+(?:\.\d+)?', li_text):
                    if li_text not in basic_info.subjects:
                        basic_info.subjects.append(li_text)

        except Exception as e:
            logger.warning(f"Error parsing basic info: {e}")

        return basic_info

    def _parse_key_players(self, soup: BeautifulSoup) -> OEILKeyPlayers:
        """Parse Section 2: Key Players.

        Table-first (15 Sep 2026): OEIL renders each role as its own table whose
        header cell names the role ("Committee responsible", "Committee for
        opinion", ...). The old code treated the first MEP link on the page as
        the rapporteur and EVERY other MEP link as a shadow, so opinion
        rapporteurs became shadows of the lead committee and no opinion
        committee was ever returned. The line-based code below stays as the
        fallback for pages without those tables.
        """
        dom = self._parse_key_players_tables(soup)
        if dom is not None:
            return dom

        key_players = OEILKeyPlayers()

        try:
            page_text = soup.get_text()

            # Committee codes pattern
            committee_codes = ['IMCO', 'LIBE', 'JURI', 'ITRE', 'ENVI', 'AFET', 'AFCO', 'BUDG',
                              'CONT', 'ECON', 'EMPL', 'INTA', 'TRAN', 'REGI', 'AGRI', 'PECH',
                              'CULT', 'DROI', 'PETI', 'FEMM', 'DEVE', 'SEDE']

            # Find all MEP links on the page
            mep_links = soup.find_all('a', href=re.compile(r'/meps/en/\d+'))

            # First MEP is usually the rapporteur for main committee
            if mep_links:
                first_mep = self._parse_mep_from_link(mep_links[0])

                # The committee RESPONSIBLE is the one printed under that
                # label, not the first code that happens to appear on the page.
                #
                # The old code walked a hardcoded list in fixed order and took
                # the first member found anywhere in the text. IMCO is first in
                # that list, so every page mentioning IMCO for any reason -- an
                # opinion committee, a cross-reference, a related procedure --
                # reported IMCO as responsible. Measured 3 Sep 2026: passenger
                # rights came back IMCO when its dossier is TRAN/10/00285, and
                # the psychosocial-risks file came back JURI when the
                # responsible committee is EMPL. The rapporteur was right in
                # both cases, so a correct name was being paired with the wrong
                # committee. [[feedback_first_match_on_a_page_is_a_related_entity]]
                lines = _oeil_lines(soup)
                committee_code = None
                committee_name = None
                try:
                    idx = lines.index('Committee responsible')
                except ValueError:
                    idx = None
                if idx is not None:
                    for j in range(idx + 1, min(idx + 8, len(lines))):
                        if lines[j] in committee_codes:
                            committee_code = lines[j]
                            if j + 1 < len(lines) and lines[j + 1] not in _OEIL_LABELS:
                                committee_name = lines[j + 1]
                            break
                if not committee_code:
                    # Fall back to the old scan, but say so rather than pass a
                    # guess off as a reading.
                    for code in committee_codes:
                        if code in page_text:
                            committee_code = code
                            logger.warning(
                                "OEIL: no 'Committee responsible' block found; "
                                "fell back to first code on page (%s)", code)
                            break

                if first_mep:
                    committee = OEILCommittee(
                        code=committee_code or 'UNKNOWN',
                        name=committee_name,
                        role='responsible',
                        rapporteur=first_mep,
                        shadow_rapporteurs=[]
                    )

                    # Remaining MEPs could be shadows
                    for link in mep_links[1:]:
                        shadow = self._parse_mep_from_link(link)
                        if shadow:
                            committee.shadow_rapporteurs.append(shadow)

                    key_players.committee_responsible = committee

            # Commission DG - search for pattern like "DG SANTE", "DG GROW"
            dg_match = re.search(r'DG\s+([A-Z]{3,})', page_text)
            if dg_match:
                key_players.commission_dg = f"DG {dg_match.group(1)}"

            # Also look for "Directorate-General" pattern
            if not key_players.commission_dg:
                dg_match = re.search(r'Directorate-General\s+(?:for\s+)?([A-Z][^,\n]+)', page_text)
                if dg_match:
                    key_players.commission_dg = dg_match.group(0).strip()

            # Commissioner - try multiple patterns
            # Pattern 1: "Commissioner Name SURNAME" or "Commissioner: Name SURNAME"
            commissioner_match = re.search(
                r'Commissioner[:\s]+([A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][a-zàáâäéèêëíîïóôöúûü]+(?:\s+[A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜa-zàáâäéèêëíîïóôöúûü]+)+)',
                page_text
            )
            if commissioner_match:
                name = commissioner_match.group(1).strip()
                # Skip if it's just a portfolio like "Justice" or "Internal Market"
                portfolio_words = ['justice', 'internal', 'market', 'digital', 'economy', 'trade',
                                   'environment', 'health', 'transport', 'energy', 'agriculture',
                                   'budget', 'cohesion', 'democracy', 'values', 'transparency']
                if not name.lower().split()[0] in portfolio_words:
                    key_players.commissioner = name

            # Pattern 2: "Name SURNAME, Commissioner" or "Name SURNAME (Commissioner)"
            if not key_players.commissioner:
                commissioner_match2 = re.search(
                    r'([A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][a-zàáâäéèêëíîïóôöúûü]+(?:\s+[A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ]+)+)[,\s]+(?:\()?Commissioner',
                    page_text
                )
                if commissioner_match2:
                    key_players.commissioner = commissioner_match2.group(1).strip()

            # Pattern 3: Look for Commission section with responsible Commissioner
            if not key_players.commissioner:
                # Try to find in structured sections
                commission_section = re.search(
                    r'European Commission[:\s]*([A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ][a-zàáâäéèêëíîïóôöúûü]+\s+[A-ZÀÁÂÄÉÈÊËÍÎÏÓÔÖÚÛÜ]+)',
                    page_text
                )
                if commission_section:
                    key_players.commissioner = commission_section.group(1).strip()

            # Council configuration
            council_match = re.search(r'Council\s*(?:of\s+the\s+EU)?[:\s]+([A-Z][^,\n]+)', page_text)
            if council_match:
                key_players.council_configuration = council_match.group(1).strip()

            # Consultative bodies - EESC
            if 'Economic and Social Committee' in page_text or 'EESC' in page_text:
                key_players.eesc = OEILConsultativeBody(body='EESC')

            # Committee of the Regions
            if 'Committee of the Regions' in page_text or 'CoR' in page_text:
                key_players.cor = OEILConsultativeBody(body='CoR')

        except Exception as e:
            logger.warning(f"Error parsing key players: {e}")

        return key_players

    @staticmethod
    def _section_table(soup: BeautifulSoup, section_id: str, headers: Tuple[str, ...]) -> Optional[Tag]:
        """The table of an OEIL section: inside div#sectionN when present, else
        any table whose leading header cells read `headers` (the Forecasts
        table also starts with "Date", so one header is not enough)."""
        div = soup.find('div', id=section_id)
        candidates = div.find_all('table') if div else soup.find_all('table')
        want = [h.lower() for h in headers]
        for t in candidates:
            got = [th.get_text(strip=True).lower() for th in t.find_all('th')[:len(want)]]
            if got == want:
                return t
        return None

    def _parse_key_events(self, soup: BeautifulSoup) -> OEILKeyEvents:
        """Parse Section 3: Key Events from the Date / Event / Reference table.

        Rewritten 15 Sep 2026. The old version scanned every date on the page
        and guessed an event type from the 250 characters around the FIRST
        occurrence of that date, then de-duplicated by date. On 2026/0074(COD)
        the referral date 18/05/2026 first appears as an opinion rapporteur's
        appointment date, so the referral was lost and only 1 of 2 events came
        back; on busier pages it minted "Committee report" events out of
        appointment dates. Every row is now read from the table, in order,
        with OEIL's own event wording (callers match by substring).
        """
        key_events = OEILKeyEvents()
        table = self._section_table(soup, 'section3', ('Date', 'Event'))
        if table is None:
            logger.warning("OEIL: no Key events table on the page")
            return key_events
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]
        for tr in rows:
            cells = tr.find_all('td')
            if len(cells) < 2:
                continue
            ev_date = _dmy(cells[0].get_text(" ", strip=True))
            ev_type = cells[1].get_text(" ", strip=True)
            if not ev_date or not ev_type:
                continue
            event = OEILEvent(date=ev_date, event_type=ev_type)
            if len(cells) > 2:
                for a in cells[2].find_all('a'):
                    text = a.get_text(" ", strip=True)
                    if text and a.get('href'):
                        event.documents.append(OEILDocument(
                            reference=text, url=self._make_absolute_url(a['href'])))
                ref_text = cells[2].get_text(" ", strip=True)
                if ref_text:
                    event.description = ref_text
            if len(cells) > 3:
                link = cells[3].find('a', href=True)
                if link:
                    event.summary = self._make_absolute_url(link['href'])
            key_events.events.append(event)
        return key_events

    def _parse_forecasts(self, soup: BeautifulSoup) -> OEILForecasts:
        """Parse Section 4: Forecasts from the Date / Subject table.

        The old version called _find_section, whose text fallback matched the
        word "Forecasts" in the page navigation and returned a container with
        no table, so no forecast was ever read (0 of 6 test refs).
        """
        forecasts = OEILForecasts()
        div = soup.find('div', id='section4')
        table = None
        if div is not None:
            table = div.find('table')
        else:
            for t in soup.find_all('table'):
                heads = [th.get_text(strip=True).lower() for th in t.find_all('th')[:2]]
                if heads == ['date', 'subject']:
                    table = t
                    break
        if table is None:
            return forecasts   # many procedures legitimately have no forecast
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]
        for tr in rows:
            cells = tr.find_all('td')
            if len(cells) < 2:
                continue
            subject = cells[1].get_text(" ", strip=True)
            if not subject:
                continue
            fc = OEILForecast(event_type=subject, forecast_date=_dmy(cells[0].get_text(" ", strip=True)))
            if 'plenary' in subject.lower():
                fc.location = 'Plenary'
            else:
                comm = re.search(r'\b([A-Z]{4})\b', subject)
                if comm:
                    fc.committee = comm.group(1)
                    fc.location = 'Committee'
            forecasts.forecasts.append(fc)
        return forecasts

    # Header of each Key players table -> role. "Former ..." tables are history
    # and must not overwrite the current roles.
    _ROLE_HEADERS = {
        'committee responsible': 'responsible',
        'committee for opinion': 'opinion',
        'committee for budgetary assessment': 'budgetary_assessment',
        'joint committee responsible': 'responsible',
    }

    def _parse_key_players_tables(self, soup: BeautifulSoup) -> Optional[OEILKeyPlayers]:
        """Table-based Key players parse. None when the page has no such tables."""
        div = soup.find('div', id='section2')
        tables = div.find_all('table') if div else []
        role_tables = []
        for t in tables:
            th = t.find('th')
            head = th.get_text(" ", strip=True).lower() if th else ''
            role_tables.append((head, t))
        if not any(h in self._ROLE_HEADERS or h.startswith('former committee') for h, _ in role_tables):
            return None

        kp = OEILKeyPlayers()
        for head, table in role_tables:
            if head == 'commission dg':
                body = table.find('tbody') or table
                tr = body.find('tr')
                if tr:
                    cells = tr.find_all(['th', 'td'])
                    if cells:
                        kp.commission_dg = cells[0].get_text(" ", strip=True) or None
                    if len(cells) > 1:
                        kp.commissioner = cells[1].get_text(" ", strip=True) or None
                continue
            role = self._ROLE_HEADERS.get(head)
            if role is None:
                continue   # "Former committee ..." and anything unknown
            for committee in self._committee_rows(table, role):
                if committee.role == 'responsible' and kp.committee_responsible is None:
                    kp.committee_responsible = committee
                elif 'associated' in committee.role:
                    kp.committees_associated.append(committee)
                else:
                    kp.committees_opinion.append(committee)

        page_text = soup.get_text(" ")
        if 'European Economic and Social Committee' in page_text:
            kp.eesc = OEILConsultativeBody(body='EESC')
        if 'European Committee of the Regions' in page_text or 'Committee of the Regions' in page_text:
            kp.cor = OEILConsultativeBody(body='CoR')
        return kp

    def _committee_rows(self, table: Tag, role: str) -> List[OEILCommittee]:
        out: List[OEILCommittee] = []
        body = table.find('tbody') or table
        for tr in body.find_all('tr', recursive=False):
            badge = tr.find(class_=re.compile(r'es_badge-committee'))
            cells = tr.find_all(['th', 'td'], recursive=False)
            if badge is None:
                # The "Shadow rapporteur" row belongs to the committee above it.
                if out:
                    for a in tr.find_all('a', href=self.MEP_URL_PATTERN):
                        mep = self._parse_mep_from_link(a)
                        if mep:
                            out[-1].shadow_rapporteurs.append(mep)
                continue
            code = badge.get_text(strip=True)
            name_el = cells[0].find('span', class_=re.compile(r'font-weight-normal')) if cells else None
            name_cell_text = cells[0].get_text(" ", strip=True) if cells else ''
            this_role = role
            if 'associated committee' in name_cell_text.lower():
                this_role = f"{role}_associated"
            rap_cell = cells[1] if len(cells) > 1 else None
            if rap_cell is not None and 'decided not to give an opinion' in rap_cell.get_text(" ", strip=True).lower():
                this_role = f"{this_role}_declined"
            committee = OEILCommittee(
                code=code,
                name=name_el.get_text(" ", strip=True) if name_el else None,
                role=this_role,
            )
            if rap_cell is not None:
                links = rap_cell.find_all('a', href=self.MEP_URL_PATTERN)
                if links:
                    committee.rapporteur = self._parse_mep_from_link(links[0])
                    for extra in links[1:]:   # co-rapporteurs
                        mep = self._parse_mep_from_link(extra)
                        if mep:
                            committee.shadow_rapporteurs.append(mep)
            if len(cells) > 2:
                committee.date_announced = _dmy(cells[2].get_text(" ", strip=True))
            out.append(committee)
        return out

    def _parse_technical_info(self, soup: BeautifulSoup, procedure_ref: str) -> OEILTechnicalInfo:
        """Parse Section 5: Technical Information"""
        tech_info = OEILTechnicalInfo(reference=procedure_ref)

        try:
            tech_section = self._find_section(soup, 'Technical information')
            if not tech_section:
                return tech_info

            # Procedure type
            type_row = self._find_row_by_label(tech_section, 'Procedure type')
            if type_row:
                tech_info.procedure_type = type_row.get_text(strip=True)

            # Procedure subtype
            subtype_row = self._find_row_by_label(tech_section, 'Procedure subtype')
            if subtype_row:
                tech_info.procedure_subtype = subtype_row.get_text(strip=True)

            # Legal basis
            legal_row = self._find_row_by_label(tech_section, 'Legal basis')
            if legal_row:
                legal_links = legal_row.find_all('a')
                for link in legal_links:
                    text = link.get_text(strip=True)
                    href = link.get('href', '')
                    # Parse treaty and article
                    treaty_match = re.match(r'(TFEU|TEU|Euratom)', text)
                    if treaty_match:
                        tech_info.legal_basis.append(OEILLegalBasis(
                            treaty=treaty_match.group(1),
                            article=text,
                            url=href
                        ))

            # Stage reached
            stage_row = self._find_row_by_label(tech_section, 'Stage reached')
            if stage_row:
                tech_info.stage_reached = stage_row.get_text(strip=True)

            # Commission reference
            comm_ref_row = self._find_row_by_label(tech_section, 'Commission DG')
            if comm_ref_row:
                tech_info.commission_reference = comm_ref_row.get_text(strip=True)

        except Exception as e:
            logger.warning(f"Error parsing technical info: {e}")

        return tech_info

    def _parse_documentation(self, soup: BeautifulSoup) -> OEILDocumentation:
        """Parse Section 6: Documentation Gateway - Direct search approach"""
        docs = OEILDocumentation()

        try:
            # Find all document links by their patterns
            # COM documents (Commission)
            com_links = soup.find_all('a', string=re.compile(r'COM\(\d{4}\)\d+'))
            for link in com_links:
                ref = link.get_text(strip=True)
                url = link.get('href', '')
                docs.commission_documents.append(OEILDocument(
                    reference=ref,
                    url=self._make_absolute_url(url) if url else None,
                    doc_type='COM'
                ))

            # EP documents (A9-xxx, PE-xxx)
            ep_patterns = [
                r'A\d+-\d+/\d+',  # Report: A9-0123/2024
                r'PE\d+\.\d+',    # PE number
            ]
            for pattern in ep_patterns:
                ep_links = soup.find_all('a', string=re.compile(pattern))
                for link in ep_links:
                    ref = link.get_text(strip=True)
                    url = link.get('href', '')
                    docs.ep_documents.append(OEILDocument(
                        reference=ref,
                        url=self._make_absolute_url(url) if url else None,
                        doc_type='EP'
                    ))

            # Council documents (ST xxx)
            council_links = soup.find_all('a', string=re.compile(r'ST\s*\d+'))
            for link in council_links:
                ref = link.get_text(strip=True)
                url = link.get('href', '')
                docs.council_documents.append(OEILDocument(
                    reference=ref,
                    url=self._make_absolute_url(url) if url else None,
                    doc_type='Council'
                ))

            # PDF links
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf'))
            for link in pdf_links:
                text = link.get_text(strip=True)
                url = link.get('href', '')
                if text and len(text) > 3:
                    docs.other_documents.append(OEILDocument(
                        reference=text[:50],
                        url=self._make_absolute_url(url),
                        pdf_url=self._make_absolute_url(url)
                    ))

            # National parliament contributions
            page_text = soup.get_text()
            parliament_names = [
                'German Bundestag', 'French Senate', 'French National Assembly',
                'Italian Senate', 'Italian Chamber', 'Spanish Congress',
                'Polish Sejm', 'Polish Senate', 'Dutch Senate', 'Dutch House',
                'Portuguese Parliament', 'Czech Senate', 'Czech Chamber',
                'Romanian Senate', 'Romanian Chamber', 'Austrian Parliament',
                'Belgian Senate', 'Belgian Chamber', 'Swedish Riksdag',
                'Danish Folketing', 'Finnish Parliament', 'Irish Houses',
            ]
            for parliament in parliament_names:
                if parliament in page_text:
                    docs.national_parliament_contributions.append(
                        OEILNationalParliamentContribution(
                            parliament=parliament,
                            contribution_type='Contribution'
                        )
                    )

        except Exception as e:
            logger.warning(f"Error parsing documentation: {e}")

        return docs

    def _parse_additional_info(self, soup: BeautifulSoup) -> OEILAdditionalInfo:
        """Parse Section 7: Additional Information - Direct search approach"""
        additional = OEILAdditionalInfo()

        try:
            # Find EUR-Lex link anywhere on the page
            eurlex_links = soup.find_all('a', href=re.compile(r'eur-lex\.europa\.eu'))
            for link in eurlex_links:
                url = link.get('href', '')
                if url:
                    additional.eurlex_url = url
                    # Extract CELEX from URL
                    celex_match = re.search(r'/(\d{5}[A-Z]\d{4})/', url)
                    if celex_match:
                        additional.celex_number = celex_match.group(1)
                    # Also try other CELEX patterns
                    if not additional.celex_number:
                        celex_match = re.search(r'CELEX[=:](\d+[A-Z]\d+)', url)
                        if celex_match:
                            additional.celex_number = celex_match.group(1)
                    break

            # Find related procedures - both old and new URL formats
            procedure_patterns = [
                r'ficheprocedure\.do',
                r'procedure-file\?reference=',
            ]
            for pattern in procedure_patterns:
                related_links = soup.find_all('a', href=re.compile(pattern))
                for link in related_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    # Extract procedure reference from URL
                    ref_match = re.search(r'reference=([^&]+)', href)
                    if ref_match:
                        ref = ref_match.group(1)
                        # Don't add the current procedure as related
                        if ref not in [p.get('reference') for p in additional.related_procedures]:
                            additional.related_procedures.append({
                                'reference': ref,
                                'title': text,
                                'url': self._make_absolute_url(href)
                            })

            # Find other useful links (EP Research, etc.)
            research_links = soup.find_all('a', href=re.compile(r'epthinktank|europarl\.europa\.eu/thinktank'))
            for link in research_links:
                text = link.get_text(strip=True)
                url = link.get('href', '')
                if text and url:
                    additional.other_links.append({
                        'text': text,
                        'url': self._make_absolute_url(url)
                    })

        except Exception as e:
            logger.warning(f"Error parsing additional info: {e}")

        return additional

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_section(self, soup: BeautifulSoup, section_title: str) -> Optional[Tag]:
        """Find a main section by its title and return all content until next section"""
        # New OEIL format (2025): sections use h2 headings
        for h2 in soup.find_all('h2'):
            if section_title.lower() in h2.get_text(strip=True).lower():
                # Collect all siblings until next h2
                content_elements = []
                for sibling in h2.find_next_siblings():
                    if sibling.name == 'h2':
                        break  # Stop at next section
                    content_elements.append(sibling)

                if content_elements:
                    # Create a wrapper to hold all content
                    from bs4 import NavigableString
                    wrapper = soup.new_tag('div')
                    for elem in content_elements:
                        if not isinstance(elem, NavigableString) or elem.strip():
                            wrapper.append(elem.extract() if hasattr(elem, 'extract') else elem)
                    # Re-insert elements (they were extracted)
                    for elem in content_elements:
                        try:
                            h2.insert_after(elem)
                        except:
                            pass
                    return wrapper if wrapper.contents else content_elements[0]

                # Fallback: return next sibling
                next_elem = h2.find_next_sibling()
                if next_elem:
                    return next_elem

                # Or return the parent container
                parent = h2.find_parent(['div', 'section', 'article'])
                if parent:
                    return parent

        # Look for headers with class containing section title
        headers = soup.find_all(['h2', 'h3', 'div'], class_=re.compile(r'section|header|title'))
        for header in headers:
            if section_title.lower() in header.get_text(strip=True).lower():
                parent = header.find_parent(['div', 'section', 'table'])
                if parent:
                    return parent
                return header.find_next_sibling()

        # Fallback: look for text containing section title
        for elem in soup.find_all(string=re.compile(section_title, re.IGNORECASE)):
            parent = elem.find_parent(['div', 'section', 'table', 'tr'])
            if parent:
                return parent

        return None

    def _find_subsection(self, section: Tag, subsection_title: str) -> Optional[Tag]:
        """Find a subsection within a section"""
        if not section:
            return None

        for elem in section.find_all(string=re.compile(subsection_title, re.IGNORECASE)):
            parent = elem.find_parent(['div', 'table', 'tr'])
            if parent:
                return parent

        return None

    def _find_row_by_label(self, container: Tag, label: str) -> Optional[Tag]:
        """Find a table row by its label text"""
        if not container:
            return None

        rows = container.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if cells and label.lower() in cells[0].get_text(strip=True).lower():
                # Return the value cell
                return cells[1] if len(cells) > 1 else cells[0]

        return None

    def _parse_mep_from_link(self, link: Tag) -> Optional[OEILMep]:
        """Extract MEP data from an anchor tag"""
        if not link:
            return None

        try:
            href = link.get('href', '')
            raw_name = link.get_text(strip=True)

            if not raw_name:
                return None

            # Clean name: remove political group if it's in the name text
            # Format is often "SURNAME Name (GROUP)" or just "SURNAME Name"
            # Any parenthesised tail is the group: Renew, PfE, The Left and
            # Greens/EFA all failed the old capitals-only pattern (15 Sep 2026).
            name, political_group = _clean_group(raw_name)

            mep = OEILMep(name=name, political_group=political_group)

            # Extract MEP ID from URL
            id_match = self.MEP_URL_PATTERN.search(href)
            if id_match:
                mep.mep_id = id_match.group(1)
                mep.profile_url = f"https://www.europarl.europa.eu/meps/en/{mep.mep_id}"
                # New format: photo URL from MEP ID
                mep.photo_url = f"https://www.europarl.europa.eu/mepphoto/{mep.mep_id}.jpg"

            # Also check for photo in data-title (legacy format)
            data_title = link.get('data-title', '')
            if data_title:
                img_match = re.search(r"src='([^']+)'", data_title)
                if img_match:
                    mep.photo_url = img_match.group(1)

            # Look for <img> tag inside or nearby (new format)
            img = link.find('img')
            if img and img.get('src'):
                mep.photo_url = img.get('src')

            # Extract political group from surrounding text if not found in name
            if not political_group:
                next_text = link.next_sibling
                if next_text and isinstance(next_text, str):
                    group_match = re.search(r'\(([A-Z&/]+(?:/[A-Z]+)?)\)', next_text)
                    if group_match:
                        mep.political_group = group_match.group(1)

            return mep

        except Exception as e:
            logger.debug(f"Error parsing MEP from link: {e}")
            return None

    def _parse_committee_from_table(self, table: Tag, role: str) -> Optional[OEILCommittee]:
        """Parse committee information from a table"""
        if not table:
            return None

        try:
            # Find committee code - usually in first cell
            first_cell = table.find('td')
            if not first_cell:
                return None

            code_text = first_cell.get_text(strip=True)
            code_match = re.match(r'^([A-Z]{4})', code_text)
            if not code_match:
                return None

            committee = OEILCommittee(
                code=code_match.group(1),
                role=role
            )

            # Find rapporteur link
            rapporteur_links = table.find_all('a', href=re.compile(r'/meps/'))
            if rapporteur_links:
                committee.rapporteur = self._parse_mep_from_link(rapporteur_links[0])

                # Remaining links are shadow rapporteurs
                for link in rapporteur_links[1:]:
                    shadow = self._parse_mep_from_link(link)
                    if shadow:
                        committee.shadow_rapporteurs.append(shadow)

            # Parse dates from text
            text = table.get_text()
            date_matches = self.DATE_PATTERN.findall(text)
            if date_matches:
                # First date is usually announcement date
                d, m, y = date_matches[0]
                committee.date_announced = date(int(y), int(m), int(d))

            return committee

        except Exception as e:
            logger.debug(f"Error parsing committee: {e}")
            return None

    def _parse_event_row(self, cells: List[Tag]) -> Optional[OEILEvent]:
        """Parse an event from table cells"""
        if len(cells) < 2:
            return None

        try:
            # First cell usually contains date
            date_text = cells[0].get_text(strip=True)
            date_match = self.DATE_PATTERN.search(date_text)
            if not date_match:
                return None

            d, m, y = date_match.groups()
            event_date = date(int(y), int(m), int(d))

            # Second cell contains event type/description
            event_type = cells[1].get_text(strip=True) if len(cells) > 1 else ''

            event = OEILEvent(
                date=event_date,
                event_type=event_type
            )

            # Look for additional details in remaining cells
            if len(cells) > 2:
                event.description = cells[2].get_text(strip=True)

            # Extract any document links
            for cell in cells:
                doc_links = cell.find_all('a')
                for link in doc_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if text and href:
                        event.documents.append(OEILDocument(
                            reference=text,
                            url=self._make_absolute_url(href)
                        ))

            return event

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _parse_forecast_row(self, cells: List[Tag]) -> Optional[OEILForecast]:
        """Parse a forecast from table cells"""
        if len(cells) < 2:
            return None

        try:
            event_type = cells[0].get_text(strip=True)
            if not event_type:
                return None

            forecast = OEILForecast(event_type=event_type)

            # Parse date from second cell
            date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            date_match = self.DATE_PATTERN.search(date_text)
            if date_match:
                d, m, y = date_match.groups()
                forecast.forecast_date = date(int(y), int(m), int(d))

            # Check for committee or plenary
            full_text = ' '.join(c.get_text(strip=True) for c in cells)
            if 'plenary' in full_text.lower():
                forecast.location = 'Plenary'
            else:
                comm_match = re.search(r'\b([A-Z]{4})\b', full_text)
                if comm_match:
                    forecast.committee = comm_match.group(1)
                    forecast.location = 'Committee'

            return forecast

        except Exception as e:
            logger.debug(f"Error parsing forecast: {e}")
            return None

    def _parse_document_row(self, row: Tag) -> Optional[OEILDocument]:
        """Parse a document from a table row"""
        if not row:
            return None

        try:
            cells = row.find_all('td')
            if not cells:
                return None

            # Find document reference - usually in a link
            link = row.find('a')
            if link:
                reference = link.get_text(strip=True)
                url = link.get('href', '')
            else:
                reference = cells[0].get_text(strip=True) if cells else ''
                url = ''

            if not reference:
                return None

            doc = OEILDocument(
                reference=reference,
                url=self._make_absolute_url(url) if url else None
            )

            # Parse date if present
            text = row.get_text()
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                d, m, y = date_match.groups()
                doc.date = date(int(y), int(m), int(d))

            # Look for PDF link
            pdf_link = row.find('a', href=re.compile(r'\.pdf'))
            if pdf_link:
                doc.pdf_url = self._make_absolute_url(pdf_link.get('href', ''))

            return doc

        except Exception as e:
            logger.debug(f"Error parsing document: {e}")
            return None

    def _parse_consultative_body(self, row: Tag, body: str) -> Optional[OEILConsultativeBody]:
        """Parse consultative body information"""
        if not row:
            return None

        try:
            text = row.get_text(strip=True)

            body_info = OEILConsultativeBody(
                body=body,
                opinion_mandatory='mandatory' in text.lower()
            )

            # Parse date
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                d, m, y = date_match.groups()
                body_info.opinion_date = date(int(y), int(m), int(d))

            return body_info

        except Exception as e:
            logger.debug(f"Error parsing consultative body: {e}")
            return None

    def _parse_national_parliament_contribution(self, item: Tag) -> Optional[OEILNationalParliamentContribution]:
        """Parse national parliament contribution"""
        if not item:
            return None

        try:
            text = item.get_text(strip=True)
            if not text:
                return None

            # Try to extract parliament name (usually at the start)
            # Common patterns: "German Bundestag", "French Senate", etc.
            contribution = OEILNationalParliamentContribution(
                parliament=text.split(':')[0].strip() if ':' in text else text[:50],
                contribution_type='Contribution'
            )

            # Check for specific contribution types
            if 'reasoned opinion' in text.lower():
                contribution.contribution_type = 'Reasoned opinion'
            elif 'political dialogue' in text.lower():
                contribution.contribution_type = 'Political dialogue'

            # Parse date
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                d, m, y = date_match.groups()
                contribution.date = date(int(y), int(m), int(d))

            # Look for link
            link = item.find('a')
            if link:
                contribution.url = self._make_absolute_url(link.get('href', ''))

            return contribution

        except Exception as e:
            logger.debug(f"Error parsing national parliament contribution: {e}")
            return None

    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from DD/MM/YYYY format"""
        if not text:
            return None

        match = self.DATE_PATTERN.search(text)
        if match:
            d, m, y = match.groups()
            try:
                return date(int(y), int(m), int(d))
            except ValueError:
                return None
        return None
