"""European Institute for Gender Equality — news, events, publications.
Backs /api/v2/eige/{news,events,publications}.

EIGE's newsroom and publications library are server-rendered Drupal listings
(teaser-item cards), paginated with ?page=N (0-indexed). One row per item:
title, date and the page URL. Row IS the content.
"""
from __future__ import annotations

import html as _html
import re
import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = "https://eige.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
# teaser-title links, in document order; the publication date sits in the markup
# shortly after each title, so we read it from the window up to the next title.
_TITLE = re.compile(r'teaser-title[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DATE = re.compile(r'(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})')


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip())


def _date(seg: str) -> datetime | None:
    m = _DATE.search(_txt(seg))
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _walk(path: str, item_type: str, max_pages: int = 120) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for page in range(max_pages):
        try:
            r = s.get(f"{_BASE}{path}", params={"page": page}, timeout=40)
        except requests.RequestException:
            break
        if r.status_code != 200:
            break
        new = 0
        matches = list(_TITLE.finditer(r.text))
        for i, tm in enumerate(matches):
            href, raw = tm.group(1), tm.group(2)
            title = _txt(raw)
            url = href if href.startswith("http") else _BASE + href
            # only items under the listing's own path (skip sidebar/related links)
            if not title or path not in url or url in out:
                continue
            window = r.text[tm.end(): matches[i + 1].start() if i + 1 < len(matches) else tm.end() + 600]
            dt = _date(window)
            lines = [title, f"Date: {dt.date()}" if dt else ""]
            lines = [l for l in lines if l]
            out[url] = Item(
                body_code="eige", item_type=item_type, title=clean(title)[:120], public_url=url,
                summary=clean(title)[:200],
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=dt, creation_date=now, source_kind="eige_drupal", guid=url)
            new += 1
        if new == 0:
            break
        time.sleep(0.2)
    return list(out.values())


def ingest_eige_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _walk("/newsroom/news", "news")


def ingest_eige_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _walk("/newsroom/events", "event")


def ingest_eige_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _walk("/publications-resources/publications", "publication")
