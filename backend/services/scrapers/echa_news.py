"""European Chemicals Agency — news. Backs /api/v2/echa/news.

ECHA publishes its news alerts on the news archive (a Liferay page). Each item
carries a date, a title and a link to the article. One row per news item.
"""
from __future__ import annotations

import asyncio
import html as _html
import re
from datetime import datetime, timezone

from services.scrapers.economy_common import Item, clean, extract_html

_ARCHIVE = "https://echa.europa.eu/news-and-events/news-alerts/archive"
_BASE = "https://echa.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

# Curated about / committees / regulation landing pages, snapshotted as topics.
# echa.europa.eu blocks the default crawler UA, so these are rendered through
# Playwright (local refresh).
_TOPIC_PATHS = [
    "/about-us/who-we-are",
    "/about-us/what-we-do",
    "/about-us/committees-and-forum",
    "/about-us/who-we-are/committee-for-risk-assessment",
    "/about-us/who-we-are/committee-for-socio-economic-analysis",
    "/about-us/who-we-are/biocidal-products-committee",
    "/about-us/who-we-are/member-state-committee",
    "/about-us/who-we-are/enforcement-forum",
    "/about-us/what-we-do/environment",
    "/about-us/health",
    "/about-us/chemicals-at-work",
    "/about-us/partners-and-networks/member-states-and-competent-authorities",
    "/about-us/partners-and-networks/international-cooperation",
    "/regulations/reach/understanding-reach",
    "/regulations/clp/understanding-clp",
    "/regulations/biocidal-products-regulation/understanding-bpr",
]
# <span ...>10 June 2026 - </span> ... <a href="/-/slug">Title</a>
_ITEM = re.compile(
    r'<span[^>]*>\s*(\d{1,2}\s+\w+\s+\d{4})\s*-\s*</span>\s*'
    r'<a href="(/-/[^"]+)"[^>]*>(.*?)</a>', re.S)


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip())


def _date(d: str) -> datetime | None:
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(d.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse(html: str, now: datetime) -> list[Item]:
    out: dict[str, Item] = {}
    for date_s, href, raw in _ITEM.findall(html):
        title = _txt(raw)
        if not title:
            continue
        url = _BASE + href
        if url in out:
            continue
        dt = _date(date_s)
        lines = [title, f"Date: {dt.date()}" if dt else ""]
        lines = [l for l in lines if l]
        out[url] = Item(
            body_code="echa", item_type="news", title=clean(title)[:120], public_url=url,
            summary=clean(f"{date_s} - {title}")[:200],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=dt, creation_date=now, source_kind="echa_news", guid=url)
    return list(out.values())


async def _scrape() -> list[Item]:
    from playwright.async_api import async_playwright
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        await page.goto(_ARCHIVE, wait_until="networkidle", timeout=55000)
        await page.wait_for_timeout(3000)
        items = _parse(await page.content(), now)
        await b.close()
    return items


def ingest_echa_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return asyncio.run(_scrape())


async def _scrape_topics(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2500)
            except Exception:
                continue
            if resp is None:
                continue
            content = await page.content()
            # ECHA's WAF returns HTTP 403 but still renders the real page for a
            # browser (Aug 2026); only its ~10KB challenge stub lacks content, so
            # gate on rendered size, not status.
            if len(content) < 40000:
                continue
            soup = BeautifulSoup(content, "html.parser")
            h1 = soup.select_one(".page-title, main h1, h1")
            if h1 and len(h1.get_text(strip=True)) > 2:
                title = clean(h1.get_text(" ", strip=True))
            elif soup.title and soup.title.get_text(strip=True):
                title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
            else:
                title = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            body_txt, body_html = (extract_html(content) if fetch_bodies else (None, None))
            items.append(Item(body_code="echa", item_type="topic", title=title[:300],
                              public_url=url, creation_date=now, source_kind="html",
                              guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_echa_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return asyncio.run(_scrape_topics(fetch_bodies=fetch_bodies))
