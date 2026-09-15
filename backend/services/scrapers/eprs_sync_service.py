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

import asyncio
import html as html_lib
import logging
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List, Optional, Tuple
import uuid

import httpx
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


# ---------------------------------------------------------------------------
# Sources (15 Sep 2026 rebuild)
#
# WHY: from ~23 July 2026 the EP Think Tank RSS answered the WAF signature
# (HTTP 202, zero bytes) to the non-browser User-Agent BaseRSSClient sends.
# httpx does not raise on 202, feedparser parses "" into zero entries, and the
# sync printed "Errors 0" for eight weeks while the table froze at 21 July.
# Every source below therefore reports a three-state result, and a WAF status
# or an unparseable body is an ERROR, never an empty feed.
# ---------------------------------------------------------------------------

THINKTANK_BASE = "https://www.europarl.europa.eu"
THINKTANK_LISTING_URL = f"{THINKTANK_BASE}/thinktank/en/research/advanced-search"
THINKTANK_RSS_URL = f"{THINKTANK_LISTING_URL}/rss"
THINKTANK_DOC_URL = f"{THINKTANK_BASE}/thinktank/en/document/"
BLOG_FEED_URL = "https://epthinktank.eu/feed/"

# The four types the table holds. Fact sheets / documentation re-date old
# documents (e.g. 04A_FT(2017)...) and are deliberately excluded.
THINKTANK_PUBLICATION_TYPES = ["AT_A_GLANCE", "BRIEFING", "IN_DEPTH_ANALYSIS", "STUDY"]

RSS_PAGE_SIZE = 25          # measured 15 Sep 2026; page index is 0-based
LISTING_PAGE_SIZE = 10      # measured 15 Sep 2026; page index is 0-based
LISTING_RESULT_CAP = 500    # "The number of results displayed is limited to 500"
MAX_RSS_PAGES = 25
MAX_BLOG_PAGES = 10
WAF_STATUSES = {202, 403, 429, 503}

_TYPE_LABELS = {
    'at a glance': EPRSPublicationTypeEnum.AT_A_GLANCE,
    'briefing': EPRSPublicationTypeEnum.BRIEFING,
    'in-depth analysis': EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS,
    'study': EPRSPublicationTypeEnum.STUDY,
}
_REF_TYPE_CODES = {
    'ATA': EPRSPublicationTypeEnum.AT_A_GLANCE,
    'BRI': EPRSPublicationTypeEnum.BRIEFING,
    'IDA': EPRSPublicationTypeEnum.IN_DEPTH_ANALYSIS,
    'STU': EPRSPublicationTypeEnum.STUDY,
}
_REF_RE = re.compile(r'([A-Z0-9]+_[A-Z]+\(\d{4}\)[A-Z0-9]+)')
_RSS_TITLE_RE = re.compile(
    r'^\s*(?P<label>[^-]+?)\s+-\s+(?P<title>.+?)\s+-\s+(?P<date>\d{2}-\d{2}-\d{4})\s*$',
    re.S,
)
_SHOWING_RE = re.compile(r'Showing\s+([\d,]+)\s+of\s+([\d,]+)\s+results', re.I)


class UnparseableSourceError(ValueError):
    """A 200 response whose body is not the document type we asked for."""


@dataclass
class SourceReport:
    """Three-state outcome of one source: ok / failed / (not run)."""
    name: str
    status: str = "not_run"        # "ok" | "failed" | "not_run"
    via: Optional[str] = None      # which route actually delivered items
    fetched: int = 0               # items fetched inside the window
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def is_waf_response(status: Optional[int], body: str) -> bool:
    """The EP WAF answers HTTP 202 with an empty body (or 403/429/503)."""
    if status in WAF_STATUSES:
        return True
    return status == 200 and not (body or "").strip()


def build_thinktank_params(start: datetime, end: datetime, page: int) -> List[Tuple[str, str]]:
    """Query string shared by the RSS and the HTML listing (dd/MM/yyyy)."""
    params = [
        ("startDate", start.strftime("%d/%m/%Y")),
        ("endDate", end.strftime("%d/%m/%Y")),
    ]
    params += [("publicationTypes", t) for t in THINKTANK_PUBLICATION_TYPES]
    if page:
        params.append(("page", str(page)))
    return params


def _parse_ddmmyyyy(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d-%m-%Y")
    except ValueError:
        return None


def _clean_summary(raw: Optional[str]) -> str:
    """Unescape, drop the '(c) European Union' Source trailer and tags."""
    if not raw:
        return ""
    text = html_lib.unescape(raw)
    text = re.split(r'Source\s*:', text, maxsplit=1)[0]
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _type_for(label: Optional[str], reference: str) -> EPRSPublicationTypeEnum:
    if label and label.strip().lower() in _TYPE_LABELS:
        return _TYPE_LABELS[label.strip().lower()]
    m = re.match(r'^[A-Z0-9]+_([A-Z]+)\(', reference or "")
    if m and m.group(1) in _REF_TYPE_CODES:
        return _REF_TYPE_CODES[m.group(1)]
    return EPRSPublicationTypeEnum.OTHER


def _thinktank_item(reference: str, title: str, label: Optional[str],
                    date: Optional[datetime], summary: str, via: str) -> Dict[str, Any]:
    return {
        "reference": reference,
        "title": title.strip(),
        "publication_type": _type_for(label, reference),
        "publication_date": date,
        "summary": summary,
        "link": THINKTANK_DOC_URL + reference,
        "via": via,
    }


def parse_thinktank_rss(xml_text: str) -> List[Dict[str, Any]]:
    """Parse the Think Tank portal RSS. Raises UnparseableSourceError when the
    body is not an RSS channel (a WAF page, an HTML error page, an empty body);
    returns [] only for a genuine, well-formed channel with no items."""
    if not (xml_text or "").strip():
        raise UnparseableSourceError("empty body")
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError as exc:
        raise UnparseableSourceError(f"not XML: {exc}") from exc
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise UnparseableSourceError(f"not an RSS channel (root <{root.tag}>)")

    items = []
    for node in channel.findall("item"):
        link = (node.findtext("link") or "").strip()
        ref_match = _REF_RE.search(link) or _REF_RE.search(node.findtext("guid") or "")
        if not ref_match:
            continue
        reference = ref_match.group(1)
        raw_title = (node.findtext("title") or "").strip()
        m = _RSS_TITLE_RE.match(raw_title)
        label, title, date = (m.group("label"), m.group("title"), _parse_ddmmyyyy(m.group("date"))) \
            if m else (None, raw_title, None)
        if date is None:
            # pubDate is Brussels midnight expressed in GMT (22:00 the day before).
            try:
                dt = parsedate_to_datetime(node.findtext("pubDate") or "")
                dt = dt.astimezone(timezone(timedelta(hours=2)))
                date = datetime(dt.year, dt.month, dt.day)
            except (TypeError, ValueError):
                date = None
        items.append(_thinktank_item(
            reference, title, label, date, _clean_summary(node.findtext("description")), "rss"))
    return items


def parse_thinktank_listing(page_html: str) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """Parse one page of the Think Tank advanced-search HTML listing.

    Returns (items, total_results). Raises UnparseableSourceError when the
    results container is absent (WAF/JS wall, error page)."""
    from bs4 import BeautifulSoup

    if not (page_html or "").strip():
        raise UnparseableSourceError("empty body")
    soup = BeautifulSoup(page_html, "html.parser")
    container = soup.find(id="publicationSearchResults")
    if container is None:
        raise UnparseableSourceError("no #publicationSearchResults container")

    total = None
    label_node = container.find(id="indexDisplayedResultsLabel")
    if label_node:
        m = _SHOWING_RE.search(label_node.get_text(" ", strip=True))
        if m:
            total = int(m.group(2).replace(",", ""))

    items = []
    for doc in container.select("div.es_document"):
        anchor = doc.select_one(".es_document-title a[href]")
        if not anchor:
            continue
        ref_match = _REF_RE.search(anchor["href"])
        if not ref_match:
            continue
        label_el = doc.select_one(".es_document-subtitle-documenttype")
        date_el = doc.select_one(".es_document-subtitle-date")
        body_el = doc.select_one(".es_document-body")
        items.append(_thinktank_item(
            ref_match.group(1),
            anchor.get_text(" ", strip=True),
            label_el.get_text(strip=True) if label_el else None,
            _parse_ddmmyyyy(date_el.get_text(strip=True) if date_el else None),
            re.sub(r'\s+', ' ', body_el.get_text(" ", strip=True)) if body_el else "",
            "listing",
        ))
    if total and total > 0 and not items:
        raise UnparseableSourceError(f"listing reports {total} results but no document blocks parsed")
    return items, total


def _load_waf_module():
    """waf_browser_fetcher imported by file path (importing the package runs
    services/scrapers/__init__.py, which imports every scraper)."""
    if "waf_browser_fetcher" in sys.modules:
        return sys.modules["waf_browser_fetcher"]
    import importlib.util
    import pathlib
    path = pathlib.Path(__file__).resolve().parent / "waf_browser_fetcher.py"
    spec = importlib.util.spec_from_file_location("waf_browser_fetcher", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["waf_browser_fetcher"] = mod
    spec.loader.exec_module(mod)
    return mod


class ThinkTankPortalSource:
    """EP Think Tank publications for a date window.

    Route order:
      1. Portal RSS with the search's own date + type filters (machine-readable,
         full summaries, 25 per page).
      2. On a WAF status or an unparseable body: the server-rendered HTML
         listing over plain HTTP.
      3. If that is walled too: the same listing rendered by Playwright.
    A WAF/unparseable route is recorded as an [ERROR] even when a later route
    recovers, so a wall never goes unnoticed; the source only FAILS when no
    route delivered.
    """

    def __init__(self, http_get=None, waf_module_loader=_load_waf_module):
        self._http_get = http_get or _default_http_get
        self._waf_module_loader = waf_module_loader

    async def fetch(self, start: datetime, end: datetime) -> Tuple[List[Dict[str, Any]], SourceReport]:
        report = SourceReport(name="thinktank_portal")

        # Measured 15 Sep 2026: the portal's startDate is EXCLUSIVE (startDate=08/09
        # drops 8 Sep documents) and its endDate is shifted by the UTC storage of
        # Brussels midnight (endDate=13/09 still returns 14 Sep). Query one day
        # wider on both sides, then filter on the document's own date below.
        q_start, q_end = start - timedelta(days=1), end + timedelta(days=1)
        items = await self._fetch_rss(q_start, q_end, report)
        if items is None:
            items = await self._fetch_listing_plain(q_start, q_end, report)
        if items is None:
            items = await self._fetch_listing_browser(q_start, q_end, report)

        if items is None:
            report.status = "failed"
            return [], report

        in_window = [
            i for i in items
            if i["publication_date"] is None or start.date() <= i["publication_date"].date() <= end.date()
        ]
        report.status = "ok"
        report.fetched = len(in_window)
        return in_window, report

    async def _fetch_rss(self, start, end, report) -> Optional[List[Dict[str, Any]]]:
        collected: List[Dict[str, Any]] = []
        for page in range(MAX_RSS_PAGES):
            params = build_thinktank_params(start, end, page)
            try:
                status, body = await self._http_get(THINKTANK_RSS_URL, params)
            except Exception as exc:
                report.errors.append(f"Think Tank RSS page {page}: {type(exc).__name__}: {exc}")
                return None
            if is_waf_response(status, body):
                report.errors.append(
                    f"Think Tank RSS page {page}: WAF signature (HTTP {status}, {len(body or '')} bytes)")
                return None
            if status != 200:
                report.errors.append(f"Think Tank RSS page {page}: HTTP {status}")
                return None
            try:
                page_items = parse_thinktank_rss(body)
            except UnparseableSourceError as exc:
                report.errors.append(f"Think Tank RSS page {page}: unparseable 200 ({exc})")
                return None
            collected.extend(page_items)
            if len(page_items) < RSS_PAGE_SIZE:
                report.via = "rss"
                return collected
        report.errors.append(
            f"Think Tank RSS: still full after {MAX_RSS_PAGES} pages; window truncated, narrow --days")
        report.via = "rss"
        return collected

    async def _fetch_listing_plain(self, start, end, report) -> Optional[List[Dict[str, Any]]]:
        collected: List[Dict[str, Any]] = []
        pages = None
        page = 0
        while pages is None or page < pages:
            params = build_thinktank_params(start, end, page)
            try:
                status, body = await self._http_get(THINKTANK_LISTING_URL, params)
            except Exception as exc:
                report.errors.append(f"Think Tank listing page {page}: {type(exc).__name__}: {exc}")
                return None
            if is_waf_response(status, body) or status != 200:
                report.errors.append(
                    f"Think Tank listing page {page}: WAF signature or HTTP {status} ({len(body or '')} bytes)")
                return None
            try:
                page_items, total = parse_thinktank_listing(body)
            except UnparseableSourceError as exc:
                report.errors.append(f"Think Tank listing page {page}: unparseable 200 ({exc})")
                return None
            collected.extend(page_items)
            if pages is None:
                pages = self._page_count(total, report)
            if not page_items:
                break
            page += 1
        report.via = "listing"
        return collected

    async def _fetch_listing_browser(self, start, end, report) -> Optional[List[Dict[str, Any]]]:
        try:
            items, errors = await asyncio.to_thread(self._render_listing_sync, start, end, report)
        except Exception as exc:
            report.errors.append(f"Think Tank listing (Playwright): {type(exc).__name__}: {exc}")
            return None
        report.errors.extend(errors)
        if items is None:
            return None
        report.via = "playwright"
        return items

    def _render_listing_sync(self, start, end, report):
        """Runs in a worker thread (Playwright's sync API refuses a running loop)."""
        from urllib.parse import urlencode

        waf = self._waf_module_loader()
        errors: List[str] = []
        collected: List[Dict[str, Any]] = []
        with waf.WafBrowserFetcher() as fetcher:
            pages = None
            page = 0
            while pages is None or page < pages:
                url = f"{THINKTANK_LISTING_URL}?{urlencode(build_thinktank_params(start, end, page))}"
                result = fetcher.fetch(url, expand_accordions=False, strip_chrome=False,
                                       wait_for_selector="#publicationSearchResults")
                if result.error or not result.html:
                    errors.append(f"Think Tank listing page {page} (Playwright): "
                                  f"{result.error or 'empty render'} (status={result.nav_status})")
                    return None, errors
                try:
                    page_items, total = parse_thinktank_listing(result.html)
                except UnparseableSourceError as exc:
                    errors.append(f"Think Tank listing page {page} (Playwright): unparseable ({exc})")
                    return None, errors
                collected.extend(page_items)
                if pages is None:
                    pages = self._page_count(total, report)
                if not page_items:
                    break
                page += 1
        return collected, errors

    @staticmethod
    def _page_count(total: Optional[int], report: SourceReport) -> int:
        if total is None:
            report.warnings.append("Think Tank listing: no result total found; reading 1 page only")
            return 1
        if total >= LISTING_RESULT_CAP:
            report.errors.append(
                f"Think Tank listing: {total} results exceeds the portal's {LISTING_RESULT_CAP} cap; "
                f"window truncated, narrow --days")
        return max(1, math.ceil(min(total, LISTING_RESULT_CAP) / LISTING_PAGE_SIZE))


async def _default_http_get(url: str, params=None) -> Tuple[int, str]:
    """Plain GET with a current browser UA (the EP host 202s non-browser UAs).
    A UA is hygiene, not the WAF answer: callers still check is_waf_response."""
    from services.scrapers.user_agent import BROWSER_UA

    async with httpx.AsyncClient(timeout=httpx.Timeout(45), follow_redirects=True,
                                 headers={"User-Agent": BROWSER_UA}) as client:
        response = await client.get(url, params=params)
        return response.status_code, response.text


class EPRSBlogFeedSource:
    """epthinktank.eu WordPress feed (blog posts), paged until the window ends."""

    def __init__(self, http_get=None):
        self._http_get = http_get or _default_http_get

    async def fetch(self, start: datetime, end: datetime) -> Tuple[List[Dict[str, Any]], SourceReport]:
        import feedparser

        report = SourceReport(name="epthinktank_blog")
        collected: List[Dict[str, Any]] = []
        for page in range(1, MAX_BLOG_PAGES + 1):
            params = [("paged", str(page))] if page > 1 else None
            try:
                status, body = await self._http_get(BLOG_FEED_URL, params)
            except Exception as exc:
                report.errors.append(f"Blog feed page {page}: {type(exc).__name__}: {exc}")
                break
            if page > 1 and status == 404:
                break  # WordPress answers 404 past the last page
            if is_waf_response(status, body) or status != 200:
                report.errors.append(
                    f"Blog feed page {page}: WAF signature or HTTP {status} ({len(body or '')} bytes)")
                break
            parsed = feedparser.parse(body)
            if not parsed.get("feed") or ("title" not in parsed.feed and not parsed.entries):
                report.errors.append(f"Blog feed page {page}: unparseable 200")
                break
            oldest = None
            for entry in parsed.entries:
                published = None
                if entry.get("published_parsed"):
                    published = datetime(*entry.published_parsed[:6])
                oldest = published if oldest is None or (published and published < oldest) else oldest
                if published and not (start <= published < end + timedelta(days=1)):
                    continue
                collected.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": published.isoformat() if published else None,
                    "summary": _clean_summary(entry.get("summary", "")),
                    "categories": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
                    "author": entry.get("author"),
                    "_source_type": "blog",
                })
            if not parsed.entries or (oldest and oldest < start):
                break

        if report.errors and not collected:
            report.status = "failed"
        else:
            report.status = "ok"
            report.via = "rss"
        report.fetched = len(collected)
        return collected, report


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
        self.portal_source = ThinkTankPortalSource()
        self.blog_source = EPRSBlogFeedSource()

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
        verbose: bool = False,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Sync EPRS / Think Tank publications for a date window.

        Args:
            days: Window length when ``since`` is not given
            limit: Maximum items processed per source (excess is reported)
            skip_existing: Skip publications already in the database
            verbose: Print progress to stdout
            since / until: Explicit window (dates, inclusive)

        Returns:
            Summary dict. ``skipped`` counts only items that were FETCHED and
            already present. ``errors`` includes every source that answered a
            WAF status or an unparseable body. ``nothing_fetched`` is True when
            no source delivered at all.
        """
        today = datetime.now()
        end = until or today
        start = since or (end - timedelta(days=days))
        start = datetime(start.year, start.month, start.day)
        end = datetime(end.year, end.month, end.day)   # inclusive; sources widen as needed

        logger.info(f"[START] EPRS sync: {start.date()} to {end.date()}")
        if verbose:
            print(f"[START] EPRS sync: publications from {start.date()} to {end.date()}...")

        stats: Dict[str, Any] = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': [],
            'warnings': [],
            'fetched': 0,
            'sources': {},
            'by_type': {},
            'added_rows': [],
            'nothing_fetched': False,
        }

        batches: List[Tuple[str, List[Dict[str, Any]]]] = []
        for source in (self.portal_source, self.blog_source):
            try:
                items, report = await source.fetch(start, end)
            except Exception as e:  # a source bug must not read as "no items"
                items, report = [], SourceReport(name=getattr(source, "__class__").__name__,
                                                  status="failed",
                                                  errors=[f"{type(e).__name__}: {e}"])
            stats['sources'][report.name] = {
                'status': report.status, 'via': report.via,
                'fetched': report.fetched, 'errors': list(report.errors),
            }
            for err in report.errors:
                stats['errors'] += 1
                stats['error_details'].append(f"{report.name}: {err}")
                logger.error(f"[ERROR] EPRS source {report.name}: {err}")
            stats['warnings'].extend(f"{report.name}: {w}" for w in report.warnings)
            if len(items) > limit:
                stats['warnings'].append(
                    f"{report.name}: {len(items)} items fetched, only {limit} processed (--limit)")
                items = items[:limit]
            if verbose:
                via = f" via {report.via}" if report.via else ""
                tag = "[OK]" if report.status == "ok" else "[ERROR]"
                print(f"  {tag} {report.name}: {report.status}{via}, {report.fetched} in window")
                for err in report.errors:
                    print(f"  [ERROR] {report.name}: {err}")
            batches.append((report.name, items))

        stats['fetched'] = sum(len(items) for _, items in batches)
        if all(s['status'] != 'ok' for s in stats['sources'].values()):
            stats['nothing_fetched'] = True
            stats['errors'] += 1
            stats['error_details'].append("No source could be fetched; nothing was synced")

        seen_ids = set()
        for source_name, items in batches:
            for item in items:
                try:
                    if source_name == "thinktank_portal":
                        result, row = self._upsert_thinktank_item(item, skip_existing, seen_ids)
                    else:
                        result, row = self._upsert_publication(item, skip_existing, seen_ids)
                    if result in ('added', 'updated', 'skipped'):
                        stats[result] += 1
                    if result == 'added':
                        stats['added_rows'].append(row)
                        key = row['publication_type']
                        stats['by_type'][key] = stats['by_type'].get(key, 0) + 1
                except Exception as e:
                    stats['errors'] += 1
                    title = (item.get('title') or 'Unknown')[:50]
                    stats['error_details'].append(f"{title}: {type(e).__name__}: {e}")
                    logger.error(f"Failed to upsert publication: {e}")

        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to commit: {str(e)}")
            self.db.rollback()
            stats['errors'] += 1
            stats['error_details'].append(f"Commit failed: {str(e)}")
            stats['added'] = stats['updated'] = 0
            stats['added_rows'] = []

        logger.info(
            f"EPRS sync complete: fetched {stats['fetched']}, "
            f"{stats['added']} added, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        if verbose:
            tag = "[ERROR]" if stats['errors'] else "[OK]"
            print(f"\n{tag} EPRS sync complete:")
            print(f"  Fetched: {stats['fetched']}")
            print(f"  Added:   {stats['added']}")
            print(f"  Updated: {stats['updated']}")
            print(f"  Skipped: {stats['skipped']} (fetched and already present)")
            print(f"  Errors:  {stats['errors']}")
            for w in stats['warnings']:
                print(f"  [WARN] {w}")
            if stats['error_details']:
                print(f"\n  Error details:")
                for err in stats['error_details'][:20]:
                    print(f"    [ERROR] {err}")
            if stats['added_rows']:
                print(f"\n  New rows:")
                for row in stats['added_rows']:
                    d = row['publication_date'].date() if row['publication_date'] else 'undated'
                    print(f"    {d}  {row['publication_id']}  {row['title'][:90]}")

        return stats

    def _upsert_thinktank_item(
        self,
        item: Dict[str, Any],
        skip_existing: bool = True,
        seen_ids: Optional[set] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Upsert one Think Tank portal item. Matches legacy rows too: before
        15 Sep 2026 these were stored as EPRS_UNK_<md5(link)>."""
        reference = item['reference']
        link = item['link']
        if seen_ids is not None:
            if reference in seen_ids:
                return 'duplicate', None
            seen_ids.add(reference)

        legacy_id = _extract_publication_id(link)
        existing = self.db.query(EPRSPublication).filter(
            or_(
                EPRSPublication.publication_id.in_([reference, legacy_id]),
                EPRSPublication.html_url == link,
            )
        ).first()

        summary = (item.get('summary') or '')[:2000] or None
        if existing:
            if skip_existing:
                return 'skipped', None
            changed = False
            if summary and existing.summary != summary and not (
                    existing.summary and summary.endswith('...') and len(existing.summary) >= len(summary)):
                existing.summary = summary
                changed = True
            if changed:
                existing.last_updated = datetime.now()
                return 'updated', None
            return 'skipped', None

        now = datetime.now()
        search_text = f"{item['title']} {summary or ''}"
        new_pub = EPRSPublication(
            id=uuid.uuid4(),
            publication_id=reference,
            title=item['title'],
            publication_type=item['publication_type'].value,
            html_url=link,
            pdf_url=None,
            authors=[],
            publication_date=item['publication_date'],
            summary=summary,
            policy_areas=[],
            committees=[],
            related_celex_numbers=_extract_celex_numbers(search_text),
            related_procedures=_extract_procedure_refs(search_text),
            categories=[],
            has_full_text=False,
            first_seen=now,
            last_updated=now,
            scraped_at=now,
        )
        self.db.add(new_pub)
        return 'added', {
            'publication_id': reference,
            'title': item['title'],
            'publication_type': item['publication_type'].value,
            'publication_date': item['publication_date'],
        }

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
        skip_existing: bool = True,
        seen_ids: Optional[set] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Upsert a single publication from RSS data (epthinktank.eu blog feed).

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
        if seen_ids is not None:
            if publication_id in seen_ids:
                return 'duplicate', None
            seen_ids.add(publication_id)

        # Check if exists
        existing = self.db.query(EPRSPublication).filter(
            EPRSPublication.publication_id == publication_id
        ).first()

        if existing:
            if skip_existing:
                return 'skipped', None

            # Update metadata; count only a real change (an assignment of an
            # identical value is not a write).
            new_values = {
                'title': title or existing.title,
                'summary': (summary[:2000] if summary else None) or existing.summary,
                'categories': categories or existing.categories,
            }
            changed = [k for k, v in new_values.items() if getattr(existing, k) != v]
            if not changed:
                return 'skipped', None
            for k in changed:
                setattr(existing, k, new_values[k])
            existing.last_updated = datetime.now()
            return 'updated', None

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
        return 'added', {
            'publication_id': publication_id,
            'title': title,
            'publication_type': pub_type.value,
            'publication_date': pub_date,
        }

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
