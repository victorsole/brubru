"""
SatCen — European Union Satellite Centre (api_defence.md). /api/v2/satcen.

satcen.europa.eu is an Angular single-page app, so it is read through Playwright.
Source map (verified 25 Jun 2026):
  - news  : /news/news — article.featured-full-width blocks with a heading/title, an
            image and a link to /News/<slug>.
  - topic : the who-we-are, what-we-do, services and key-documents pages.

SatCen provides geospatial intelligence from satellite imagery to support EU
decision-making in security and defence (CSDP missions, crisis response, treaty
monitoring). Reads from economy_items (body row seeded by migration 177); 5
mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html

_BASE = "https://www.satcen.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

NEWS_PAGE = f"{_BASE}/news/news"
_DATE = re.compile(r"(\d{1,2})[ /.-]([A-Za-z]{3,9}|\d{1,2})[ /.-](\d{4})")

_TOPIC_PATHS = [
    "/who-we-are/our-mission",
    "/who-we-are/the_centre",
    "/page/structure",
    "/what-we-do/our-services",
    "/page/geospatial_intelligence",
    "/page/training",
    "/page/capability_development_initiatives",
    "/services/copernicus",
    "/services/humanitarian_aid",
    "/services/contingency_planning_",
    "/services/critical_infrastructure",
    "/services/military_capabilities",
    "/services/weapons_of_mass_destruction",
    "/page/key_documents_and_publications",
]


async def _render(page, url: str, settle: int = 3000) -> str | None:
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
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        html = await _render(page, NEWS_PAGE)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for art in soup.select("article"):
                a = art.select_one('a[href*="/News/"], a[href*="/news/"]')
                if not a or not a.get("href"):
                    continue
                href = a["href"]
                if re.search(r"/news/news/?$", href, re.I):
                    continue
                url = norm_url(href if href.startswith("http") else _BASE + href)
                if url in seen:
                    continue
                h = art.select_one("h1, h2, h3, h4, .title")
                img = art.select_one("img[alt]")
                title = clean(h.get_text(" ", strip=True)) if h else ""
                if not title and img:
                    title = clean(img.get("alt", ""))
                if not title or len(title) < 8:
                    continue
                seen.add(url)
                m = _DATE.search(art.get_text(" ", strip=True))
                items.append(Item(body_code="satcen", item_type="news", title=title[:300],
                                  public_url=url, creation_date=now, source_kind="html", guid=url))
        if fetch_bodies:
            for it in items:
                dhtml = await _render(page, it.public_url, settle=2000)
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
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            html = await _render(page, url, settle=2200)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.select_one("main h1, h1, .title")
            if h1 and len(h1.get_text(strip=True)) > 2:
                title = clean(h1.get_text(" ", strip=True))
            else:
                title = clean(path.rstrip("/").rsplit("/", 1)[-1].replace("_", " ").replace("-", " ").title())
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="satcen", item_type="topic", title=title[:300],
                              public_url=norm_url(url), creation_date=now, source_kind="html",
                              guid=norm_url(url), body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_satcen_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_satcen_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
