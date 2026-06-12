"""European Union Drugs Agency — news and events.
Backs /api/v2/euda/{news,events}.

The complete set of EUDA news and event URLs comes from the site's XML sitemap
(the listing pages WAF their query-string pagination); each title is read from
the page's og:title. One row per item.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean
from services.scrapers.euda_publications import sitemap_urls, fetch_title, _HEADERS


def _item(url: str, title: str, item_type: str, now: datetime) -> Item:
    title = title or clean(url.rsplit("/", 1)[-1].replace("_en", "").replace("-", " ").title())
    noun = "News" if item_type == "news" else "Event"
    return Item(
        body_code="euda", item_type=item_type, title=clean(title)[:120], public_url=url,
        summary=clean(title)[:200],
        body_txt=clean(f"{noun}: {title}\nEUDA page: {url}"),
        body_html=clean(f"<ul><li>{noun}: {title}</li><li>{url}</li></ul>"),
        document_date=None, creation_date=now, source_kind="euda_sitemap", guid=url)


def _ingest(substr: str, item_type: str, fetch_bodies: bool) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for url in sitemap_urls(s, substr):
        items.append(_item(url, fetch_title(s, url) if fetch_bodies else "", item_type, now))
        time.sleep(0.15)
    return items


def ingest_euda_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _ingest("/news/", "news", fetch_bodies)


def ingest_euda_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _ingest("/events/", "event", fetch_bodies)
