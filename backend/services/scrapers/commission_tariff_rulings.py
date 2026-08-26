"""
EBTI — European Binding Tariff Information — the database behind
/api/v2/commission/tariff-rulings.

Binding customs-classification rulings issued by Member State customs
authorities. Source: the EBTI bulk extract (DDS2), a ~371 MB zip of yearly CSVs
(EBTI_2004.csv ... EBTI_<year>.csv), reached via a 3-step session flow:
  1. GET ebti_consultation.jsp            -> JSESSIONID cookie
  2. GET ebti_export_management.jsp?message=extract  -> prepares the tmp file
  3. GET downloadcsv?filepath=...&filename=DDS2-EBTI_Full.zip  -> the zip
The full archive holds millions of rulings, so we ingest the most recent two
years (the descriptions are in the issuing country's language; the KEYWORDS
field is English, so the rows stay searchable in English). Row IS the content.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
import zipfile
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_CONSULT = "https://ec.europa.eu/taxation_customs/dds2/ebti/ebti_consultation.jsp?Lang=en"
_EXTRACT = "https://ec.europa.eu/taxation_customs/dds2/ebti/ebti_export_management.jsp?message=extract&Lang=en"
_DOWNLOAD = ("https://ec.europa.eu/taxation_customs/dds2/ebti/downloadcsv"
             "?filepath=/ec/prod/server/d2ebti_1_p/data/group_WLS124/app/dds2-ebti/tmp/DDS2-EBTI_Full.zip"
             "&filetype=application/zip&filename=DDS2-EBTI_Full.zip")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_RECENT_YEARS = 2


def _date(s: str):
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _download_zip(dest: str, tries: int = 3) -> bool:
    """The 371 MB bulk zip download is flaky; re-establish the session, re-trigger
    the extract and retry the streamed download, verifying it's a real zip."""
    for _ in range(tries):
        s = requests.Session()
        s.headers.update({"User-Agent": _UA})
        try:
            s.get(_CONSULT, timeout=60)
            s.get(_EXTRACT, timeout=120)
            r = s.get(_DOWNLOAD, headers={"Referer": _CONSULT}, stream=True, timeout=600)
            if r.status_code != 200 or "zip" not in r.headers.get("content-type", ""):
                continue
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            # sanity: a valid zip starts with PK and is sizeable
            if os.path.getsize(dest) > 1_000_000:
                with open(dest, "rb") as fh:
                    if fh.read(2) == b"PK":
                        return True
        except (requests.RequestException, OSError):
            continue
    return False


def ingest_tariff_rulings(*, fetch_bodies: bool = True, recent_years: int = _RECENT_YEARS,
                          **_) -> list[Item]:
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    try:
        if not _download_zip(tmp.name):
            return []
        z = zipfile.ZipFile(tmp.name)
        years = sorted(n for n in z.namelist()
                       if n.startswith("EBTI_") and n.endswith(".csv"))
        targets = years[-recent_years:]
        now = datetime.now(timezone.utc)
        items: list[Item] = []
        seen: set[str] = set()
        for member in targets:
            with z.open(member) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    ref = (row.get("BTI_REFERENCE") or "").strip()
                    if not ref or ref in seen:
                        continue
                    seen.add(ref)
                    desc = clean(row.get("DESCRIPTION_OF_GOODS"))
                    nomenc = (row.get("NOMENCLATURE_CODE") or "").rstrip("*").strip()
                    country = (row.get("ISSUING_COUNTRY") or "").strip()
                    keywords = clean(row.get("KEYWORDS"))
                    status = (row.get("STATUS") or "").strip()
                    just = clean(row.get("CLASSIFICATION_JUSTIFICATION"))
                    issue = row.get("DATE_OF _ISSUE") or row.get("DATE_OF_ISSUE")
                    doc_dt = _date(issue) or _date(row.get("START_DATE_OF_VALIDITY"))
                    title = (desc[:90] if desc else f"BTI {ref}")
                    url = (f"https://ec.europa.eu/taxation_customs/dds2/ebti/ebti_details.jsp"
                           f"?Lang=en&reference={ref}")
                    lines = [
                        f"BTI reference: {ref}",
                        f"Nomenclature (CN/TARIC) code: {nomenc}" if nomenc else "",
                        f"Issuing country: {country}" if country else "",
                        f"Status: {status}" if status else "",
                        f"Valid from: {(row.get('START_DATE_OF_VALIDITY') or '').strip()}"
                        if row.get("START_DATE_OF_VALIDITY") else "",
                        f"Valid to: {(row.get('END_DATE_OF_VALIDITY') or '').strip()}"
                        if row.get("END_DATE_OF_VALIDITY") else "",
                        f"Description of goods: {desc}" if desc else "",
                        f"Keywords: {keywords}" if keywords else "",
                        f"Classification justification: {just}" if just else "",
                        f"Place of issue: {clean(row.get('PLACE_OF_ISSUE'))}"
                        if row.get("PLACE_OF_ISSUE") else "",
                    ]
                    lines = [l for l in lines if l]
                    items.append(Item(
                        body_code="commission", item_type="tariff_ruling", title=title,
                        public_url=url,
                        summary=clean(" | ".join(x for x in [nomenc, (desc[:60] if desc else ""),
                                                             country, status] if x)),
                        body_txt=clean("\n".join(lines)),
                        body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                        document_date=doc_dt, creation_date=now, source_kind="ebti", guid=ref))
        return items
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
