"""What one export folder says about its act: its CELEX, its title and date, and which of its files is the act.

Pure functions, no database imports, so tests can load them next to the API (CI runs every test in one process, and
importing the models under two module names breaks the mapping). import_corpus_update.py re-exports them; the repair
scripts of 15 Oct 2026 read them from there. corrigendum_corrections alone queries: it takes the caller's session.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
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


# The number an act prints under its title in the OJ C series (<TITLE><TI>...<NO.DOC.C>2014/C 34/01</NO.DOC.C></TI>).
_TITLE_BLOCK = re.compile(r"<TITLE>(.*?)</TITLE>", re.S)
_NO_DOC_C = re.compile(r"<NO\.DOC\.C>(.*?)</NO\.DOC\.C>", re.S)


def numbered_title(title: Optional[str], act_file: Optional[Path]) -> Optional[str]:
    """A title that is only the act's type ("Decision": the Parliament Secretary-General's staff decisions in OJ C, 10
    laws) takes the number the act prints under it: "Decision 2014/C 34/01" (Victor, 20 Oct 2026). The metadata and
    the parser give the bare word; any title with a digit, or a file without that number, is left as it is."""
    if not title or re.search(r"\d", title) or act_file is None or not Path(act_file).exists():
        return title
    block = _TITLE_BLOCK.search(Path(act_file).read_text(encoding="utf-8", errors="replace")[:40000])
    m = _NO_DOC_C.search(block.group(1)) if block else None
    number = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split()) if m else ""
    return f"{title} {number}" if re.search(r"\d", number) else title


# The date an act's title gives it ("Commission Implementing Regulation (EU) 2026/144 of 14 January 2026 ..."). Cellar's
# work_date_document is wrong for some acts (20 Oct 2026, every LEG_2026-10 title read against it, the signature read
# where they differ: 32026R0144 held 2025-01-14, 32013D0719 "of 16 November 2012" 2013-11-16, 32022L2523 "of 14 December
# 2022" 2022-12-15). A date after a lowercase word other than of/the/and/for is another act's ("Corrigendum to ...",
# "... adopting the Agency Rules ... of 5 May 1960"). The signature is not used: an annexed agreement carries its own,
# and 21 acts are signed on another day than their title's.
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")
_TITLE_DATE = re.compile(r"\bof\s+(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})(?!\d)", re.I)
_TITLE_HEAD_WORDS = {"of", "the", "and", "for"}
_CORRIGENDUM = re.compile(r"R\(\d{2}\)$")


def title_date(title: Optional[str]) -> Optional[str]:
    """The date a title gives its own act, as YYYY-MM-DD; None when it states none or the date is another act's."""
    t = " ".join((title or "").replace("\xa0", " ").split())
    m = _TITLE_DATE.search(t)
    if not m or any(w not in _TITLE_HEAD_WORDS for w in re.findall(r"\b[a-z]{2,}\b", t[:m.start()])):
        return None
    try:
        return date(int(m.group(3)), _MONTHS.index(m.group(2).lower()) + 1, int(m.group(1))).isoformat()
    except ValueError:
        return None


def act_date(celex: Optional[str], title: Optional[str], recorded, corrections=()):
    """The value of eu_laws.date: for a corrigendum the recorded date (Cellar's: its own publication; its title names
    or repeats the corrected act's date), for any other act the date its title gives it, else the recorded date.

    The title itself can be wrong (23 Oct 2026, register O65): a corrigendum may correct it, "for: 4 April 2006, read:
    4 April 2005" (32006D0635R(01)). corrections are the (old, new, stated) triples the act's corrigenda give
    (title_date_corrections; plain (old, new) pairs count as not stated). A correction of the title's date wins:
      - alone when stated, i.e. its passage says it corrects the act's own date (names the title, signature or
        adoption date, or quotes the act's number): Cellar kept the uncorrected date of 20 acts (O66, 32005H0737
        "for: 18 May 2005, read: 18 October 2005");
      - otherwise only when the recorded date (Cellar's) is the corrected one: a corrigendum of an Article date that
        happens to equal the title's (32014D0447 "eligible as of 9 July 2014") never moves it alone."""
    if _CORRIGENDUM.search(celex or ""):
        return recorded
    t = title_date(title)
    if t:
        corr = [tuple(c) + (False,) * (3 - len(c)) for c in corrections or ()]
        stated = {new for old, new, sure in corr if old == t and sure}
        if len(stated) == 1:
            return stated.pop()
        if recorded and recorded != t and (t, recorded) in {(old, new) for old, new, _sure in corr}:
            return recorded
    return t or recorded


# "for: <old text> read: <new text>", up to the next correction ("for:", "On page", a numbered item) or the end. The
# shapes, read in 26 corrigenda on 23 Oct 2026: "title: for: 29 May 2007 read: 25 May 2007", "for: … of 26 July 2022 …,
# read: … of 5 December 2022 …", "adoption date: for: 15 March 2021, read: 15 February 2021", a whole title in each.
_CORR_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s*(\d{4})(?!\d)", re.I)
_FOR_READ = re.compile(r"\bfor\s*:(.*?)\bread\s*:(.*?)(?=\bfor\s*:|\bOn (?:the )?(?:page|cover)|\s\d+\.\s+On\b|\Z)",
                       re.I | re.S)


def _first_date(s: str) -> Optional[str]:
    m = _CORR_DATE.search(s)
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MONTHS.index(m.group(2).lower()) + 1, int(m.group(1))).isoformat()
    except ValueError:
        return None


# Where a correction says it applies, written before "for:" ("On page 26 in the title and the signature: for: ..."). The
# OJ citation of the corrigendum's own heading is cut off first: a heading such as "... on the signature of an
# Agreement ( Official Journal of the European Union L 261 of 22 September 2006 )" must not count.
_STATED_PLACE = re.compile(r"\btitles?\b|\bsignature\b|\badoption\b|concluding formula|closing formula|place and date",
                           re.I)
_OJ_CITATION = re.compile(r"Official Journal of the European Union[^)]*\)", re.I)
# a place starts after the previous correction's value or sentence: "; ", ". ", a closing quotation mark or "read:"
_PLACE_START = re.compile(r";|\.\s|[\u2019\u201d'\"]|\bread\s*:", re.I)


def _act_numbers(celex: Optional[str]) -> tuple:
    """The act's number as titles write it, from its CELEX: 32018D1109 -> ("2018/1109", "1109/2018")."""
    m = re.match(r"^\d(\d{4})[A-Z]{1,2}0*(\d+)", celex or "")
    return (f"{m.group(1)}/{m.group(2)}", f"{m.group(2)}/{m.group(1)}") if m else ()


def title_date_corrections(text: Optional[str], celex: Optional[str] = None) -> list:
    """Every (old, new, stated) date correction a corrigendum gives as "for: ... <date> ... read: ... <date>", in ISO
    form. stated: the correction says it is of the act's own date, because the place it names (the text before "for:")
    is the title, the signature or the adoption date, or because what it corrects quotes the act's number (celex)."""
    t = " ".join((text or "").replace("\xa0", " ").split())
    numbers = [re.compile(r"(?<!\d)" + re.escape(n) + r"(?!\d)") for n in _act_numbers(celex)]
    out = []
    for m in _FOR_READ.finditer(t):
        old, new = _first_date(m.group(1)), _first_date(m.group(2))
        if old and new and old != new:
            # the place is what comes just before "for:", back to the end of the previous correction or sentence
            place = _PLACE_START.split(_OJ_CITATION.split(t[max(0, m.start() - 300):m.start()])[-1])[-1]
            stated = bool(_STATED_PLACE.search(place)) or any(n.search(m.group(1)) for n in numbers)
            out.append((old, new, stated))
    return out


def corrigendum_corrections(db, acts, dump: Optional[Path] = None) -> dict:
    """{act CELEX: [(old, new, stated), ...]} given by the corrigenda eu_laws holds for these acts (CELEX + "R(NN)"): each
    corrigendum read from its folder under dump, else from its stored body_txt (a row synced from Cellar has no folder).
    Takes the caller's session and imports sqlalchemy only when called (see the module docstring)."""
    from sqlalchemy import text
    acts = sorted({a for a in acts if a})
    if not acts:
        return {}
    rows = db.execute(text("SELECT celex, uuid FROM eu_laws WHERE celex ~ 'R\\(\\d\\d\\)$' "
                           "AND regexp_replace(celex, 'R\\(\\d\\d\\)$', '') = ANY(:a)"), {"a": acts}).fetchall()
    out, unread = {}, []
    for celex, uuid in rows:
        if dump is not None and uuid and (Path(dump) / uuid).is_dir():
            act = _CORRIGENDUM.sub("", celex)
            out.setdefault(act, []).extend(title_date_corrections(corrigendum_text(Path(dump) / uuid), act))
        else:
            unread.append(celex)
    if unread:
        for celex, body in db.execute(text("SELECT celex, body_txt FROM eu_laws WHERE celex = ANY(:c)"),
                                      {"c": unread}).fetchall():
            act = _CORRIGENDUM.sub("", celex)
            out.setdefault(act, []).extend(title_date_corrections(body, act))
    return out


def corrigendum_text(folder: Path) -> str:
    """A corrigendum folder's own text, tags stripped: the Formex files holding the act, never the cover page."""
    parts = [re.sub(r"<[^>]+>", " ", f.read_text(encoding="utf-8", errors="replace"))
             for f in sorted(folder.rglob("*.xml")) if file_root(f) in MAIN_ROOTS]
    return " ".join(" ".join(parts).split())


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
