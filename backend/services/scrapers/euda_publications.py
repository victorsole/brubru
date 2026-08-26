"""European Union Drugs Agency database — EUDA publications.
Backs /api/v2/euda/publications.

The EUDA (formerly EMCDDA) publishes the EU's reference analyses on drugs — the
European Drug Report, EU Drug Markets analyses, drug-profile and health-response
guides, country and technical reports. The publications-library listing WAFs its
query-string pagination, so the complete set of publication URLs is taken from
the site's XML sitemap (served cleanly to crawlers) and the title of each is read
from its page's og:title. One row per publication: title and the publication page.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import html as _html

import requests

from services.scrapers.economy_common import Item, clean

_SITEMAP = "https://www.euda.europa.eu/sitemap.xml?page={page}"
# The EUDA sitemap index has 35 sub-sitemap pages; scan them all (news/events/
# publications URLs are spread across them). The old cap of 7 missed most.
_SITEMAP_PAGES = 35
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
_OG = re.compile(r'<meta property="og:title" content="([^"]+)"')
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_LOC = re.compile(r"<loc>([^<]+)</loc>")


def sitemap_urls(session: requests.Session, substr: str) -> list[str]:
    """Every ..._en URL containing `substr` from the EUDA XML sitemap."""
    urls: dict[str, None] = {}
    for page in range(1, _SITEMAP_PAGES + 1):
        try:
            r = session.get(_SITEMAP.format(page=page), timeout=40)
        except Exception:  # requests OR curl_cffi errors
            continue
        if r.status_code != 200:
            continue
        for loc in _LOC.findall(r.text):
            if substr in loc and loc.endswith("_en"):
                urls[loc] = None
    return list(urls)


def sitemap_publication_urls(session: requests.Session) -> list[str]:
    """Every /publications/..._en URL from the EUDA XML sitemap."""
    return sitemap_urls(session, "/publications/")


def _clean_title(raw: str) -> str:
    # og:title is "<title> | The European Union Drugs Agency (EUDA)"; some titles
    # arrive double-escaped (e.g. &amp;#039;), so unescape twice.
    return clean(_html.unescape(_html.unescape(raw)).split(" | ")[0]) or ""


def fetch_title(session: requests.Session, url: str) -> str | None:
    for attempt in range(2):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                m = _OG.search(r.text) or _TITLE.search(r.text)
                if m:
                    return _clean_title(m.group(1))
                return None
        except requests.RequestException:
            time.sleep(1.0)
    return None


def _slug_title(url: str) -> str:
    slug = url.split("/publications/", 1)[1].rsplit("_en", 1)[0]
    slug = slug.replace("/html", "").strip("/").replace("-", " ").replace("/", " - ")
    return clean(slug.title()) or url


def _item(url: str, title: str, now: datetime) -> Item:
    title = title or _slug_title(url)
    return Item(
        body_code="euda", item_type="publication",
        title=clean(title)[:120], public_url=url,
        summary=clean(title)[:200],
        body_txt=clean(f"Publication: {title}\nEUDA publication page: {url}"),
        body_html=clean(f"<ul><li>Publication: {title}</li><li>{url}</li></ul>"),
        document_date=None, creation_date=now, source_kind="euda_sitemap", guid=url)


def ingest_euda_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for url in sitemap_publication_urls(s):
        items.append(_item(url, fetch_title(s, url) if fetch_bodies else "", now))
        time.sleep(0.15)
    return items
