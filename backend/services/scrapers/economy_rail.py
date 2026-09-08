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
    Item, clean, norm_url, fetch_detail, fetch_detail_dated, snapshot_topics,
    http_get, error_body_reason,
)

_BASE = "https://rail-research.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

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
            # The listing is a Playwright render of anchor tags only -- it carries no
            # date, so every rail news row was written with document_date NULL (17
            # rows, measured 8 Sep 2026). The item pages publish
            # <meta property="article:published_time">, and fetch_detail_dated reads
            # it from the fetch this loop already makes.
            body_txt, body_html, kind, doc_dt, _carrier = fetch_detail_dated(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if it.document_date is None and doc_dt is not None:
                it.document_date = doc_dt
    return items


# EU-Rail runs WordPress and exposes the REST API, which is a far better source than
# rendering the listing (measured 8 September 2026):
#
#   * DISCOVERY: the Playwright listing yielded ONE item, against 17 rows already in
#     the store and `x-wp-total: 528` posts actually published. The rendered page is
#     anchor-tags-only and the selector was finding almost nothing.
#   * DATE: every post carries `date_gmt`, authoritative and needing no extraction.
#   * NO BROWSER: one HTTP call replaces a Chromium launch, which matters on a
#     memory-constrained machine (feedback_mac_has_8gb_never_fan_out_local_workers).
#
# The BODY still comes from the item page, deliberately. `content.rendered` is
# unreliable here: some posts return raw Divi page-builder shortcodes
# (`[et_pb_section fb_built="1" ...]`) rather than prose, and storing that as body_txt
# is the same class of defect as storing a 404 page. `error_body_reason` now rejects
# page-builder markup, and fetch_detail_dated gets clean text from the rendered page.
# Which WP URL sections are news, and what each maps to on the v2 contract. Anything
# not listed here is deliberately dropped rather than mislabelled as news.
_RAIL_KIND_BY_PATH = {
    "latest-news": "news",
    "press-releases": "press_release",
}


def _rail_section(url: str) -> str:
    m = re.match(r"^https?://[^/]+/([^/]+)/", url or "")
    return m.group(1) if m else ""


_WP_POSTS = f"{_BASE}/wp-json/wp/v2/posts"
_WP_FIELDS = "id,date_gmt,link,title"


def _wp_posts(per_page: int, max_pages: int) -> list[dict]:
    import json as _json
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        url = (f"{_WP_POSTS}?per_page={per_page}&page={page}"
               f"&_fields={_WP_FIELDS}&orderby=date&order=desc")
        r = http_get(url)
        if r is None:
            break
        try:
            batch = _json.loads(r.text)
        except Exception:  # noqa: BLE001
            break
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
    return out


def ingest_rail_news(*, fetch_bodies: bool = True, per_page: int = 50,
                     max_pages: int = 1, **_) -> list[Item]:
    """News from the WordPress REST API. Falls back to the rendered listing only if
    the API gives nothing, so a WP change cannot silently zero the body."""
    import html as _html
    from datetime import datetime as _dt

    posts = _wp_posts(per_page, max_pages)
    if not posts:
        import asyncio
        return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))

    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for p in posts:
        link = norm_url((p.get("link") or "").strip())
        if not link or link in seen:
            continue
        # The WP `posts` collection is NOT all news. Measured on page 1 of 50:
        # 42 /latest-news/, 2 /press-releases/, 5 /procurement-opportunities/ and
        # 1 /publications/. Procurement notices are tenders and belong to the tender
        # surface; a publication is a document. Admitting them would put six
        # non-news rows in the news feed and create a second home for facts that
        # already have one, which is what the /news/all union exists to avoid.
        kind = _RAIL_KIND_BY_PATH.get(_rail_section(link))
        if kind is None:
            continue
        seen.add(link)
        title = clean(_html.unescape((p.get("title") or {}).get("rendered") or ""))
        if not title:
            continue
        doc_dt = None
        raw = (p.get("date_gmt") or "").strip()
        if raw:
            try:
                doc_dt = _dt.fromisoformat(raw).replace(tzinfo=timezone.utc)
            except ValueError:
                doc_dt = None
        items.append(Item(body_code="rail", item_type=kind, title=title[:300],
                          public_url=link, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=link))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind, doc_dt, _c = fetch_detail_dated(it.public_url)
            reason = error_body_reason(body_txt)
            if reason:
                print(f"[rail] discarding body for {it.public_url}: {reason}")
            else:
                it.body_txt, it.body_html = body_txt, body_html
            if it.document_date is None and doc_dt is not None:
                it.document_date = doc_dt
    return items


def ingest_rail_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("rail", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
