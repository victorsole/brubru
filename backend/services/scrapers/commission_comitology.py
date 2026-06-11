"""
Comitology register (DG-wide) - the database behind
/api/v2/commission/comitology.

The comitology committees: the Member-State committees that assist the
Commission when it adopts implementing acts. Public JSON behind the comitology
register SPA (the endpoint needs the X-Requested-With AJAX header, otherwise it
returns "can only be accessed programmatically"):
  POST /transparency/comitology-register/core/api/front/committees/search?page=&size=
       body {"reset": false}

One row per committee: code, title, lead DG and abolition status, linking to its
register page. Row IS the content.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = ("https://ec.europa.eu/transparency/comitology-register/core/api/front"
         "/committees/search")
_SCREEN = "https://ec.europa.eu/transparency/comitology-register/screen/committees/"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {
    "User-Agent": _UA, "Accept": "application/json", "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://ec.europa.eu/transparency/comitology-register/screen/committees",
}


def ingest_comitology(*, fetch_bodies: bool = True, **_) -> list[Item]:
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    page, size = 0, 500
    while True:
        r = requests.post(_BASE, params={"page": page, "size": size},
                          headers=_HEADERS, data='{"reset":false}', timeout=120)
        r.raise_for_status()
        d = r.json()
        content = d.get("content") or []
        for c in content:
            code = (c.get("committeeCode") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            title = clean(c.get("committeeTitle") or code)
            dg_code = c.get("dgCode") or ""
            dg_title = clean(c.get("dgTitle") or "")
            abolished = c.get("abolishedSince")
            status = f"Abolished since {abolished}" if abolished else "Active"
            lines = [
                f"Committee code: {code}",
                f"Committee: {title}",
                f"Lead DG: {dg_title} ({dg_code})" if dg_title else "",
                f"Status: {status}",
            ]
            lines = [l for l in lines if l]
            items.append(Item(
                body_code="commission", item_type="comitology_committee",
                title=title[:120], public_url=_SCREEN + code + "/consult",
                summary=clean(" | ".join(x for x in [code, dg_title, status] if x)),
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=None, creation_date=now, source_kind="comitology", guid=code))
        if d.get("last") or not content or page >= (d.get("totalPages", 1) - 1):
            break
        page += 1
    return items
