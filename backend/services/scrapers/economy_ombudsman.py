"""
European Ombudsman (api_eesc_cor_ombud.md). /api/v2/ombudsman.

ombudsman.europa.eu is a single-page app: the listing and about pages render their
content client-side, so the Ombudsman is read through Playwright. Source map
(verified 25 Jun 2026):
  - news  : /news-documents — rendered links to /news-document/<id>, each prefixed
            with a category label ("Latest news or press release", "Press release",
            "Speech", ...) that is stripped from the title.
  - topic : the about, strategy, how-we-work, areas-of-work, impact, complaints,
            inquiries-overview and publications pages.

The European Ombudsman investigates complaints of maladministration in the EU
institutions and bodies. Reads from economy_items (body row seeded by migration
171); 5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html

_BASE = "https://www.ombudsman.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

NEWS_PAGE = f"{_BASE}/news-documents"

_TOPIC_PATHS = [
    "/the-ombudsman",
    "/our-strategy/strategy",
    "/history",
    "/how-we-work",
    "/areas-of-work",
    "/impact",
    "/legal-basis/treaties",
    "/european-network-of-ombudsmen/about",
    "/make-a-complaint",
    "/strategic-issues/strategic-inquiries/all-strategic-inquiries",
    "/top-inquiries",
    "/publications",
]

_CATEGORY_PREFIX = re.compile(
    r"^(Latest news or press release|Press release|News article|News|Speech|"
    r"Document|Publication|Featured story|Decision|Report|Letter)\s+", re.I)


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
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        html = await _render(page, NEWS_PAGE)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select('a[href*="/news-document/"]'):
                href = a.get("href", "")
                if not re.search(r"/news-document/[a-z]+/\d+", href):
                    continue
                url = norm_url(href if href.startswith("http") else _BASE + href)
                if url in seen:
                    continue
                raw = clean(a.get_text(" ", strip=True))
                title = clean(_CATEGORY_PREFIX.sub("", raw))
                if not title or len(title) < 10:
                    continue
                seen.add(url)
                items.append(Item(body_code="ombudsman", item_type="news", title=title[:300],
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
            # The SPA h1 is a fixed "About" banner on every page, so prefer <title>;
            # fall back to a slug-derived title.
            tt = soup.title.get_text(strip=True) if soup.title else ""
            tt = clean(tt.split(" | ")[0].split(" - ")[0])
            slug = clean(path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title())
            title = tt if tt and tt.lower() not in ("about", "european ombudsman", "") else slug
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="ombudsman", item_type="topic", title=title[:300],
                              public_url=norm_url(url), creation_date=now, source_kind="html",
                              guid=norm_url(url), body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_ombudsman_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_ombudsman_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
