#!/usr/bin/env python3.12
"""Refile register documents stored under another document's identity.

13 Oct 2026, found by comparing every row of commission_documents with what Cellar states for it:

  A. 294 rows are corrigenda filed under the act they correct. The EUR-Lex feed lists a corrigendum
     as "CELEX:32011L0089R(02)"; the reader kept the digits before the R, so the row took the 2011
     directive's CELEX and, from the fill-in scripts, its date and its text. Cellar holds each
     corrigendum as its own work, dated 2026.
  B. 4 rows hold a CELEX rebuilt from their reference ("SWD(2026) 50" gave 52026SC0050) where their
     own link states another (52026SC0050(01)). 52026SC0050 is an opinion of the Regulatory Scrutiny
     Board, so the staff working document carried the opinion's text.
  C. 1 row filed as SWD(2026) 133 is SEC(2026) 133: the reader named every 5YYYYSC document "SWD",
     and SC also numbers SEC documents. Cellar states the document's own number.

Each row is refiled under the identifier it states itself, once Cellar holds it. What was read under
the wrong one (date, text, links) is cleared, and complete_commission_documents.py reads it again.
Nothing is derived, and a row is changed only while it still holds the value that was checked.

    python3.12 scripts/refile_register_documents.py --rehearse
    python3.12 scripts/refile_register_documents.py --apply

Exit code: 0 done; 1 when Cellar answered for none of the rows that needed it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import ssl
import sys
import urllib.parse
import urllib.request

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from scripts import complete_commission_documents as fill  # noqa: E402

ROWS = text("""
    SELECT id, reference, doc_type::text AS doc_type, celex, title, portal_url, publication_date
      FROM commission_documents""")

REFILE_CORRIGENDUM = text("""
    UPDATE commission_documents
       SET reference = :own, celex = :own, publication_date = NULL, text_body = NULL, body_html = NULL,
           portal_url = NULL, pdf_url = NULL, last_updated = now(),
           -- a corrigendum to an act exists only in the languages it corrects: read them again
           languages = CASE WHEN :own LIKE '3%' THEN CAST('{}' AS varchar[]) ELSE languages END
     WHERE id = :rid AND reference = :old""")
REFILE_CELEX = text("""
    UPDATE commission_documents
       SET celex = :own, text_body = NULL, body_html = NULL,
           pdf_url = CASE WHEN pdf_url LIKE '%' || :old THEN NULL ELSE pdf_url END,
           publication_date = CASE WHEN :keep_date THEN publication_date ELSE NULL END,
           last_updated = now()
     WHERE id = :rid AND celex = :old""")
REFILE_NUMBER = text("""
    UPDATE commission_documents
       SET reference = :own, doc_type = CAST(:doc_type AS commission_doc_type_enum),
           document_register_category = NULLIF(document_register_category, :was), last_updated = now()
     WHERE id = :rid AND reference = :old""")

_NUMBERS = (
    "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
    "SELECT ?c ?p ?n ?y WHERE {{ VALUES ?c {{ {vals} }} ?w cdm:resource_legal_id_celex ?c ; "
    "cdm:resource_legal_internal_number_prefix ?p ; cdm:resource_legal_internal_number_sequential_number ?n ; "
    "cdm:resource_legal_internal_number_year ?y . }}")
_FILED = re.compile(r"^(SWD|JOIN|SEC|COM)\((\d{4})\)\s*(\d+)$")


# --------------------------------------------------------------------------
# Pure functions (tested without a network or a database)
# --------------------------------------------------------------------------

def own_corrigendum(reference: str, title: str) -> str | None:
    """The CELEX a row's title states (a corrigendum, or a proposal's later version), where the row
    is filed under something else."""
    if not (title or "").startswith("CELEX:"):
        return None
    own = fill.stated_celex(None, title, None)
    return own if own and re.search(r"R\([0-9]{2}\)$", own) and own != (reference or "").strip() else None


def own_link_celex(celex: str | None, link: str | None) -> str | None:
    """The CELEX a row's own link states, where the celex column holds another."""
    own = fill.stated_celex(None, None, link)
    return own if own and celex and own != celex else None


def own_number(reference: str, number: tuple[str, str, str] | None) -> tuple[str, str] | None:
    """(reference, doc_type) as Cellar numbers the document, where the row is filed under another
    series. SEC documents are written as the register writes them, without a space."""
    m = _FILED.match((reference or "").strip())
    if not number or not m:
        return None
    prefix, year, num = number[0], number[1], str(int(number[2]))
    if prefix == m.group(1):
        return None  # same series: a later version shares its reference, and is not refiled here
    return (f"{prefix}({year}){num}" if prefix == "SEC" else f"{prefix}({year}) {num}"), prefix


def plan(rows: list, facts: dict[str, dict], numbers: dict[str, tuple[str, str, str]]) -> dict[str, list[dict]]:
    """What to refile, from the rows and what Cellar states. Writes nothing."""
    references = {r.reference for r in rows}
    held = {r.celex for r in rows if r.celex}
    out: dict[str, list[dict]] = {"corrigendum": [], "celex": [], "number": [], "not_held_by_cellar": []}
    celex_now = {r.id: r.celex for r in rows}
    for r in rows:
        own = own_corrigendum(r.reference, r.title)
        if own:
            if own not in facts:
                out["not_held_by_cellar"].append({"reference": r.reference, "own": own})
            elif own not in references:
                out["corrigendum"].append({"rid": r.id, "old": r.reference, "own": own})
                references.add(own)
            continue
        own = own_link_celex(r.celex, r.portal_url)
        if own:
            if own not in facts:
                out["not_held_by_cellar"].append({"reference": r.reference, "own": own})
            elif own not in held:
                dates = facts[own].get("dates") or set()
                stored = r.publication_date.date().isoformat() if r.publication_date else None
                out["celex"].append({"rid": r.id, "old": r.celex, "own": own, "reference": r.reference,
                                     "keep_date": dates == {stored}})
                held.add(own)
                celex_now[r.id] = own
    for r in rows:
        new = own_number(r.reference, numbers.get(celex_now[r.id] or ""))
        if new and new[0] not in references:
            out["number"].append({"rid": r.id, "old": r.reference, "own": new[0], "doc_type": new[1],
                                  "was": r.doc_type})
            references.add(new[0])
    return out


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def _numbers(celexes: list[str], ctx) -> dict[str, tuple[str, str, str]]:
    """The document number Cellar states for each CELEX: (prefix, year, number). One answer or none."""
    seen: dict[str, set] = {}
    for i in range(0, len(celexes), fill.BATCH):
        vals = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in celexes[i:i + fill.BATCH])
        req = urllib.request.Request(
            fill.SPARQL, data=urllib.parse.urlencode({"query": _NUMBERS.format(vals=vals)}).encode(),
            headers={"Accept": "application/sparql-results+json"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            for b in json.load(r)["results"]["bindings"]:
                seen.setdefault(b["c"]["value"], set()).add(
                    (b["p"]["value"], b["y"]["value"][:4], b["n"]["value"]))
    return {c: next(iter(v)) for c, v in seen.items() if len(v) == 1}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(fill._laws._database_url(), pool_pre_ping=True, pool_recycle=300)
    ctx = ssl.create_default_context(cafile=certifi.where())
    with engine.connect() as c:
        rows = list(c.execute(ROWS))

    stated = sorted({own for r in rows for own in (own_corrigendum(r.reference, r.title),
                                                   own_link_celex(r.celex, r.portal_url)) if own})
    facts, reached = fill.facts_for(stated, ctx)
    if stated and not reached:
        print(f"[ERROR] {len(stated)} identifiers needed Cellar and it answered for none")
        return 1
    link_celex = {r.id: own_link_celex(r.celex, r.portal_url) for r in rows}
    series = sorted({(link_celex[r.id] if link_celex[r.id] in facts else r.celex) for r in rows
                     if _FILED.match(r.reference or "") and r.celex})
    todo = plan(rows, facts, _numbers(series, ctx))

    print(f"[INFO] rows read: {len(rows)}")
    print(f"[INFO] A. corrigenda filed under the act they correct : {len(todo['corrigendum'])}")
    print(f"[INFO] B. CELEX other than the one their link states  : {len(todo['celex'])} "
          f"{[(w['reference'], w['old'], w['own']) for w in todo['celex']]}")
    print(f"[INFO] C. filed under a series Cellar does not state  : {len(todo['number'])} "
          f"{[(w['old'], w['own']) for w in todo['number']]}")
    if todo["not_held_by_cellar"]:
        print(f"[INFO] stated but not held by Cellar, left alone      : {todo['not_held_by_cellar']}")
    if args.rehearse:
        print(f"[INFO] sample A: {[(w['old'], w['own']) for w in todo['corrigendum'][:4]]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    done = {"corrigendum": 0, "celex": 0, "number": 0}
    for kind, stmt in (("corrigendum", REFILE_CORRIGENDUM), ("celex", REFILE_CELEX), ("number", REFILE_NUMBER)):
        for w in todo[kind]:
            params = {k: v for k, v in w.items() if k != "reference"}
            with engine.begin() as c:
                done[kind] += c.execute(stmt, params).rowcount
    print(f"[INFO] refiled: {done}")
    if any(done[k] != len(todo[k]) for k in done):
        print("[ERROR] a row changed between the check and the write; run it again")
        return 1
    print(f"[OK] every row refiled under the identifier it states, {dt.date.today().isoformat()}; "
          "now run complete_commission_documents.py --apply --days 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
