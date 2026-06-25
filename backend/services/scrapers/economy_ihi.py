"""
Innovative Health Initiative JU — IHI (api_euratom_ju.md). /api/v2/ihi.

ihi.europa.eu serves an incomplete TLS certificate chain that Python's requests
rejects, and renders its listings client-side, so IHI is read through Playwright
(ignore_https_errors). Source map (verified 25 Jun 2026):
  - news  : /news-events/newsroom — rendered teasers linking to /news/<slug>.
  - topic : the about-IHI, funding and projects pages.

The IHI JU funds cross-sector health research and innovation (succeeding IMI),
bringing together pharma, medtech, biotech and digital health. Reads from
economy_items (body row seeded by migration 185); 5 mandatory datapoints. Scope:
read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html

_BASE = "https://www.ihi.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

NEWS_PAGE = f"{_BASE}/news-events/newsroom"
_NEWS_HREF = re.compile(r"^(?:https://www\.ihi\.europa\.eu)?/news/[a-z0-9-]{8,}")

_TOPIC_PATHS = [
    "/about-ihi",
    "/about-ihi/mission-and-objectives",
    "/about-ihi/research-and-innovation-agenda",
    "/about-ihi/ihi-funding-model",
    "/about-ihi/who-we-are",
    "/about-ihi/history",
    "/about-ihi/imi-ihi",
    "/about-ihi/plans-reports-and-finances",
    "/apply-funding",
    "/apply-funding/open-calls",
    "/apply-funding/future-opportunities",
    "/projects-results",
    "/projects-results/project-factsheets",
    "/projects-results/maps-statistics",
    "/resources-projects",
]


async def _render(page, url: str, settle: int = 2800) -> str | None:
    try:
        resp = await page.goto(url, wait_until="networkidle", timeout=55000)
        await page.wait_for_timeout(settle)
    except Exception:
        return None
    if resp is None or resp.status != 200:
        return None
    return await page.content()


async def _ingest_news_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA, ignore_https_errors=True)
        page = await ctx.new_page()
        html = await _render(page, NEWS_PAGE)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if not _NEWS_HREF.match(href):
                    continue
                title = clean(a.get_text(" ", strip=True))
                if not title or len(title) < 12:
                    continue
                url = norm_url(href if href.startswith("http") else _BASE + href)
                if url in seen:
                    continue
                seen.add(url)
                items.append(Item(body_code="ihi", item_type="news", title=title[:300],
                                  public_url=url, creation_date=now, source_kind="html", guid=url))
        if fetch_bodies:
            for it in items:
                dhtml = await _render(page, it.public_url, settle=1800)
                if dhtml:
                    it.body_txt, it.body_html = extract_html(dhtml)
        await b.close()
    return items


async def _ingest_topics_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA, ignore_https_errors=True)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            html = await _render(page, url, settle=2000)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.select_one("main h1, h1")
            if h1 and len(h1.get_text(strip=True)) > 2:
                title = clean(h1.get_text(" ", strip=True))
            else:
                title = clean(path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title())
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="ihi", item_type="topic", title=title[:300],
                              public_url=norm_url(url), creation_date=now, source_kind="html",
                              guid=norm_url(url), body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_ihi_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_ihi_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
