"""
EBA — European Banking Authority ingestion (/api/v2/eu-financial-institutions/eba).

Verified source map (URL-verification pass, api_econ.md L282-367):
  EBA's /rss.xml is only a 10-item e-mail-alert digest (not per-content), but the
  listing pages are SERVER-RENDERED Drupal "teaser-columns" views (paginated,
  ?page=N). So we scrape the listing pages directly — no Playwright needed.

  - news         : press-releases + speeches + interviews
  - publications : the publications listing
  - events       : the events listing
  (The doc gives EBA no dedicated legal-acts section; its rulebook content lives
   under publications, so EBA exposes news/publications/events only.)

Row shape: <article class="teaser-columns"> with the date in .link-icon--calendar,
the title+link in h3.teaser-columns__title a, and a teaser in .teaser-columns__text.
Detail pages are server-rendered. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date,
)

_BASE = "https://www.eba.europa.eu"

EBA_LISTINGS = {
    "news": [
        f"{_BASE}/publications-and-media/press-releases",
        f"{_BASE}/publications-and-media/speeches",
        f"{_BASE}/publications-and-media/interviews",
    ],
    "publication": [
        f"{_BASE}/publications-and-media/publications",
    ],
    "event": [
        f"{_BASE}/publications-and-media/events",
    ],
}


def _parse_teaser_page(html: str) -> list[tuple[str, str, datetime | None, str | None]]:
    """Handle EBA's three Drupal teaser variants: teaser-columns (news),
    teaser (publications, links to a file), teaser-event-calendar (events)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, datetime | None, str | None]] = []
    for art in soup.select("article.teaser-columns, article.teaser, article.teaser-event-calendar"):
        a = art.select_one('[class*="__title"] a[href]') or art.find("a", href=True)
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title = clean(a.get_text(" ", strip=True).replace("​", "").strip())
        if not title:
            continue
        # Date: news/publications carry .link-icon--calendar ("8 June 2026");
        # events split day/month/year across spans.
        doc_dt = None
        cal = art.select_one(".link-icon--calendar")
        if cal:
            doc_dt = parse_listing_date(cal.get_text(" ", strip=True))
        else:
            day = art.select_one(".teaser-event-calendar__calendar-day")
            mon = art.select_one(".teaser-event-calendar__calendar-month")
            yr = art.select_one(".teaser-event-calendar__calendar-year")
            if day and mon and yr:
                doc_dt = parse_listing_date(
                    f"{day.get_text(strip=True)} {mon.get_text(strip=True)} {yr.get_text(strip=True)}")
        summ_el = art.select_one(".teaser-columns__text, .teaser__text")
        summary = clean(summ_el.get_text(" ", strip=True)[:1000]) if summ_el else None
        rows.append((url, title, doc_dt, summary))
    return rows


def scrape_listings(body_code: str, item_type: str, listing_urls, *,
                    fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    """Page through server-rendered teaser-columns listings and build Items."""
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for base_url in listing_urls:
        for page in range(max_pages):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 0 else f"{base_url}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = _parse_teaser_page(r.text)
            if not rows:
                break  # past the last page
            new = 0
            for item_url, title, doc_dt, summary in rows:
                if item_url in seen:
                    continue
                seen.add(item_url)
                new += 1
                items.append(Item(body_code=body_code, item_type=item_type, title=title,
                                  public_url=item_url, summary=summary, document_date=doc_dt,
                                  creation_date=now, source_kind="html", guid=item_url))
            if new == 0:
                break  # all-duplicate page -> stop
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eba_news(**kw) -> list[Item]:
    return scrape_listings("eba", "news", EBA_LISTINGS["news"], **kw)


def ingest_eba_publications(**kw) -> list[Item]:
    return scrape_listings("eba", "publication", EBA_LISTINGS["publication"], **kw)


def ingest_eba_events(**kw) -> list[Item]:
    return scrape_listings("eba", "event", EBA_LISTINGS["event"], **kw)
