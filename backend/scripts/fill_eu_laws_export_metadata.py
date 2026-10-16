#!/usr/bin/env python3.12
"""Fill eu_laws' metadata columns (migration 293) from the LEG_2026-10 export's own tables, without moving updated_at.

Victor, 16 Oct 2026: "05 eur-lex/laws" serves the export's datapoints; filling them is not a change of the record,
so a client syncing by updated_from must not receive 30,000 laws again. Sources, all built from the export's
metadata (tree_non_inferred.rdf of each folder) and audited on 14 Oct 2026, in backend/data/leg_2026-10_table/:
  - leg_2026-10_table.csv: authors (work_created_by_agent codes), in_force (resource_legal_in-force; 'unknown'
    stays NULL), eli (the URI that belongs to this publication);
  - leg_2026-10_folders.csv: entry_into_force dates, and the interinstitutional procedure numbers ('procedure:'
    links only; 'internal_proc' hashes and 'pegase' budget ids are not procedures a client can look up);
  - aliases.csv: alias and acronym (curated, the only source; never derived).
A law the export does not describe keeps NULL, except in_force = false for rows marked 'repealed', which the
importer marks only when Cellar's in-force flag is 0. Acts the daily OJ sync added after 11 Oct stay NULL until that
sync fills them (step 5, later).

Dry run by default. --apply writes a JSON backup of the columns it changes, updates in chunks of 500 rows, each
chunk in its own transaction with SET LOCAL brubru.keep_change_signal = 'on' (migration 293), checks that no
touched row's updated_at moved, and re-measures. Needs migration 293.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.fill_eu_laws_export_metadata [--apply]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.scripts.fix_eu_laws_2025_leftovers import check  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "backend/data/leg_2026-10_table"
COLS = ("alias", "acronym", "authors", "in_force", "eli", "entry_into_force", "procedures")
CHUNK = 500
UPDATE = ("UPDATE eu_laws e SET alias = v.alias, acronym = v.acronym, authors = v.authors, in_force = v.in_force, "
          "eli = v.eli, entry_into_force = v.entry_into_force, procedures = v.procedures "
          "FROM (VALUES %s) AS v (id, alias, acronym, authors, in_force, eli, entry_into_force, procedures) "
          "WHERE e.id = v.id RETURNING e.id, e.updated_at")
TEMPLATE = "(%s, %s, %s, %s::text[], %s::boolean, %s, %s::date[], %s::text[])"


def procedure_numbers(cell: str) -> list:
    """'procedure:2019_145|internal_proc:ABC...' -> ['2019/0145'] (the OEIL reference without its type)."""
    out = []
    for p in (cell or "").split("|"):
        m = re.fullmatch(r"procedure:(\d{4})_0*(\d{1,4})", p.strip())
        if m:
            out.append(f"{m[1]}/{int(m[2]):04d}")
    return sorted(set(out))


def sources():
    table = {r["CELEX"]: r for r in csv.DictReader((TABLES / "leg_2026-10_table.csv").open(encoding="utf-8-sig"))}
    folders = {r["celex"]: r for r in csv.DictReader((TABLES / "leg_2026-10_folders.csv").open(encoding="utf-8-sig")) if r["celex"]}
    aliases = {r["celex"]: r for r in csv.DictReader((TABLES / "aliases.csv").open(encoding="utf-8-sig"))}
    return table, folders, aliases


def wanted(celex, status, table, folders, aliases) -> dict:
    """The values the export states for one law; None where it states nothing."""
    t, f, a = table.get(celex), folders.get(celex), aliases.get(celex)
    v = dict.fromkeys(COLS)
    if a:
        v["alias"], v["acronym"] = (a.get("alias") or "").strip() or None, (a.get("acronym") or "").strip() or None
    if t:
        v["authors"] = [x for x in (t.get("author") or "").split("|") if x] or None
        v["in_force"] = {"true": True, "false": False}.get((t.get("in_force") or "").strip())
        v["eli"] = (t.get("eli") or "").strip() or None
    elif status == "repealed":
        v["in_force"] = False  # marked repealed by the importer only when Cellar's in-force flag is 0
    if f:
        v["entry_into_force"] = sorted({d for d in (f.get("entry_into_force") or "").split("|") if d}) or None
        v["procedures"] = procedure_numbers(f.get("procedures")) or None
    return v


def norm(v):
    return [str(x) for x in v] if isinstance(v, list) else v


def plan(db):
    table, folders, aliases = sources()
    rows = db.execute(text(f"SELECT id, celex, corpus_status, {', '.join(COLS)} FROM eu_laws "
                           "WHERE coalesce(celex, '') <> '' ORDER BY id")).mappings().all()
    changes, why = [], collections.Counter()
    for r in rows:
        w = wanted(r["celex"], r["corpus_status"], table, folders, aliases)
        if any(norm(w[c]) != norm(r[c]) for c in COLS):
            changes.append((r["id"], w))
            why["in the export" if r["celex"] in table else "repealed, not in the export" if w["in_force"] is False else "alias only"] += 1
        elif r["celex"] not in table:
            why["not in the export: left NULL"] += 1
    return changes, why, len(rows)


MEASURE = ("SELECT count(alias), count(acronym), count(authors), count(in_force), count(*) FILTER (WHERE in_force), "
           "count(eli), count(entry_into_force), count(procedures), count(*) FROM eu_laws WHERE coalesce(celex, '') <> ''")


def measure(db) -> str:
    a = db.execute(text(MEASURE)).one()
    return (f"alias {a[0]}, acronym {a[1]}, authors {a[2]}, in_force {a[3]} (true {a[4]}), eli {a[5]}, "
            f"entry_into_force {a[6]}, procedures {a[7]}, of {a[8]} laws")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        before = measure(db)
        changes, why, n = plan(db)
        print(f"[INFO] {n} laws with a CELEX | to fill: {len(changes)} | now: {before}")
        for k, v in why.most_common():
            print(f"[INFO]   {v:6d}  {k}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        ids = [i for i, _ in changes]
        snap = {r["id"]: dict(r) for r in db.execute(text(f"SELECT id, celex, updated_at, {', '.join(COLS)} FROM eu_laws "
                                                          "WHERE id = ANY(:i)"), {"i": ids}).mappings()}
        backup = ROOT / f"backend/data/backups/eu_laws_export_metadata_before_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        backup.write_text(json.dumps({"columns": ("id", "celex", "updated_at") + COLS, "rows_before": list(snap.values())}, default=str))
        print(f"[OK] backup of {len(snap)} rows -> {backup.relative_to(ROOT)}")
        done, moved = 0, []
        for j in range(0, len(changes), CHUNK):
            part = changes[j:j + CHUNK]
            db.execute(text("SET LOCAL brubru.keep_change_signal = 'on'"))  # this transaction only (migration 293)
            cur = db.connection().connection.cursor()
            got = execute_values(cur, UPDATE, [(i,) + tuple(w[c] for c in COLS) for i, w in part],
                                 template=TEMPLATE, page_size=CHUNK, fetch=True)
            check(len(got) == len(part), f"chunk {j // CHUNK}: updated {len(got)} of {len(part)}: rolled back")
            moved += [i for i, u in got if u != snap[i]["updated_at"]]
            check(not moved, f"updated_at moved on {len(moved)} rows (first {moved[:5]}): rolled back")
            db.commit()
            done += len(got)
        print(f"[OK] committed: {done} laws filled in {(len(changes) + CHUNK - 1) // CHUNK} chunks, updated_at kept on all")
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
