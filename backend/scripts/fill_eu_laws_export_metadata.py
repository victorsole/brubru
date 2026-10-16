#!/usr/bin/env python3.12
"""Fill eu_laws' metadata columns (migrations 301, 302) from the Publications Office's metadata, without moving updated_at.

Victor, 16 Oct 2026: "05 eur-lex/laws" serves the LEG_2026-10 export's datapoints; filling them is not a change of the
record, so a client syncing by updated_from must not receive 30,000 laws again. Sources (leg_export_metadata):
  - the laws the export holds (a folder with or without text): each folder's tree_non_inferred.rdf (rdf_facts);
  - the laws it does not hold: Cellar (cellar_facts: authors, ELI, typed dates, in force, procedures);
  - procedures for every law: the export's links, Cellar's dossier_contains_work and the OEIL references of
    legislative_carriages (Brubru's Legislative Observatory data), together;
  - alias and acronym: Brubru's curated aliases.csv.
Cellar answers are cached in backend/data/leg_2026-10_table/cellar_facts.json.

What it writes, all with the change signal kept (brubru.keep_change_signal = this transaction's id, migration 302):
  - an empty column the sources fill;
  - a column this script filled earlier that the sources now give differently (second pass, 16 Oct 2026: the
    placeholders 1001-01-01 and 1002-02-02 dropped, MA/PROV and APPLICATION dates moved to application_dates,
    lettered procedures such as 2011/0901A kept, procedures added from Cellar and OEIL). This script is these
    columns' only writer so far; a value from another writer is reported and left.
in_force, once set, is never changed here: refresh_eu_laws_in_force.py owns it (a law entering or leaving force is
a change of the record, so that job moves updated_at).

Dry run by default. --apply writes a JSON backup of the columns it changes, updates in chunks of 500 rows in their
own transactions, checks that no touched row's updated_at moved, and re-measures.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.fill_eu_laws_export_metadata [--apply]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.scripts.fix_eu_laws_2025_leftovers import check  # noqa: E402
from backend.scripts.leg_export_metadata import (COLS, ROOT, TABLES, aliases, cellar_facts,  # noqa: E402
                                                 folder_of_celex, rdf_facts)

CORPUS = ROOT / "docs/LEG_2026-10"
CACHE = TABLES / "cellar_facts.json"
CHUNK = 500
# each row names the columns it changes (v.cols); the others keep their live value, so a writer that changed one during
# the run is not overwritten with what this script read minutes earlier
UPDATE = ("UPDATE eu_laws e SET " + ", ".join(f"{c} = CASE WHEN '{c}' = ANY(v.cols) THEN v.{c} ELSE e.{c} END" for c in COLS) +
          f" FROM (VALUES %s) AS v (id, cols, {', '.join(COLS)}) WHERE e.id = v.id RETURNING e.id, e.updated_at")
TEMPLATE = "(%s, %s::text[], %s, %s, %s::text[], %s::boolean, %s, %s::date[], %s::date[], %s::date[], %s::text[])"


def _facts(folder):
    return folder, rdf_facts(CORPUS, folder)


def carriage_procedures(db) -> dict:
    """{CELEX: {YYYY/NNNN}} from the OEIL references Brubru holds (legislative_carriages): 288 of 288 agree with Cellar."""
    out = {}
    for ref, celexes in db.execute(text("SELECT oeil_procedure_ref, celex_numbers FROM legislative_carriages "
                                        "WHERE oeil_procedure_ref IS NOT NULL AND celex_numbers IS NOT NULL")).fetchall():
        m = re.match(r"\s*(\d{4})/0*(\d{1,4})([A-Z]?)\(", ref or "")
        for c in (celexes or []) if m else []:
            out.setdefault(c, set()).add(f"{m[1]}/{int(m[2]):04d}{m[3]}")
    return out


def plan(db):
    rows = db.execute(text(f"SELECT id, celex, {', '.join(COLS)} FROM eu_laws "
                           "WHERE coalesce(celex, '') <> '' ORDER BY id")).mappings().all()
    folders, names = folder_of_celex(), aliases()
    held = sorted({folders[r["celex"]] for r in rows if r["celex"] in folders})
    with mp.Pool(8) as pool:
        facts = dict(pool.map(_facts, held, chunksize=100))
    outside = [r["celex"] for r in rows if r["celex"] not in folders]
    remote = cellar_facts([r["celex"] for r in rows], groups=("dossier",), cache=CACHE)
    remote_full = cellar_facts(outside, groups=("dossier", "work", "dates"), cache=CACHE)
    oeil = carriage_procedures(db)
    blank = {k: None for k in COLS}
    changes, kept, why = [], [], collections.Counter()
    for r in rows:
        c = r["celex"]
        stored = {k: [str(x) for x in r[k]] if isinstance(r[k], list) else r[k] for k in COLS}
        if c in folders:
            w = {**blank, **facts[folders[c]]}
        elif c in remote_full:
            w = {**blank, **{k: v for k, v in remote_full[c].items() if k in COLS}}
        else:
            w = dict(stored)  # Cellar did not answer for this law in this run: what is stored stays, never blanked
        w["alias"], w["acronym"] = names.get(c, (None, None))
        procs = set(w["procedures"] or []) | set((remote.get(c) or {}).get("procedures") or []) | oeil.get(c, set())
        if c not in remote:
            procs |= set(stored["procedures"] or [])  # Cellar's procedures unknown in this run: keep the stored ones
        w["procedures"] = sorted(procs) or None
        if w["in_force"] is None and c in remote:
            w["in_force"] = remote[c]["in_force"]
        new = {}
        for k, v in w.items():
            have = stored[k]
            if have == v or v is None and r[k] is None:
                continue
            if k == "in_force" and r[k] is not None:
                kept.append((r["id"], c, k, have, v))  # refresh_eu_laws_in_force.py owns a set in_force
                continue
            new[k] = v
            why[("fill " if r[k] is None else "correct ") + k] += 1
        if new:
            changes.append((r["id"], new))
    return changes, kept, why, len(rows), len(outside)


MEASURE = ("SELECT " + ", ".join(f"count({c})" for c in COLS) + ", count(*) FILTER (WHERE in_force), "
           "count(*) FILTER (WHERE NOT in_force), count(*) FROM eu_laws WHERE coalesce(celex, '') <> ''")


def measure(db) -> str:
    a = db.execute(text(MEASURE)).one()
    filled = ", ".join(f"{c} {a[i]}" for i, c in enumerate(COLS))
    return f"{filled} (in force: true {a[len(COLS)]}, false {a[len(COLS) + 1]}) of {a[-1]} laws"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        before = measure(db)
        db.rollback()  # end the read transaction: no lock held while the RDF and Cellar are read
        changes, kept, why, n, outside = plan(db)
        db.rollback()
        print(f"[INFO] {n} laws with a CELEX ({outside} outside the export, read from Cellar) | rows to write: {len(changes)}")
        for k, v in sorted(why.items()):
            print(f"[INFO]   {v:6d}  {k}")
        print(f"[INFO] in_force set and different at the source, left to refresh_eu_laws_in_force.py: {len(kept)} {kept[:3]}")
        print(f"[INFO] now: {before}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        ids = [i for i, _ in changes]
        snap = {r["id"]: dict(r) for r in db.execute(text(f"SELECT id, celex, updated_at, {', '.join(COLS)} FROM eu_laws "
                                                          "WHERE id = ANY(:i)"), {"i": ids}).mappings()}
        backup = ROOT / f"backend/data/backups/eu_laws_export_metadata_before_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        backup.write_text(json.dumps({"columns": ("id", "celex", "updated_at") + COLS, "rows_before": list(snap.values()),
                                      "restore": "set each column back by id inside a transaction with the switch on (migration 302)"},
                                     default=str))
        db.rollback()
        print(f"[OK] backup of {len(snap)} rows -> {backup.relative_to(ROOT)}")
        done = 0
        for j in range(0, len(changes), CHUNK):
            part = changes[j:j + CHUNK]
            # this transaction's id: the trigger keeps updated_at only inside this transaction (migration 302)
            db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
            cur = db.connection().connection.cursor()
            got = execute_values(cur, UPDATE, [(i, sorted(w)) + tuple(w.get(c) for c in COLS) for i, w in part],
                                 template=TEMPLATE, page_size=CHUNK, fetch=True)
            moved = [i for i, u in got if u != snap[i]["updated_at"]]
            check(len(got) == len(part), f"chunk {j // CHUNK}: updated {len(got)} of {len(part)}: rolled back")
            check(not moved, f"updated_at moved on {len(moved)} rows (first {moved[:5]}): rolled back")
            db.commit()
            done += len(got)
        print(f"[OK] committed: {done} laws written in {(len(changes) + CHUNK - 1) // CHUNK} chunks, updated_at kept on all")
        left = plan(db)[0]
        db.rollback()
        print(f"[VERIFY] {before} -> {measure(db)} | still to write: {len(left)}")
        return 0 if not left else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
