"""
ECA — European Court of Auditors (api_eca.md). /api/v2/eca.

The ECA's site (eca.europa.eu) is a SharePoint single-page app: the listing and
about pages render their content client-side, so ECA is read through Playwright.
Source map (verified 25 Jun 2026):
  - news        : /en/all-news          — .card blocks with a title link to
                  /en/news/<id> and a <time datetime="DD/MM/YYYY">.
  - publication : /en/search-publications — .media__body rows with .media__title a
                  (e.g. "Special report 16/2026: ...") linking to
                  /en/publications/<id> and a <time class="date" datetime="DD-MM-YYYY">.
                  The ECA audit output: special reports, reviews, opinions, annual
                  reports.
  - event       : /en/events            — .card-event blocks with a title link.
  - topic       : about + documents-and-research landing pages.

Playwright-only (SPA), so the refresh runs on the cron with Chromium. Reads from
economy_items (body row seeded by migration 168); 5 mandatory datapoints. Scope:
read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html

_BASE = "https://www.eca.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

NEWS_PAGE = f"{_BASE}/en/all-news"
PUB_PAGE = f"{_BASE}/en/search-publications"
EVENTS_PAGE = f"{_BASE}/en/events"

_TOPIC_PATHS = [
    "/en/mission-vision-and-values",
    "/en/governance",
    "/en/organisation",
    "/en/legal-framework",
    "/en/history",
    "/en/what-we-do",
    "/en/the-eu-finances",
    "/en/international-overview",
    "/en/institutional-relations",
    "/en/transparency",
    "/en/topics",
    "/en/multiple-reports",
    "/en/annual-activity-reports",
    "/en/journal",
]

_DATE = re.compile(r"(\d{2})[/-](\d{2})[/-](\d{4})")


def _date(s: str) -> datetime | None:
    m = _DATE.search(s or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _abs(href: str) -> str:
    return norm_url(href if href.startswith("http") else _BASE + href)


async def _render(page, url: str, settle: int = 3000) -> str | None:
    try:
        resp = await page.goto(url, wait_until="networkidle", timeout=55000)
        await page.wait_for_timeout(settle)
    except Exception:
        return None
    if resp is None or resp.status != 200:
        return None
    return await page.content()


def _parse_news(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".card"):
        a = card.select_one('a[href*="/en/news/"], a[href]')
        if not a or not a.get("href") or "/en/" not in a["href"]:
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 8:
            continue
        t = card.select_one("time")
        doc_dt = _date(t.get("datetime") or t.get_text(strip=True)) if t else None
        out.append((_abs(a["href"]), title, doc_dt))
    return out


def _parse_publications(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for media in soup.select(".media, .media__body"):
        a = media.select_one(".media__title a[href], h3 a[href], a[href]")
        if not a or not a.get("href"):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 8:
            continue
        t = media.select_one("time")
        doc_dt = _date(t.get("datetime") or t.get_text(strip=True)) if t else None
        out.append((_abs(a["href"]), title, doc_dt))
    return out


def _parse_events(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".card-event, .card"):
        a = card.select_one("a[href]")
        if not a or not a.get("href") or "/en/" not in a["href"]:
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue
        t = card.select_one("time")
        doc_dt = _date(t.get("datetime") or t.get_text(strip=True)) if t else None
        out.append((_abs(a["href"]), title, doc_dt))
    return out


async def _ingest_listing(url: str, parser, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        html = await _render(page, url)
        rows = parser(html) if html else []
        for purl, title, doc_dt in rows:
            if purl in seen:
                continue
            seen.add(purl)
            it = Item(body_code="eca", item_type=item_type, title=title[:300],
                      public_url=purl, document_date=doc_dt, creation_date=now,
                      source_kind="html", guid=purl)
            if fetch_bodies:
                dhtml = await _render(page, purl, settle=2000)
                if dhtml:
                    it.body_txt, it.body_html = extract_html(dhtml)
            items.append(it)
        await b.close()
    return items


async def _ingest_topics_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            html = await _render(page, url, settle=2200)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.select_one("main h1, h1")
            title = clean(h1.get_text(" ", strip=True)) if h1 else ""
            # The SPA h1 is a route slug; prefer a real heading or the slug text.
            if not title or "-" in title and " " not in title:
                title = clean(path.rsplit("/", 1)[-1].replace("-", " ").title())
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="eca", item_type="topic", title=title[:300],
                              public_url=norm_url(url), creation_date=now, source_kind="html",
                              guid=norm_url(url), body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_eca_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_listing(NEWS_PAGE, _parse_news, "news", fetch_bodies=fetch_bodies))


def ingest_eca_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_listing(PUB_PAGE, _parse_publications, "publication", fetch_bodies=fetch_bodies))


def ingest_eca_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_listing(EVENTS_PAGE, _parse_events, "event", fetch_bodies=fetch_bodies))


def ingest_eca_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
