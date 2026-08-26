"""
Trade defence (DG TRADE / TRON) - the database behind
/api/v2/commission/trade-defence.

The EU's trade-defence cases: anti-dumping, anti-subsidy (countervailing) and
safeguard investigations and the measures in force, managed in the Commission's
TRON system. Public JSON API behind the investigations search SPA:
  POST /investigations/api/eucase/search  (body {} = the full case set)

Each row is one EU trade-defence case: the product, the proceeding type, the
measure status, the countries concerned and the case reference (AD###/AS###),
linking to the case detail page. Row IS the content.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_API = "https://tron.trade.ec.europa.eu/investigations/api/eucase/search"
_CASE = "https://tron.trade.ec.europa.eu/investigations/case/"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")


def ingest_trade_defence(*, fetch_bodies: bool = True, **_) -> list[Item]:
    r = requests.post(_API, headers={"User-Agent": _UA, "Accept": "application/json",
                                     "Content-Type": "application/json"},
                      data="{}", timeout=60)
    r.raise_for_status()
    rows = r.json()
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for c in rows:
        cid = c.get("caseInitId")
        if cid is None or str(cid) in seen:
            continue
        seen.add(str(cid))
        product = clean(c.get("shortName") or "")
        category = c.get("caseCategory") or ""
        status = clean(c.get("measureStatus") or "")
        ongoing = (c.get("ongoingInvestigation") or "").upper() == "Y"
        countries = [cc.get("countryName") for cc in (c.get("caseCountries") or [])
                     if cc.get("countryName")]
        related = [rc.get("caseNumber") for rc in (c.get("relatedCases") or [])
                   if rc.get("caseNumber")]
        case_no = related[0] if related else ""
        title = clean(f"{case_no} - {product}") if case_no and product else (product or f"Case {cid}")
        lines = [
            f"Case reference: {', '.join(dict.fromkeys(related))}" if related else "",
            f"Product: {product}" if product else "",
            f"Proceeding type: {category}" if category else "",
            f"Measure status: {status}" if status else "",
            "Investigation ongoing: yes" if ongoing else "",
            f"Countries concerned: {', '.join(countries)}" if countries else "",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="trade_defence_case", title=title[:120],
            public_url=_CASE + str(cid),
            summary=clean(" | ".join(x for x in [case_no, category, status,
                                                 ", ".join(countries[:3])] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=None, creation_date=now, source_kind="tron", guid=str(cid)))
    return items
