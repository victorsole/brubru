"""
TARIC / Combined Nomenclature - the database behind
/api/v2/commission/taric-tariffs.

The Combined Nomenclature (CN) is the EU goods-classification used for customs
duties and external-trade statistics: ~15,000 codes from 2-digit chapters down
to 8-digit CN subheadings, each subdividing the world Harmonized System.

Source: the official CN annual table published by Eurostat on EU Vocabularies as
SKOS RDF. We use the leaner "skos_core" distribution (~163 MB, all languages)
rather than the 435 MB "skos_ap_eu" profile, stream-parse it, and keep the
English label, the descriptive scope note, the hierarchy depth and the parent
code. Duty rates are NOT in the nomenclature itself - they live in the live
TARIC measures lookup, which the per-row public_url links to. Row IS the content.

The CN edition is resolved dynamically from the EU Vocabularies dataset metadata
(combined-nomenclature-<year>) so the scraper follows the yearly republication
without a code change.
"""
from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

_RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
_SKOS = "{http://www.w3.org/2004/02/skos/core#}"
_XKOS = "{http://rdf-vocabulary.ddialliance.org/xkos#}"
_XML = "{http://www.w3.org/XML/1998/namespace}"
_M8G = "{http://data.europa.eu/m8g/}"

# EU Vocabularies dataset for the current CN edition. The dataset RDF carries
# the release expression, which carries the skos_core distribution file URL.
_DATASET = "http://publications.europa.eu/resource/dataset/combined-nomenclature-{year}"

_LEVEL = {2: "Chapter", 4: "Heading", 6: "HS subheading",
          8: "CN subheading", 10: "TARIC code"}


def _resolve_skos_core_url(year: int) -> tuple[str, datetime | None]:
    """Resolve the CN <year> skos_core RDF file URL via EU Vocabularies metadata.

    dataset -> work_dataset (release) -> expression -> skos_core distribution ->
    .../skos_core/ESTAT-CN<year>.rdf (the DOC_1 manifestation item).
    Returns (file_url, edition_date)."""
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "application/rdf+xml"})

    def _rdf(url: str) -> str:
        r = s.get(url, timeout=90)
        r.raise_for_status()
        return r.text

    ds = _rdf(_DATASET.format(year=year))
    rel = re.search(r"combined-nomenclature-%d/(\d{8}-\d+)" % year, ds)
    if not rel:
        raise RuntimeError(f"CN {year}: no release found in dataset metadata")
    release = rel.group(1)
    edition = None
    m = re.search(r"work_date_document[^>]*>(\d{4}-\d{2}-\d{2})", ds)
    if m:
        edition = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)

    exp = (f"http://publications.europa.eu/resource/expression/"
           f"combined-nomenclature-{year}/{release}")
    exp_rdf = _rdf(exp)
    if "rdf/skos_core" not in exp_rdf:
        raise RuntimeError(f"CN {year}: no skos_core distribution on expression")
    dist = (f"http://publications.europa.eu/resource/distribution/"
            f"combined-nomenclature-{year}/{release}/rdf/skos_core")
    # The distribution deref lists the actual file item (DOC_1 / ESTAT-CN<year>.rdf).
    dist_rdf = _rdf(dist)
    fm = re.search(r"(skos_core/ESTAT-CN\d{4}\.rdf)", dist_rdf)
    file_url = ("http://publications.europa.eu/resource/distribution/"
                f"combined-nomenclature-{year}/{release}/rdf/"
                + (fm.group(1) if fm else f"skos_core/ESTAT-CN{year}.rdf"))
    return file_url, edition


def _download(url: str, dest: str, tries: int = 3) -> bool:
    for _ in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": _UA}, timeout=900, stream=True)
            if r.status_code != 200:
                continue
            n = 0
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
                    n += len(chunk)
            if n > 10_000_000:  # a real CN dump is >100 MB; small = error page
                with open(dest, "rb") as fh:
                    if fh.read(5).lstrip().startswith(b"<?xml"):
                        return True
        except (requests.RequestException, OSError):
            continue
    return False


def _strip_dashes(text: str) -> str:
    return re.sub(r"^[-\s]+", "", text or "").strip()


def ingest_taric_tariffs(*, fetch_bodies: bool = True, year: int | None = None,
                         **_) -> list[Item]:
    yr = year or datetime.now(timezone.utc).year
    try:
        file_url, edition = _resolve_skos_core_url(yr)
    except Exception:
        # Fall back one edition (a new year may not be published in January).
        yr -= 1
        file_url, edition = _resolve_skos_core_url(yr)

    tmp = tempfile.NamedTemporaryFile(suffix=".rdf", delete=False)
    tmp.close()
    try:
        if not _download(file_url, tmp.name):
            return []
        now = datetime.now(timezone.utc)
        items: list[Item] = []
        seen: set[str] = set()
        ctx = ET.iterparse(tmp.name, events=("start", "end"))
        _, root = next(ctx)
        for ev, el in ctx:
            if ev != "end" or el.tag != _RDF + "Description":
                continue
            about = el.get(_RDF + "about", "")
            cid = about.rsplit("/", 1)[-1]
            is_concept = any(
                t.get(_RDF + "resource", "").endswith("core#Concept")
                for t in el.findall(_RDF + "type"))
            if not (is_concept and cid.isdigit()):
                root.clear()
                continue
            notation = en_pref = en_alt = en_scope = depth = broader = unit = None
            for ch in el:
                tag = ch.tag
                lang = ch.get(_XML + "lang")
                if tag == _SKOS + "notation":
                    notation = (ch.text or "").strip()
                elif tag == _SKOS + "prefLabel" and lang == "en":
                    en_pref = (ch.text or "").strip()
                elif tag == _SKOS + "altLabel" and lang == "en":
                    en_alt = (ch.text or "").strip()
                elif tag == _SKOS + "scopeNote" and lang == "en":
                    en_scope = (ch.text or "").strip()
                elif tag == _XKOS + "depth":
                    depth = (ch.text or "").strip()
                elif tag == _SKOS + "broader":
                    broader = ch.get(_RDF + "resource", "").rsplit("/", 1)[-1]
                elif tag == _M8G + "statUnitMeasure":
                    unit = ch.get(_RDF + "resource", "").rsplit("/", 1)[-1]
            root.clear()
            if not notation:
                continue
            digits = re.sub(r"\D", "", notation)
            if not digits or digits in seen:
                continue
            seen.add(digits)
            desc = _strip_dashes(en_alt) or _strip_dashes(en_pref)
            level = _LEVEL.get(len(digits), f"Level (depth {depth})" if depth else "Code")
            parent = None
            if broader and broader.isdigit():
                # parent notation isn't carried; expose the live TARIC lookup digits
                parent = re.sub(r"\D", "", broader)[:10] or None
            title = clean(f"{notation} {desc}")[:120] if desc else f"CN {notation}"
            url = ("https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp"
                   f"?Lang=en&Taric={digits}")
            lines = [
                f"CN code: {notation}",
                f"Classification level: {level}",
                f"Description: {desc}" if desc else "",
                f"Definition: {clean(en_scope)}" if en_scope else "",
                f"Supplementary unit: {unit}" if unit and unit != "NO_SU" else "",
            ]
            lines = [l for l in lines if l]
            items.append(Item(
                body_code="commission", item_type="tariff_code", title=title,
                public_url=url,
                summary=clean(" | ".join(x for x in [notation, desc[:80] if desc else "", level] if x)),
                body_txt=clean("\n".join(lines)),
                body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                document_date=edition, creation_date=now, source_kind="cn", guid=cid))
        return items
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
