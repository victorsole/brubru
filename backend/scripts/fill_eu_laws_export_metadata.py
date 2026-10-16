#!/usr/bin/env python3.12
"""Fill eu_laws' metadata columns (migrations 301, 302) from the Publications Office's metadata, without moving updated_at.

Victor, 16 Oct 2026: "05 eur-lex/laws" serves the LEG_2026-10 export's datapoints; filling them is not a change of the
record, so a client syncing by updated_from must not receive 30,000 laws again. Sources:
  - for the laws the export holds with text (30,257 on 16 Oct): each folder's tree_non_inferred.rdf through
    leg_export_metadata.rdf_facts (authors, in_force, eli, entry_into_force, application_dates, effect_dates,
    procedures), the reading the importer uses too;
  - for every law, Cellar's dossier_contains_work for the procedure numbers the export lacks (GDPR, DSA...), and
    Cellar's in-force flag for the laws the export does not hold (the 289 marked repealed and the acts the daily OJ
    sync added); Cellar answers are cached in backend/data/leg_2026-10_table/cellar_dossiers.json, and a batch counts
    only if its control law (GDPR: procedure 2012/0011, in force) comes back right;
  - alias and acronym: Brubru's curated aliases.csv.
Only empty columns are filled: a value another writer set is never overwritten (a difference is reported instead),
so a re-run cannot undo a newer fact. Laws marked repealed but stated in force, or the reverse, are counted.

Dry run by default (it fetches and caches the Cellar answers). --apply writes a JSON backup of the columns it fills,
updates in chunks of 500 rows, each chunk in its own transaction with brubru.keep_change_signal set to that
transaction's id (migration 302), checks that no touched row's updated_at moved, and re-measures.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.fill_eu_laws_export_metadata [--apply]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import multiprocessing as mp
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.scripts.fix_eu_laws_2025_leftovers import check  # noqa: E402
from backend.scripts.leg_export_metadata import (COLS, ROOT, TABLES, aliases, folder_of_celex,  # noqa: E402
                                                 procedure_number, rdf_facts)

CORPUS = ROOT / "docs/LEG_2026-10"
CACHE = TABLES / "cellar_dossiers.json"
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CONTROL = ("32016R0679", "2012/0011")
BATCH = 80
CHUNK = 500
UPDATE = ("UPDATE eu_laws e SET " + ", ".join(f"{c} = coalesce(e.{c}, v.{c})" for c in COLS) +
          f" FROM (VALUES %s) AS v (id, {', '.join(COLS)}) WHERE e.id = v.id RETURNING e.id, e.updated_at")
TEMPLATE = "(%s, %s, %s, %s::text[], %s::boolean, %s, %s::date[], %s::date[], %s::date[], %s::text[])"


def _facts(folder):
    return folder, rdf_facts(CORPUS, folder)


def _ask(batch: list) -> dict:
    """One SPARQL call for a batch plus the control law; {} when it fails or the control does not come back right."""
    values = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in batch + [CONTROL[0]])
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> PREFIX owl: <http://www.w3.org/2002/07/owl#> "
         f"SELECT ?c ?s ?f WHERE {{ VALUES ?c {{ {values} }} ?w cdm:resource_legal_id_celex ?c . "
         "OPTIONAL { ?d cdm:dossier_contains_work ?w . ?d owl:sameAs ?s } OPTIONAL { ?w cdm:resource_legal_in-force ?f } }")
    try:
        req = urllib.request.Request(SPARQL + "?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}),
                                     headers={"Accept": "application/sparql-results+json"})
        rows = json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]
    except Exception:
        return {}
    got = {}
    for b in rows:
        g = got.setdefault(b["c"]["value"], {"procedures": set(), "flags": set()})
        p = procedure_number(b.get("s", {}).get("value", ""))
        if p:
            g["procedures"].add(p)
        if "f" in b:
            g["flags"].add(b["f"]["value"])
    ctl = got.get(CONTROL[0], {})
    if CONTROL[1] not in ctl.get("procedures", ()) or ctl.get("flags") != {"1"}:
        return {}
    out = {}
    for c in batch:
        g = got.get(c, {"procedures": set(), "flags": set()})
        flag = next(iter(g["flags"])) if len(g["flags"]) == 1 else None
        out[c] = {"procedures": sorted(g["procedures"]), "in_force": {"1": True, "0": False}.get(flag)}
    return out


def _ask_or_split(batch: list) -> dict:
    """Retry a batch twice, then split it in halves: Cellar times out on some batches of 80 that answer at once in tens
    (16 Oct 2026). A law that fails alone is left out: unknown, never "none"."""
    for attempt in range(2):
        got = _ask(batch)
        if got:
            return got
        time.sleep(5 * (attempt + 1))
    if len(batch) == 1:
        return {}
    mid = len(batch) // 2
    return {**_ask_or_split(batch[:mid]), **_ask_or_split(batch[mid:])}


def cellar(celexes: list) -> dict:
    """{CELEX: {"procedures": [...], "in_force": bool|None}} from Cellar, cached in CACHE; every call carries a control
    law (GDPR, procedure 2012/0011, in force) and counts only if it comes back right."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [c for c in celexes if c not in cache]
    for i in range(0, len(todo), BATCH):
        cache.update(_ask_or_split(todo[i:i + BATCH]))
        if (i // BATCH) % 25 == 24 or i + BATCH >= len(todo):
            CACHE.write_text(json.dumps(cache))
            print(f"[INFO]   Cellar: {min(i + BATCH, len(todo))} of {len(todo)} asked, {len(cache)} cached", flush=True)
    return cache


def plan(db):
    rows = db.execute(text(f"SELECT id, celex, corpus_status, {', '.join(COLS)} FROM eu_laws "
                           "WHERE coalesce(celex, '') <> '' ORDER BY id")).mappings().all()
    folders, names = folder_of_celex(), aliases()
    with mp.Pool(8) as pool:
        facts = dict(pool.map(_facts, sorted({folders[r["celex"]] for r in rows if r["celex"] in folders}), chunksize=100))
    remote = cellar([r["celex"] for r in rows])
    blank = {k: None for k in COLS}
    fills, differs, why = [], [], collections.Counter()
    for r in rows:
        c = r["celex"]
        w = {**blank, **facts.get(folders.get(c), {})}
        w["alias"], w["acronym"] = names.get(c, (None, None))
        cel = remote.get(c)
        if cel:
            w["procedures"] = sorted(set(w["procedures"] or []) | set(cel["procedures"])) or None
            if c not in folders:
                w["in_force"] = cel["in_force"]
        for k, v in w.items():
            have = [str(x) for x in r[k]] if isinstance(r[k], list) else r[k]
            if r[k] is not None and v is not None and have != v:
                differs.append((r["id"], c, k, have, v))
        new = {k: (v if r[k] is None else None) for k, v in w.items()}
        if any(v is not None for v in new.values()):
            fills.append((r["id"], new))
            why["in the export" if c in folders else "not in the export (Cellar)"] += 1
    return fills, differs, why, len(rows), remote


MEASURE = ("SELECT " + ", ".join(f"count({c})" for c in COLS) + ", count(*) FILTER (WHERE in_force), "
           "count(*) FILTER (WHERE in_force AND corpus_status = 'repealed'), "
           "count(*) FILTER (WHERE NOT in_force AND corpus_status <> 'repealed'), count(*) "
           "FROM eu_laws WHERE coalesce(celex, '') <> ''")


def measure(db) -> str:
    a = db.execute(text(MEASURE)).one()
    filled = ", ".join(f"{c} {a[i]}" for i, c in enumerate(COLS))
    return (f"{filled} (in force {a[len(COLS)]}) of {a[-1]} laws | in force but marked repealed {a[len(COLS) + 1]}, "
            f"not in force but not marked repealed {a[len(COLS) + 2]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        before = measure(db)
        fills, differs, why, n, remote = plan(db)
        procs = sum(1 for v in remote.values() if v["procedures"])
        print(f"[INFO] {n} laws with a CELEX | to fill: {len(fills)} | Cellar answers: {len(remote)} ({procs} with a procedure)")
        for k, v in why.most_common():
            print(f"[INFO]   {v:6d}  {k}")
        print(f"[INFO] values already set that differ (never overwritten, for a person): {len(differs)} {differs[:3]}")
        print(f"[INFO] now: {before}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        ids = [i for i, _ in fills]
        snap = {r["id"]: dict(r) for r in db.execute(text(f"SELECT id, celex, updated_at, {', '.join(COLS)} FROM eu_laws "
                                                          "WHERE id = ANY(:i)"), {"i": ids}).mappings()}
        backup = ROOT / f"backend/data/backups/eu_laws_export_metadata_before_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        backup.write_text(json.dumps({"columns": ("id", "celex", "updated_at") + COLS, "rows_before": list(snap.values()),
                                      "restore": "set each column back by id inside a transaction with the switch on (migration 302)"},
                                     default=str))
        print(f"[OK] backup of {len(snap)} rows -> {backup.relative_to(ROOT)}")
        done = 0
        for j in range(0, len(fills), CHUNK):
            part = fills[j:j + CHUNK]
            # this transaction's id: the trigger keeps updated_at only inside this transaction (migration 302)
            db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
            cur = db.connection().connection.cursor()
            got = execute_values(cur, UPDATE, [(i,) + tuple(w[c] for c in COLS) for i, w in part],
                                 template=TEMPLATE, page_size=CHUNK, fetch=True)
            moved = [i for i, u in got if u != snap[i]["updated_at"]]
            check(len(got) == len(part), f"chunk {j // CHUNK}: updated {len(got)} of {len(part)}: rolled back")
            check(not moved, f"updated_at moved on {len(moved)} rows (first {moved[:5]}): rolled back")
            db.commit()
            done += len(got)
        print(f"[OK] committed: {done} laws filled in {(len(fills) + CHUNK - 1) // CHUNK} chunks, updated_at kept on all")
        left = plan(db)[0]
        print(f"[VERIFY] {before} -> {measure(db)} | still to fill: {len(left)}")
        return 0 if not left else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
