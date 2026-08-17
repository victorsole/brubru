"""European Union Agency for Fundamental Rights — databases + topics.
FRA is behind an Anubis proof-of-work wall, so the listings are walked through a
real browser (eu_agency_listing.walk_browser). One database per ingestor.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html
from services.scrapers.eu_agency_listing import ingest_browser, _UA

_BASE = "https://fra.europa.eu"

_THEMES = [
    "access-asylum", "artificial-intelligence-and-big-data",
    "borders-and-information-systems", "business-and-human-rights",
    "child-protection", "children-youth-and-older-people", "civil-justice",
    "civil-society", "climate-change-and-environmental-protection",
    "consumer-protection", "data-protection", "defendants-rights",
    "eu-charter-fundamental-rights", "hate-crime", "human-rights-due-diligence",
    "inter-governmental-human-rights-systems",
    "irregular-migration-return-and-immigration-detention",
    "judicial-cooperation-and-rule-law", "just-and-green-transition",
    "legal-migration-and-integration", "national-human-rights-systems-and-bodies",
    "people-disabilities", "racial-and-ethnic-origin", "religion-and-belief",
    "roma", "security", "sex-sexual-orientation-and-gender",
    "trafficking-and-labour-exploitation", "unlawful-profiling", "victims-rights",
]
# Curated about + fundamental-rights theme pages, snapshotted as topics. FRA is
# behind Anubis, so each page is rendered in a real browser (networkidle + settle).
_TOPIC_PATHS = [
    "/en/about-fra/who-we-are",
    "/en/about-fra/what-we-do",
] + [f"/en/themes/{t}" for t in _THEMES]


def ingest_fra_case_law(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return ingest_browser(_BASE, "/en/case-law-database", "fra", "case_law",
                          "/en/caselaw-reference/", "fra_caselaw")


async def _scrape_topics_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = norm_url(_BASE + path)
            try:
                resp = await page.goto(url, wait_until="networkidle", timeout=55000)
                await page.wait_for_timeout(1800)
            except Exception:
                continue
            if resp is None or resp.status != 200:
                continue
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.select_one("main h1, h1")
            if h1 and len(h1.get_text(strip=True)) > 2:
                title = clean(h1.get_text(" ", strip=True))
            elif soup.title and soup.title.get_text(strip=True):
                title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
            else:
                title = clean(path.rsplit("/", 1)[-1].replace("-", " ").title())
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            # Skip pages where the Anubis challenge never cleared (no real body).
            if fetch_bodies and (not body_txt or len(body_txt) < 200):
                continue
            items.append(Item(body_code="fra", item_type="topic", title=(title or url)[:300],
                              public_url=url, creation_date=now, source_kind="html",
                              guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_fra_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_scrape_topics_async(fetch_bodies=fetch_bodies))


# The EU Charter of Fundamental Rights (CELEX 12012P/TXT) is static public law:
# 54 articles across 7 titles, unchanged since 2012. FRA's Charterpedia listing
# went behind an Anubis anti-bot verification wall (Aug 2026), so re-source the
# articles authoritatively from EUR-Lex rather than scraping past the wall — more
# reliable, and the canonical text. EUR-Lex marks each article with a `ti-art`
# ("Article N") heading followed by an `sti-art` subtitle (the article name).
_CHARTER_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:12012P/TXT"


def ingest_fra_charterpedia(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import re
    import urllib.request
    req = urllib.request.Request(_CHARTER_URL, headers={"User-Agent": _UA})
    try:
        html = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for ti in soup.select(".ti-art"):
        m = re.match(r"Article\s+(\d{1,2})\b", ti.get_text(" ", strip=True))
        if not m:
            continue
        n = m.group(1)
        sti = ti.find_next(class_="sti-art")
        name = clean(sti.get_text(" ", strip=True)) if sti else ""
        if not name:
            continue
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:12012P/TXT#art_{n}"
        body = f"{name}\nEU Charter of Fundamental Rights, Article {n} (CELEX 12012P/TXT)."
        items.append(Item(
            body_code="fra", item_type="charter_article",
            title=f"Article {n}: {name}"[:300], public_url=url,
            body_txt=clean(body), document_date=None, creation_date=now,
            source_kind="eurlex_charter", guid=f"charter-art-{n}"))
    return items
