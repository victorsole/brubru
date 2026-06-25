"""
CERT-EU — Cybersecurity Service for the Union institutions, bodies, offices and
agencies (cert.europa.eu). /api/v2/cert-eu.

CERT-EU runs a static site, reachable with plain requests for the blog, but its
publication listings (security advisories, threat intelligence, guidance) are
rendered client-side, so those are read through Playwright. Source map (verified
25 Jun 2026):
  - news        : /blog — article.news--articles--item (h3 title link + a date in
                  the <time> text + description). Plain requests.
  - advisory    : /publications/security-advisories/<year> — .publications--list--item
                  rows (advisory id + title + "Weekday, Month DD, YYYY" date).
                  Rendered. The CERT-EU vulnerability advisories.
  - publication : /publications/threat-intelligence/ + /publications/security-guidance/
                  — same .publications--list--item layout: Cyber Briefs, Threat
                  Landscape Reports, frameworks and guidance. Rendered.
  - topic       : about, the Interinstitutional Cybersecurity Board (IICB) and its
                  annual reports, the publication hubs and vacancies.

Reads from economy_items (body row seeded by migration 166); 5 mandatory
datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://cert.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

NEWS_PAGES = [f"{_BASE}/blog"]
# Current + previous year of advisories (the year archive pages).
_ADVISORY_PAGES = [f"{_BASE}/publications/security-advisories/2026",
                   f"{_BASE}/publications/security-advisories/2025"]
_PUBLICATION_PAGES = [f"{_BASE}/publications/threat-intelligence/",
                      f"{_BASE}/publications/security-guidance/"]

_TOPIC_PATHS = [
    "/about-us",
    "/iicb/",
    "/iicb/annual-report-2025/",
    "/iicb/annual-report-2024/",
    "/publications",
    "/publications/security-advisories/",
    "/publications/security-guidance/",
    "/publications/threat-intelligence/",
    "/vacancies",
]

_WEEKDAY = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_DATE = re.compile(rf"(?:{_WEEKDAY}),?\s+([A-Z][a-z]+ \d{{1,2}}, \d{{4}})")


def _md_date(text: str) -> datetime | None:
    m = _DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def ingest_cert_eu_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(NEWS_PAGES[0])
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for art in soup.select("article.news--articles--item, article"):
        a = art.select_one(".news--articles--item--title a[href], h3 a[href], h2 a[href]")
        if not a or "/blog/" not in a.get("href", ""):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        if url in seen:
            continue
        seen.add(url)
        title = clean(a.get_text(" ", strip=True))
        t = art.select_one("time")
        doc_dt = _md_date(t.get_text(" ", strip=True)) if t else None
        desc = art.select_one(".news--articles--item--description")
        summary = clean(desc.get_text(" ", strip=True)[:300]) if desc else None
        items.append(Item(body_code="cert_eu", item_type="news", title=title[:300],
                          public_url=url, summary=summary, document_date=doc_dt,
                          creation_date=now, source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


async def _scrape_list_async(pages, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for listing in pages:
            try:
                await page.goto(listing, wait_until="networkidle", timeout=55000)
                await page.wait_for_timeout(2200)
            except Exception:
                continue
            soup = BeautifulSoup(await page.content(), "html.parser")
            for row in soup.select(".publications--list--item"):
                a = row.select_one("a[href]")
                if not a or not a.get("href"):
                    continue
                url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
                if url in seen:
                    continue
                seen.add(url)
                txt = clean(row.get_text(" ", strip=True))
                doc_dt = _md_date(txt)
                m = _DATE.search(txt)
                title = clean(txt[:m.start()]) if m else clean(a.get_text(" ", strip=True))
                if not title:
                    continue
                items.append(Item(body_code="cert_eu", item_type=item_type, title=title[:300],
                                  public_url=url, document_date=doc_dt, creation_date=now,
                                  source_kind="html", guid=url))
        await b.close()
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_cert_eu_advisories(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_scrape_list_async(_ADVISORY_PAGES, "advisory", fetch_bodies=fetch_bodies))


def ingest_cert_eu_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_scrape_list_async(_PUBLICATION_PAGES, "publication", fetch_bodies=fetch_bodies))


def ingest_cert_eu_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("cert_eu", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
