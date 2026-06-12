"""European Environment Agency — news and events (Plone REST API).
Backs /api/v2/eea/{news,events}.

The EEA newsroom exposes its news items and events through the Plone REST API
(`++api++ @search`). One row per item: title, summary, date and the page URL.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = "https://www.eea.europa.eu/++api++"
_NEWS = _BASE + "/en/newsroom/news/@search"
_EVENTS = _BASE + "/en/@search"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}


def _date(v) -> datetime | None:
    if not v or str(v).startswith("1969") or str(v).startswith("0"):
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _walk(session: requests.Session, url: str, extra: dict, item_type: str,
          date_field: str) -> list[Item]:
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    b_start = 0
    while True:
        params = {"b_size": 100, "b_start": b_start,
                  "metadata_fields": ["Description", date_field, "effective"], **extra}
        j = session.get(url, params=params, timeout=40).json()
        rows = j.get("items") or []
        if not rows:
            break
        for r in rows:
            u = clean(r.get("@id") or "")
            title = clean(r.get("title") or "")
            if not u or not title or u in out:
                continue
            desc = clean(r.get("Description") or r.get("description") or "")
            dt = _date(r.get(date_field)) or _date(r.get("effective"))
            lines = [f"{title}", f"Date: {dt.date()}" if dt else "", desc or ""]
            lines = [l for l in lines if l]
            out[u] = Item(
                body_code="eea", item_type=item_type, title=title[:120], public_url=u,
                summary=clean(desc[:280]) if desc else title[:120],
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=dt, creation_date=now, source_kind="eea_plone", guid=u)
        b_start += len(rows)
        if b_start >= int(j.get("items_total") or 0):
            break
    return list(out.values())


def ingest_eea_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return _walk(s, _NEWS, {}, "news", "effective")


def ingest_eea_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return _walk(s, _EVENTS, {"portal_type": "Event"}, "event", "start")
