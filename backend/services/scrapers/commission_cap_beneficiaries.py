"""
Common Agricultural Policy beneficiaries - the directory behind
/api/v2/commission/cap-beneficiaries.

Under EU transparency rules, the names of CAP beneficiaries (EAGF direct
payments + EAFRD rural-development support) are published by each Member State
on its own national portal, not in a single EU dataset. DG AGRI maintains the
canonical index of those national search portals. This endpoint mirrors that
index: one row per Member State, each linking to the national portal where the
actual beneficiary records can be searched. Row IS the content.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_PAGE = ("https://agriculture.ec.europa.eu/common-agricultural-policy/"
         "financing-cap/beneficiaries_en")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# EU27 + the United Kingdom (legacy CAP payments still published).
_COUNTRIES = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Czech Republic", "Denmark", "Estonia", "Finland", "France", "Germany",
    "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania",
    "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania",
    "Slovakia", "Slovenia", "Spain", "Sweden", "United Kingdom",
}
_ANCHOR = re.compile(r"<a\s[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.S)


def ingest_cap_beneficiaries(*, fetch_bodies: bool = True, **_) -> list[Item]:
    r = requests.get(_PAGE, headers={"User-Agent": _UA}, timeout=40)
    r.raise_for_status()
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for url, raw in _ANCHOR.findall(r.text):
        if not url.startswith("http"):
            continue
        txt = clean(re.sub(r"<[^>]+>", "", raw))
        if txt not in _COUNTRIES or txt in seen:
            continue
        seen.add(txt)
        title = f"{txt} - CAP beneficiaries portal"
        lines = [
            f"Member State: {txt}",
            "National transparency portal for Common Agricultural Policy beneficiaries "
            "(EAGF direct payments and EAFRD rural-development support).",
            "Under EU transparency rules each Member State publishes the names of CAP "
            "beneficiaries on its own portal; search the recipients there.",
            f"Portal: {url}",
        ]
        items.append(Item(
            body_code="commission", item_type="cap_beneficiary_portal", title=title,
            public_url=url,
            summary=clean(f"{txt} | national CAP beneficiary transparency portal"),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=None, creation_date=now, source_kind="cap_beneficiaries", guid=txt))
    return items
