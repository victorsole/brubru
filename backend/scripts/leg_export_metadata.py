"""The Publications Office's metadata for one law, as eu_laws stores it (migrations 301, 302). No database imports.

One reading for both writers of the columns: fill_eu_laws_export_metadata.py (the backfill) and import_corpus_update.py
(later exports) call rdf_facts on a folder's tree_non_inferred.rdf. Fields:
  - authors: work_created_by_agent, the corporate-body codes (COM, CONSIL, EP, a DG...);
  - in_force: resource_legal_in-force; None when the metadata carries no flag (not false);
  - eli: resource_legal_eli, the one the metadata states on the work (one per folder or none, 29,275 of 30,246 folders
    with text). The table builder's regex stopped at "(" and cut 701 ELIs short (32014D0026 is .../26(1)/oj);
  - entry_into_force / application_dates / effect_dates: resource_legal_date_entry-into-force, split by the type each
    date carries in the metadata (fd_335: EV, MA or MA/PART, PE); an untyped date stays an entry-into-force date;
  - procedures: work_part_of_dossier links to resource/procedure/YYYY_N, as YYYY/NNNN (the OEIL reference without its
    type). The export lacks most (GDPR has none there); fill_eu_laws_export_metadata adds Cellar's dossier_contains_work.
alias and acronym come from Brubru's curated aliases.csv only.
"""
from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "backend/data/leg_2026-10_table"
COLS = ("alias", "acronym", "authors", "in_force", "eli", "entry_into_force", "application_dates", "effect_dates",
        "procedures")
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CDM = "{http://publications.europa.eu/ontology/cdm#}"
OWL = "{http://www.w3.org/2002/07/owl#}"
ANN = "{http://publications.europa.eu/ontology/annotation#}"
EIF = "http://publications.europa.eu/ontology/cdm#resource_legal_date_entry-into-force"
DATE_COLUMN = {"EV": "entry_into_force", "MA": "application_dates", "MA/PART": "application_dates", "PE": "effect_dates"}
PROCEDURE = re.compile(r"/resource/procedure/(\d{4})_0*(\d{1,4})$")


def procedure_number(uri: str) -> Optional[str]:
    """http://publications.europa.eu/resource/procedure/2012_11 -> 2012/0011; anything else (internal_proc, pegase) None."""
    m = PROCEDURE.search(uri or "")
    return f"{m[1]}/{int(m[2]):04d}" if m else None


def rdf_facts(corpus_path: Path, folder: str) -> dict:
    """Every metadata column but alias and acronym, as one folder's RDF states it; None where it states nothing."""
    root = ET.parse(Path(corpus_path) / folder / "tree_non_inferred.rdf").getroot()

    def lit(tag):
        return [e.text.strip() for e in root.iter(CDM + tag) if (e.text or "").strip()]

    def res(tag):
        return sorted({e.get(RDF + "resource") for e in root.iter(CDM + tag) if e.get(RDF + "resource")})

    kinds = {}  # date -> the columns its types send it to
    for d in root.findall(RDF + "Description"):
        p, t = d.find(OWL + "annotatedProperty"), d.find(OWL + "annotatedTarget")
        if p is None or p.get(RDF + "resource") != EIF or t is None or not (t.text or "").strip():
            continue
        k = d.find(ANN + "type_of_date")
        code = (k.text or "").strip().strip("{}").split("|")[0] if k is not None else ""
        kinds.setdefault(t.text.strip(), set()).add(DATE_COLUMN.get(code, "entry_into_force"))
    out = {c: None for c in COLS if c not in ("alias", "acronym")}
    for day in sorted(set(lit("resource_legal_date_entry-into-force"))):
        for col in sorted(kinds.get(day) or {"entry_into_force"}):  # untyped: the property names it entry into force
            out[col] = (out[col] or []) + [day]
    flag = (lit("resource_legal_in-force") or [""])[0].lower()
    elis = sorted(set(lit("resource_legal_eli")))
    out.update(authors=[u.rsplit("/", 1)[-1] for u in res("work_created_by_agent")] or None,
               in_force={"true": True, "false": False}.get(flag),
               eli=elis[0] if len(elis) == 1 else None,
               procedures=sorted({p for p in map(procedure_number, res("work_part_of_dossier")) if p}) or None)
    return out


def export_metadata(corpus_path: Path, uuid: str, celex: Optional[str] = None) -> dict:
    """The importer's call: rdf_facts for the folder (celex kept for the signature callers use)."""
    return rdf_facts(corpus_path, uuid)


def folder_of_celex() -> dict:
    """{CELEX: folder} for the export folders with text (leg_2026-10_folders.csv, one CELEX per folder)."""
    with (TABLES / "leg_2026-10_folders.csv").open(encoding="utf-8-sig") as fh:
        return {r["celex"]: r["folder"] for r in csv.DictReader(fh) if r["celex"] and r["has_text"] == "yes"}


def aliases() -> dict:
    """{CELEX: (alias, acronym)} from Brubru's curated aliases.csv."""
    with (TABLES / "aliases.csv").open(encoding="utf-8-sig") as fh:
        return {r["celex"]: ((r.get("alias") or "").strip() or None, (r.get("acronym") or "").strip() or None)
                for r in csv.DictReader(fh)}
