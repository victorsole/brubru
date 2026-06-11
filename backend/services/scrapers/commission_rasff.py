"""
RASFF - Rapid Alert System for Food and Feed - the database behind
/api/v2/commission/rasff.

Cross-border food, feed and food-contact-material safety notifications between
EU/EEA members. Public JSON behind the RASFF Window SPA (needs the
X-Requested-With AJAX header):
  POST /rasff-window/backend/public/notification/search/consolidated/en/
       body {"parameters":{"pageNumber":N,"itemsPerPage":100}}

One row per notification: reference, subject, notifying country, product
category/type, classification (alert / border rejection / information), risk
decision and origin countries. ~31,000 notifications. Row IS the content.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = ("https://webgate.ec.europa.eu/rasff-window/backend/public/notification"
         "/search/consolidated/en/")
_SCREEN = "https://webgate.ec.europa.eu/rasff-window/screen/notification/"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_HEADERS = {
    "User-Agent": _UA, "Accept": "application/json", "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://webgate.ec.europa.eu/rasff-window/screen/search",
}


def _desc(o) -> str:
    if isinstance(o, dict):
        return clean(o.get("description") or o.get("organizationName") or "")
    return ""


def _country(o) -> str:
    if isinstance(o, dict):
        return clean(o.get("organizationName") or o.get("isoCode") or "")
    return ""


def _date(s: str):
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime((s or "").strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def ingest_rasff(*, fetch_bodies: bool = True, **_) -> list[Item]:
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    page, size = 1, 100
    while True:
        body = '{"parameters":{"pageNumber":%d,"itemsPerPage":%d}}' % (page, size)
        r = requests.post(_BASE, headers=_HEADERS, data=body, timeout=60)
        r.raise_for_status()
        d = r.json()
        notifs = d.get("notifications") or []
        for n in notifs:
            nid = str(n.get("notifId") or "").strip()
            if not nid or nid in seen:
                continue
            seen.add(nid)
            ref = clean(n.get("reference") or "")
            subject = clean(n.get("subject") or "")
            notifying = _country(n.get("notifyingCountry"))
            origins = ", ".join(_country(c) for c in (n.get("originCountries") or []) if _country(c))
            pcat = _desc(n.get("productCategory"))
            ptype = _desc(n.get("productType"))
            clazz = _desc(n.get("notificationClassification"))
            risk = _desc(n.get("riskDecision"))
            doc_dt = _date(n.get("ecValidationDate"))
            title = clean(f"{ref} - {subject}") if ref and subject else (subject or f"RASFF {nid}")
            lines = [
                f"Reference: {ref}" if ref else "",
                f"Subject: {subject}" if subject else "",
                f"Classification: {clazz}" if clazz else "",
                f"Risk decision: {risk}" if risk else "",
                f"Product category: {pcat}" if pcat else "",
                f"Product type: {ptype}" if ptype else "",
                f"Notifying country: {notifying}" if notifying else "",
                f"Origin: {origins}" if origins else "",
            ]
            lines = [l for l in lines if l]
            items.append(Item(
                body_code="commission", item_type="rasff_notification", title=title[:120],
                public_url=_SCREEN + nid,
                summary=clean(" | ".join(x for x in [ref, clazz, risk, pcat] if x)),
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=doc_dt, creation_date=now, source_kind="rasff", guid=nid))
        total_pages = d.get("totalPages", 1)
        if not notifs or page >= total_pages:
            break
        page += 1
    return items
