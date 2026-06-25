"""
EMSA — European Maritime Safety Agency (api_socjust.md). /api/v2/emsa.

EMSA runs a FlexiContent/Joomla site (emsa.europa.eu) with item URLs of the form
/newsroom/latest-news/item/<id>-<slug>.html. Each list card is an
li.fc_bloglist_item whose title link is span.fc_item_title a and whose date sits
in span.date_value as DD.MM.YYYY. Plain requests work (no WAF). Events are only
landing pages with no dated listing, so news + publications only.

Source map (verified 25 Jun 2026):
  - news        : /newsroom/latest-news.html
  - publication : /publications/reports.html

Reads from economy_items (body row in migration 150); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, http_get, fetch_detail, extract_html

_BASE = "https://www.emsa.europa.eu"

NEWS_PAGES = [f"{_BASE}/newsroom/latest-news.html"]
PUB_PAGES = [f"{_BASE}/publications/reports.html"]

# Curated thematic / reference pages (api_socjust.md): EMSA's "what we do" areas
# and its operational systems. Snapshotted as item_type='topic'.
_TOPIC_PATHS = [
    "/we-do.html",
    "/we-do/sustainability/environment.html",
    "/we-do/sustainability/pollution-response-services.html",
    "/we-do/safety/accident-investigation.html",
    "/we-do/safety/ship-safety-standards.html",
    "/we-do/safety/places-of-refuge.html",
    "/we-do/safety/marine-equipment.html",
    "/we-do/safety/maritime-security.html",
    "/we-do/safety/human-element.html",
    "/we-do/digitalisation/maritime-monitoring.html",
    "/we-do/digitalisation/ship-inspection-support.html",
    "/we-do/digitalisation/mss.html",
    "/we-do/surveillance/earthobservationservices.html",
    "/we-do/surveillance/rpas.html",
    "/we-do/assistance/training.html",
    "/we-do/assistance/enlargement.html",
    "/we-do/assistance/visits-and-inspections.html",
    "/we-do/assistance/coast-guard-function.html",
    "/ssn-main.html", "/lrit.html", "/emsw.html", "/copernicus.html", "/cise.html",
]

_DMY = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _parse_dmy(s: str | None) -> datetime | None:
    if not s:
        return None
    m = _DMY.search(s)
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    cards = soup.select("li.fc_bloglist_item, div.fc_bloglist_item")
    for li in cards:
        a = li.select_one("span.fc_item_title a[href], h2.contentheading a[href], a[href*='/item/']")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        seen.add(url)
        # The per-item created date is the single DD.MM.YYYY in the card (div
        # value.field_created). Regex the whole card text: the label div carries
        # no digits, so a class selector would mis-hit it.
        doc_dt = _parse_dmy(li.get_text(" ", strip=True))
        out.append((url, title, doc_dt))
    return out


def _scrape(item_type: str, listing_urls, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        r = http_get(listing)
        if r is None:
            continue
        for url, title, doc_dt in _parse(r.text):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="emsa", item_type=item_type, title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_emsa_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)


def ingest_emsa_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("publication", PUB_PAGES, fetch_bodies=fetch_bodies)


def ingest_emsa_topics(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1, .contentheading, .page-header")
        if h1 and len(h1.get_text(strip=True)) > 3:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" - ")[0].split(" | ")[0])
        else:
            title = path.rsplit("/", 1)[-1].replace(".html", "").replace("-", " ").title()
        if not title:
            continue
        items.append(Item(body_code="emsa", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items
