"""Digital Product Passport — the two feeds that actually change.

The /api/v2/dpp folder is mostly curated: the acts, sectors, registry facts,
harmonised standards, audience guides and battery data points move only when the law
or the Commission guidance moves, and they are (re)built by
`scripts/backfill_dpp_folder.py`.

News and events are different: the Commission adds to them without warning, and they
are the surface a subscriber watches to know that something moved. So those two are
ingested here and refreshed by cron like any other body feed.

The Commission's single-market listings render server-side, so plain HTTP is enough
and no Chromium render is needed. That is why `dpp` can sit in any cron window.

Listing URLs are the site's own facet filters on the title token "dpp".
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import List

import requests

from services.scrapers.economy_common import Item, clean

logger = logging.getLogger(__name__)

_BASE = "https://single-market-economy.ec.europa.eu"
_NEWS = f"{_BASE}/news_en?f%5B0%5D=oe_news_title%3Adpp"
_EVENTS = (f"{_BASE}/events_en?f%5B0%5D=oe_event_status%3Apast"
           "&f%5B1%5D=oe_event_status%3Aupcoming&f%5B2%5D=oe_event_title%3Adpp")

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "en",
}

# The slug always ends in the publication date, which is far more reliable than the
# listing's three-line "07 JUL 2026" date rendering. The anchor text carries the real
# title: deriving it from the slug instead loses the casing and the parentheses
# ("Eu digital product passport dpp web page" rather than the published headline).
_SLUG = r'href="(/{kind}/[a-z0-9\-]+-(\d{{4}})-(\d{{2}})-(\d{{2}})_en)"[^>]*>(.*?)</a>'
_TAGS = re.compile(r"<[^>]+>")


def _harvest(url: str, kind: str, item_type: str, noun: str) -> List[Item]:
    now = datetime.now(timezone.utc)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=45)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DPP] %s listing fetch failed: %s", kind, exc)
        return []

    seen: set = set()
    items: List[Item] = []
    for m in re.finditer(_SLUG.format(kind=kind), r.text, re.S):
        path, y, mo, d, anchor = m.groups()
        if path in seen:
            continue
        seen.add(path)
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        title = re.sub(r"\s+", " ", _TAGS.sub(" ", anchor)).strip()
        if len(title) < 10:
            # fall back to the slug if the anchor held only an image or an icon
            title = slug[: -len(f"-{y}-{mo}-{d}_en")].replace("-", " ").strip().capitalize()
        try:
            doc_date = datetime(int(y), int(mo), int(d), tzinfo=timezone.utc)
        except ValueError:
            doc_date = None

        lines = [
            title,
            "",
            f"{noun} on the EU Digital Product Passport.",
            f"Published: {y}-{mo}-{d}",
            "Source: European Commission, single market newsroom",
            f"Link: {_BASE}{path}",
        ]
        items.append(Item(
            body_code="dpp",
            item_type=item_type,
            title=title[:120],
            public_url=f"{_BASE}{path}",
            summary=f"{noun} on the Digital Product Passport.",
            body_txt=clean("\n".join(lines)),
            body_html=clean(
                f"<h2>{title}</h2><p>{noun} on the EU Digital Product Passport.</p>"
                f"<ul><li>Published: {y}-{mo}-{d}</li>"
                f"<li>Source: European Commission, single market newsroom</li></ul>"
            ),
            document_date=doc_date,
            creation_date=now,
            source_kind="html",
            guid=f"dpp-{item_type}-{slug[:60]}",
        ))
    logger.info("[DPP] %s: %d item(s)", kind, len(items))
    return items


def ingest_dpp_news(**_) -> List[Item]:
    return _harvest(_NEWS, "news", "news", "Commission news item")


def ingest_dpp_events(**_) -> List[Item]:
    return _harvest(_EVENTS, "events", "event", "Commission event")
