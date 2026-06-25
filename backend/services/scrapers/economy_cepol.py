"""
CEPOL — EU Agency for Law Enforcement Training (api_socjust.md). /api/v2/cepol.

cepol.europa.eu is a modern JS-rendered site (Next.js) that blocks the default
BrubruBot user agent: both its listing and its detail pages are empty on the
plain requests path, so CEPOL is delivered through Playwright (real browser,
paced). News items come from the rendered /newsroom/news listing (title links to
/newsroom/news/<slug>), each detail page carrying a "DD Month YYYY" date; the
thematic-area, training and international-cooperation pages are substantial
reference content, snapshotted as topics.

Source map (verified 25 Jun 2026):
  - news  : /newsroom/news               (rendered listing -> per-item detail)
  - topic : thematic-areas + training-education + international-cooperation pages

Playwright-only, so the refresh runs locally, not on the Railway cron. Reads from
economy_items (body row seeded by migration 154); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, extract_html

_BASE = "https://www.cepol.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

NEWS_LISTING = "/newsroom/news"
_NEWS_HREF = re.compile(r"^/newsroom/news/[a-z0-9-]{8,}$")

_TOPIC_PATHS = [
    "/thematic-areas/cepol-exchange-programme",
    "/thematic-areas/counter-terrorism",
    "/thematic-areas/cybercrime-and-cyber-related-crime",
    "/thematic-areas/european-union-missions-csdp",
    "/thematic-areas/fundamental-rights-and-data-protection",
    "/thematic-areas/higher-education-and-research",
    "/thematic-areas/law-enforcement-cooperation-information-exchange-and-interoperability",
    "/thematic-areas/law-enforcement-technologies-forensics-and-specific-areas",
    "/thematic-areas/leadership-training-and-other-skills",
    "/thematic-areas/public-order-and-prevention",
    "/thematic-areas/serious-and-organised-crime",
    "/training-education/our-learning-portfolio",
    "/training-education/leed",
    "/training-education/cepol-knowledge-centres",
    "/training-education/training-quality-standards",
    "/training-education/european-multidisciplinary-platform-against-criminal-threats",
    "/international-cooperation/ct-inflow",
    "/international-cooperation/euromed",
    "/international-cooperation/topcop",
    "/international-cooperation/wb-pact",
    "/international-cooperation/eu4sec-moldova",
    "/scientific-knowledge-research",
    "/publications",
]

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DMY = re.compile(rf"(\d{{1,2}})\s+({_MONTHS})\s+(\d{{4}})")
_MONTH_IDX = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def _text_date(s: str) -> datetime | None:
    m = _DMY.search(s)
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), _MONTH_IDX[m.group(2).lower()],
                        int(m.group(1)), tzinfo=timezone.utc)
    except (ValueError, KeyError):
        return None


def _title_from(soup: BeautifulSoup, path: str) -> str:
    h1 = soup.select_one("main h1, article h1, h1")
    if h1:
        t = clean(h1.get_text(" ", strip=True))
        if t and len(t) > 3 and "can't find that page" not in t.lower():
            return t[:300]
    if soup.title and soup.title.get_text(strip=True):
        return clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])[:300]
    return path.rsplit("/", 1)[-1].replace("-", " ").title()[:300]


async def _ingest_news_async(*, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        try:
            await page.goto(_BASE + NEWS_LISTING, wait_until="networkidle", timeout=55000)
            await page.wait_for_timeout(2000)
            listing = await page.content()
        except Exception:
            await b.close()
            return items
        soup = BeautifulSoup(listing, "html.parser")
        found: dict[str, str] = {}
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            txt = a.get_text(" ", strip=True)
            if _NEWS_HREF.match(href) and txt and len(txt) >= 12 and href not in found:
                found[href] = clean(txt)
        for href, title in found.items():
            url = _BASE + href
            doc_dt = None
            body_txt = body_html = None
            if fetch_bodies:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(1200)
                    dhtml = await page.content()
                    ds = BeautifulSoup(dhtml, "html.parser")
                    h1 = ds.select_one("main h1, article h1, h1")
                    if h1 and "can't find that page" not in h1.get_text().lower():
                        title = clean(h1.get_text(" ", strip=True))[:300] or title
                    body_txt, body_html = extract_html(dhtml)
                    doc_dt = _text_date(ds.get_text(" ", strip=True))
                except Exception:
                    pass
            items.append(Item(body_code="cepol", item_type="news", title=title[:300],
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url,
                              body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


async def _ingest_topics_async(*, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(900)
            except Exception:
                continue
            if resp is None or resp.status != 200:
                continue
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            title = _title_from(soup, path)
            if "can't find that page" in title.lower():
                continue
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="cepol", item_type="topic", title=title,
                              public_url=url, creation_date=now, source_kind="html",
                              guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_cepol_news(*, fetch_bodies: bool = True) -> list[Item]:
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_cepol_topics(*, fetch_bodies: bool = True) -> list[Item]:
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
