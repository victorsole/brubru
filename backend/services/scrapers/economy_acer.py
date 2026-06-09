"""
ACER — Agency for the Cooperation of Energy Regulators (api_market.md).
/api/v2/acer.

ACER runs a custom Drupal site (acer.europa.eu). Source map (verified):
  - news         : /news-and-events/news + /news-and-events/press-releases —
                   .views-row > .related-news-wrapper with .related-new-date
                   ("2nd June 2026"), a .title-wrapper link and an .intro-wrapper
                   summary; ?page=N paginated. Detail = HTML.
  - publications : /documents/publications — .views-row > .document with a .date
                   ("29.05.2026"), a category and a PDF link; ?page=N paginated.
                   Bodies extracted from the PDFs.

ACER's public-events listing is JS-rendered from an extranet and exposes no
server-side data, so only news + publications are surfaced. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date,
)

_BASE = "https://www.acer.europa.eu"

NEWS_PAGES = [f"{_BASE}/news-and-events/news", f"{_BASE}/news-and-events/press-releases"]
PUB_PAGES = [f"{_BASE}/documents/publications"]


def _parse_news(html: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for row in main.select(".views-row"):
        w = row.select_one(".related-news-wrapper") or row
        a = w.select_one(".title-wrapper a") or w.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        de = w.select_one(".related-new-date")
        doc_dt = parse_listing_date(de.get_text(" ", strip=True)) if de else None
        intro = w.select_one(".intro-wrapper")
        summary = clean(intro.get_text(" ", strip=True)[:1000]) if intro else None
        out.append((url, title, doc_dt, summary))
    return out


def _parse_pub(html: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for row in main.select(".views-row"):
        doc = row.select_one(".document") or row
        a = None
        for cand in doc.find_all("a", href=True):
            if ".pdf" in cand["href"].lower():
                a = cand
                break
        a = a or doc.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        # title: the document title link text, else the filename stem
        title_el = doc.select_one(".title-wrapper a, .title a, .document-title")
        title = clean(title_el.get_text(" ", strip=True)) if title_el else None
        if not title:
            stem = a["href"].rstrip("/").split("/")[-1].rsplit(".", 1)[0]
            title = clean(stem.replace("-", " ").replace("_", " ")) or url
        de = doc.select_one(".date")
        doc_dt = parse_listing_date(de.get_text(" ", strip=True)) if de else None
        out.append((url, title, doc_dt, None))
    return out


def _scrape(item_type: str, listing_urls, parser, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        for page in range(max_pages):
            sep = "&" if "?" in listing else "?"
            url = listing if page == 0 else f"{listing}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = parser(r.text)
            new = 0
            for u, title, doc_dt, summary in rows:
                if u in seen:
                    continue
                seen.add(u)
                new += 1
                items.append(Item(body_code="acer", item_type=item_type, title=title,
                                  public_url=u, summary=summary, document_date=doc_dt,
                                  creation_date=now, source_kind="html", guid=u))
            if new == 0:
                break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_acer_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("news", NEWS_PAGES, _parse_news, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_acer_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("publication", PUB_PAGES, _parse_pub, fetch_bodies=fetch_bodies, max_pages=max_pages)
