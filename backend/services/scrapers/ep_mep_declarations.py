"""
MEP declarations of financial interests - the database behind
/api/v2/parliament/mep-declarations.

Every current Member of the European Parliament must file a declaration of
financial (private) interests. They are published per MEP on the Parliament
website. This endpoint is a directory: one row per current MEP, with name,
country and a direct link to that MEP's declarations page (which lists the DPI
declaration PDFs for the current term).

Current MEPs come from the EP Open Data Portal
(data.europarl.europa.eu/api/v2/meps?parliamentary-term=10); the per-MEP detail
gives the exact name slug and country used to build the declarations URL. Row IS
the content.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_API = "https://data.europarl.europa.eu/api/v2/meps"
_TERM = 10  # current parliamentary term
_DECL = "https://www.europarl.europa.eu/meps/en/{mid}/{slug}/declarations"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Accept": "application/ld+json"}


def _country(detail: dict) -> str:
    mem = detail.get("hasMembership")
    mem = mem if isinstance(mem, list) else ([mem] if mem else [])
    for m in mem:
        rep = m.get("represents")
        if not rep:
            continue
        for r in (rep if isinstance(rep, list) else [rep]):
            if "authority/country/" in str(r):
                return str(r).rsplit("/", 1)[-1]
    return ""


def ingest_mep_declarations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    lst = s.get(_API, params={"parliamentary-term": _TERM, "limit": 1000}, timeout=40).json()
    meps = lst.get("data") or []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for m in meps:
        mid = str(m.get("identifier") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        label = clean(m.get("label") or "")
        country = ""
        slug = None
        for attempt in range(3):
            try:
                d = s.get(f"{_API}/{mid}", timeout=30).json().get("data") or [{}]
                detail = d[0]
                gv = (detail.get("upperGivenName") or "").strip()
                fm = (detail.get("upperFamilyName") or "").strip()
                slug = f"{gv} {fm}".strip().replace(" ", "_")
                country = _country(detail)
                if not label:
                    label = clean(detail.get("label") or "")
                break
            except Exception:
                if attempt == 2:
                    slug = None
                time.sleep(1.0)
        if not slug:
            slug = (label or mid).upper().replace(" ", "_")
        url = _DECL.format(mid=mid, slug=slug)
        lines = [
            f"Member of the European Parliament: {label}" if label else "",
            f"Country: {country}" if country else "",
            "Declaration of financial (private) interests for the current parliamentary term, "
            "as published on the European Parliament website.",
            f"Declarations page: {url}",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="parliament", item_type="mep_declaration",
            title=clean(f"{label} - declaration of financial interests")[:120] if label else f"MEP {mid}",
            public_url=url,
            summary=clean(" | ".join(x for x in [label, country, "declaration of financial interests"] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=None, creation_date=now, source_kind="ep_meps", guid=mid))
    return items
