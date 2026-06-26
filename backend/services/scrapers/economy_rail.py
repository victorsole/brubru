"""
Europe's Rail JU (api_euratom_ju.md). /api/v2/europes-rail.

rail-research.europa.eu is a WordPress/Elementor site: the news listing is rendered
client-side (so news is read through Playwright), while the about and reference
pages are plain HTML. Source map (verified 25 Jun 2026):
  - news  : /news — rendered links to /latest-news/<slug>.
  - topic : about, members, governance, projects, pillars and reference-document pages.

Europe's Rail is the EU Joint Undertaking that funds research and innovation to
deliver an integrated European railway network (succeeding Shift2Rail). Reads from
economy_items (body row seeded by migration 189); 5 mandatory datapoints. Scope:
read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, fetch_detail, snapshot_topics,
)

_BASE = "https://rail-research.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

NEWS_PAGE = f"{_BASE}/news"
_NEWS_HREF = re.compile(r"/latest-news/[a-z0-9-]{6,}")

_TOPIC_PATHS = [
    "/about-europes-rail/",
    "/about-europes-rail/europes-rail-ju-members/",
    "/about-europes-rail/europes-rail-structure-of-governance/",
    "/rail-projects",
    "/solutions-catalogue",
    "/shift2rail-projects/",
    "/innovation-pillar/",
    "/system_pillar/",
    "/about-deployment-group/",
    "/participate/call-for-proposals/",
    "/about-europes-rail/europes-rail-reference-documents/europes-rail-key-documents/",
    "/about-europes-rail/europes-rail-reference-documents/europes-rail-annual-activity-report/",
    "/about-europes-rail/europes-rail-reference-documents/europes-rail-annual-work-plan-and-budget/",
]


async def _ingest_news_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        try:
            await page.goto(NEWS_PAGE, wait_until="networkidle", timeout=55000)
            await page.wait_for_timeout(3000)
            html = await page.content()
        except Exception:
            await b.close()
            return items
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not _NEWS_HREF.search(href):
                continue
            title = clean(a.get_text(" ", strip=True))
            if not title or len(title) < 12:
                continue
            url = norm_url(href if href.startswith("http") else _BASE + href)
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="rail", item_type="news", title=title[:300],
                              public_url=url, creation_date=now, source_kind="html", guid=url))
        await b.close()
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
    return items


def ingest_rail_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_rail_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("rail", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
