"""
EDPS — European Data Protection Supervisor (api_market.md L421-505). /api/v2/edps.

edps.europa.eu is a Drupal site, server-rendered and reachable with plain requests.
Its listings render as article.node--type-edpsweb-<kind> blocks with a .node__title,
a link field and a <time datetime>. Source map (verified 25 Jun 2026):
  - news          : /press-publications/press-news/news_en       (edpsweb-news)
  - press_release : /press-publications/press-news/press-releases_en (edpsweb-press-release; PDFs)
  - publication   : /press-publications/publications/annual-activity-reports_en
                    + /press-publications/publications/factsheets_en (edpsweb-publication; PDFs)
  - topic         : about + data-protection role/work + technology-monitoring + AI pages.

The EDPS is the EU's independent data-protection authority, supervising the EU
institutions and advising on data-protection legislation. Reads from economy_items
(body row seeded by migration 172); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.edps.europa.eu"

NEWS_PAGE = f"{_BASE}/press-publications/press-news/news_en"
PRESS_PAGE = f"{_BASE}/press-publications/press-news/press-releases_en"
PUB_PAGES = [f"{_BASE}/press-publications/publications/annual-activity-reports_en",
             f"{_BASE}/press-publications/publications/factsheets_en"]

_TOPIC_PATHS = [
    "/about-edps_en",
    "/about/supervisor_en",
    "/about/about-us_en",
    "/data-protection_en",
    "/data-protection/data-protection/legislation_en",
    "/data-protection/our-role-supervisor_en",
    "/data-protection/our-role-advisor_en",
    "/data-protection/our-work/our-work-by-type/audits_en",
    "/data-protection/our-role-supervisor/complaints_en",
    "/data-protection/our-work/our-work-by-type/guidelines_en",
    "/data-protection/technology-monitoring_en",
    "/data-protection/our-work/our-work-by-type/techdispatch_en",
    "/data-protection/technology-monitoring/techsonar_en",
    "/data-protection/eu-institutions-dpo_en",
    "/data-protection/our-work/international-cooperation_en",
    "/artificial-intelligence/artificial-intelligence-act_en",
    "/data-protection/our-work/subjects/artificial-intelligence_en",
]


def _best_link(node):
    for sel in ('.field[class*="link"] a[href]', 'a[href$=".pdf"]', ".node__title a[href]"):
        a = node.select_one(sel)
        if a and a.get("href"):
            return a
    for a in node.select("a[href]"):
        if a.get("href") and not a.find("img") and len(a.get_text(strip=True)) > 3:
            return a
    return None


def _parse_nodes(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for node in soup.select('[class*="node--type-edpsweb"]'):
        te = node.select_one(".node__title")
        title = clean(te.get_text(" ", strip=True)) if te else ""
        a = _best_link(node)
        if not title or not a or not a.get("href"):
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        t = node.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        out.append((url, title, doc_dt, ".pdf" in url.lower()))
    return out


def _scrape(pages, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    # EDPS sits behind a WAF that returns 202/empty (and 403 to curl) for raw HTTP
    # clients (Aug 2026), so http_get gets nothing. Render the listings through the
    # headless-browser WafBrowserFetcher (same tool as FRA / eu_osha); the
    # node--type-edpsweb markup the parser expects is unchanged.
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    page_list = pages if isinstance(pages, list) else [pages]
    with WafBrowserFetcher() as f:
        html_by_page = {}
        for page in page_list:
            res = f.fetch(page, strip_chrome=False)
            html_by_page[page] = getattr(res, "html", None)
    for page in page_list:
        html = html_by_page.get(page)
        if not html:
            continue
        for url, title, doc_dt, is_pdf in _parse_nodes(html):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="edps", item_type=item_type, title=title[:300],
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="pdf" if is_pdf else "html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_edps_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGE, "news", fetch_bodies=fetch_bodies)


def ingest_edps_press_releases(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # EDPS collapsed press-releases + publications into the single press-news feed
    # (Europa ECL migration, Aug 2026): the old /press-releases_en and
    # /publications/*_en listings now all redirect to the same news content. Running
    # them here would mislabel news items as press_release, so return nothing until
    # a distinct source resurfaces. edps `news` carries the merged feed.
    return []


def ingest_edps_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # See ingest_edps_press_releases: the distinct publications listing is gone;
    # returning [] avoids mislabeling the merged press-news feed as publications.
    return []


def ingest_edps_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # edps.europa.eu rate-limits bursts; pace requests and retry harder.
    return snapshot_topics("edps", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies,
                           pace=0.6, retries=2)
