"""The Publications Office's metadata for one law, as eu_laws stores it (migrations 301, 302). No database imports.

One reading for every writer of the columns: fill_eu_laws_export_metadata.py (the backfill), import_corpus_update.py
(later exports) and, for laws the export does not hold, Cellar through cellar_facts. Fields:
  - authors: work_created_by_agent, the corporate-body codes (COM, CONSIL, EP, a DG...);
  - in_force: resource_legal_in-force; None when the metadata carries no flag (not false);
  - eli: resource_legal_eli, the one the metadata states on the work (one per folder or none). The table builder's
    regex stopped at "(" and cut 701 ELIs short (32014D0026 is .../26(1)/oj);
  - entry_into_force / application_dates / effect_dates: resource_legal_date_entry-into-force, split by the type each
    date carries (fd_335: EV, MA, MA/PART, MA/PROV, APPLICATION, PE, PE/PART); an untyped date or another code (V,
    DATPUB, DATNOT, ECHLET, P, AU+TARD: 19 dates in the export, 11 in eu_laws) stays an entry-into-force date. The
    placeholders 1001-01-01 and 1002-02-02 (260 entries on 235 export folders) are not dates and are dropped;
  - procedures: links to resource/procedure/YYYY_N[A-Z], as YYYY/NNNN[A-Z] (the OEIL reference without its type).
alias and acronym come from Brubru's curated aliases.csv only.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "backend/data/leg_2026-10_table"
COLS = ("alias", "acronym", "authors", "in_force", "eli", "entry_into_force", "application_dates", "effect_dates",
        "procedures")
DATE_COLS = ("entry_into_force", "application_dates", "effect_dates")
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CDM = "{http://publications.europa.eu/ontology/cdm#}"
OWL = "{http://www.w3.org/2002/07/owl#}"
ANN = "{http://publications.europa.eu/ontology/annotation#}"
EIF = "http://publications.europa.eu/ontology/cdm#resource_legal_date_entry-into-force"
DATE_COLUMN = {"EV": "entry_into_force", "MA": "application_dates", "MA/PART": "application_dates",
               "MA/PROV": "application_dates", "APPLICATION": "application_dates", "PE": "effect_dates",
               "PE/PART": "effect_dates"}
PROCEDURE = re.compile(r"/resource/procedure/(\d{4})_0*(\d{1,4})([A-Z]?)$")
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"


def procedure_number(uri: str) -> Optional[str]:
    """.../resource/procedure/2012_11 -> 2012/0011, .../2011_901A -> 2011/0901A; internal_proc, pegase -> None."""
    m = PROCEDURE.search(uri or "")
    return f"{m[1]}/{int(m[2]):04d}{m[3]}" if m else None


def type_code(text: Optional[str]) -> str:
    """'{EV|http://.../fd_335/EV}' -> 'EV'."""
    return (text or "").strip().strip("{}").split("|")[0]


def place_dates(pairs) -> dict:
    """{column: sorted dates} from (date, type code) pairs; a date with two types sits in both; placeholders dropped."""
    out = {c: set() for c in DATE_COLS}
    for day, code in pairs:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day or "") or int(day[:4]) < 1900:
            continue
        out[DATE_COLUMN.get(code, "entry_into_force")].add(day)
    return {c: sorted(v) or None for c, v in out.items()}


def rdf_facts(corpus_path: Path, folder: str) -> dict:
    """Every metadata column but alias and acronym, as one folder's RDF states it; None where it states nothing."""
    root = ET.parse(Path(corpus_path) / folder / "tree_non_inferred.rdf").getroot()

    def lit(tag):
        return [e.text.strip() for e in root.iter(CDM + tag) if (e.text or "").strip()]

    def res(tag):
        return sorted({e.get(RDF + "resource") for e in root.iter(CDM + tag) if e.get(RDF + "resource")})

    typed = {}
    for d in root.findall(RDF + "Description"):
        p, t = d.find(OWL + "annotatedProperty"), d.find(OWL + "annotatedTarget")
        if p is None or p.get(RDF + "resource") != EIF or t is None or not (t.text or "").strip():
            continue
        k = d.find(ANN + "type_of_date")
        typed.setdefault(t.text.strip(), set()).add(type_code(k.text if k is not None else ""))
    pairs = [(day, code) for day in set(lit("resource_legal_date_entry-into-force")) for code in (typed.get(day) or {""})]
    flag = (lit("resource_legal_in-force") or [""])[0].lower()
    elis = sorted(set(lit("resource_legal_eli")))
    out = place_dates(pairs)
    out.update(authors=[u.rsplit("/", 1)[-1] for u in res("work_created_by_agent")] or None,
               in_force={"true": True, "false": False}.get(flag),
               eli=elis[0] if len(elis) == 1 else None,
               procedures=sorted({p for p in map(procedure_number, res("work_part_of_dossier")) if p}) or None)
    return out


def merged(column: str, stored, read):
    """What a later export's read of one column stores over the stored value (audit of 16 Oct 2026): the export states
    less than the backfill gathered, so a read never blanks a value, procedures are merged, and a set in_force is left
    to refresh_eu_laws_in_force.py, its daily owner. Returns the stored value when nothing should change."""
    if column == "in_force" and stored is not None:
        return stored
    if column == "procedures":
        return sorted(set(stored or []) | set(read or [])) or None
    return stored if read is None else read


def export_metadata(corpus_path: Path, uuid: str, celex: Optional[str] = None) -> dict:
    """The importer's call: rdf_facts for the folder (celex kept for the signature callers use)."""
    return rdf_facts(corpus_path, uuid)


def folder_of_celex() -> dict:
    """{CELEX: folder} for every export folder (one CELEX each); a folder with text wins over one without. The 11
    without text that eu_laws holds (Directive 2001/83/EC, Regulation 726/2004...) carry full metadata too."""
    out = {}
    with (TABLES / "leg_2026-10_folders.csv").open(encoding="utf-8-sig") as fh:
        for r in sorted(csv.DictReader(fh), key=lambda r: r["has_text"] == "yes"):
            if r["celex"]:
                out[r["celex"]] = r["folder"]
    return out


def aliases() -> dict:
    """{CELEX: (alias, acronym)} from Brubru's curated aliases.csv."""
    with (TABLES / "aliases.csv").open(encoding="utf-8-sig") as fh:
        return {r["celex"]: ((r.get("alias") or "").strip() or None, (r.get("acronym") or "").strip() or None)
                for r in csv.DictReader(fh)}


# Cellar, for laws the export does not hold and for the facts that change after it (in force, procedures). One small
# query per group, so a law with several authors, dates and dossiers does not multiply the rows of the others; each
# call carries a control law and counts only if the control comes back as expected.
CONTROL = "32016R0679"  # GDPR: procedure 2012/0011, in force, created by CONSIL and EP, entered into force 2016-05-24
GROUPS = {
    "dossier": ("?c ?s ?f", "OPTIONAL { ?d cdm:dossier_contains_work ?w . ?d owl:sameAs ?s } "
                            "OPTIONAL { ?w cdm:resource_legal_in-force ?f }"),
    "work": ("?c ?a ?e", "OPTIONAL { ?w cdm:work_created_by_agent ?a } OPTIONAL { ?w cdm:resource_legal_eli ?e }"),
    "dates": ("?c ?d ?t", "?w cdm:resource_legal_date_entry-into-force ?d . OPTIONAL { ?ax owl:annotatedSource ?w ; "
                          "owl:annotatedProperty cdm:resource_legal_date_entry-into-force ; owl:annotatedTarget ?d ; "
                          "ann:type_of_date ?t }"),
}


class CellarDown(RuntimeError):
    """Cellar failed the control on several calls in a row, or the time budget ran out: stop, do not split further."""


class Budget:
    """Stops a run cleanly: after FAILS_IN_A_ROW failed calls (the endpoint is down or walled, so splitting batches
    would only multiply the calls) or once `seconds` are spent (the caller's timeout must never cut the run blind)."""
    FAILS_IN_A_ROW = 4

    def __init__(self, seconds: Optional[float] = None):
        self.deadline = time.monotonic() + seconds if seconds else None
        self.failed = 0

    def check(self):
        if self.deadline and time.monotonic() > self.deadline:
            raise CellarDown("time budget spent")

    def result(self, ok: bool):
        self.failed = 0 if ok else self.failed + 1
        if self.failed >= self.FAILS_IN_A_ROW:
            raise CellarDown(f"{self.failed} calls in a row failed the control law")


def _parse(group: str, rows: list) -> dict:
    got = {}
    for b in rows:
        g = got.setdefault(b["c"]["value"], {"procedures": set(), "flags": set(), "authors": set(), "elis": set(), "pairs": set()})
        v = lambda k: b.get(k, {}).get("value")
        if group == "dossier":
            if procedure_number(v("s") or ""):
                g["procedures"].add(procedure_number(v("s")))
            if v("f"):
                g["flags"].add(v("f"))
        elif group == "work":
            if v("a"):
                g["authors"].add(v("a").rsplit("/", 1)[-1])
            if v("e"):
                g["elis"].add(v("e"))
        elif v("d"):
            g["pairs"].add((v("d")[:10], type_code(v("t"))))
    return got


def _control_ok(group: str, g: Optional[dict]) -> bool:
    if not g:
        return False
    if group == "dossier":
        return "2012/0011" in g["procedures"] and g["flags"] == {"1"}
    if group == "work":
        return {"CONSIL", "EP"} <= g["authors"] and "http://data.europa.eu/eli/reg/2016/679/oj" in g["elis"]
    return ("2016-05-24", "EV") in g["pairs"]


def _ask(group: str, batch: list, budget: Budget) -> dict:
    budget.check()
    sel, pattern = GROUPS[group]
    values = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in batch + [CONTROL])
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> PREFIX owl: <http://www.w3.org/2002/07/owl#> "
         "PREFIX ann: <http://publications.europa.eu/ontology/annotation#> "
         f"SELECT {sel} WHERE {{ VALUES ?c {{ {values} }} ?w cdm:resource_legal_id_celex ?c . {pattern} }}")
    try:
        req = urllib.request.Request(SPARQL + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}),
                                     headers={"Accept": "application/sparql-results+json"})
        got = _parse(group, json.load(urllib.request.urlopen(req, timeout=60))["results"]["bindings"])
    except Exception:
        got = {}
    ok = _control_ok(group, got.get(CONTROL))
    budget.result(ok)
    if not ok:
        return {}
    # "seen": Cellar returned the law at all (an unknown CELEX gives no row); its facts may still be empty
    return {c: {**got[c], "seen": True} if c in got else {"procedures": set(), "flags": set(), "authors": set(),
                                                          "elis": set(), "pairs": set(), "seen": False} for c in batch}


def _ask_or_split(group: str, batch: list, budget: Budget) -> dict:
    """Retry once, then split in halves: Cellar times out on some batches of 80 that answer at once in tens
    (16 Oct 2026). A law that fails alone is left out: unknown, never "none". Raises CellarDown via the budget."""
    for attempt in range(2):
        got = _ask(group, batch, budget)
        if got:
            return got
        time.sleep(3 * (attempt + 1))
    if len(batch) == 1:
        return {}
    mid = len(batch) // 2
    return {**_ask_or_split(group, batch[:mid], budget), **_ask_or_split(group, batch[mid:], budget)}


def cellar_facts(celexes: list, groups=("dossier",), cache: Optional[Path] = None, batch: int = 80, log=print,
                 budget: Optional[Budget] = None) -> dict:
    """{CELEX: {column: value}} from Cellar for the asked groups ('dossier': procedures, in_force; 'work': authors,
    eli; 'dates': the three date columns). With a cache file, only laws missing from it are asked; a law Cellar does
    not answer for is absent (unknown)."""
    store = json.loads(cache.read_text()) if cache and cache.exists() else {}
    budget = budget or Budget()
    for group in groups:
        todo = [c for c in celexes if group not in store.get(c, {})]
        for i in range(0, len(todo), batch):
            for c, g in _ask_or_split(group, todo[i:i + batch], budget).items():
                if group == "dossier":
                    flag = next(iter(g["flags"])) if len(g["flags"]) == 1 else None
                    part = {"procedures": sorted(g["procedures"]) or None, "in_force": {"1": True, "0": False}.get(flag),
                            "seen": g["seen"]}
                elif group == "work":
                    part = {"authors": sorted(g["authors"]) or None, "eli": next(iter(g["elis"])) if len(g["elis"]) == 1 else None}
                else:
                    part = place_dates(g["pairs"])
                store.setdefault(c, {})[group] = part
            if cache and ((i // batch) % 25 == 24 or i + batch >= len(todo)):
                cache.write_text(json.dumps(store))
                log(f"[INFO]   Cellar {group}: {min(i + batch, len(todo))} of {len(todo)} asked")
    return {c: {k: v for part in store[c].values() for k, v in part.items()}
            for c in celexes if c in store and all(g in store[c] for g in groups)}
