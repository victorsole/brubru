"""
Agri-food data portal (DG AGRI) - the catalogue behind
/api/v2/commission/agridata.

The DG AGRI Agri-food data portal exposes a public REST API of agricultural
market data (prices, production, trade, balance sheets, CMEF/PMEF indicators)
across ~19 sectors: beef, pigmeat, poultry, sheep & goat, milk & dairy, cereals,
rice, oilseeds, sugar, olive oil, wine, fruit & vegetables, fertiliser, organic,
and the customs (TAXUD) weekly import data.

The underlying data are statistical time-series, so this endpoint is a CATALOGUE
of the available data resources (one row per agri-food data series) rather than a
dump of every price point: each row carries the series title, sector, the filter
parameters it accepts and a ready-to-run link to the live agri-food API that
returns the actual figures. Built from the agri-food OpenAPI spec, so it tracks
new sectors and series automatically. Row IS the content.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_SPEC = "https://api.tech.ec.europa.eu/agrifood/v3/api-docs"
_API = "https://api.tech.ec.europa.eu/agrifood"
_PORTAL = "https://agridata.ec.europa.eu/extensions/DataPortal/home.html"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_EXAMPLE = re.compile(r"\[(/api/[^\]\s]+)\]")


def ingest_agridata_catalogue(*, fetch_bodies: bool = True, **_) -> list[Item]:
    r = requests.get(_SPEC, headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    spec = r.json()
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for path, methods in (spec.get("paths") or {}).items():
        op = methods.get("get")
        if not op:
            continue
        summary = clean(op.get("summary") or "")
        desc = op.get("description") or ""
        tags = op.get("tags") or []
        sector = clean(tags[0]) if tags else ""
        # A working example query lives in the description as [/api/.../...?...].
        m = _EXAMPLE.search(desc)
        example = m.group(1) if m else path
        live_url = _API + example
        if live_url in seen:
            continue
        seen.add(live_url)
        params = []
        for p in op.get("parameters") or []:
            nm = p.get("name")
            if nm:
                pd = clean((p.get("description") or "").split("<br")[0])
                params.append(f"{nm} ({pd})" if pd else nm)
        # Clean the markdown example link out of the human description.
        desc_txt = clean(re.sub(r"\(\.\./[^)]*\)", "", _EXAMPLE.sub(r"\1", desc)))
        title = summary or clean(path.replace("/api/", "").replace("/", " - "))
        if sector and sector.lower() not in title.lower():
            title = f"{sector} - {title}"
        lines = [
            f"Sector: {sector}" if sector else "",
            f"Agri-food data series: {summary}" if summary else "",
            desc_txt,
            ("Filter parameters: " + "; ".join(params)) if params else "",
            f"Live data endpoint: {live_url}",
            f"Data portal: {_PORTAL}",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="agri_data_series", title=title[:120],
            public_url=live_url,
            summary=clean(" | ".join(x for x in [sector, summary, "agri-food data series"] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=None, creation_date=now, source_kind="agridata", guid=path))
    return items
