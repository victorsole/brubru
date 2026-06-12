"""Generic listing scraper for the server-rendered EU agency sites
(api_socjust.md: Cedefop, ERA, Eurofound, EUAA, ...).

These are mostly Drupal/EU-theme sites whose news / events / publications
listings are server-rendered and paginated with ?page=N (0-indexed). The card
markup differs per agency, but every item is an <a> whose href sits under a known
path prefix, with the title as the anchor text and the date in a nearby <time>
tag or a "DD Mon YYYY" string. This walker extracts items by that contract, so a
new agency is one thin wrapper: walk(base, path, body_code, item_type, link_substr).
"""
from __future__ import annotations

import html as _html
import re
import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
_ISO = re.compile(r'datetime="(\d{4}-\d{2}-\d{2})')
_DMY = re.compile(r'(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})')


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip())


def _date(window: str) -> datetime | None:
    m = _ISO.search(window)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    m = _DMY.search(_txt(window))
    if m:
        try:
            return datetime.strptime(m.group(1), "%d %b %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def walk(base: str, path: str, body_code: str, item_type: str, link_substr: str,
         source_kind: str, *, min_title: int = 12, max_pages: int = 200,
         page_param: str = "page", page_start: int = 0) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    anchor = re.compile(
        r'<a\s+[^>]*href="(' + re.escape(link_substr) + r'[^"#?]*)"[^>]*>(.*?)</a>', re.S)
    for page in range(page_start, page_start + max_pages):
        try:
            r = s.get(f"{base}{path}", params={page_param: page}, timeout=40)
        except requests.RequestException:
            break
        if r.status_code != 200:
            break
        text = r.text
        matches = list(anchor.finditer(text))
        new = 0
        for i, m in enumerate(matches):
            href, raw = m.group(1), m.group(2)
            title = _txt(raw)
            if len(title) < min_title:
                continue
            url = href if href.startswith("http") else base + href
            if url in out:
                continue
            window = text[max(0, m.start() - 500): m.end() + 120]
            dt = _date(window)
            lines = [title, f"Date: {dt.date()}" if dt else ""]
            lines = [l for l in lines if l]
            out[url] = Item(
                body_code=body_code, item_type=item_type, title=clean(title)[:120],
                public_url=url, summary=clean(title)[:200],
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=dt, creation_date=now, source_kind=source_kind, guid=url)
            new += 1
        if new == 0:
            break
        time.sleep(0.2)
    return list(out.values())
