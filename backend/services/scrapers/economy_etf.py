"""
ETF — European Training Foundation (api_socjust.md). /api/v2/etf.

ETF runs a Drupal site (etf.europa.eu). The news and events listings pair a
<time datetime> with a content link (no stable class), so the scraper anchors on
each <time> and climbs to the nearest content anchor. The "what we do" pages are
server-rendered reference content. Plain requests work (no WAF). The publications
listing is JS-rendered, so news + events + topics. Source map (verified
25 Jun 2026):
  - news  : /en/news-and-events/news
  - event : /en/news-and-events/events
  - topic : /en/what-we-do/<slug>

Reads from economy_items (body row already seeded); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, http_get, fetch_detail, extract_html, _iso_dt

_BASE = "https://www.etf.europa.eu"

NEWS_PAGES = [(f"{_BASE}/en/news-and-events/news", "/news-and-events/news/")]
EVENT_PAGES = [(f"{_BASE}/en/news-and-events/events", "/news-and-events/events/")]

_TOPIC_PATHS = [
    "/en/what-we-do/career-guidance",
    "/en/what-we-do/digital-skills-and-learning",
    "/en/what-we-do/employability-and-transition-work",
    "/en/what-we-do/governance-and-financing-lifelong-learning",
    "/en/what-we-do/green-skills",
    "/en/what-we-do/innovative-teaching-and-learning-cnl",
    "/en/what-we-do/internationalising-vocational-excellence",
    "/en/what-we-do/qualifications-and-qualification-systems",
    "/en/what-we-do/quality-assurance-vocational-training",
    "/en/what-we-do/skills-demands-analysis",
    "/en/what-we-do/skills-enterprise-development",
    "/en/what-we-do/vocational-excellence",
]


def _parse(html: str, link_substr: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for tm in soup.select("time[datetime]"):
        node = tm
        link = None
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            link = node.select_one(f"a[href*='{link_substr}']")
            if link and len(link.get_text(strip=True)) >= 12:
                break
        if not link or not link.get("href"):
            continue
        href = link["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        title = clean(link.get_text(" ", strip=True))
        if not title or len(title) < 10:
            # Event cards wrap an image link with no text; recover the title from a
            # nearby heading or the URL slug.
            anc = link
            for _ in range(4):
                anc = anc.parent
                if anc is None:
                    break
                h = anc.select_one("h2, h3, h4")
                if h and len(h.get_text(strip=True)) >= 10:
                    title = clean(h.get_text(" ", strip=True))
                    break
            if not title or len(title) < 10:
                title = href.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
        seen.add(url)
        out.append((url, title, _iso_dt(tm.get("datetime"))))
    return out


def _scrape(item_type: str, pages, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing, substr in pages:
        r = http_get(listing)
        if r is None:
            continue
        for url, title, doc_dt in _parse(r.text, substr):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="etf", item_type=item_type, title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_etf_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)


def ingest_etf_events(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("event", EVENT_PAGES, fetch_bodies=fetch_bodies)


def ingest_etf_topics(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        if h1 and len(h1.get_text(strip=True)) > 3:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = path.rsplit("/", 1)[-1].replace("-", " ").title()
        if not title:
            continue
        items.append(Item(body_code="etf", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items
