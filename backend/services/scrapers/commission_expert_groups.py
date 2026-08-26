"""
Register of Commission Expert Groups - the database behind
/api/v2/commission/expert-groups.

The expert groups and sub-groups that advise the Commission in preparing
legislation and policy. Public JSON behind the register SPA (needs the
X-Requested-With AJAX header):
  POST /transparency/expert-groups-register/core/api/front/expertGroups/search?page=&size=
       body {}   (all groups + subgroups)

One row per group: code, name, lead DG and type, linking to its register page.
Row IS the content.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = ("https://ec.europa.eu/transparency/expert-groups-register/core/api/front"
         "/expertGroups/search")
_SCREEN = ("https://ec.europa.eu/transparency/expert-groups-register/screen/"
           "expert-groups/consult?lang=en&groupID=")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {
    "User-Agent": _UA, "Accept": "application/json", "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://ec.europa.eu/transparency/expert-groups-register/screen/expert-groups",
}


def ingest_expert_groups(*, fetch_bodies: bool = True, **_) -> list[Item]:
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    page, size = 0, 500
    while True:
        r = requests.post(_BASE, params={"page": page, "size": size},
                          headers=_HEADERS, data="{}", timeout=120)
        r.raise_for_status()
        d = r.json()
        content = d.get("content") or []
        for g in content:
            gid = str(g.get("id") or "").strip()
            if not gid or gid in seen:
                continue
            seen.add(gid)
            name = clean(g.get("name") or "")
            code = clean(g.get("codeGroup") or "")
            lead = clean(g.get("leadDg") or "")
            gtype = (g.get("type") or "").replace("_", " ").title()
            lines = [
                f"Group code: {code}" if code else "",
                f"Name: {name}" if name else "",
                f"Lead DG: {lead}" if lead else "",
                f"Type: {gtype}" if gtype else "",
            ]
            lines = [l for l in lines if l]
            items.append(Item(
                body_code="commission", item_type="expert_group",
                title=(name or code or f"Expert group {gid}")[:120],
                public_url=_SCREEN + gid,
                summary=clean(" | ".join(x for x in [code, lead, gtype] if x)),
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=None, creation_date=now, source_kind="expert_groups", guid=gid))
        if d.get("last") or not content or page >= (d.get("totalPages", 1) - 1):
            break
        page += 1
    return items
