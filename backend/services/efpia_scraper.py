"""
EFPIA pharma/health scraper.

Source catalogue: backend/data/efpia_brief/sources.json (83 sources across
DG SANTE, EP SANT, EMA, horizontal EC).
Storage: efpia_scraped_items table (migration 092).
Driver:  backend/scripts/scrape_efpia_sources.py.

Three parsers ship in this module:
  - parse_ecl: DG SANTE health.ec.europa.eu pages (`.ecl-content-item` items
    with `<time>` and a heading link).
  - parse_ema: EMA www.ema.europa.eu pages (article.ema-news teaser cards
    with `.teaser-title a`, `.metadata-item` date, badges).
  - parse_ep_sant_press: europarl.europa.eu/committees/en/sant pages
    (a[href*="/news/en/press-room/"] anchors with date prefix in the
    YYYYMMDD-IPRNNNNN URL).

Generic fallback (parse_generic) tries each of the above shapes in order
before giving up and emitting nothing.

Playwright is only used if the requests-based fetch returns a body with a
clear WAF marker ("just a moment...", "challenge-platform", "Attention Required",
"<title>Just a moment", or status 202). The fallback is opt-in via
`force_playwright_for=[source_id]` in the per-source map, mainly to cover
WAF regressions when europarl.europa.eu adds challenge pages.

Created 28 May 2026.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SOURCES_PATH = _BACKEND_ROOT / "data" / "efpia_brief" / "sources.json"

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

_WAF_MARKERS = (
    "just a moment",
    "challenge-platform",
    "attention required",
    "cf-mitigated",
    "checking your browser",
)


@dataclass
class ScrapedItem:
    """Normalised scraped item ready for UPSERT into efpia_scraped_items."""

    source_id: str
    institution: str
    bucket: str
    kind: str
    item_url: str
    item_title: str
    item_summary: Optional[str] = None
    item_published_at: Optional[datetime] = None
    relevance_score: int = 50
    raw_text: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def dedup_hash(self) -> str:
        seed = f"{self.source_id}|{self.item_url.strip().lower()}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------


def load_sources() -> dict:
    if not _SOURCES_PATH.is_file():
        raise FileNotFoundError(f"sources.json not found at {_SOURCES_PATH}")
    with _SOURCES_PATH.open() as fh:
        return json.load(fh)


def get_source(source_id: str) -> Optional[dict]:
    for s in load_sources().get("sources", []):
        if s.get("id") == source_id:
            return s
    return None


def tier1_source_ids() -> List[str]:
    return list(load_sources().get("tier1_priority_sources") or [])


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


def _waf_blocked(body: str) -> bool:
    if not body:
        return True
    head = body[:4000].lower()
    return any(marker in head for marker in _WAF_MARKERS)


def fetch_html(url: str, timeout: float = 12.0, force_playwright: bool = False) -> Optional[str]:
    """Fetch a URL as HTML. requests first, Playwright fallback if WAF / empty."""

    if not force_playwright:
        try:
            resp = requests.get(url, headers=_REQUEST_HEADERS, timeout=timeout, allow_redirects=True)
        except requests.RequestException as exc:
            logger.warning("requests.get failed for %s: %s", url, exc)
            resp = None

        if resp is not None and resp.status_code == 200 and not _waf_blocked(resp.text):
            return resp.text

        if resp is not None and resp.status_code not in (200, 202):
            logger.warning("%s returned HTTP %s", url, resp.status_code)

    return _fetch_html_playwright(url, timeout=timeout)


def _fetch_html_playwright(url: str, timeout: float = 30.0) -> Optional[str]:
    """Playwright fallback. Used when requests hits WAF or empty body."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed; cannot fall back for %s", url)
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=_REQUEST_HEADERS["User-Agent"])
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
            page.wait_for_timeout(1500)  # let WAF challenge resolve
            html = page.content()
            browser.close()
            if _waf_blocked(html):
                logger.warning("playwright still WAF-blocked on %s", url)
                return None
            return html
    except Exception as exc:  # noqa: BLE001
        logger.warning("playwright failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


_ABS_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _absolute(url: str, base: str) -> str:
    if not url:
        return ""
    if _ABS_URL_RE.match(url):
        return url
    return urljoin(base, url)


def _parse_iso_datetime(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


_DATE_HUMAN_RE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_human_date(text_value: str) -> Optional[datetime]:
    if not text_value:
        return None
    m = _DATE_HUMAN_RE.search(text_value)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _MONTH_MAP.get(month_name.lower())
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day), tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_ecl(html: str, source: dict) -> List[ScrapedItem]:
    """DG SANTE / health.ec.europa.eu pages with `.ecl-content-item` cards."""

    soup = BeautifulSoup(html, "html.parser")
    items: List[ScrapedItem] = []
    base = source["url"]

    for card in soup.select(".ecl-content-item"):
        link = card.find("a", href=True)
        if not link:
            continue
        title_el = card.find(["h1", "h2", "h3", "h4"])
        title = (title_el.get_text(" ", strip=True) if title_el else link.get_text(" ", strip=True)).strip()
        if not title:
            continue
        time_el = card.find("time")
        published = _parse_iso_datetime(time_el.get("datetime", "") if time_el else "") or _parse_human_date(card.get_text(" "))
        url_abs = _absolute(link["href"], base)
        # Strip a leading "News announcement DD Month YYYY" prefix from title
        title = re.sub(r"^\s*News announcement\s+\d{1,2}\s+\w+\s+\d{4}\s*", "", title).strip()
        summary = title  # ECL cards repeat the heading; deeper summary needs a per-page fetch.
        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=url_abs,
                item_title=title,
                item_summary=summary,
                item_published_at=published,
                relevance_score=60 if source["bucket"] == "dg_sante" else 50,
                metadata={"parser": "ecl"},
            )
        )
    return items


def parse_ema(html: str, source: dict) -> List[ScrapedItem]:
    """EMA pages with `article.ema-news` teaser cards."""

    soup = BeautifulSoup(html, "html.parser")
    items: List[ScrapedItem] = []
    base = "https://www.ema.europa.eu/"

    for art in soup.select("article.ema-news, article.node.ema-news, article.node--type-ema-news, article.ema-publications, article.ema-event"):
        title_link = art.select_one(".teaser-title a")
        if not title_link:
            continue
        title = title_link.get_text(" ", strip=True)
        if not title:
            continue
        href = title_link.get("href", "")
        if not href:
            continue
        url_abs = _absolute(href, base)

        summary_el = art.select_one(".ema-news__field-ema-summary, .field--name-ema-summary, .card-text p")
        summary = summary_el.get_text(" ", strip=True) if summary_el else None

        date_el = art.select_one(".metadata-item")
        published = _parse_human_date(date_el.get_text(" ", strip=True) if date_el else "")

        kind_badge = art.select_one(".bundle-name .label")
        category_badge = art.select_one(".ema-bg-category .label")
        topic_badge = art.select_one(".ema-bg-topic .label")
        metadata = {"parser": "ema"}
        if kind_badge:
            metadata["badge_kind"] = kind_badge.get_text(strip=True)
        if category_badge:
            metadata["badge_category"] = category_badge.get_text(strip=True)
        if topic_badge:
            metadata["badge_topic"] = topic_badge.get_text(strip=True)

        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=url_abs,
                item_title=title,
                item_summary=summary,
                item_published_at=published,
                relevance_score=70,
                metadata=metadata,
            )
        )
    return items


_EP_PRESS_DATE_RE = re.compile(r"/press-room/(\d{8})IPR", re.IGNORECASE)


def parse_ep_sant_press(html: str, source: dict) -> List[ScrapedItem]:
    """EP SANT press-room links, embedded in committee pages."""

    soup = BeautifulSoup(html, "html.parser")
    items: List[ScrapedItem] = []
    base = "https://www.europarl.europa.eu/"
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/news/" not in href or "/press-room/" not in href:
            continue
        url_abs = _absolute(href, base)
        if url_abs in seen:
            continue
        seen.add(url_abs)
        title = link.get_text(" ", strip=True)
        if not title or len(title) < 12:
            continue

        m = _EP_PRESS_DATE_RE.search(url_abs)
        published: Optional[datetime] = None
        if m:
            try:
                published = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=url_abs,
                item_title=title,
                item_summary=None,
                item_published_at=published,
                relevance_score=75,
                metadata={"parser": "ep_sant_press"},
            )
        )
    return items


def parse_ep_sant_documents(html: str, source: dict) -> List[ScrapedItem]:
    """
    EP SANT committee document listings (latest-documents, votes, minutes,
    meeting-documents). The page lists links to PDFs / EP-doceo references.
    """

    soup = BeautifulSoup(html, "html.parser")
    items: List[ScrapedItem] = []
    base = "https://www.europarl.europa.eu/"
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href:
            continue
        lower = href.lower()
        if not any(token in lower for token in ("/doceo/", "/cmsdata/", "/regdata/", "epdoc")):
            continue
        url_abs = _absolute(href, base)
        if url_abs in seen:
            continue
        seen.add(url_abs)
        title = link.get_text(" ", strip=True)
        if not title or len(title) < 6:
            continue
        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=url_abs,
                item_title=title,
                item_summary=None,
                item_published_at=None,
                relevance_score=65,
                metadata={"parser": "ep_sant_documents"},
            )
        )
    return items


_EMA_DATE_DMY_RE = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\s*[-–]\s*(.+)$")


def parse_ema_whats_new_table(html: str, source: dict) -> List[ScrapedItem]:
    """
    EMA What's new is one big <tr> table with columns: date, kind+title, action.
    Each row is a product update, document update, EPAR change, etc. Volume is
    high (~450 rows) so we cap at the most recent 60 by document order (table
    is already date-sorted) and assign a low relevance_score (30) so individual
    EPAR updates do not dominate the daily-candidates pool.
    """

    soup = BeautifulSoup(html, "html.parser")
    items: List[ScrapedItem] = []
    base = "https://www.ema.europa.eu/"

    cap = 60
    rows = soup.find_all("tr")
    for row in rows:
        a = row.find("a", href=True)
        if not a:
            continue
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        date_text = cells[0].get_text(" ", strip=True)
        title_text = cells[1].get_text(" ", strip=True)
        action_text = cells[2].get_text(" ", strip=True) if len(cells) > 2 else ""
        if not title_text:
            continue
        # Parse DD/MM/YYYY
        published_dt: Optional[datetime] = None
        try:
            published_dt = datetime.strptime(date_text, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        url_abs = _absolute(a["href"], base)
        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=url_abs,
                item_title=title_text[:512],
                item_summary=(action_text or None),
                item_published_at=published_dt,
                relevance_score=30,
                metadata={"parser": "ema_whats_new_table", "action": action_text},
            )
        )
        if len(items) >= cap:
            break
    return items


def parse_ema_open_consultations(html: str, source: dict) -> List[ScrapedItem]:
    """
    EMA Open consultations lists each consultation as an h3 with text
    "DD/MM/YYYY - <consultation title>" followed by a 'View' link to the
    consultation document.
    """

    soup = BeautifulSoup(html, "html.parser")
    items: List[ScrapedItem] = []
    base = "https://www.ema.europa.eu/"
    main = soup.find("main") or soup

    for heading in main.find_all(["h2", "h3", "h4"]):
        text = heading.get_text(" ", strip=True)
        m = _EMA_DATE_DMY_RE.match(text)
        if not m:
            continue
        day, month, year, title = m.groups()
        try:
            published_dt = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
        except ValueError:
            published_dt = None

        # The View link lives inside the heading's containing accordion-item
        # (a parent <div>), not in the next sibling chain. Walk up two levels
        # to find the container, then pick the first /documents/ link.
        view_url: Optional[str] = None
        container = heading
        for _ in range(4):
            container = container.parent
            if container is None:
                break
            if container.name == "div":
                for link in container.find_all("a", href=True):
                    href = link["href"]
                    if href.startswith("/en/documents/") or "/documents/" in href:
                        view_url = href
                        break
            if view_url:
                break

        if not view_url:
            continue
        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=_absolute(view_url, base),
                item_title=title.strip().strip('“”'),
                item_summary=None,
                item_published_at=published_dt,
                relevance_score=75,
                metadata={"parser": "ema_open_consultations"},
            )
        )
    return items


def parse_rss(body: str, source: dict) -> List[ScrapedItem]:
    """
    RSS 2.0 / Atom feed parser. Used by DG GROW newsroom feeds and any
    future RSS-shaped source in the catalogue. Stays on stdlib ElementTree
    to avoid an extra dependency.
    """

    import xml.etree.ElementTree as ET

    items: List[ScrapedItem] = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        logger.warning("rss parse failed for %s: %s", source.get("id"), exc)
        return items

    channel = root.find("channel")
    nodes = channel.findall("item") if channel is not None else root.findall("{http://www.w3.org/2005/Atom}entry")

    for node in nodes:
        # RSS 2.0
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub_raw = (node.findtext("pubDate") or "").strip()
        desc = (node.findtext("description") or "").strip() or None

        # Atom fallback
        if not link:
            link_el = node.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.get("href", "")
        if not title:
            title_el = node.find("{http://www.w3.org/2005/Atom}title")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()
        if not pub_raw:
            updated = node.find("{http://www.w3.org/2005/Atom}updated")
            published = node.find("{http://www.w3.org/2005/Atom}published")
            if published is not None and published.text:
                pub_raw = published.text.strip()
            elif updated is not None and updated.text:
                pub_raw = updated.text.strip()

        if not title or not link:
            continue

        published_dt: Optional[datetime] = None
        if pub_raw:
            for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    published_dt = datetime.strptime(pub_raw, fmt)
                    if published_dt.tzinfo is None:
                        published_dt = published_dt.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

        items.append(
            ScrapedItem(
                source_id=source["id"],
                institution=source["institution"],
                bucket=source["bucket"],
                kind=source["kind"],
                item_url=link,
                item_title=title,
                item_summary=desc,
                item_published_at=published_dt,
                relevance_score=60,
                metadata={"parser": "rss"},
            )
        )
    return items


def parse_generic(html: str, source: dict) -> List[ScrapedItem]:
    """Fallback: try RSS, then ECL, then EMA, then EP press, then EP documents."""

    if html.lstrip().startswith("<?xml") or "<rss" in html[:200].lower() or "<feed" in html[:200].lower():
        try:
            items = parse_rss(html, source)
            if items:
                return items
        except Exception as exc:  # noqa: BLE001
            logger.warning("rss parser raised on %s: %s", source.get("id"), exc)

    for parser in (parse_ecl, parse_ema, parse_ep_sant_press, parse_ep_sant_documents):
        try:
            items = parser(html, source)
        except Exception as exc:  # noqa: BLE001
            logger.warning("parser %s raised on %s: %s", parser.__name__, source.get("id"), exc)
            continue
        if items:
            return items
    return []


def parse_cellar_sparql(payload: str, source: dict) -> List[ScrapedItem]:
    """Parse Cellar SPARQL JSON results into ScrapedItems.

    Expects SPARQL JSON bindings with ?celex ?title ?date. Used for the OJ
    L-series pharma feed: EUR-Lex HTML is WAF-walled, but the Cellar SPARQL
    endpoint (publications.europa.eu/webapi/rdf/sparql) is the official
    machine-readable path and is not walled. item_url is the EUR-Lex CELEX
    permalink (clickable for users).
    """
    items: List[ScrapedItem] = []
    try:
        bindings = json.loads(payload).get("results", {}).get("bindings", [])
    except Exception as e:  # noqa: BLE001
        logger.warning("[cellar-sparql] bad JSON for %s: %s", source.get("id"), e)
        return items
    seen: set = set()
    for b in bindings:
        celex = (b.get("celex") or {}).get("value", "").strip()
        title = (b.get("title") or {}).get("value", "").strip()
        date_raw = (b.get("date") or {}).get("value", "").strip()
        if not celex or not title or celex in seen:
            continue
        seen.add(celex)
        items.append(ScrapedItem(
            source_id=source["id"],
            institution=source.get("institution", "EC"),
            bucket=source.get("bucket", "horizontal_ec"),
            kind=source.get("kind", "official_journal"),
            item_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
            item_title=title,
            item_summary=None,
            item_published_at=_parse_iso_datetime(date_raw),
            relevance_score=70,
            metadata={"parser": "cellar_sparql", "celex": celex},
        ))
    return items


_PARSERS: dict[str, Callable[[str, dict], List[ScrapedItem]]] = {
    "rss": parse_rss,
    "cellar_sparql": parse_cellar_sparql,
    "ecl": parse_ecl,
    "ema": parse_ema,
    "ema_whats_new_table": parse_ema_whats_new_table,
    "ema_open_consultations": parse_ema_open_consultations,
    "ep_sant_press": parse_ep_sant_press,
    "ep_sant_documents": parse_ep_sant_documents,
    "generic": parse_generic,
}


_SOURCE_PARSER_OVERRIDES: dict[str, str] = {
    # EMA non-standard shapes
    "ema_whats_new": "ema_whats_new_table",
    "ema_open_consultations": "ema_open_consultations",
}


def parser_for(source: dict) -> Callable[[str, dict], List[ScrapedItem]]:
    sid = source.get("id", "")
    explicit = _SOURCE_PARSER_OVERRIDES.get(sid)
    if explicit:
        return _PARSERS.get(explicit, parse_generic)
    if source.get("fetch_strategy") == "sparql":
        return parse_cellar_sparql
    if source.get("fetch_strategy") == "rss" or source.get("kind") == "rss":
        return parse_rss
    bucket = source.get("bucket")
    if bucket == "dg_sante":
        return parse_ecl
    if bucket == "ema":
        return parse_ema
    if bucket == "dg_comp":
        # DG COMP competition-policy.ec.europa.eu pages use the same ECL
        # `.ecl-content-item` card layout as DG SANTE (server-rendered).
        return parse_ecl
    if bucket == "dg_grow":
        # Current DG GROW news (single-market-economy.ec.europa.eu) is
        # server-rendered with ECL .ecl-content-item cards. The legacy
        # newsroom RSS/HTML topic feeds (topic_id 5048/5061) are dead since
        # 2021 (pharma + medical devices moved to DG SANTE). RSS handled above.
        return parse_ecl
    if bucket == "ep_sant":
        if source.get("kind") in ("press", "highlights", "newsletters"):
            return parse_ep_sant_press
        return parse_ep_sant_documents
    return parse_generic


# ---------------------------------------------------------------------------
# Scraping driver
# ---------------------------------------------------------------------------


# Buckets whose feed is GENERAL (not already pharma-scoped by the source URL).
# Items from these are re-scored by pharma relevance so only relevant ones
# clear the default candidate threshold (min_relevance=50).
_GENERAL_FEED_BUCKETS = {"dg_grow"}

# Pharma / health / medical-device / pharma-industrial relevance markers.
_PHARMA_KEYWORDS = (
    "medicine", "medicinal", "pharmaceutic", "pharma", "biosimilar", "biotech",
    "vaccine", "antimicrobial", "antibiotic", "medical device", "in vitro", " ivd",
    "eudamed", "clinical trial", "orphan", "atmp", "advanced therap",
    "active pharmaceutical", "active substance", "supply of medicines",
    "critical medicines", "medicine shortage", "shortage of medicines",
    "marketing authorisation", "marketing authorization", "life science",
    "blood", "tissue", "plasma", "oncolog", "rare disease", "health technology",
    "api ", "good manufacturing practice", "gmp",
)


def _pharma_relevance(title: Optional[str], summary: Optional[str]) -> int:
    """Score a general-feed item by pharma relevance.

    60 if the title/summary mentions a pharma / health / medical-device term,
    otherwise 25 (below the default min_relevance=50 so non-pharma items from a
    general DG GROW feed do not flood the candidate pool).
    """
    blob = f"{title or ''} {summary or ''}".lower()
    return 60 if any(kw in blob for kw in _PHARMA_KEYWORDS) else 25


_SPARQL_WINDOW_DAYS = 45


def _fetch_sparql(endpoint: str, query_template: str) -> Optional[str]:
    """Run a Cellar SPARQL query (rolling date window) and return JSON text."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=_SPARQL_WINDOW_DAYS)).strftime("%Y-%m-%d")
    query = query_template.replace("{since}", since)
    try:
        resp = requests.get(
            endpoint,
            params={"query": query, "format": "application/sparql-results+json"},
            headers={"User-Agent": _REQUEST_HEADERS["User-Agent"],
                     "Accept": "application/sparql-results+json"},
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.text
        logger.warning("[cellar-sparql] HTTP %s for %s", resp.status_code, endpoint)
    except Exception as e:  # noqa: BLE001
        logger.warning("[cellar-sparql] fetch failed: %s", e)
    return None


def scrape_source(source: dict, force_playwright: bool = False) -> List[ScrapedItem]:
    """Fetch one source URL and return the parsed items."""

    # SPARQL sources (OJ L-series via Cellar) query the RDF endpoint instead of
    # fetching HTML -- EUR-Lex HTML is WAF-walled; Cellar SPARQL is the official
    # machine-readable path.
    if source.get("fetch_strategy") == "sparql":
        endpoint = source.get("url") or "http://publications.europa.eu/webapi/rdf/sparql"
        payload = _fetch_sparql(endpoint, source.get("query_template", ""))
        if not payload:
            return []
        return parse_cellar_sparql(payload, source)

    url = source.get("url")
    if not url:
        url_template = source.get("url_template")
        if url_template:
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            url = url_template.format(yyyymmdd=today)
    if not url:
        logger.warning("source %s has no url", source.get("id"))
        return []

    html = fetch_html(url, force_playwright=force_playwright)
    if not html:
        logger.warning("no HTML returned for %s (%s)", source.get("id"), url)
        return []

    parser = parser_for(source)
    items = parser(html, source)

    # Re-score general feeds (DG GROW) by pharma relevance so non-pharma items
    # sink below the default candidate threshold instead of flooding the pool.
    if source.get("bucket") in _GENERAL_FEED_BUCKETS:
        for it in items:
            it.relevance_score = _pharma_relevance(it.item_title, it.item_summary)
    return items


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


_UPSERT_SQL = text(
    """
    INSERT INTO efpia_scraped_items (
        source_id, institution, bucket, kind, item_url, item_title, item_summary,
        item_published_at, scraped_at, relevance_score, raw_text, dedup_hash, metadata
    )
    VALUES (
        :source_id, :institution, :bucket, :kind, :item_url, :item_title, :item_summary,
        :item_published_at, NOW(), :relevance_score, :raw_text, :dedup_hash, CAST(:metadata AS jsonb)
    )
    ON CONFLICT (dedup_hash) DO UPDATE
       SET item_title        = EXCLUDED.item_title,
           item_summary      = COALESCE(EXCLUDED.item_summary, efpia_scraped_items.item_summary),
           item_published_at = COALESCE(EXCLUDED.item_published_at, efpia_scraped_items.item_published_at),
           scraped_at        = EXCLUDED.scraped_at,
           relevance_score   = GREATEST(EXCLUDED.relevance_score, efpia_scraped_items.relevance_score),
           raw_text          = COALESCE(EXCLUDED.raw_text, efpia_scraped_items.raw_text),
           metadata          = efpia_scraped_items.metadata || EXCLUDED.metadata,
           updated_at        = NOW()
    """
)


def save_items(db: Session, items: Iterable[ScrapedItem]) -> int:
    """UPSERT a batch of items. Returns the number written."""

    count = 0
    for item in items:
        if not item.item_url or not item.item_title:
            continue
        db.execute(
            _UPSERT_SQL,
            {
                "source_id": item.source_id,
                "institution": item.institution,
                "bucket": item.bucket,
                "kind": item.kind,
                "item_url": item.item_url[:2048],
                "item_title": item.item_title[:1024],
                "item_summary": item.item_summary[:4096] if item.item_summary else None,
                "item_published_at": item.item_published_at,
                "relevance_score": int(item.relevance_score),
                "raw_text": item.raw_text[:8000] if item.raw_text else None,
                "dedup_hash": item.dedup_hash,
                "metadata": json.dumps(item.metadata or {}),
            },
        )
        count += 1
    return count
