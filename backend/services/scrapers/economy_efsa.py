"""
EFSA — European Food Safety Authority (api_health.md). /api/v2/efsa.

EFSA runs a Drupal site (efsa.europa.eu). Source map (verified):
  - news         : /en/press/rss — the press RSS feed (clean, dated) -> detail HTML.
                   (The /en/news page mixes in multimedia and paginates via JS.)
  - publications : /en/publications — article cards with a heading link and a
                   <time datetime>. Many entries are EFSA Journal outputs hosted on
                   Wiley (external DOI); the 5 datapoints + title + date are always
                   present, body_txt only when the target is fetchable.

EFSA has no separate events feed, so news + publications. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt,
)
from services.scrapers.economy_ecb import ingest_feeds

_BASE = "https://www.efsa.europa.eu"
EFSA_NEWS_FEEDS = [f"{_BASE}/en/press/rss"]


def ingest_efsa_news(**kw) -> list[Item]:
    return ingest_feeds("efsa", "news", EFSA_NEWS_FEEDS, **kw)


def _parse_pubs(html: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for a_art in main.select("article"):
        a = a_art.select_one("h2 a[href], h3 a[href]") or a_art.find("a", href=True)
        t = a_art.select_one("time[datetime]")
        if not a or not a.get("href") or not t:
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        out.append((url, title, _iso_dt(t.get("datetime"))))
    return out


def ingest_efsa_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    listing = f"{_BASE}/en/publications"
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = listing if page == 0 else f"{listing}?page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = _parse_pubs(r.text)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="efsa", item_type="publication", title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=u))
        if new == 0:
            break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items
