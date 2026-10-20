#!/usr/bin/env python3.12
"""Set eu_laws.date to the date the act's title gives it, Cellar's date otherwise; a corrigendum gets Cellar's.

20 Oct 2026: 665 laws held a date that was neither. Read against every title (where title and Cellar differ, the act's signature sides with the title):

  - 540 corrigenda held the corrected act's date (the old parser read it from the corrigendum's title) or their
    Formex date, not their own (Cellar's work_date_document, the corrigendum's publication, which the others hold).
  - 125 acts held the old parser's misreadings (the OJ publication date, a date cited in the text) or Cellar's
    errors, copied by the importer and the daily sync: 32026R0144 "of 14 January 2026" held 2025-01-14 at Cellar.
  - 86 acts hold the right date while Cellar's is wrong (32013D0719 "of 16 November 2012": Cellar 2013-11-16):
    left as they are, listed.

The rule is leg_folder.act_date, which the importer, the repair script and the daily Cellar sync now apply. Cellar's
date is the LEG_2026-10 folder's tree_non_inferred.rdf (the export's own metadata); a row with no folder keeps its
stored date as Cellar's. Each write is skipped when another writer changed the date since it was read; updated_at
moves (a corrected date partners should receive). Dry run unless --apply.

Usage (from backend/):
    python3.12 scripts/fix_eu_laws_dates.py [--apply] [--backup] [--dump PATH]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))  # production runs with PYTHONPATH=/app (the backend folder)

CHUNK = 200
UPDATE = """UPDATE eu_laws e SET date = v.new::date
FROM (VALUES %s) AS v(id, old, new)
WHERE e.id = v.id AND e.date IS NOT DISTINCT FROM v.old::date
RETURNING e.id"""


def changes_for(rows, recorded_of):
    """(id, celex, stored, new, how) for every row whose date the rule changes; (id, celex, stored, cellar) where the
    stored date is the title's and Cellar's differs."""
    from scripts.leg_folder import act_date
    out, cellar_wrong = [], []
    for i, celex, uuid, stored, title, version in rows:
        recorded = recorded_of(uuid, version) or stored
        new = act_date(celex, title, recorded)
        if new and new != stored:
            out.append((i, celex, stored, new, "corrigendum" if re.search(r"R\(\d{2}\)$", celex) else "act"))
        elif recorded != stored:
            cellar_wrong.append((i, celex, stored, recorded))
    return out, cellar_wrong


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", action="store_true", help="write the replaced dates to backend/data/backups first")
    ap.add_argument("--dump", default=str(BACKEND.parent / "docs/LEG_2026-10"), help="the LEG_2026-10 folders")
    a = ap.parse_args()
    import logging
    from dotenv import load_dotenv
    load_dotenv(BACKEND.parent / ".env")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    from psycopg2.extras import execute_values
    from sqlalchemy import text
    from core.database import SessionLocal
    from scripts.leg_folder import rdf_meta
    dump = Path(a.dump)
    if not dump.is_dir():
        print(f"[ERROR] no LEG_2026-10 folders at {dump}", file=sys.stderr)
        return 2

    def recorded_of(uuid, version):
        if (version or "").startswith("LEG_2026-10") and uuid and (dump / uuid).is_dir():
            return rdf_meta(dump, uuid)["date"]
        return None

    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, celex, uuid, date::text, title, corpus_version FROM eu_laws "
                               "WHERE coalesce(celex, '') <> '' ORDER BY id")).fetchall()
        db.rollback()
        changes, cellar_wrong = changes_for(rows, recorded_of)
        print(f"[INFO] {len(rows)} laws read | to change: {len(changes)} "
              f"{dict(collections.Counter(c[4] for c in changes))} | stored right, Cellar wrong: {len(cellar_wrong)}")
        for c in changes[:8]:
            print(f"[INFO]   e.g. {c[1]}: {c[2]} -> {c[3]} ({c[4]})")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0
        if a.backup and changes:
            path = BACKEND / f"data/backups/eu_laws_dates_before_{dt.datetime.now():%Y%m%d_%H%M}.json"
            path.parent.mkdir(parents=True, exist_ok=True)  # untracked: absent from a fresh checkout
            path.write_text(json.dumps({"columns": ["id", "celex", "date_before", "date_after", "kind"], "rows": changes,
                                        "cellar_wrong": {"columns": ["id", "celex", "date", "cellar"],
                                                         "rows": cellar_wrong},
                                        "restore": "set date back to date_before by id"}))
            print(f"[OK] backup of {len(changes)} rows -> {path.relative_to(BACKEND.parent)}")
        done = 0
        for j in range(0, len(changes), CHUNK):
            part = [(c[0], c[2], c[3]) for c in changes[j:j + CHUNK]]
            cur = db.connection().connection.cursor()
            got = execute_values(cur, UPDATE, part, template="(%s, %s, %s)", page_size=len(part), fetch=True)
            db.commit()
            done += len(got)
            time.sleep(0.2)
        print(f"[OK] written: {done} of {len(changes)} (a row another writer changed meanwhile is left)")
        return 0 if done == len(changes) else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
