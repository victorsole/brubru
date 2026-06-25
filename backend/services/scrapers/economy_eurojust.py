"""
Eurojust — EU Agency for Criminal Justice Cooperation (api_socjust.md).
/api/v2/eurojust.

Eurojust runs a Drupal site (eurojust.europa.eu) using Views: each news item is a
.views-row whose title sits in .field--name-node-title h3 a and whose date is a
"DD Month YYYY" string. Plain requests work (no WAF). News + topics only:
Eurojust's casework page is an aggregate-statistics dashboard, not a scrapeable
list of cases (individual cases are confidential), and the events listing is
JS-rendered without a stable item structure. The substantive casework content is
the crime-types and judicial-cooperation instrument pages, captured as topics.

Source map (verified 25 Jun 2026):
  - news  : /media-and-events/press-releases-and-news
  - topic : crime-types + judicial-cooperation instrument pages

Reads from economy_items (body row already seeded); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, http_get, fetch_detail, extract_html

_BASE = "https://www.eurojust.europa.eu"

NEWS_PAGES = [f"{_BASE}/media-and-events/press-releases-and-news"]

_TOPIC_PATHS = [
    "/crime-types-and-cases/crime-types/terrorism",
    "/crime-types-and-cases/crime-types/cybercrime",
    "/crime-types-and-cases/crime-types/drug-trafficking",
    "/crime-types-and-cases/crime-types/economic-crimes",
    "/crime-types-and-cases/crime-types/migrant-smuggling",
    "/crime-types-and-cases/crime-types/trafficking-human-beings",
    "/crime-types-and-cases/crime-types/core-international-crimes",
    "/crime-types-and-cases/crime-types/crimes-against-children",
    "/crime-types-and-cases/crime-types/pif-crimes",
    "/crime-types-and-cases/crime-types/cbrn-e",
    "/judicial-cooperation/instruments/european-arrest-warrant",
    "/judicial-cooperation/instruments/european-investigation-order",
    "/judicial-cooperation/instruments/joint-investigation-teams",
    "/judicial-cooperation/instruments/asset-recovery",
    "/judicial-cooperation/instruments/extradition",
    "/judicial-cooperation/instruments/electronic-evidence",
]

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_DMY = re.compile(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")


def _text_date(s: str) -> datetime | None:
    m = _DMY.search(s)
    if not m:
        return None
    d = int(m.group(1)); mo = _MONTHS.get(m.group(2).lower()); y = int(m.group(3))
    if not mo:
        return None
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for row in soup.select("div.views-row, .views-row"):
        link = row.select_one(".field--name-node-title a[href], h3 a[href], h2 a[href]")
        if not link:
            for a in row.select("a[href]"):
                if len(a.get_text(strip=True)) >= 12:
                    link = a
                    break
        if not link or not link.get("href"):
            continue
        href = link["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        title = clean(link.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        seen.add(url)
        out.append((url, title, _text_date(row.get_text(" ", strip=True))))
    return out


def ingest_eurojust_news(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in NEWS_PAGES:
        r = http_get(listing)
        if r is None:
            continue
        for url, title, doc_dt in _parse(r.text):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="eurojust", item_type="news", title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eurojust_topics(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        soup = BeautifulSoup(r.text, "html.parser")
        # The page h1 is the generic site name; the real title is in <title>.
        if soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = path.rsplit("/", 1)[-1].replace("-", " ").title()
        if not title or title.lower() == "eurojust":
            title = path.rsplit("/", 1)[-1].replace("-", " ").title()
        items.append(Item(body_code="eurojust", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items
