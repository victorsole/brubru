"""
CPVO — Community Plant Variety Office (api_market.md). /api/v2/cpvo.

CPVO runs a Drupal site (cpvo.europa.eu). Source map (verified):
  - news         : /en/news-and-events/news — .views-row with a heading link and
                   a <time datetime>; ?page=N paginated. Detail = HTML.
  - events       : /en/news-and-events/conferences-and-events — same shape.
  - publications : /en/about-us/what-we-do/reports — .views-row report rows with
                   the title in .views-field-title_field and a PDF download link;
                   date taken from the /YYYY-MM/ segment of the PDF path. Bodies
                   extracted from the PDFs.

No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt,
)

_BASE = "https://cpvo.europa.eu"
_PATH_DATE = re.compile(r"/(\d{4})-(\d{2})/")


def _parse_listing(html: str):
    """news / events: heading link + time[datetime]."""
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for row in main.select(".views-row"):
        a = row.select_one("h2 a[href], h3 a[href]") or next(
            (x for x in row.find_all("a", href=True) if x.get_text(strip=True)), None)
        t = row.select_one("time[datetime]")
        if not a or not a.get("href") or not t:
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        out.append((url, title, _iso_dt(t.get("datetime"))))
    return out


def _parse_reports(html: str):
    """reports: title in .views-field-title_field, PDF download link, date from path."""
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for row in main.select(".views-row"):
        title_el = row.select_one(".views-field-title_field")
        pdf = next((x["href"] for x in row.find_all("a", href=True) if ".pdf" in x["href"].lower()), None)
        if not title_el or not pdf:
            continue
        title = clean(title_el.get_text(" ", strip=True))
        if not title:
            continue
        url = norm_url(pdf if pdf.startswith("http") else _BASE + pdf)
        m = _PATH_DATE.search(url)
        doc_dt = None
        if m:
            try:
                doc_dt = datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
            except ValueError:
                doc_dt = None
        out.append((url, title, doc_dt))
    return out


def _scrape(item_type: str, listing, parser, *, fetch_bodies: bool, max_pages: int,
            default_kind: str) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        sep = "&" if "?" in listing else "?"
        url = listing if page == 0 else f"{listing}{sep}page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = parser(r.text)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="cpvo", item_type=item_type, title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind=default_kind, guid=u))
        if new == 0:
            break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            it.source_kind = kind if kind in ("pdf", "html") else it.source_kind
    return items


def ingest_cpvo_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("news", f"{_BASE}/en/news-and-events/news", _parse_listing,
                   fetch_bodies=fetch_bodies, max_pages=max_pages, default_kind="html")


def ingest_cpvo_events(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("event", f"{_BASE}/en/news-and-events/conferences-and-events", _parse_listing,
                   fetch_bodies=fetch_bodies, max_pages=max_pages, default_kind="html")


def ingest_cpvo_publications(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("publication", f"{_BASE}/en/about-us/what-we-do/reports", _parse_reports,
                   fetch_bodies=fetch_bodies, max_pages=max_pages, default_kind="pdf")
