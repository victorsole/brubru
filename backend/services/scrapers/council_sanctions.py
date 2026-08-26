"""Council of the EU database — EU sanctions (restrictive measures) regimes.
Backs /api/v2/council/sanctions-regimes.

The Council decides the EU's restrictive measures. The EU Sanctions Map
(sanctionsmap.eu, run under the Council Presidency) publishes every regime with
its legal basis, the measures imposed, the target country/theme and explanatory
notes, via a public JSON API. One row per regime (55 of them). Row IS the content
(specification + notes + country + legal acts + measure types).
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_API = "https://www.sanctionsmap.eu/api/v1/regime"
_DETAIL = "https://www.sanctionsmap.eu/#/main/details/{id}"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Accept": "application/json",
            "Referer": "https://www.sanctionsmap.eu/"}


def _ts(v) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc) if v else None
    except (TypeError, ValueError, OSError):
        return None


def _data(node) -> list:
    if isinstance(node, dict):
        d = node.get("data")
        return d if isinstance(d, list) else ([d] if d else [])
    return node if isinstance(node, list) else []


def ingest_council_sanctions(*, fetch_bodies: bool = True, **_) -> list[Item]:
    j = requests.get(_API, headers=_HEADERS, timeout=60).json()
    regimes = j.get("data") or []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for r in regimes:
        rid = str(r.get("id") or "").strip()
        spec = clean(r.get("specification") or "")
        if not rid or not spec:
            continue
        country = ""
        cd = (r.get("country") or {}).get("data") or {}
        if isinstance(cd, dict):
            country = clean(cd.get("title") or "")
        acronym = clean(r.get("acronym") or "")
        notes = clean(r.get("notes") or "")
        legal = _data(r.get("legal_acts"))
        measures = _data(r.get("measures"))
        measure_types = []
        for m in measures:
            t = ((m.get("type") or {}).get("data") or {}).get("title") if isinstance(m, dict) else None
            if t and t not in measure_types:
                measure_types.append(clean(t))
        lines = [f"Sanctions regime: {spec}",
                 f"Target: {country}" if country else "",
                 f"Acronym: {acronym}" if acronym else "",
                 f"Last amended: {_ts(r.get('amendment')).date()}" if _ts(r.get("amendment")) else "",
                 f"Expires: {_ts(r.get('expiration')).date()}" if _ts(r.get("expiration")) else ""]
        if measure_types:
            lines.append(f"Measures ({len(measure_types)}): " + "; ".join(measure_types))
        if notes:
            lines.append(f"Notes: {notes}")
        if legal:
            lines.append("Legal acts:")
            for la in legal:
                if not isinstance(la, dict):
                    continue
                t = clean(la.get("title") or "")
                num = clean(la.get("number") or "")
                url = clean(la.get("url") or "")
                lines.append(f"  - {t}{' (' + num + ')' if num else ''}{' ' + url if url else ''}")
        lines = [l for l in lines if l]
        summary = clean(" | ".join(x for x in [
            country, acronym, f"{len(legal)} legal acts", f"{len(measure_types)} measure types"] if x))
        items.append(Item(
            body_code="council", item_type="sanctions_regime",
            title=spec[:120], public_url=_DETAIL.format(id=rid),
            summary=summary or spec[:120],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=_ts(r.get("amendment")), creation_date=now,
            source_kind="sanctions_map", guid=rid))
    return items
