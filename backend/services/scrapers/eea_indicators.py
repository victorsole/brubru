"""European Environment Agency database — EU environmental indicators.
Backs /api/v2/eea/indicators.

The EEA publishes a curated set of environmental indicators (air, climate,
biodiversity, waste, water, energy...), each a standing assessment of the state
of and trends in one environmental issue. They are content items of type
`ims_indicator` exposed through the EEA Plone REST API (`++api++`). One row per
indicator: title, the assessment summary, topic/indicator-code tags, the last
update date and the indicator page URL. Row IS the content.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_API = ("https://www.eea.europa.eu/++api++/en/analysis/indicators/@search"
        "?portal_type=ims_indicator&b_size=500"
        "&metadata_fields=Description&metadata_fields=Subject&metadata_fields=effective")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}


def _eff(v) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def ingest_eea_indicators(*, fetch_bodies: bool = True, **_) -> list[Item]:
    j = requests.get(_API, headers=_HEADERS, timeout=60).json()
    rows = j.get("items") or []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for r in rows:
        url = clean(r.get("@id") or "")
        title = clean(r.get("title") or "")
        if not url or not title or url in seen:
            continue
        seen.add(url)
        desc = clean(r.get("Description") or r.get("description") or "")
        subjects = r.get("Subject") or []
        subjects = [clean(s) for s in subjects if s] if isinstance(subjects, list) else []
        eff = _eff(r.get("effective"))
        lines = [f"Environmental indicator: {title}",
                 f"Topics: {', '.join(subjects)}" if subjects else "",
                 f"Last updated: {eff.date()}" if eff else "",
                 desc or ""]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="eea", item_type="environmental_indicator",
            title=title[:120], public_url=url,
            summary=clean(desc[:300]) if desc else title[:120],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=eff, creation_date=now,
            source_kind="eea_plone", guid=url))
    return items
