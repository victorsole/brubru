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


_PARSERS: dict[str, Callable[[str, dict], List[ScrapedItem]]] = {
    "rss": parse_rss,
    "ecl": parse_ecl,
    "ema": parse_ema,
    "ep_sant_press": parse_ep_sant_press,
    "ep_sant_documents": parse_ep_sant_documents,
    "generic": parse_generic,
}


_SOURCE_PARSER_OVERRIDES: dict[str, str] = {
    # Anything starting with dg_sante_ uses the ECL parser by default
    # except where overridden below.
}


def parser_for(source: dict) -> Callable[[str, dict], List[ScrapedItem]]:
    sid = source.get("id", "")
    explicit = _SOURCE_PARSER_OVERRIDES.get(sid)
    if explicit:
        return _PARSERS.get(explicit, parse_generic)
    if source.get("fetch_strategy") == "rss" or source.get("kind") == "rss":
        return parse_rss
    bucket = source.get("bucket")
    if bucket == "dg_sante":
        return parse_ecl
    if bucket == "ema":
        return parse_ema
    if bucket == "dg_grow":
        # DG GROW newsroom HTML topic pages -- fall through to generic which
        # tries ECL, EMA, EP shapes. RSS is already handled above.
        return parse_generic
    if bucket == "ep_sant":
        if source.get("kind") in ("press", "highlights", "newsletters"):
            return parse_ep_sant_press
        return parse_ep_sant_documents
    return parse_generic


# ---------------------------------------------------------------------------
# Scraping driver
# ---------------------------------------------------------------------------


def scrape_source(source: dict, force_playwright: bool = False) -> List[ScrapedItem]:
    """Fetch one source URL and return the parsed items."""

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
