"""
ESMA — European Securities and Markets Authority (/api/v2/eu-financial-institutions/esma).

Verified source map (URL-verification pass, api_econ.md L368-414). ESMA's site is a
Drupal 10 mid-migration: /rss.xml carries no dates, there is no sitemap or JSON:API,
and the library search + key-dates pages are JS-rendered. But two streams ARE
server-rendered and paginated:

  - news         : /press-news/esma-news -> article.node--type-news cards with
                   .search-title + .search-date (DD/MM/YYYY) + a bookmark link.
  - publications : /press-news/consultations -> article.node--type-library-document
                   cards (PDF file links; title from the file name, date from the
                   /YYYY-MM/ path segment).

  events         : DEFERRED — ESMA's "key dates" agenda is JS-rendered with no clean
                   server-rendered feed; revisit with deeper Playwright interaction.

Detail pages (news) are server-rendered. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date,
)

_BASE = "https://www.esma.europa.eu"

ESMA_NEWS_PAGES = [f"{_BASE}/press-news/esma-news"]
ESMA_PUB_PAGES = [f"{_BASE}/press-news/consultations"]

_PATH_DATE_RE = re.compile(r"/(\d{4})-(\d{2})/")
_ESMA_REF_RE = re.compile(r"^ESMA[0-9A-Za-z-]+_")


def _date_from_path(url: str) -> datetime | None:
    m = _PATH_DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
    except ValueError:
        return None


def _title_from_filename(name: str) -> str:
    name = name.rsplit(".", 1)[0]          # drop extension
    name = _ESMA_REF_RE.sub("", name)      # drop the ESMA reference prefix
    return clean(name.replace("_", " ").strip()) or name


def _parse_news_page(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for art in soup.select("article.node--type-news"):
        a = art.select_one('a[href*="/press-news/esma-news/"]') or art.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title_el = art.select_one(".search-title .field--name-title") or art.select_one(".search-title")
        title = clean(title_el.get_text(" ", strip=True)) if title_el else clean(a.get_text(" ", strip=True))
        if not title:
            continue
        date_el = art.select_one(".search-date")
        doc_dt = parse_listing_date(date_el.get_text(" ", strip=True)) if date_el else None
        intro = art.select_one('.field--name-field-news-introduction')
        summary = clean(intro.get_text(" ", strip=True)[:1000]) if intro else None
        out.append(Item(body_code="esma", item_type="news", title=title, public_url=url,
                        summary=summary, document_date=doc_dt, creation_date=now,
                        source_kind="html", guid=url))
    return out


def _parse_pub_page(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for art in soup.select("article.node--type-library-document"):
        a = art.select_one('a[href*="/sites/default/files"]') or art.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        fname = a.get_text(strip=True) or url.rsplit("/", 1)[-1]
        title = _title_from_filename(fname)
        if not title:
            continue
        out.append(Item(body_code="esma", item_type="publication", title=title, public_url=url,
                        document_date=_date_from_path(url), creation_date=now,
                        source_kind="html", guid=url))
    return out


def _scrape_paged(pages, parser, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    for base_url in pages:
        for page in range(max_pages):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 0 else f"{base_url}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = parser(r.text)
            if not rows:
                break
            new = 0
            for it in rows:
                if it.public_url in seen:
                    continue
                seen.add(it.public_url)
                new += 1
                items.append(it)
            if new == 0:
                break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_esma_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape_paged(ESMA_NEWS_PAGES, _parse_news_page, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_esma_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape_paged(ESMA_PUB_PAGES, _parse_pub_page, fetch_bodies=fetch_bodies, max_pages=max_pages)
