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

RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CDM = "{http://publications.europa.eu/ontology/cdm#}"
WRAPPERS = (".doc.xml", ".toc.xml", ".doc.fmx.xml", ".toc.fmx.xml")
CELLAR = "https://publications.europa.eu/webapi/rdf/sparql"

# EUR-Lex "Types of documents in EUR-Lex", sector 3 and the one sector-5 descriptor in this dump.
TYPE_LABELS = {
    ("3", "A"): "Opinion", ("3", "B"): "Budget", ("3", "C"): "Declaration", ("3", "D"): "Decision",
    ("3", "E"): "CFSP act (common position, joint action, common strategy)",
    ("3", "F"): "Police and judicial cooperation in criminal matters act",
    ("3", "G"): "Resolution", ("3", "H"): "Recommendation",
    ("3", "J"): "Non-opposition to a notified joint venture", ("3", "K"): "ECSC recommendation",
    ("3", "L"): "Directive", ("3", "M"): "Non-opposition to a notified concentration",
    ("3", "O"): "ECB guideline", ("3", "Q"): "Institutional arrangement",
    ("3", "R"): "Regulation", ("3", "S"): "ECSC decision of general interest",
    ("3", "X"): "Other document published in OJ L", ("3", "Y"): "Other document published in OJ C",
    ("5", "XG"): "Other document of the Council or the Member States",
}
ELI_PREFIX = {"R": ("reg", "reg_impl", "reg_del"), "L": ("dir", "dir_impl", "dir_del"),
              "D": ("dec", "dec_impl", "dec_del")}
SUFFIX_RE = re.compile(r"(?:\(\d{2}\))*(?:R\(\d{2}\))*$")
CELEX_RE = re.compile(r"^(?P<s>[0-9CE])(?P<y>\d{4})(?P<t>[A-Z]{1,3})(?P<n>\d{4,6})")

TABLE_HEADERS = ["CELEX", "Sector", "Year", "Type of document", "Number of document", "Title of document",
                 "Alias of document", "Acronym of the alias"]
EXTRA_HEADERS = ["base_celex", "date_document", "in_force", "eli", "author", "eurovoc_count",
                 "eurovoc_domains", "title_source"]
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
    for d in root.findall(RDF + "Description"):
        lang = d.find(CDM + "expression_uses_language")
        if lang is not None and lang.get(RDF + "resource", "").endswith("/ENG"):
            t = d.find(CDM + "expression_title")
            if t is not None and t.text and t.text.strip():
                title = " ".join(t.text.split())
    source = "rdf" if title else ""
    title_formex = ""
    if not title:  # last resort when neither the RDF nor Cellar has it: the TITLE of the first Formex part that has one
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
        "title": title or "", "title_source": source, "title_formex": title_formex,
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


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, table, ev_rows, qa, domains, built_on):
    """Read me (method check), Table, EuroVoc, Statistics. Statistics are live formulas."""
    import xlsxwriter
    wb = xlsxwriter.Workbook(str(path), {"constant_memory": True})
    wb.formats[0].set_font_name("Arial")
    wb.formats[0].set_font_size(10)
    f = lambda **k: wb.add_format({"font_name": "Arial", "font_size": 10, **k})
    head, bold, wrap, num, title_f = f(bold=True, bg_color="#1F3864", font_color="#FFFFFF"), f(bold=True), f(text_wrap=True, valign="top"), f(num_format="0"), f(bold=True, font_size=14)
    n, nev = len(table), len(ev_rows)
    rng = lambda sheet, col, last: f"{sheet}!${col}$2:${col}${last}"
    T = lambda col: rng("Table", col, n + 1)
    E = lambda col: rng("EuroVoc", col, nev + 1)

    # ---- Read me (written first so it is the first tab); formulas reference the later sheets
    rm = wb.add_worksheet("Read me")
    st = wb.add_worksheet("Statistics")
    tb = wb.add_worksheet("Table")
    ev = wb.add_worksheet("EuroVoc")
    rm.set_column(0, 0, 44); rm.set_column(1, 1, 22); rm.set_column(2, 2, 22); rm.set_column(3, 3, 12); rm.set_column(4, 4, 90)

    py_type = Counter(t[3] for t in table)
    py_sector = Counter(t[1] for t in table)
    rows = [
        ("LEG_2026-10: summary table by CELEX and EuroVoc", None, None, None, None, "title"),
        (f"Built on {built_on} by backend/scripts/build_leg_table.py. Source: docs/LEG_2026-10, the Publications Office bulk export of 11 Oct 2026 (legislation in force, Formex 4 + metadata). One row = one OJ publication (one UUID folder, one CELEX).", None, None, None, None, "text"),
        ("", None, None, None, None, "text"),
        ("Method check", "Formula", "Independent count", "Check", "How the independent count was made", "header"),
        ("Rows in Table", f"=COUNTA({T('A')})", qa["folders_with_fmx4"], "chk", "Folders holding an fmx4 directory, counted on disk before parsing", "row"),
        ("Sector 3 rows", f"=COUNTIF({T('B')},3)", py_sector.get(3, 0), "chk", "Counter over the parsed sector values", "row"),
        ("Regulations (R)", f"=COUNTIF({T('D')},\"R = Regulation\")", py_type.get("R = Regulation", 0), "chk", "Counter over the parsed type letters", "row"),
        ("Directives (L)", f"=COUNTIF({T('D')},\"L = Directive\")", py_type.get("L = Directive", 0), "chk", "Counter over the parsed type letters", "row"),
        ("EuroVoc pairs in EuroVoc sheet", f"=COUNTA({E('A')})", f"=SUM({T('N')})", "chk", "Sum of eurovoc_count in Table (two sheets built from the same RDF; they must agree)", "row"),
        ("Rows with an alias", f"=COUNTIF({T('G')},\"?*\")", qa["rows_with_alias"], "chk", "Rows of aliases.csv whose CELEX is in the dump", "row"),
        ("Rows with an ELI", f"=COUNTIF({T('L')},\"?*\")", qa["rows_with_eli"], "chk", "ELI URI matching the act's own type, year and number, counted while building", "row"),
        ("Rows with no title", f"=COUNTBLANK({T('F')})", qa["rows_without_title"], "chk", "Counted while building", "row"),
        (f"All {qa['distinct_celex']:,} CELEX are distinct (asserted by the builder before writing; a COUNTIF-based distinct count over 30,000 rows would take minutes to recalculate).", None, None, None, None, "text"),
        ("Columns", "Source", None, None, "Definition", "header"),
        ("CELEX", "resource_legal_id_celex", None, None, "Own CELEX of the OJ publication. Sector, Year, Type and Number are read from the CELEX string; the metadata fields agree in all rows but " + str(sum(qa["celex_string_vs_metadata_disagreements"].values())) + " field(s): " + json.dumps(qa["celex_string_vs_metadata_disagreements"]), "row"),
        ("Sector", "resource_legal_id_sector", None, None, "First CELEX character (3 = legal acts, 5 = preparatory documents).", "row"),
        ("Year", "resource_legal_year", None, None, "Year in the CELEX. In the one row where the metadata year differs (a corrigendum) the CELEX year is shown.", "row"),
        ("Type of document", "resource_legal_type", None, None, "Descriptor letter and its meaning in the EUR-Lex table 'Types of documents in EUR-Lex'.", "row"),
        ("Number of document", "resource_legal_number_natural_celex", None, None, "Natural number of the act, without leading zeros (CELEX 32016R0679 gives 679).", "row"),
        ("Title of document", "expression_title (ENG)", None, None, f"Official English title. {qa['title_from_cellar'] + qa['title_from_formex']} acts have none in the RDF: {qa['title_from_cellar']} were read from Cellar (title_source = cellar), {qa['title_from_formex']} from the Formex TITLE (title_source = formex).", "row"),
        ("Alias of document / Acronym of the alias", "aliases.csv", None, None, f"Not in the dump. Filled only from aliases.csv ({qa['rows_with_alias']} acts, seeded from the curated full_name entries of legislation_acronyms.json). Empty = unknown, never derived. Add rows to aliases.csv and rebuild.", "row"),
        ("base_celex", "derived from CELEX", None, None, "CELEX without (nn) and R(nn) suffixes: groups corrigenda and further publications with their act.", "row"),
        ("date_document / in_force", "work_date_document / resource_legal_in-force", None, None, "in_force is 'unknown' when the metadata carries no flag (not the same as false).", "row"),
        ("eli", "ELI URI in the RDF", None, None, "Only the URI whose type, year and number match the act; empty when none or several match.", "row"),
        ("eurovoc_count / eurovoc_domains", "work_is_about_concept_eurovoc", None, None, "Number of EuroVoc concepts of the act and the EuroVoc domains of their microthesauri (code and name). Concept labels and microthesauri: EuroVoc 4.24 on Cellar. Detail in the EuroVoc sheet.", "row"),
        ("author", "work_created_by_agent", None, None, "Authority-table code(s) of the creating body, '|' separated.", "row"),
    ]
    r = 0
    for lab, a, b, c, d, kind in rows:
        if kind == "title":
            rm.write(r, 0, lab, title_f)
        elif kind == "text":
            rm.merge_range(r, 0, r, 4, lab, wrap) if lab else None
            if lab: rm.set_row(r, 42)
        elif kind == "header":
            for j, v in enumerate((lab, a, b, c, d)):
                rm.write(r, j, v if v is not None else "", head)
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
    widths = [16, 7, 7, 34, 11, 110, 34, 14, 16, 12, 10, 44, 14, 13, 40, 12]
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
    block("Title source", ["rdf", "cellar", "formex"], lambda lab, rr: f"=COUNTIF({T('P')},A{rr + 1})")
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

    folders = sorted(p.name for p in dump.iterdir() if (p / "fmx4").is_dir())
    with mp.Pool(8) as pool:
        recs = list(pool.imap_unordered(parse_folder, [(str(dump), f) for f in folders], chunksize=40))
    print(f"{len(recs)} folders parsed")

    # ---- QA before anything is written
    qa = {"folders_with_fmx4": len(folders), "rows": len(recs),
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

    missing = [r["celex"] for r in recs if not r["title"]]
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
                      SUFFIX_RE.sub("", r["celex"]), r["date"], r["in_force"] or "unknown", pick_eli(r, r["celex"]), r["author"],
                      len(r["eurovoc"]), " | ".join(domains), r["title_source"]])
        for i in sorted(r["eurovoc"], key=lambda x: (meta["concept"].get(x, "~"), x)):
            mt, dom = mt_domain(i)
            ev_rows.append([r["celex"], i, f"http://eurovoc.europa.eu/{i}", meta["concept"].get(i, ""), mt, dom])
    qa["rows_without_title"] = sum(1 for t in table if not t[5])
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
    write_xlsx(out / "leg_2026-10_table.xlsx", table, ev_rows, qa, doms, datetime.date.today().isoformat())
    print(json.dumps(qa, indent=1, ensure_ascii=False))
    print("CSV written to", out)


if __name__ == "__main__":
    sys.exit(main())
