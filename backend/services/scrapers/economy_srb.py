"""
SRB — Single Resolution Board (/api/v2/eu-financial-institutions/srb).

SRB runs a Drupal site (api_econ.md L509-566). Source map (all verified):
  - news         : /en/news/search — the news archive is rendered client-side by
                   the EU "Europa Search" (EAMS) widget, so plain requests get a
                   403. We render it with the WAF browser and read the
                   .node--type-srb-news.node--view-mode-search-result cards
                   (title link + <time datetime>). Detail = /en/content/<slug> HTML.
  - publications : /en/public-register-of-documents — server-rendered, paginated
                   ?page=N; each .views-row is a media--type-srb-document with a
                   PDF link, a <time datetime> publishing date and a clean title
                   in the .srb-document-icon[title]. Bodies extracted from the PDF.
  - events       : /en/events — server-rendered, paginated ?page=N;
                   .node--type-srb-event cards with an .srb-event__title heading,
                   a "Read more" link to /en/content/<slug> and an .srb-calendar-date
                   in month-first form ("Jun 10 - 11 2026"). Detail = HTML.

SRB throttles rapid requests (HTTP 429), so the requests-based feeds space and
retry. No LLM is used.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, extract_html, extract_pdf, parse_listing_date,
)

_BASE = "https://www.srb.europa.eu"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 BrubruBot/1.0"
_TIMEOUT = 30
_BODY_CAP = 800_000

# month-first event dates: "Jun 10 - 11 2026", "Jun 12 2026"
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTHFIRST_RE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\s+(\d{4})")


def _parse_monthfirst(text: str) -> datetime | None:
    m = _MONTHFIRST_RE.search(text or "")
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower()[:3])
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _get(url: str, *, tries: int = 4) -> requests.Response | None:
    """GET with backoff on SRB's 429 throttle."""
    for attempt in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT,
                             allow_redirects=True)
        except requests.RequestException:
            time.sleep(3.0 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r
        if r.status_code == 429:
            time.sleep(4.0 * (attempt + 1))
            continue
        return None
    return None


def _fetch_detail_spaced(url: str) -> tuple[str | None, str | None, str]:
    """fetch_detail but using the backoff getter (SRB throttles)."""
    r = _get(url)
    if r is None:
        return None, None, "unreachable"
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/pdf" in ctype or url.lower().endswith(".pdf"):
        return extract_pdf(r.content), f'<p>PDF document: <a href="{url}">{url}</a></p>', "pdf"
    if "html" not in ctype and "xml" not in ctype:
        kind = (ctype.split(";")[0].split("/")[-1] or "file")[:20] or "file"
        return None, f'<p>Document: <a href="{url}">{url}</a></p>', kind
    body_txt, body_html = extract_html(r.text)
    return body_txt, body_html, "html"


# --- news (Playwright; EAMS search widget) ---------------------------------
def _parse_news_cards(html: str) -> list[tuple[str, str, datetime | None]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for n in soup.select(".node--type-srb-news.node--view-mode-search-result"):
        a = n.find("a", href=True)
        if not a or "/search" in a["href"]:
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        t = n.select_one("time[datetime]")
        doc_dt = None
        if t and t.get("datetime"):
            try:
                doc_dt = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00"))
            except ValueError:
                doc_dt = None
        if doc_dt is None:
            doc_dt = parse_listing_date(n.get_text(" ", strip=True))
        out.append((url, title, doc_dt))
    return out


def _render_news_page(url: str) -> str:
    """Render one EAMS news-search page: results load async, so wait for the
    result cards to appear before reading the DOM."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=_UA)
        pg = ctx.new_page()
        try:
            pg.goto(url, wait_until="networkidle", timeout=45000)
            try:
                pg.wait_for_selector(".node--view-mode-search-result", timeout=15000)
            except Exception:
                pass
            pg.wait_for_timeout(6000)
            return pg.content()
        finally:
            b.close()


def ingest_srb_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = f"{_BASE}/en/news/search" if page == 0 else f"{_BASE}/en/news/search?page={page}"
        rows = _parse_news_cards(_render_news_page(url) or "")
        if not rows and page > 0:
            # an empty page is usually SRB throttling the rapid render, not the
            # end of results — back off once and retry before giving up.
            time.sleep(8.0)
            rows = _parse_news_cards(_render_news_page(url) or "")
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="srb", item_type="news", title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=u))
        if new == 0:
            break
        time.sleep(4.0)
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = _fetch_detail_spaced(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
            time.sleep(1.5)
    return items


# --- publications (public register of documents) ---------------------------
def _parse_register_rows(html: str) -> list[tuple[str, str, datetime | None]]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup
    out = []
    for row in main.select(".views-row"):
        h3a = row.select_one("h3 a[href]") or row.find("a", href=True)
        if not h3a or not h3a.get("href"):
            continue
        href = h3a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        icon = row.select_one(".srb-document-icon")
        h3 = row.select_one("h3")
        title = clean((icon.get("title") if icon and icon.get("title") else None)
                      or (h3.get_text(" ", strip=True) if h3 else None)
                      or h3a.get_text(" ", strip=True))
        if not title:
            continue
        t = row.select_one("time[datetime]")
        doc_dt = None
        if t and t.get("datetime"):
            try:
                doc_dt = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00"))
            except ValueError:
                doc_dt = None
        out.append((url, title, doc_dt))
    return out


def ingest_srb_publications(*, fetch_bodies: bool = True, max_pages: int = 10) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = (f"{_BASE}/en/public-register-of-documents" if page == 0
               else f"{_BASE}/en/public-register-of-documents?page={page}")
        r = _get(url)
        if r is None:
            break
        rows = _parse_register_rows(r.text)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="srb", item_type="publication", title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind="pdf", guid=u))
        if new == 0:
            break
        time.sleep(2.5)
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = _fetch_detail_spaced(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            it.source_kind = kind if kind in ("pdf", "html") else it.source_kind
            time.sleep(1.0)
    return items


# --- events ----------------------------------------------------------------
def _parse_event_cards(html: str) -> list[tuple[str, str, datetime | None]]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup
    out = []
    for n in main.select(".node--type-srb-event"):
        a = n.find("a", href=True)
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title_el = n.select_one(".srb-event__title") or n.select_one("h2, h3")
        title = clean(title_el.get_text(" ", strip=True)) if title_el else None
        if not title:
            continue
        cal = n.select_one(".srb-calendar-date")
        doc_dt = _parse_monthfirst(cal.get_text(" ", strip=True)) if cal else None
        if doc_dt is None:
            t = n.select_one("time[datetime]")
            if t and t.get("datetime"):
                try:
                    doc_dt = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00"))
                except ValueError:
                    doc_dt = None
        out.append((url, title, doc_dt))
    return out


def ingest_srb_events(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = f"{_BASE}/en/events" if page == 0 else f"{_BASE}/en/events?page={page}"
        r = _get(url)
        if r is None:
            break
        rows = _parse_event_cards(r.text)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="srb", item_type="event", title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=u))
        if new == 0:
            break
        time.sleep(2.5)
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = _fetch_detail_spaced(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
            time.sleep(1.0)
    return items
