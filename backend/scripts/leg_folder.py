"""What one export folder says about its act: its CELEX, its title and date, and which of its files is the act.

Pure functions, no database imports, so tests can load them next to the API (CI runs every test in one process, and
importing the models under two module names breaks the mapping). import_corpus_update.py re-exports them; the repair
scripts of 15 Oct 2026 read them from there.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

RDF_CELEX = re.compile(r"<[\w.-]+:resource_legal_id_celex\b[^>]*>\s*([^<\s]+)\s*<")
# sector, year, type, number, then any suffix: all 59,010 LEG_2026-10 values match (32010D0646, 32019D0038R(01), ...P0001)
CELEX_SHAPE = re.compile(r"^[0-9CE][0-9]{4}[A-Z]{1,2}[0-9]{1,6}[0-9A-Z()-]*$")
# Formex root elements, counted over every LEG_2026-10 file (15 Oct 2026): the act is ACT 29,039, CORR 1,541,
# GENERAL 1,065 or AGR 354; ANNEX 32,834 are annex pages; DOC 30,261 and PUBLICATION 7,349 are the cover page
# and the contents list. Picking an ANNEX or a cover page as the main file gave 10,203 rows the wrong title.
MAIN_ROOTS = ("ACT", "CORR", "GENERAL", "AGR")
WRAPPERS = (".doc.fmx.xml", ".toc.fmx.xml", ".doc.xml", ".toc.xml")
FMX_ROOT = re.compile(rb"<(?![?!])([A-Za-z][\w.:-]*)[\s>/]")
RDF_NS = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CDM_NS = "{http://publications.europa.eu/ontology/cdm#}"
TITLE_STOP = set("the of and to in on for a an by with from as at or be is which its this that european union "
                 "council commission parliament regulation decision directive no eu ec eec".split())
MATCH_MIN = 0.4  # title_match of rows read from their act's file: 1% below 0.45 (15 Oct 2026, 18,294 rows)
TYPE_OF_LETTER = {"R": "Regulation", "L": "Directive", "D": "Decision", "H": "Recommendation", "A": "Opinion"}
WRONG_FILE_TYPES = ("Annex", "Table of Contents")
# extra_metadata keys written from the file, and keys other code computes from the file and caches (rebuilt on
# demand when missing): all go when a row's file changes. Keys from Cellar or written by hand stay.
FILE_KEYS = ("short_title", "language", "page_count", "eea_relevance", "article_count", "recital_count",
             "annex_count", "page_first", "page_last", "eea_relevant")
DERIVED_FROM_FILE = ("defined_terms", "defined_terms_version", "recital_article_map", "recital_article_map_version")
# EUR-Lex prefixes older titles with the act's number ("2014/866/EU: Council Decision of ..."); the title as printed
# in the OJ has none (Victor, 15 Oct 2026: drop it, the style of the other rows). Repeated, comma- or dash-joined
# prefixes and 11 without a separator ("2004/619/ECCouncil Decision") occur; 9,099 of 48,905 export titles change.
NUMBER_PREFIX = re.compile(r"^\s*\d{2,4}\s*/\s*\d{1,4}\s*/\s*[A-Za-z]*(?:\s*,\s*[A-Za-z]+)*\s*(?::|-|,)\s*#?"
                           r"|^\s*\d{2,4}/\d{1,4}/(?:EC|EU|EEC|CFSP|ECSC|Euratom|JHA)\s*(?=[A-Z][a-z])")


def file_root(path: Path) -> str:
    """The root element of a Formex file (ACT, CORR, ANNEX, DOC...), read from its first 4 KB; 'TIFF' for a scan."""
    head = path.open("rb").read(4000)
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"
    m = FMX_ROOT.search(head)
    return m.group(1).decode() if m else "?"


def strip_number_prefix(title: Optional[str]) -> Optional[str]:
    """The title without EUR-Lex's leading act number(s), whitespace normalised."""
    if not title:
        return title
    t = " ".join(title.split())
    while True:
        s = NUMBER_PREFIX.sub("", t, count=1)
        if s == t:
            return s
        t = s


def usable_title(title: Optional[str]) -> Optional[str]:
    """A metadata title without its number prefix, or None when it elides the act's number ("2023/…"; 3 export titles)."""
    t = strip_number_prefix(title)
    return None if not t or re.search(r"/\s*(?:…|\.\.\.)", t) else t


def rdf_meta(corpus_path: Path, uuid: str) -> dict:
    """What the folder's own metadata states: {'title': the English expression title, 'date': work_date_document}."""
    out = {"title": None, "date": None}
    rdf = corpus_path / uuid / "tree_non_inferred.rdf"
    if not rdf.exists():
        return out
    root = ET.fromstring(rdf.read_bytes())
    for d in root.findall(RDF_NS + "Description"):
        lang, t = d.find(CDM_NS + "expression_uses_language"), d.find(CDM_NS + "expression_title")
        if lang is not None and t is not None and (t.text or "").strip() \
                and lang.get(RDF_NS + "resource", "").endswith("/ENG"):
            out["title"] = " ".join(t.text.split())
            break
    dates = {e.text.strip() for e in root.iter(CDM_NS + "work_date_document") if (e.text or "").strip()}
    out["date"] = dates.pop() if len(dates) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", next(iter(dates))) else None
    return out


def title_match(a: Optional[str], b: Optional[str]) -> float:
    """Share of distinctive title words two titles have in common (0..1); robust to number prefixes and spacing."""
    wa, wb = ({w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in TITLE_STOP} for s in (a, b))
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def main_file(corpus_path: Path, uuid: str, celex: Optional[str], title_of, parser, current: Optional[Path] = None) -> tuple:
    """(the act's own file in the folder, title match or None), chosen by what each file contains.

    Only a file whose root is the act (MAIN_ROOTS) can be the main file, never an ANNEX page, the DOC cover page or
    the PUBLICATION contents. A corrigendum takes the republished act when its folder holds one (it carries the
    articles, legal basis and citations; Victor, 14 and 15 Oct 2026), else its CORR notice. Several candidates: the
    one whose own title best matches the folder's title (title_of() is called only then); on a tie the row's
    current file stays. (None, None) when the folder holds no act file (32015D1735 holds two TIFF scans).
    """
    fmx = corpus_path / uuid / "fmx4"
    files = sorted((p for p in fmx.rglob("*") if p.is_file() and not p.name.endswith(WRAPPERS + (".log",))),
                   key=lambda p: p.name) if fmx.is_dir() else []
    roots = {p: file_root(p) for p in files}
    cands = [p for p in files if roots[p] in MAIN_ROOTS]
    if celex and "R(" in celex:
        for kind in ("ACT", "CORR"):
            if any(roots[p] == kind for p in cands):
                cands = [p for p in cands if roots[p] == kind]
                break
    if len(cands) < 2:
        return (cands[0] if cands else None), None
    title = title_of()
    if not title:
        return (current if current in cands else cands[0]), None
    scored = [(title_match(parser.parse_file(p).title, title), p == current, -i, p) for i, p in enumerate(cands)]
    best = max(scored)
    return best[3], best[0]


def number_in_title(celex: Optional[str], title: Optional[str]) -> bool:
    """The act's number, as titles write it (2025/395, 395/2025, 87/369, No 1305/2013), appears in the title."""
    m = re.match(r"^3(\d{4})[A-Z]{1,2}0*(\d+)", celex or "")
    if not m:
        return False
    y, n = m.groups()
    forms = (f"{y}/{n}", f"{n}/{y}", f"{y[2:]}/{n}", f"{n}/{y[2:]}")
    return any(re.search(rf"(?<![\d/]){re.escape(f)}(?![\d/])", title or "") for f in forms)


def act_confirmed(celex: Optional[str], parsed, meta_title: Optional[str]) -> Optional[str]:
    """None when the parsed file is that act in English, else why not. Its title must match the metadata title
    (title_match >= MATCH_MIN) or carry the act's number; with no metadata title, English is enough."""
    if not (parsed.language or "EN").upper().startswith("EN"):
        return "not English"
    if meta_title and title_match(parsed.title, meta_title) < MATCH_MIN and not number_in_title(celex, parsed.title):
        return "neither title nor number match"
    return None


def type_label(celex: Optional[str], current: Optional[str]) -> Optional[str]:
    """doc_type_normalized from the CELEX type letter, the rule the table already follows (17,440 of 17,605 typed
    rows read from their act's file, 15 Oct 2026: D Decision, R Regulation, L Directive, H Recommendation,
    A Opinion; a corrigendum takes its act's letter). Sector 3 only (in sector 2, A is an agreement). Otherwise the
    current value stays unless it names the wrong file."""
    m = re.match(r"^3[0-9]{4}([A-Z]{1,2})", celex or "")
    if m and m.group(1) in TYPE_OF_LETTER:
        return TYPE_OF_LETTER[m.group(1)]
    return "Other" if current in WRONG_FILE_TYPES or not current else current


def is_legal_act(celex: Optional[str]) -> bool:
    """eu_laws holds legal acts, CELEX sector 3; the export also carries a few documents of other sectors (two
    corrigenda of Council notices, sector 5, removed 17 Oct 2026), which are never imported."""
    return bool(celex) and celex[0] == "3"


def folder_celex(corpus_path: Path, uuid: str) -> Optional[str]:
    """The folder's own CELEX from the dump's metadata; None unless it states exactly one."""
    rdf = corpus_path / uuid / "tree_non_inferred.rdf"
    if not rdf.exists():
        return None
    found = set(RDF_CELEX.findall(rdf.read_text(errors="ignore")))
    return found.pop() if len(found) == 1 and CELEX_SHAPE.match(next(iter(found))) else None


def celex_for(uuid: str, cx: Optional[str], row_celex: Optional[str], held: dict) -> tuple:
    """(CELEX the row gets, outcome) given its folder's CELEX cx and the {celex: uuid} map of rows holding one.

    keep: the row already carries cx | conflict: the row carries another CELEX than its folder states:
    kept, for a person (checked before held: a mis-keyed row is not a duplicate) | held: the row has no
    CELEX and another row holds cx, so this folder duplicates an act already in the table: not written |
    fill: a new row, or a row without CELEX, takes cx | none: the metadata states no single CELEX.
    """
    if not cx:
        return row_celex, "none"
    if row_celex == cx:
        return cx, "keep"
    if row_celex:
        return row_celex, "conflict"
    if held.get(cx, uuid) != uuid:
        return None, "held"
    return cx, "fill"
