"""
EUIPO — European Union Intellectual Property Office (api_market.md).
/api/v2/euipo.

EUIPO runs an anti-bot Material-UI SPA (euipo.europa.eu): no RSS, no server-side
content, headless renders are blocked. The SPA's listings are powered by a
public Algolia search index, which we call directly (the search-only key is the
one the site ships to browsers). Each hit already carries the full body, so no
detail fetch is needed. Source map (verified):
  - news   : Algolia index ews-en-news   (title, summary, body, fullSlug, date ms).
  - events : Algolia index ews-en-events  (title, summary, body, fullSlug, startDate ms).

EUIPO Observatory publications are served from a separate CMS with no public
search index, so only news + events are surfaced. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, _BODY_CAP

_APP = "ZYN8P9OCP2"
_KEY = "428a6eab6ad825546f741c199084e245"  # public search-only key shipped by the EUIPO site
_SITE = "https://www.euipo.europa.eu/"
_INDEXES = {"news": ("ews-en-news", "date"), "event": ("ews-en-events", "startDate")}


def _epoch_dt(ms) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _algolia(index: str, page: int, hits: int = 100) -> dict:
    url = (f"https://{_APP.lower()}-dsn.algolia.net/1/indexes/{index}/query"
           f"?x-algolia-api-key={_KEY}&x-algolia-application-id={_APP}")
    try:
        r = requests.post(url, json={"query": "", "page": page, "hitsPerPage": hits},
                          timeout=30)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        return {}
    return {}


def _scrape(item_type: str, *, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    index, date_field = _INDEXES[item_type]
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        data = _algolia(index, page)
        rows = data.get("hits") or []
        if not rows:
            break
        for h in rows:
            slug = (h.get("fullSlug") or "").lstrip("/")
            link = h.get("link") or (norm_url(_SITE + slug) if slug else None)
            if not link or link in seen:
                continue
            seen.add(link)
            title = clean(h.get("title"))
            if not title:
                continue
            raw = h.get("body") or ""
            if isinstance(raw, list):
                raw = " ".join(str(x) for x in raw)
            elif not isinstance(raw, str):
                raw = str(raw)
            body_txt = clean(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)[:_BODY_CAP]) or None
            body_html = clean(raw[:_BODY_CAP]) or None
            items.append(Item(
                body_code="euipo", item_type=item_type, title=title,
                public_url=link, summary=clean(h.get("summary")),
                body_txt=body_txt, body_html=body_html,
                document_date=_epoch_dt(h.get(date_field)),
                creation_date=now, source_kind="algolia", guid=link,
            ))
        if page + 1 >= int(data.get("nbPages", 0)):
            break
    return items


def ingest_euipo_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("news", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_euipo_events(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("event", fetch_bodies=fetch_bodies, max_pages=max_pages)
