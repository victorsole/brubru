"""European Environment Agency — news, events and topics.
Backs /api/v2/eea/{news,events,topics}.

The EEA newsroom exposes its news items and events through the Plone REST API
(`++api++ @search`). One row per item: title, summary, date and the page URL.
The thematic "in-depth" topic pages are plain HTML, snapshotted via the shared
snapshot_topics helper.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean, snapshot_topics

_BASE = "https://www.eea.europa.eu/++api++"
_NEWS = _BASE + "/en/newsroom/news/@search"
_EVENTS = _BASE + "/en/@search"
_SITE = "https://www.eea.europa.eu"

# Curated about + thematic in-depth landing pages, snapshotted as topics.
_IN_DEPTH = [
    "agriculture-and-food", "air-pollution", "bathing-water", "biodiversity",
    "buildings-and-construction", "chemicals", "circular-economy",
    "climate-change-impacts-risks-and-adaptation",
    "climate-change-mitigation-reducing-emissions", "electric-vehicles", "energy",
    "energy-efficiency", "environmental-health-impacts", "environmental-inequalities",
    "extreme-weather-floods-droughts-and-heatwaves", "forests-and-forestry", "industry",
    "land-use", "nature-protection-and-restoration", "noise", "plastics",
    "production-and-consumption", "renewable-energy", "resource-use-and-materials",
    "road-transport", "seas-and-coasts", "soil", "sustainability-challenges",
    "sustainability-solutions", "sustainable-finance", "textiles",
    "transport-and-mobility", "urban-sustainability", "waste-and-recycling", "water",
]
_TOPIC_PATHS = [
    "/en/about/who-we-are",
    "/en/about/working-practices",
    "/en/about/key-partners",
    "/en/topics/at-a-glance",
    "/en/analysis/publications/the-european-environment-agency-in-brief",
] + [f"/en/topics/in-depth/{slug}" for slug in _IN_DEPTH]
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


def ingest_eea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eea", _SITE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
