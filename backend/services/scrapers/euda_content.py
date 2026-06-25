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

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html
from services.scrapers.euda_publications import sitemap_urls, fetch_title, _HEADERS

_SITE = "https://www.euda.europa.eu"

# Curated about + epidemiological-data landing pages (EUDA serves these to a
# browser UA with an _en suffix). The /data/stats2026/* set is the key-indicator
# Statistical Bulletin (drug-related deaths, drug use prevalence, treatment demand,
# problem drug use, drug law offences, health and social responses, seizures,
# price and purity).
_TOPIC_PATHS = [
    "/about/mission_en", "/about/history_en", "/about/organisation_en",
    "/about/mb_en", "/about/executive-director_en", "/about/manifesto_en",
    "/about/partners_en",
    "/data/data-catalogue_en",
    "/data/stats2026/drd_en", "/data/stats2026/dup_en", "/data/stats2026/tdi_en",
    "/data/stats2026/pdu_en", "/data/stats2026/dlo_en", "/data/stats2026/hsr_en",
    "/data/stats2026/szr_en", "/data/stats2026/ppp_en",
]


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


def ingest_euda_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for path in _TOPIC_PATHS:
        url = _SITE + path
        r = None
        for attempt in range(3):
            try:
                resp = s.get(url, timeout=30)
                if resp.status_code == 200:
                    r = resp
                    break
            except requests.RequestException:
                pass
            time.sleep(1.2 * (attempt + 1))
        time.sleep(0.25)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        if h1 and len(h1.get_text(strip=True)) > 2:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = clean(path.rsplit("/", 1)[-1].replace("_en", "").replace("-", " ").title())
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        items.append(Item(body_code="euda", item_type="topic", title=(title or url)[:300],
                          public_url=norm_url(url), creation_date=now, source_kind="html",
                          guid=norm_url(url), body_txt=body_txt, body_html=body_html))
    return items
