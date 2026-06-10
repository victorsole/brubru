"""
ESM — European Stability Mechanism (api_econ.md L718-779).
/api/v2/esm — ESM is intergovernmental (NOT an EU institution), so it lives in
its own folder rather than eu-financial-institutions.

ESM runs a Drupal site (esm.europa.eu). Source map (verified):
  - news         : /newsroom — .views-row (node--type-news) with a title link and
                   a <time datetime>; ?page=N paginated. Detail = HTML.
  - publications : /publications — .views-row (node--type-publications /
                   annual-report) with a title link and a <time datetime>;
                   ?page=N paginated. Detail = HTML (links to the PDF).
  - events       : /events — .views-row with an .event-title link and an
                   .event-date-wrapper (day + month, NO year). The listing is
                   upcoming events only, so the year is resolved to the next
                   occurrence from today. Detail = HTML.

No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail,
)

_BASE = "https://www.esm.europa.eu"
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _iso(dt_attr: str | None) -> datetime | None:
    if not dt_attr:
        return None
    try:
        return datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
    except ValueError:
        return None


def _title(row) -> str | None:
    el = (row.select_one(".event-title a") or row.select_one("h2 a, h3 a")
          or row.select_one(".field--name-title") or row.select_one("h2, h3"))
    if el:
        return clean(el.get_text(" ", strip=True))
    a = row.find("a", href=True)
    return clean(a.get_text(" ", strip=True)) if a else None


def _event_date(row) -> datetime | None:
    """ESM event listings give day + month but no year; resolve to the next
    occurrence from today (the listing is upcoming events only)."""
    w = row.select_one(".event-date-wrapper")
    if not w:
        return None
    day_el = w.select_one(".event-date")
    mon_el = w.select_one(".event-month")
    if not (day_el and mon_el):
        return None
    try:
        day = int(day_el.get_text(strip=True))
    except ValueError:
        return None
    month = _MONTHS.get(mon_el.get_text(strip=True).lower()[:3])
    if not month:
        return None
    now = datetime.now(timezone.utc)
    for year in (now.year, now.year + 1):
        try:
            cand = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
        if cand.date() >= now.date():
            return cand
    return cand


def _scrape(item_type: str, path: str, *, date_mode: str,
            fetch_bodies: bool, max_pages: int) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = f"{_BASE}{path}" if page == 0 else f"{_BASE}{path}?page={page}"
        r = http_get(url)
        if r is None:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select(".views-row")
        if not rows:
            break
        new = 0
        for row in rows:
            a = row.select_one(".event-title a") or row.select_one("h2 a, h3 a") or row.find("a", href=True)
            if not a or not a.get("href"):
                continue
            href = a["href"]
            link = norm_url(href if href.startswith("http") else _BASE + href)
            if link in seen:
                continue
            title = _title(row)
            if not title:
                continue
            seen.add(link)
            new += 1
            if date_mode == "event":
                doc_dt = _event_date(row)
            else:
                t = row.select_one("time[datetime]")
                doc_dt = _iso(t.get("datetime")) if t else None
            items.append(Item(body_code="esm", item_type=item_type, title=title,
                              public_url=link, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=link))
        if new == 0:
            break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_esm_news(*, fetch_bodies: bool = True, max_pages: int = 8) -> list[Item]:
    return _scrape("news", "/newsroom", date_mode="time", fetch_bodies=fetch_bodies, max_pages=max_pages)


# ESM splits its written output across several Drupal listings, all sharing the
# .views-row + <time datetime> pattern: the main publications list, ESM briefs
# and economics research & analysis.
_PUB_PATHS = ["/publications", "/ESM-briefs", "/our-work/research-and-analysis"]


def ingest_esm_publications(*, fetch_bodies: bool = True, max_pages: int = 8) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    for path in _PUB_PATHS:
        for it in _scrape("publication", path, date_mode="time",
                          fetch_bodies=fetch_bodies, max_pages=max_pages):
            if it.public_url in seen:
                continue
            seen.add(it.public_url)
            items.append(it)
    return items


def ingest_esm_events(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("event", "/events", date_mode="event", fetch_bodies=fetch_bodies, max_pages=max_pages)


# --- ESM/EFSF financial-assistance programmes -------------------------------
# ESM's "programme database" overview/disbursements pages are a Power BI embedded
# report (analysis.windows.net) — its query protocol is disproportionately
# complex to mirror. But the programmes themselves are a small, fixed set with
# server-rendered country pages at /assistance/<country>; we catalogue those.
_ESM_PROGRAMMES = ["greece", "ireland", "portugal", "spain", "cyprus"]


def ingest_esm_programmes(*, fetch_bodies: bool = True, **_) -> list[Item]:
    from services.scrapers.economy_common import extract_html
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for country in _ESM_PROGRAMMES:
        url = f"{_BASE}/assistance/{country}"
        r = http_get(url)
        if r is None:
            continue
        body_txt, body_html = extract_html(r.text)
        title = f"{country.capitalize()} — ESM/EFSF financial-assistance programme"
        summary = clean((body_txt or "")[:300]) if body_txt else None
        items.append(Item(
            body_code="esm", item_type="programme", title=title, public_url=norm_url(url),
            summary=summary, body_txt=body_txt, body_html=body_html,
            document_date=None, creation_date=now, source_kind="html", guid=country))
    return items
