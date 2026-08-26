"""
EU Consolidated Financial Sanctions List (DG FISMA / FPI) — the database behind
/api/v2/commission/financial-sanctions.

Source: the public FSD XML full list
  https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=...
(the token is the public one the FSD ships; the same data is also offered as CSV).
~6,000 sanctioned persons / entities / groups; one <sanctionEntity> per record,
so the row IS the content — no per-row fetch, no LLM.
"""
from __future__ import annotations

from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

from services.scrapers.economy_common import Item, clean, norm_url, _iso_dt

_FSD_URL = ("https://webgate.ec.europa.eu/fsd/fsf/public/files/"
            "xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_SUBJECT = {"person": "Person", "enterprise": "Entity", "P": "Person", "E": "Entity"}


def _ln(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def ingest_financial_sanctions(*, fetch_bodies: bool = True, **_) -> list[Item]:
    try:
        r = requests.get(_FSD_URL, headers={"User-Agent": _UA}, timeout=120)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError):
        return []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for ent in root:
        if _ln(ent.tag) != "sanctionEntity":
            continue
        ref = ent.attrib.get("euReferenceNumber") or ent.attrib.get("logicalId")
        if not ref or ref in seen:
            continue
        seen.add(ref)
        subject = regulation = None
        names: list[str] = []
        aliases: list[str] = []
        citizenships: list[str] = []
        births: list[str] = []
        ids: list[str] = []
        addresses: list[str] = []
        programmes: set[str] = set()
        reg_dates: list[str] = []
        for c in ent:
            tag = _ln(c.tag)
            if tag == "subjectType":
                subject = _SUBJECT.get(c.attrib.get("code") or c.attrib.get("classificationCode"),
                                       c.attrib.get("code"))
            elif tag == "regulation":
                a = c.attrib
                regulation = a.get("numberTitle")
                if a.get("programme"):
                    programmes.add(a["programme"])
                d = a.get("entryIntoForceDate") or a.get("publicationDate")
                if d:
                    reg_dates.append(d)
            elif tag == "nameAlias":
                wn = clean(c.attrib.get("wholeName"))
                if wn:
                    (names if c.attrib.get("strong") == "true" else aliases).append(wn)
            elif tag == "citizenship":
                cd = c.attrib.get("countryDescription")
                if cd:
                    citizenships.append(cd)
            elif tag == "birthdate":
                bd = c.attrib.get("birthdate") or c.attrib.get("year")
                place = c.attrib.get("city") or c.attrib.get("countryDescription")
                if bd or place:
                    births.append(" ".join(x for x in [bd, f"({place})" if place else ""] if x))
            elif tag == "identification":
                num = c.attrib.get("number")
                idt = c.attrib.get("identificationTypeDescription") or c.attrib.get("identificationTypeCode")
                if num:
                    ids.append(f"{idt}: {num}" if idt else num)
            elif tag == "address":
                a = c.attrib
                parts = [a.get("street"), a.get("city"), a.get("zipCode"), a.get("countryDescription")]
                addr = ", ".join(x for x in parts if x)
                if addr:
                    addresses.append(addr)
        title = (names or aliases or [ref])[0]
        doc_dt = _iso_dt(min(reg_dates)) if reg_dates else None
        url = norm_url(f"https://data.europa.eu/eu-financial-sanctions/{ref}")
        lines = [
            f"Name: {title}",
            f"Subject type: {subject}" if subject else "",
            f"Aliases: {'; '.join(aliases)}" if aliases else "",
            f"Sanctions programme(s): {', '.join(sorted(programmes))}" if programmes else "",
            f"Legal act: {regulation}" if regulation else "",
            f"Citizenship: {', '.join(sorted(set(citizenships)))}" if citizenships else "",
            f"Date/place of birth: {'; '.join(births)}" if births else "",
            f"Identification: {'; '.join(ids)}" if ids else "",
            f"Address: {'; '.join(addresses)}" if addresses else "",
            f"EU reference number: {ref}",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="financial_sanction", title=title,
            public_url=url,
            summary=clean(" | ".join(x for x in [title, subject or "",
                                                 ", ".join(sorted(programmes))] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="fsd", guid=ref))
    return items
