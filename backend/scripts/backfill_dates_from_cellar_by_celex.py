#!/usr/bin/env python3.12
"""Read the document date of register documents and secondary acts from Cellar, by CELEX.

A full walk on 2 October 2026 found document_date empty on 877 of 1,485 register
documents and 862 of 6,227 implementing acts. Nearly all of them now carry a CELEX
(read from Cellar or confirmed there earlier the same day), and Cellar states each
work's date as cdm:work_date_document: 52026PC0186 -> 2026-05-08, which is the date
printed on the proposal itself ("Brussels, 8.5.2026").

So the date is READ from the authority for that CELEX, never inferred from an
import timestamp. Only an empty column is written:
  commission_documents.publication_date   (served as document_date)
  secondary_acts.adoption_date            (document_date = publication_date or adoption_date)

    python3.12 scripts/backfill_dates_from_cellar_by_celex.py --rehearse
    python3.12 scripts/backfill_dates_from_cellar_by_celex.py --apply
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
BATCH = 60

TARGETS = [
    ("commission_documents", "publication_date",
     "SELECT id, celex FROM commission_documents WHERE publication_date IS NULL AND coalesce(celex,'') <> ''"),
    ("secondary_acts", "adoption_date",
     "SELECT id, celex FROM secondary_acts WHERE publication_date IS NULL AND adoption_date IS NULL "
     "AND coalesce(celex,'') <> ''"),
]


def _db_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _dates(celexes: list[str], ctx) -> dict[str, set[str]]:
    vals = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in celexes)
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
         f"SELECT ?c ?d WHERE {{ VALUES ?c {{ {vals} }} "
         "?w cdm:resource_legal_id_celex ?c ; cdm:work_date_document ?d . }")
    req = urllib.request.Request(SPARQL + "?" + urllib.parse.urlencode({"query": q}),
                                 headers={"Accept": "application/sparql-results+json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                data = json.load(r)
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    out: dict[str, set[str]] = {}
    for b in data["results"]["bindings"]:
        out.setdefault(b["c"]["value"], set()).add(b["d"]["value"][:10])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_db_url(), pool_pre_ping=True, pool_recycle=300)
    ctx = ssl.create_default_context(cafile=certifi.where())
    total = 0
    for table, col, pick in TARGETS:
        with engine.connect() as c:
            rows = list(c.execute(text(pick)))
        celexes = sorted({r.celex for r in rows})
        found: dict[str, set[str]] = {}
        for i in range(0, len(celexes), BATCH):
            found.update(_dates(celexes[i:i + BATCH], ctx))
            time.sleep(0.3)
        writes, ambiguous, missing = [], 0, 0
        for r in rows:
            ds = found.get(r.celex)
            if not ds:
                missing += 1
            elif len(ds) > 1:
                ambiguous += 1
            else:
                writes.append({"rid": r.id, "d": date.fromisoformat(next(iter(ds)))})
        print(f"[INFO] {table}.{col}: {len(rows)} undated with a CELEX | dated by Cellar "
              f"{len(writes)} | none {missing} | ambiguous {ambiguous}")
        if args.apply and writes:
            with engine.begin() as c:
                for w in writes:
                    total += c.execute(text(
                        f"UPDATE {table} SET {col} = :d, last_updated = now() "
                        f"WHERE id = :rid AND {col} IS NULL"), w).rowcount
    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
        return 0
    print(f"[INFO] dates stored: {total}")
    if total == 0:
        print("[ERROR] nothing stored; this run proves nothing")
        return 1
    print("[OK] every stored date is Cellar's work_date_document for that CELEX")
    return 0


if __name__ == "__main__":
    sys.exit(main())
