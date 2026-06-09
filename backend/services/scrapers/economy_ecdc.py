"""
ECDC — European Centre for Disease Prevention and Control (api_health.md).
/api/v2/ecdc.

ECDC runs a Drupal site (ecdc.europa.eu) whose listings are server-rendered by
its Search API view. The category-filtered search endpoint is the canonical
paginated feed. Source map (verified):
  - news         : /en/search?...&f[0]=categories:1307 — article.ct-news cards
                   (heading link + <time datetime>); ?page=N paginated. Detail = HTML.
  - publications : /en/search?...&f[0]=categories:1244 — article.ct-publication cards.

ECDC has no separate events feed (news + events share the news-events space), so
news + publications. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt,
)

_BASE = "https://www.ecdc.europa.eu"
_SEARCH = _BASE + "/en/search?s=&sort_bef_combine=date_DESC&f%5B0%5D=categories%3A"
_SOURCES = {
    "news": (f"{_SEARCH}1307", "article.ct-news"),
    "publication": (f"{_SEARCH}1244", "article.ct-publication"),
}


def _parse(html: str, node_sel: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for node in soup.select(node_sel):
        a = node.select_one("h2 a[href], h3 a[href]") or node.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        t = node.select_one("time[datetime]")
        out.append((url, title, _iso_dt(t.get("datetime")) if t else None))
    return out


def _scrape(item_type: str, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    listing, node_sel = _SOURCES[item_type]
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = listing if page == 0 else f"{listing}&page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = _parse(r.text, node_sel)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="ecdc", item_type=item_type, title=title,
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


def ingest_ecdc_news(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("news", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_ecdc_publications(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("publication", fetch_bodies=fetch_bodies, max_pages=max_pages)
