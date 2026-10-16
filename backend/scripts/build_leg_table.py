#!/usr/bin/env python3.12
"""Build the LEG_2026-10 summary tables: one row per OJ publication, ordered by CELEX.

Outputs (CSV UTF-8 with BOM, plus one Excel) in --out:
  leg_2026-10_table.csv     8 columns in Victor's order, then extras (base_celex, date, in_force, eli, ...)
  leg_2026-10_eurovoc.csv   one row per (act, EuroVoc concept): label, microthesaurus, domain
  leg_2026-10_table.xlsx    Read me (method check), Table, EuroVoc, Statistics (live formulas)
  aliases.csv               INPUT: celex, alias, acronym, source. Edit it and rebuild; seeded once
                            from legislation_acronyms.json (entries with a full_name only).

Every value is read from the dump itself (`tree_non_inferred.rdf` of each UUID folder, plus the
Formex title for the few acts whose RDF has no English title). No LLM, no network except the
EuroVoc labels (Cellar SPARQL, cached in --out). NULL (empty) when unknown: an alias or acronym is
never derived, only taken from aliases.csv.

After a build, run `scripts/recalc.py` of the xlsx skill (LibreOffice) so the formulas carry values; it
re-saves the workbook, which is why docProps shows LibreOffice.

Usage (from the repo root):
    python3.12 backend/scripts/build_leg_table.py [--dump docs/LEG_2026-10] [--out backend/data/leg_2026-10_table]
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT)

# the labels, the CELEX shape and the corrigendum rule live in one place, read by the laws API too
from backend.services.celex_types import CELEX_RE, CORR_RE, TYPE_LABELS, base_of  # noqa: E402,F401

RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CDM = "{http://publications.europa.eu/ontology/cdm#}"
WRAPPERS = (".doc.xml", ".toc.xml", ".doc.fmx.xml", ".toc.fmx.xml")
CELLAR = "https://publications.europa.eu/webapi/rdf/sparql"

ELI_PREFIX = {"R": ("reg", "reg_impl", "reg_del"), "L": ("dir", "dir_impl", "dir_del"),
              "D": ("dec", "dec_impl", "dec_del")}
SUFFIX_RE = re.compile(r"(?:\(\d{2}\))*(?:R\(\d{2}\))*$")  # used by pick_eli only

TABLE_HEADERS = ["CELEX", "Sector", "Year", "Type of document", "Number of document", "Title of document",
                 "Alias of document", "Acronym of the alias"]
EXTRA_HEADERS = ["base_celex", "date_document", "in_force", "eli", "author", "eurovoc_count",
                 "eurovoc_domains", "title_source", "kind_sheet", "eurovoc_microthesauri", "eurovoc_concepts", "has_text", "title_other_language"]
EV_HEADERS = ["celex", "concept_id", "concept_uri", "label_en", "microthesaurus", "domain"]


def parse_folder(args):
    dump, folder = args
    base = pathlib.Path(dump) / folder
    raw = (base / "tree_non_inferred.rdf").read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(raw.encode("utf-8"))

    def lit(tag):
        return [e.text.strip() for e in root.iter(CDM + tag) if e.text and e.text.strip()]

    def res(tag):
        return sorted({e.get(RDF + "resource") for e in root.iter(CDM + tag) if e.get(RDF + "resource")})

    title = None
    others = {}
    for d in root.findall(RDF + "Description"):
        lang = d.find(CDM + "expression_uses_language")
        t = d.find(CDM + "expression_title")
        if lang is None or t is None or not (t.text and t.text.strip()):
            continue
        code = lang.get(RDF + "resource", "").rsplit("/", 1)[-1]
        if code == "ENG":
            title = " ".join(t.text.split())
        else:
            others.setdefault(code, " ".join(t.text.split()))
    title_other = ""
    if not title and others:  # deterministic: FRA, SPA, ITA, NLD, DEU first, then alphabetical
        for code in ("FRA", "SPA", "ITA", "NLD", "DEU") + tuple(sorted(others)):
            if code in others:
                title_other = f"{code}: {others[code]}"
                break
    source = "rdf" if title else ""
    title_formex = ""
    has_text = (base / "fmx4").is_dir()
    if not title and has_text:  # last resort when neither the RDF nor Cellar has it: the TITLE of the first Formex part that has one
        fmx = base / "fmx4"
        for p in sorted(fmx.glob("*.xml")):
            if p.name.endswith(WRAPPERS):
                continue
            m = re.search(r"<TITLE>(.*?)</TITLE>", p.read_text(encoding="utf-8", errors="replace"), re.S)
            if m:
                title_formex = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split())
                break
    celexes = lit("resource_legal_id_celex")
    return {
        "folder": folder, "n_celex_literals": len(set(celexes)), "celex": celexes[0] if celexes else None,
        "sector": (lit("resource_legal_id_sector") or [None])[0],
        "year": (lit("resource_legal_year") or [None])[0],
        "type": (lit("resource_legal_type") or [None])[0],
        "number": (lit("resource_legal_number_natural_celex") or [None])[0],
        "date": (lit("work_date_document") or [""])[0],
        "in_force": (lit("resource_legal_in-force") or [""])[0],
        "author": "|".join(u.rsplit("/", 1)[-1] for u in res("work_created_by_agent")),
        "eurovoc": [u.rsplit("/", 1)[-1] for u in res("work_is_about_concept_eurovoc")],
        "eli_all": sorted(set(re.findall(r"http://data\.europa\.eu/eli/[A-Za-z0-9_/\-.]+", raw))),
        "title": title or "", "title_source": source, "title_formex": title_formex, "has_text": has_text, "title_other": title_other,
    }


def sparql(query):
    for attempt in range(5):
        try:
            req = urllib.request.Request(CELLAR + "?" + urllib.parse.urlencode(
                {"query": query, "format": "application/sparql-results+json"}),
                headers={"Accept": "application/sparql-results+json"})
            return json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Cellar SPARQL failed 5 times")


def cellar_titles(celexes, cache):
    """English title of each CELEX from Cellar (expression whose language is ENG); '' unless exactly one."""
    got = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [c for c in celexes if c not in got]
    for i in range(0, len(todo), 20):
        vals = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in todo[i:i + 20])
        found = defaultdict(set)
        for b in sparql("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?c ?t WHERE { VALUES ?c { " + vals +
                        " } ?w cdm:resource_legal_id_celex ?c . ?e cdm:expression_belongs_to_work ?w ; "
                        "cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ; "
                        "cdm:expression_title ?t }"):
            found[b["c"]["value"]].add(" ".join(b["t"]["value"].split()))
        for c in todo[i:i + 20]:
            got[c] = sorted(found.get(c, []))
    cache.write_text(json.dumps(got))
    return {c: v[0] for c, v in got.items() if len(v) == 1}


def eurovoc_meta(ids, cache):
    """English label, microthesauri and domains of each concept id, from EuroVoc on Cellar."""
    meta = json.loads(cache.read_text()) if cache.exists() else {"concept": {}, "mts": {}, "domains": {}}
    todo = [i for i in ids if i not in meta["concept"] and i not in meta.get("absent", [])]
    P = ("PREFIX skos: <http://www.w3.org/2004/02/skos/core#> PREFIX xl: <http://www.w3.org/2008/05/skos-xl#> "
         "PREFIX et: <http://eurovoc.europa.eu/schema#> ")
    if not meta["domains"]:
        meta["domains"] = {b["l"]["value"][:2]: b["l"]["value"][3:] for b in sparql(
            P + 'SELECT ?l WHERE { ?d a et:Domain ; xl:prefLabel/xl:literalForm ?l FILTER(lang(?l)="en") }')}
    mts = defaultdict(set, {k: set(v) for k, v in meta["mts"].items()})
    for i in range(0, len(todo), 70):
        vals = " ".join(f"<http://eurovoc.europa.eu/{x}>" for x in todo[i:i + 70])
        for b in sparql(P + f'SELECT ?c ?l WHERE {{ VALUES ?c {{ {vals} }} ?c skos:prefLabel ?l '
                            f'FILTER(lang(?l)="en") }}'):
            meta["concept"][b["c"]["value"].rsplit("/", 1)[-1]] = b["l"]["value"]
        for b in sparql(P + f'SELECT ?c ?ml WHERE {{ VALUES ?c {{ {vals} }} ?c skos:inScheme ?m . '
                            f'?m a et:MicroThesaurus ; xl:prefLabel/xl:literalForm ?ml FILTER(lang(?ml)="en") }}'):
            mts[b["c"]["value"].rsplit("/", 1)[-1]].add(b["ml"]["value"])
    meta["absent"] = sorted(set(meta.get("absent", [])) | {i for i in todo if i not in meta["concept"]})
    meta["mts"] = {k: sorted(v) for k, v in mts.items()}
    cache.write_text(json.dumps(meta))
    return meta


def seed_aliases(path, celexes):
    """One-off seed of the INPUT file from the curated entries (those with a full_name)."""
    data = json.loads((pathlib.Path(_REPO_ROOT) / "backend/knowledge_base/institutions/legislation_acronyms.json")
                      .read_text())["acronyms"]
    by_celex = defaultdict(list)
    for key, v in data.items():
        if v.get("full_name") and v.get("celex") in celexes:
            by_celex[v["celex"]].append((key, v["full_name"]))
    rows = []
    for celex, items in sorted(by_celex.items()):
        alias = items[0][1]
        keys = sorted((k for k, _ in items if k.lower() != alias.lower()), key=len)
        rows.append((celex, alias, keys[0] if keys else "", "legislation_acronyms.json (curated full_name)"))
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["celex", "alias", "acronym", "source"])
        w.writerows(rows)
    return len(rows)


def pick_eli(rec, celex):
    """The ELI that belongs to THIS publication, or '' when none or several qualify.

    Plain CELEX: eli/<type>/<year>/<number>[/oj] with the act's own year and number (the type token
    must suit R/L/D). `R(nn)` corrigendum: the .../corrigendum/<date>/oj URI of that act. `(nn)`
    publications are left empty: the only ELI in the file is the base act's."""
    year, num = str(int(rec["year"])), str(int(rec["number"]))
    base = SUFFIX_RE.sub("", celex)
    suffix = celex[len(base):]
    hits = []
    for e in rec["eli_all"]:
        m = re.fullmatch(r"http://data\.europa\.eu/eli/([a-z_]+)/(\d{4})/(\d+)(?:/(.*))?", e)
        if not m or m[2] != year or m[3] != num:
            continue
        tok, rest = m[1], m[4] or ""
        if not suffix:
            if rest in ("", "oj") and (rec["type"] not in ELI_PREFIX or tok in ELI_PREFIX[rec["type"]]):
                hits.append(e)
        elif re.fullmatch(r"R\(\d{2}\)", suffix):
            if rest.startswith("corrigendum/"):
                hits.append(e)
    return hits[0] if len(hits) == 1 else ""


ISSUER_HEADER = "issuer_in_title"
# One sheet per kind of act (instrument + who adopted it). Names are <= 31 characters (Excel limit).
KIND_SHEETS = [
    ("Regulations", "Title starts with 'Regulation' and the title does not say the Council or the Commission adopted it (Parliament and Council, a few Parliament-only and European Central Bank acts)."),
    ("Commission Impl. Regulations", "Commission Implementing Regulations."),
    ("Commission Regulations", "Commission Regulations, plus older acts titled 'Regulation ... of the Commission'."),
    ("Commission Deleg. Regulations", "Commission Delegated Regulations."),
    ("Council Regulations", "Council Regulations, plus older acts titled 'Regulation ... of the Council'."),
    ("Council Impl. Regulations", "Council Implementing Regulations."),
    ("Directives", "Title starts with 'Directive' and the title does not say the Council or the Commission adopted it (all are Parliament and Council)."),
    ("Council+Commission Directives", "Council Directives, Commission Directives, Commission Delegated and Implementing Directives."),
    ("Council Decisions", "Council Decisions and European Council Decisions, including CFSP decisions."),
    ("Commission Decisions", "Commission Decisions."),
    ("Commission Impl. Decisions", "Commission Implementing Decisions."),
    ("Council Impl. Decisions", "Council Implementing Decisions."),
    ("Parliament+Council Decisions", "Decisions adopted by the European Parliament and the Council (or by Parliament alone)."),
    ("Commission Deleg. Decisions", "Commission Delegated Decisions."),
    ("Other decisions and regulations", "CELEX types M (non-opposition to a notified concentration, merger control), J (joint ventures) and K, which together are about nine in ten rows here; decisions of agencies and bodies (political parties authority, High Representative, ECB, administrative commissions, Political and Security Committee); untitled acts of types R, L and D; and the few regulation titles no rule recognised."),
    ("Recommendations", "CELEX type H: Council and Commission Recommendations."),
    ("Opinions", "CELEX type A: Council and Commission Opinions."),
    ("ECB guidelines", "CELEX type O."),
    ("CFSP and justice acts (E,F)", "CELEX types E and F: pre-Lisbon common positions, joint actions, framework decisions."),
    ("Institutional arrangements (Q)", "CELEX type Q: rules of procedure and internal rules of institutions and bodies."),
    ("OJ C documents (Y)", "CELEX type Y: other documents published in the OJ C series (interinstitutional agreements, ECB and ESRB decisions)."),
    ("Budget (B)", "CELEX type B: discharge decisions and amending budgets."),
    ("Council resolutions (G)", "CELEX type G."),
    ("Other OJ L documents (X,S)", "CELEX type X (other documents published in OJ L: agreements, addenda) and S (ECSC decision of general interest)."),
    ("Corrigenda", "Every corrigendum, whatever the type of the act it corrects (title starts 'Corrigendum' in any case, or the CELEX ends in R(NN))."),
]
KIND_NAMES = [k for k, _ in KIND_SHEETS]
assert all(len(k) <= 31 for k in KIND_NAMES) and len(set(KIND_NAMES)) == len(KIND_NAMES)


ISSUER_RE = re.compile(r"\bof the (european parliament and (?:of )?the council|european parliament|european central bank|council|commission)\b", re.I)


def issuer_of(title):
    """Who the title says adopted the act: the issuer named right after the act's number
    ("Regulation (EU) 2016/679 of the European Parliament and of the Council"). An issuer that comes
    after another "of" ("Decision No A2 of 12 June 2009 ... Regulation ... of the European Parliament
    and of the Council") is a cited act, not the author."""
    t = title[:250]
    m = ISSUER_RE.search(t)
    if not m or re.search(r"\bof\b", t[:m.start()], re.I):
        return "not stated"
    g = m.group(1).lower()
    if g.startswith("european parliament and"):
        return "European Parliament and Council"
    return {"european parliament": "European Parliament", "european central bank": "European Central Bank",
            "council": "Council", "commission": "Commission"}[g]


LETTER_SHEET = {"H": "Recommendations", "A": "Opinions", "O": "ECB guidelines", "E": "CFSP and justice acts (E,F)",
                "F": "CFSP and justice acts (E,F)", "Q": "Institutional arrangements (Q)", "Y": "OJ C documents (Y)",
                "B": "Budget (B)", "G": "Council resolutions (G)", "X": "Other OJ L documents (X,S)",
                "S": "Other OJ L documents (X,S)"}


def kind_of(letter, title, celex=""):
    """The ONE sheet an act belongs to, from its CELEX descriptor and the start of its title.
    A corrigendum is recognised by its title ("Corrigendum to ...", any case) or by the R(NN) suffix
    of its CELEX, because many corrigenda have no English title. For types other than R, L and D the
    CELEX letter decides, title or not."""
    if title.lower().startswith("corrigendum") or CORR_RE.search(celex):
        return "Corrigenda"
    if letter in LETTER_SHEET:
        return LETTER_SHEET[letter]
    if letter not in ("R", "L", "D") or not title:
        return "Other decisions and regulations"
    t = re.sub(r"^[\d/]+[A-Za-z,/ .\-]*?:\s*", "", title)  # old tags: "2004/741/EC:", "74/296/Euratom:"
    low, iss = t.lower(), issuer_of(t)
    if letter == "R":
        if low.startswith("commission implementing regulation"):
            return "Commission Impl. Regulations"
        if low.startswith("commission delegated regulation"):
            return "Commission Deleg. Regulations"
        if low.startswith("implementing regulation"):  # "Implementing Regulation Commission (EU) ..." is a Commission act
            return "Commission Impl. Regulations" if "commission" in low[:45] else "Council Impl. Regulations"
        if low.startswith("council implementing regulation"):
            return "Council Impl. Regulations"
        if low.startswith("european central bank") or (low.startswith("regulation") and iss not in ("Council", "Commission")):
            return "Regulations"
        if low.startswith("commission regulation") or (low.startswith("regulation") and iss == "Commission"):
            return "Commission Regulations"
        if low.startswith("council regulation") or (low.startswith("regulation") and iss == "Council"):
            return "Council Regulations"
        return "Other decisions and regulations"
    if letter == "L":
        if low.startswith("directive") and iss not in ("Council", "Commission"):
            return "Directives"
        return "Council+Commission Directives"
    if low.startswith("commission implementing decision"):
        return "Commission Impl. Decisions"
    if low.startswith("commission delegated decision"):
        return "Commission Deleg. Decisions"
    if low.startswith("commission decision") or (low.startswith("decision") and iss == "Commission"):
        return "Commission Decisions"
    if low.startswith("council implementing decision"):
        return "Council Impl. Decisions"
    if low.startswith("council decision") or low.startswith("european council decision") or (low.startswith("decision") and iss == "Council"):
        return "Council Decisions"
    if low.startswith("european parliament decision") or (low.startswith("decision") and iss in ("European Parliament and Council", "European Parliament")):
        return "Parliament+Council Decisions"
    return "Other decisions and regulations"


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, table, ev_rows, qa, domains, built_on, kinds, meta):
    """Read me (method check), Table, EuroVoc, Statistics. Statistics are live formulas."""
    import xlsxwriter
    wb = xlsxwriter.Workbook(str(path), {"constant_memory": True})
    wb.formats[0].set_font_name("Arial")
    wb.formats[0].set_font_size(10)
    f = lambda **k: wb.add_format({"font_name": "Arial", "font_size": 10, **k})
    head, bold, wrap, num, title_f = f(bold=True, bg_color="#1F3864", font_color="#FFFFFF"), f(bold=True), f(text_wrap=True, valign="top"), f(num_format="0"), f(bold=True, font_size=14)
    n, nev = len(table), len(ev_rows)
    qs = lambda name: "'" + name.replace("'", "''") + "'"
    rng = lambda sheet, col, last: f"{qs(sheet)}!${col}$2:${col}${last}"
    T = lambda col: rng("Table", col, n + 1)
    E = lambda col: rng("EuroVoc", col, nev + 1)

    # ---- Read me (written first so it is the first tab); formulas reference the later sheets
    rm = wb.add_worksheet("Read me")
    st = wb.add_worksheet("Statistics")
    tp = wb.add_worksheet("Topics")
    tb = wb.add_worksheet("Table")
    kind_ws = {name: wb.add_worksheet(name) for name in KIND_NAMES}
    ev = wb.add_worksheet("EuroVoc")
    rm.set_column(0, 0, 44); rm.set_column(1, 1, 22); rm.set_column(2, 2, 22); rm.set_column(3, 3, 12); rm.set_column(4, 4, 90)

    py_type = Counter(t[3] for t in table)
    py_sector = Counter(t[1] for t in table)
    rows = [
        ("LEG_2026-10: summary table by CELEX and EuroVoc", None, None, None, None, "title"),
        (f"Built on {built_on} by backend/scripts/build_leg_table.py. Source: docs/LEG_2026-10, the Publications Office bulk export of 11 Oct 2026 (legislation in force, Formex 4 + metadata). One row = one OJ publication (one UUID folder, one CELEX). has_text = yes when the folder holds Formex text; the others (older acts, corrigenda) are described by metadata only.", None, None, None, None, "text"),
        ("", None, None, None, None, "text"),
        ("Method check", "Formula", "Second count", "Check", "How the second count was made. Only 'Rows in Table' and 'Rows with text' are read from disk; the others check that the sheets agree with each other. An independent audit (re-derived from the raw files) was run separately.", "header"),
        ("Rows in Table", f"=COUNTA({T('A')})", qa["folders_in_export"], "chk", "Folders of the export, counted on disk before parsing (each holds a metadata file)", "row"),
        ("Rows with text (has_text = yes)", f"=COUNTIF({T('T')},\"yes\")", qa["folders_with_text"], "chk", "Folders holding an fmx4 directory (Formex text), counted on disk", "row"),
        ("Sector 3 rows", f"=COUNTIF({T('B')},3)", py_sector.get(3, 0), "chk", "Counted from the table rows in the builder", "row"),
        ("Regulations (R)", f"=COUNTIF({T('D')},\"R = Regulation\")", py_type.get("R = Regulation", 0), "chk", "Counted from the table rows in the builder", "row"),
        ("Directives (L)", f"=COUNTIF({T('D')},\"L = Directive\")", py_type.get("L = Directive", 0), "chk", "Counted from the table rows in the builder", "row"),
        ("EuroVoc pairs in EuroVoc sheet", f"=COUNTA({E('A')})", f"=SUM({T('N')})", "chk", "Sum of eurovoc_count in Table (two sheets built from the same RDF; they must agree)", "row"),
        ("Rows with an alias", f"=COUNTIF({T('G')},\"?*\")", qa["rows_with_alias"], "chk", "Rows of aliases.csv whose CELEX is in the dump", "row"),
        ("Rows with an ELI", f"=COUNTIF({T('L')},\"?*\")", qa["rows_with_eli"], "chk", "ELI URI matching the act's own type, year and number, counted while building", "row"),
        ("Rows with no title", f"=COUNTBLANK({T('F')})", qa["rows_without_title"], "chk", "Counted while building", "row"),
        ("", None, None, None, None, "text"),
        ("Sheets (click a name to jump)", "Rows in the sheet", "Rows of that kind in Table", "Check", "What it holds. Every act is in exactly one of these sheets; the second count is a different formula, over the kind_sheet column of Table.", "header"),
        *[(name, f"=COUNTA({rng(name, 'A', len(kinds[name]) + 1)})", f"=COUNTIF({T('Q')},\"{name}\")", "sheetrow", desc, "sheetrow") for name, desc in KIND_SHEETS],
        ("All kind sheets together", None, None, "sheettotal", f"Must equal the {n:,} rows of Table.", "sheettotal"),
        ("", None, None, None, None, "text"),
        ("How to find laws on a topic (filters are on every header row)", None, None, None, None, "header"),
        ("1. Broad field", "eurovoc_domains", None, None, "EuroVoc has 21 domains, e.g. '12 LAW', '52 ENVIRONMENT', '28 SOCIAL QUESTIONS'. Filter the column with Text Filters > Contains.", "row"),
        ("2. Sub-field", "eurovoc_microthesauri", None, None, "127 microthesauri, e.g. '2841 health', '3236 information technology and data processing'. The Topics sheet lists them with act counts.", "row"),
        ("3. Precise subject", "eurovoc_concepts", None, None, f"The act's EuroVoc concepts as words, e.g. 'digital single market', 'sustainable development', 'public health'. Contains 'digital' finds {qa['topic']['digital']['concepts']:,} acts here.", "row"),
        ("4. Words in the title", "Title of document", None, None, f"Contains 'digital' finds {qa['topic']['digital']['title']:,} acts by title alone. Searching title, eurovoc_concepts and eurovoc_microthesauri together (case-insensitive) finds {qa['topic']['digital']['any']:,} for 'digital', {qa['topic']['health']['any']:,} for 'health' and {qa['topic']['sustainab']['any']:,} for 'sustainab'.", "row"),
        (f"All {qa['distinct_celex']:,} CELEX are distinct (asserted by the builder before writing; a COUNTIF-based distinct count over {n:,} rows would take minutes to recalculate).", None, None, None, None, "text"),
        ("Columns", "Source", None, None, "Definition", "header"),
        ("CELEX", "resource_legal_id_celex", None, None, "Own CELEX of the OJ publication. Sector, Year, Type and Number are read from the CELEX string; the metadata fields agree in all rows but " + str(sum(qa["celex_string_vs_metadata_disagreements"].values())) + " field(s): " + json.dumps(qa["celex_string_vs_metadata_disagreements"]), "row"),
        ("Sector", "resource_legal_id_sector", None, None, "First CELEX character (2 = international agreements, 3 = legal acts, 5 = preparatory documents).", "row"),
        ("Year", "resource_legal_year", None, None, "Year in the CELEX. In the one row where the metadata year differs (a corrigendum) the CELEX year is shown.", "row"),
        ("Type of document", "resource_legal_type", None, None, "Descriptor letter and its meaning in the EUR-Lex table 'Types of documents in EUR-Lex'.", "row"),
        ("Number of document", "resource_legal_number_natural_celex", None, None, "Natural number of the act, without leading zeros (CELEX 32016R0679 gives 679).", "row"),
        ("Title of document", "expression_title (ENG)", None, None, f"Official English title. {qa['title_from_cellar'] + qa['title_from_formex'] + qa['rows_without_title']:,} acts have none in the RDF: {qa['title_from_cellar']} were read from Cellar (title_source = cellar) and {qa['rows_without_title']:,} stay blank (title_source = none), mostly corrigenda issued in one language; their title is in title_other_language.", "row"),
        ("Alias of document / Acronym of the alias", "aliases.csv", None, None, f"Not in the dump. Filled only from aliases.csv ({qa['rows_with_alias']} acts, seeded from the curated full_name entries of legislation_acronyms.json). Empty = unknown, never derived. Add rows to aliases.csv and rebuild.", "row"),
        ("base_celex", "derived from CELEX", None, None, "CELEX without a corrigendum suffix R(NN), so a corrigendum is grouped with its act. A plain (NN) suffix is a different act and is kept; a consolidated text maps to its sector-3 act.", "row"),
        ("title_other_language", "expression_title (not ENG)", None, None, "Only for acts with no English title: the title in the language that exists, prefixed with its code (FRA: ...). If several languages exist, the first of FRA, SPA, ITA, NLD, DEU, then alphabetical. Empty for every act that has an English title.", "row"),
        ("has_text", "folder content", None, None, "yes = the export holds the Formex text of the act; no = metadata only (older acts, merger-control decisions and corrigenda; the scans were not extracted).", "row"),
        ("date_document / in_force", "work_date_document / resource_legal_in-force", None, None, "in_force is 'unknown' when the metadata carries no flag (not the same as false).", "row"),
        ("eli", "ELI URI in the RDF", None, None, "Only the URI whose type, year and number match the act; empty when none or several match.", "row"),
        ("eurovoc_count / eurovoc_domains", "work_is_about_concept_eurovoc", None, None, "Number of EuroVoc concepts of the act and the EuroVoc domains of their microthesauri (code and name). Concept labels and microthesauri: EuroVoc 4.24 on Cellar. Detail in the EuroVoc sheet.", "row"),
        ("author", "work_created_by_agent", None, None, "Authority-table code(s) of the creating body, '|' separated.", "row"),
    ]
    r = 0
    idx_first = idx_last = None
    for lab, a, b, c, d, kind in rows:
        if kind == "title":
            rm.write(r, 0, lab, title_f)
        elif kind == "text":
            rm.merge_range(r, 0, r, 4, lab, wrap) if lab else None
            if lab: rm.set_row(r, 42)
        elif kind == "header":
            for j, v in enumerate((lab, a, b, c, d)):
                rm.write(r, j, v if v is not None else "", head)
        elif kind == "sheetrow":
            idx_first = r if idx_first is None else idx_first
            idx_last = r
            rm.write_url(r, 0, f"internal:{qs(lab)}!A1", string=lab)
            rm.write_formula(r, 1, a, num)
            rm.write_formula(r, 2, b, num)
            rm.write_formula(r, 3, f'=IF(B{r + 1}=C{r + 1},"OK","DIFF")', bold)
            rm.write(r, 4, d, wrap)
        elif kind == "sheettotal":
            rm.write(r, 0, lab, bold)
            rm.write_formula(r, 1, f"=SUM(B{idx_first + 1}:B{idx_last + 1})", num)
            rm.write_formula(r, 2, f"=COUNTA({T('A')})", num)
            rm.write_formula(r, 3, f'=IF(B{r + 1}=C{r + 1},"OK","DIFF")', bold)
            rm.write(r, 4, d, wrap)
        else:
            rm.write(r, 0, lab, wrap)
            if isinstance(a, str) and a.startswith("="):
                rm.write_formula(r, 1, a, num)
            else:
                rm.write(r, 1, a, wrap)
            if c == "chk":
                if isinstance(b, str) and b.startswith("="):
                    rm.write_formula(r, 2, b, num)
                elif b is not None:
                    rm.write(r, 2, b, num)
                rm.write_formula(r, 3, f'=IF(B{r + 1}=C{r + 1},"OK","DIFF")', bold)
            else:
                rm.write(r, 2, b if b is not None else "", wrap)
            rm.write(r, 4, d, wrap)
        r += 1

    # ---- Table
    heads = TABLE_HEADERS + EXTRA_HEADERS
    for j, h in enumerate(heads):
        tb.write(0, j, h, head)
    widths = [16, 7, 7, 34, 11, 110, 34, 14, 16, 12, 10, 44, 14, 13, 40, 12, 30, 60, 90, 10, 70]
    for j, w in enumerate(widths):
        tb.set_column(j, j, w)
    for i, row in enumerate(table, start=1):
        for j, v in enumerate(row):
            if j in (1, 2, 4, 13):
                tb.write_number(i, j, v, num)
            else:
                tb.write_string(i, j, str(v))
    tb.freeze_panes(1, 1)
    tb.autofilter(0, 0, n, len(heads) - 1)

    # ---- One sheet per kind of act: same columns as Table plus who adopted the act, read from the title
    sub_heads = heads + [ISSUER_HEADER]
    for name in KIND_NAMES:
        w_, rows_ = kind_ws[name], kinds[name]
        for j, h in enumerate(sub_heads):
            w_.write(0, j, h, head)
        for j, wd in enumerate(widths + [32]):
            w_.set_column(j, j, wd)
        for i, row in enumerate(rows_, start=1):
            for j, v in enumerate(row):
                if j in (1, 2, 4, 13):
                    w_.write_number(i, j, v, num)
                else:
                    w_.write_string(i, j, str(v))
        w_.freeze_panes(1, 1)
        w_.autofilter(0, 0, max(len(rows_), 1), len(sub_heads) - 1)

    # ---- Topics: every EuroVoc domain and microthesaurus with the number of acts (live COUNTIF over Table)
    tp.set_column(0, 0, 48); tp.set_column(1, 1, 58); tp.set_column(2, 2, 14)
    tp.write(0, 0, "Domain (broad field)", head); tp.write(0, 1, "Microthesaurus (sub-field)", head); tp.write(0, 2, "Acts", head)
    mts_used = sorted({m for v in meta["mts"].values() for m in v})
    r_ = 1
    for code in sorted(domains):
        dom = f"{code} {domains[code]}"
        tp.write(r_, 0, dom, bold)
        tp.write_formula(r_, 2, f'=COUNTIF({T("O")},"*"&A{r_ + 1}&"*")', f(bold=True, num_format="0"))
        r_ += 1
        for m in (x for x in mts_used if x[:2] == code):
            tp.write(r_, 1, m)
            tp.write_formula(r_, 2, f'=COUNTIF({T("R")},"*"&B{r_ + 1}&"*")', num)
            r_ += 1
    tp.freeze_panes(1, 0)
    tp.autofilter(0, 0, r_ - 1, 2)

    # ---- EuroVoc
    for j, h in enumerate(EV_HEADERS):
        ev.write(0, j, h, head)
    for j, w in enumerate([16, 14, 36, 48, 52, 52]):
        ev.set_column(j, j, w)
    for i, row in enumerate(ev_rows, start=1):
        for j, v in enumerate(row):
            ev.write_string(i, j, str(v))
    ev.freeze_panes(1, 1)
    ev.autofilter(0, 0, nev, len(EV_HEADERS) - 1)

    # ---- Statistics (formulas over Table and EuroVoc)
    st.set_column(0, 0, 58); st.set_column(1, 2, 14)
    r = 0
    st.write(r, 0, "Statistics (live formulas over the Table and EuroVoc sheets)", title_f); r += 2

    def block(heading, items, formula, share=True):
        nonlocal r
        st.write(r, 0, heading, head); st.write(r, 1, "Rows", head); st.write(r, 2, "Share", head); r += 1
        first = r
        for lab in items:
            st.write(r, 0, lab)
            st.write_formula(r, 1, formula(lab, r), num)
            if share:
                st.write_formula(r, 2, f"=B{r + 1}/{n}", f(num_format="0.0%"))
            r += 1
        r += 1

    block("By sector", sorted(py_sector), lambda lab, rr: f"=COUNTIF({T('B')},A{rr + 1})")
    block("By type of document", [k for k, _ in py_type.most_common()], lambda lab, rr: f"=COUNTIF({T('D')},A{rr + 1})")
    decades = [(d, d + 9) for d in range(1950, 2030, 10)]
    st.write(r, 0, "By decade of the CELEX year", head); st.write(r, 1, "Rows", head); st.write(r, 2, "Share", head); r += 1
    for lo, hi in decades:
        st.write(r, 0, f"{lo}-{hi}")
        st.write_formula(r, 1, f'=COUNTIFS({T("C")},">={lo}",{T("C")},"<={hi}")', num)
        st.write_formula(r, 2, f"=B{r + 1}/{n}", f(num_format="0.0%")); r += 1
    r += 1
    block("In force (metadata flag)", ["true", "false", "unknown"], lambda lab, rr: f"=COUNTIF({T('K')},A{rr + 1})")
    block("Title source", ["rdf", "cellar", "formex", "none"], lambda lab, rr: f"=COUNTIF({T('P')},A{rr + 1})")
    block("Has text (Formex text in the export)", ["yes", "no"], lambda lab, rr: f"=COUNTIF({T('T')},A{rr + 1})")
    for name in ("Regulations", "Directives"):
        rows_ = kinds[name]
        st.write(r, 0, f"{name} sheet: who the title says adopted the act", head); st.write(r, 1, "Rows", head); st.write(r, 2, "Share", head); r += 1
        for iss in sorted({x[-1] for x in rows_}):
            st.write(r, 0, iss)
            st.write_formula(r, 1, f"=COUNTIF({rng(name, 'V', len(rows_) + 1)},A{r + 1})", num)
            st.write_formula(r, 2, f"=B{r + 1}/{len(rows_)}", f(num_format="0.0%")); r += 1
        r += 1
    st.write(r, 0, "EuroVoc", head); st.write(r, 1, "Value", head); r += 1
    st.write(r, 0, "Acts with at least one EuroVoc concept"); st.write_formula(r, 1, f'=COUNTIF({T("N")},">0")', num); r += 1
    st.write(r, 0, "Act-concept pairs"); st.write_formula(r, 1, f"=COUNTA({E('A')})", num); r += 1
    st.write(r, 0, "Largest number of concepts on one act"); st.write_formula(r, 1, f"=MAX({T('N')})", num); r += 2
    st.write(r, 0, "EuroVoc domain", head); st.write(r, 1, "Acts", head); st.write(r, 2, "Pairs", head); r += 1
    for code in sorted(domains):
        lab = f"{code} {domains[code]}"
        st.write(r, 0, lab)
        st.write_formula(r, 1, f'=COUNTIF({T("O")},"*"&A{r + 1}&"*")', num)
        st.write_formula(r, 2, f'=COUNTIF({E("F")},"*"&A{r + 1}&"*")', num); r += 1
    wb.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dump", default="docs/LEG_2026-10")
    ap.add_argument("--out", default="backend/data/leg_2026-10_table")
    a = ap.parse_args()
    dump = pathlib.Path(a.dump) if pathlib.Path(a.dump).is_absolute() else pathlib.Path(_REPO_ROOT) / a.dump
    out = pathlib.Path(a.out) if pathlib.Path(a.out).is_absolute() else pathlib.Path(_REPO_ROOT) / a.out
    out.mkdir(parents=True, exist_ok=True)

    all_dirs = sorted(p.name for p in dump.iterdir() if p.is_dir())
    folders = [f for f in all_dirs if (dump / f / "tree_non_inferred.rdf").exists()]
    with mp.Pool(8) as pool:
        recs = list(pool.imap_unordered(parse_folder, [(str(dump), f) for f in folders], chunksize=40))
    print(f"{len(recs)} folders parsed")

    # ---- QA before anything is written
    qa = {"folders_in_export": len(all_dirs), "folders_with_metadata": len(folders),
          "folders_with_text": sum(1 for r in recs if r["has_text"]), "folders_metadata_only": sum(1 for r in recs if not r["has_text"]),
          "rows": len(recs),
          "folders_without_exactly_one_distinct_celex": sum(1 for r in recs if r["n_celex_literals"] != 1),
          "distinct_celex": len({r["celex"] for r in recs})}
    assert qa["folders_without_exactly_one_distinct_celex"] == 0 and qa["distinct_celex"] == len(recs), qa
    dis = Counter()
    for r in recs:
        m = CELEX_RE.match(r["celex"])
        assert m, r["celex"]
        for k, x, y in (("sector", m["s"], r["sector"]), ("year", m["y"], r["year"]), ("type", m["t"], r["type"]),
                        ("number", str(int(m["n"])), str(int(r["number"])))):
            if x != y:
                dis[k] += 1
    qa["celex_string_vs_metadata_disagreements"] = dict(dis)

    # ---- aliases (input file)
    alias_path = out / "aliases.csv"
    if not alias_path.exists():
        print("aliases.csv seeded with", seed_aliases(alias_path, {r["celex"] for r in recs}), "rows")
    aliases = {}
    with alias_path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            aliases[row["celex"]] = (row["alias"], row["acronym"])
    celex_set = {r["celex"] for r in recs}
    qa["alias_rows_not_in_dump"] = sorted(c for c in aliases if c not in celex_set)

    # ---- EuroVoc labels
    ids = sorted({e for r in recs for e in r["eurovoc"]})
    meta = eurovoc_meta(ids, out / "eurovoc_4.24_meta.json")
    doms = meta["domains"]
    qa["eurovoc_concepts_used"] = len(ids)
    qa["eurovoc_concepts_without_label"] = sum(1 for i in ids if i not in meta["concept"])

    def mt_domain(i):
        mts = meta["mts"].get(i, [])
        return " | ".join(mts), " | ".join(f"{m[:2]} {doms.get(m[:2], '?')}" for m in dict.fromkeys(mts))

    def sort_key(r):
        m = CELEX_RE.match(r["celex"])
        return (m["s"], int(m["y"]), m["t"], int(m["n"]), r["celex"])

    missing = [r["celex"] for r in recs if not r["title"] and not CORR_RE.search(r["celex"])]  # corrigenda have no English title in Cellar either
    ct = cellar_titles(missing, out / "cellar_titles_cache.json") if missing else {}
    for r in recs:
        if not r["title"]:
            if r["celex"] in ct:
                r["title"], r["title_source"] = ct[r["celex"]], "cellar"
            elif r["title_formex"]:
                r["title"], r["title_source"] = r["title_formex"], "formex"
    recs.sort(key=sort_key)
    table, ev_rows = [], []
    for r in recs:
        m = CELEX_RE.match(r["celex"])  # columns 2-5 follow the CELEX itself; the RDF fields are the cross-check (qa)
        label = TYPE_LABELS.get((m["s"], m["t"]))
        type_cell = f"{m['t']} = {label}" if label else f"{m['t']} = (not in the EUR-Lex table)"
        alias, acro = aliases.get(r["celex"], ("", ""))
        domains = sorted({d for i in r["eurovoc"] for d in (mt_domain(i)[1].split(" | ") if mt_domain(i)[1] else [])})
        table.append([r["celex"], int(m["s"]) if m["s"].isdigit() else m["s"], int(m["y"]), type_cell, int(m["n"]), r["title"], alias, acro,
                      base_of(r["celex"]), r["date"], r["in_force"] or "unknown", pick_eli(r, r["celex"]), r["author"],
                      len(r["eurovoc"]), " | ".join(domains), r["title_source"] or "none", kind_of(m["t"], r["title"], r["celex"]),
                      " | ".join(sorted({x for i in r["eurovoc"] for x in meta["mts"].get(i, [])})),
                      " | ".join(sorted(meta["concept"][i] for i in r["eurovoc"] if i in meta["concept"])),
                      "yes" if r["has_text"] else "no", r["title_other"] if not r["title"] else ""])
        for i in sorted(r["eurovoc"], key=lambda x: (meta["concept"].get(x, "~"), x)):
            mt, dom = mt_domain(i)
            ev_rows.append([r["celex"], i, f"http://eurovoc.europa.eu/{i}", meta["concept"].get(i, ""), mt, dom])
    qa["topic"] = {w: {"concepts": sum(1 for t in table if w in t[18].lower()), "title": sum(1 for t in table if w in t[5].lower()),
                       "any": sum(1 for t in table if w in (t[18] + " " + t[17] + " " + t[5]).lower())} for w in ("digital", "health", "sustainab")}
    qa["rows_without_title"] = sum(1 for t in table if not t[5])
    qa["rows_without_english_title_but_with_another_language"] = sum(1 for t in table if not t[5] and t[20])
    qa["corrigenda_by_title"] = sum(1 for t in table if t[5].lower().startswith("corrigendum"))
    qa["corrigenda_by_celex_suffix"] = sum(1 for t in table if CORR_RE.search(t[0]))
    qa["corrigenda_title_and_suffix_disagree"] = sum(1 for t in table if t[5].lower().startswith("corrigendum") != bool(CORR_RE.search(t[0])) and t[5])
    qa["title_from_cellar"] = sum(1 for t in table if t[15] == "cellar")
    qa["title_from_formex"] = sum(1 for t in table if t[15] == "formex")
    qa["rows_with_alias"] = sum(1 for t in table if t[6])
    qa["rows_with_eli"] = sum(1 for t in table if t[11])
    qa["rows_unmapped_type"] = sum(1 for t in table if "(not in the EUR-Lex table)" in t[3])
    qa["eurovoc_pairs"] = len(ev_rows)

    for name, headers, rows in (("leg_2026-10_table.csv", TABLE_HEADERS + EXTRA_HEADERS, table),
                                ("leg_2026-10_eurovoc.csv", EV_HEADERS, ev_rows)):
        with (out / name).open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            w.writerows(rows)
    (out / "qa.json").write_text(json.dumps(qa, indent=1, ensure_ascii=False))
    import datetime
    for stale in ("leg_2026-10_regulations.csv", "leg_2026-10_directives.csv"):  # earlier two-sheet version
        (out / stale).unlink(missing_ok=True)
    kinds = {k: [] for k in KIND_NAMES}
    for t in table:
        kinds[t[16]].append(list(t) + [issuer_of(t[5])])
    assert sum(len(v) for v in kinds.values()) == len(table) == len({t[0] for rows_ in kinds.values() for t in rows_}), "partition is not exact"
    qa["rows_per_sheet"] = {k: len(v) for k, v in kinds.items()}
    (out / "qa.json").write_text(json.dumps(qa, indent=1, ensure_ascii=False))
    write_xlsx(out / "leg_2026-10_table.xlsx", table, ev_rows, qa, doms, datetime.date.today().isoformat(), kinds, meta)
    print(json.dumps(qa, indent=1, ensure_ascii=False))
    print("CSV written to", out)


if __name__ == "__main__":
    sys.exit(main())
