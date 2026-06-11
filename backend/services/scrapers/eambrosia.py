"""
eAmbrosia - the EU register of geographical indications (DG AGRI).

The authoritative EU register of GIs for wine, spirits, agricultural products
and foodstuffs (PDO / PGI / GI / TSG), plus the third-country GIs protected in
the EU under international trade agreements. Public OpenAPI, no auth:
  GET /api/v1/geographical-indications   -> the whole EU register in one call
  GET /api/v1/g3c                         -> third-country GIs (3C)

Backs two endpoints under the "Geographical Indications" domain:
  geographical-indications/eu-register    item_type 'geographical_indication'
  geographical-indications/third-country  item_type 'third_country_gi'
Row IS the content; both calls return the full list, no pagination.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_BASE = "https://webgate.ec.europa.eu/eambrosia-api/api/v1"
_REGISTER = ("https://ec.europa.eu/agriculture/eambrosia/"
             "geographical-indications-register/details/")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_GI_TYPE = {
    "PDO": "Protected Designation of Origin (PDO)",
    "PGI": "Protected Geographical Indication (PGI)",
    "GI": "Geographical Indication (GI, spirits/aromatised wines)",
    "TSG": "Traditional Speciality Guaranteed (TSG)",
}


def _get(path: str) -> list:
    r = requests.get(_BASE + path, headers={"User-Agent": _UA, "Accept": "application/json"},
                     timeout=120)
    r.raise_for_status()
    d = r.json()
    return d if isinstance(d, list) else (d.get("content") or [])


def _names(value) -> str:
    if isinstance(value, list):
        out = []
        for n in value:
            out.append(n.get("value", "") if isinstance(n, dict) else str(n))
        return ", ".join(x for x in out if x)
    return str(value or "")


def ingest_eambrosia_gis(*, fetch_bodies: bool = True, **_) -> list[Item]:
    rows = _get("/geographical-indications")
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for g in rows:
        gid = (g.get("giIdentifier") or "").strip()
        if not gid:
            continue
        name = _names(g.get("protectedNames"))
        gtype = g.get("giType") or ""
        gtype_full = _GI_TYPE.get(gtype, gtype)
        ptype = (g.get("productType") or "").replace("_", " ").title()
        countries = ", ".join(g.get("countries") or [])
        status = g.get("status") or ""
        file_no = g.get("fileNumber") or ""
        prot = g.get("euProtectionDate") or ""
        legal = g.get("legalInstrument") or {}
        pg_name = g.get("producerGroupName")
        cn = g.get("cnClassification") or []
        cn_txt = "; ".join(c.get("cnTranslation") or c.get("cnText") or "" for c in cn if isinstance(c, dict))
        pubs = g.get("publications") or []
        pub_txt = "; ".join(p.get("text") or "" for p in pubs if isinstance(p, dict))
        doc_dt = None
        if prot:
            try:
                doc_dt = datetime.strptime(prot, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                doc_dt = None
        title = clean(f"{name} ({gtype})") if gtype else clean(name) or f"GI {gid}"
        lines = [
            f"Name: {name}" if name else "",
            f"Type: {gtype_full}" if gtype_full else "",
            f"Product type: {ptype}" if ptype else "",
            f"Country: {countries}" if countries else "",
            f"Status: {status}" if status else "",
            f"File number: {file_no}" if file_no else "",
            f"EU protection date: {prot}" if prot else "",
            f"Legal instrument: {legal.get('text')}" if legal.get("text") else "",
            f"CN classification: {cn_txt}" if cn_txt else "",
            f"Producer group: {pg_name}" if pg_name else "",
            f"Producer group e-mail: {g.get('producerGroupEmail')}" if g.get("producerGroupEmail") else "",
            f"Publications: {pub_txt}" if pub_txt else "",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="geographical_indication", title=title,
            public_url=_REGISTER + gid,
            summary=clean(" | ".join(x for x in [name, gtype, ptype, countries, status] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="eambrosia", guid=gid))
    return items


def ingest_eambrosia_third_country(*, fetch_bodies: bool = True, **_) -> list[Item]:
    rows = _get("/g3c")
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for g in rows:
        gid = (g.get("giIdentifier") or "").strip()
        if not gid:
            continue
        name = _names(g.get("names"))
        category = g.get("category") or ""
        subcat = g.get("subcategory") or ""
        prot_type = g.get("type") or ""
        status = g.get("status") or ""
        countries = ", ".join(g.get("countries") or [])
        agr_name = g.get("agreementName") or g.get("instrumentName") or ""
        agr_link = g.get("agreementLink") or g.get("instrumentLink") or ""
        agr_date = g.get("agreementDate") or g.get("instrumentDate") or ""
        agr_variant = g.get("agreementVariant") or ""
        doc_dt = None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                doc_dt = datetime.strptime(agr_date, fmt).replace(tzinfo=timezone.utc)
                break
            except (ValueError, TypeError):
                continue
        title = clean(f"{name} ({countries})") if countries else clean(name) or f"3C GI {gid}"
        lines = [
            f"Name: {name}" if name else "",
            f"Third country: {countries}" if countries else "",
            f"Product category: {category}" + (f" / {subcat}" if subcat else "") if category else "",
            f"Protection type: {prot_type}" if prot_type else "",
            f"Status: {status}" if status else "",
            f"Agreement: {agr_variant}" if agr_variant else "",
            f"Protected under: {agr_name}" if agr_name else "",
            f"Agreement date: {agr_date}" if agr_date else "",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="commission", item_type="third_country_gi", title=title,
            public_url=_REGISTER + gid,
            summary=clean(" | ".join(x for x in [name, countries, category, status] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines)
                            + (f'<li>Agreement: <a href="{agr_link}">{clean(agr_name)}</a></li>' if agr_link else "")
                            + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="eambrosia_3c", guid=gid))
    return items
