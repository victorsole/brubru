#!/usr/bin/env python3.12
"""Keep eu_laws.in_force equal to Cellar's in-force flag, daily; the column's only writer once it is set.

Audit of 16 Oct 2026: in_force was a snapshot of the LEG_2026-10 export (11 Oct) that nothing refreshed; 10 laws it
flagged in force had expired by 16 Oct (32021R1413...), and laws flagged not in force enter into force within weeks
(32026R2301 on 4 Nov). This job reads Cellar's resource_legal_in-force for every law with a CELEX (leg_export_metadata
.cellar_facts, 80 per call, each call checked by a control law) and writes the flag where it differs, or where the
column is empty. A law entering or leaving force is a change of the record, so updated_at moves and brubru_change_log
records 'in_force' (no keep_change_signal here). A law Cellar gives no flag for keeps its value: unknown is not false.
It exits 1 when Cellar answered for under 90% of the laws, after writing what it got.

Daily tier (api/cron.py, key eu_laws_in_force). Usage (from backend/):
    python3.12 scripts/refresh_eu_laws_in_force.py [--apply] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))  # production runs with PYTHONPATH=/app (the backend folder)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND.parent / ".env")

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from scripts.leg_export_metadata import cellar_facts  # noqa: E402

CHUNK = 500
MIN_ANSWERED = 0.90
UPDATE = ("UPDATE eu_laws e SET in_force = v.f FROM (VALUES %s) AS v (id, f) "
          "WHERE e.id = v.id AND e.in_force IS DISTINCT FROM v.f RETURNING e.id")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N laws (a test run)")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, celex, in_force FROM eu_laws WHERE coalesce(celex, '') <> '' ORDER BY id")).fetchall()
        db.rollback()  # no transaction open while Cellar is read
        rows = rows[:a.limit] if a.limit else rows
        flags = cellar_facts([c for _, c, _ in rows], groups=("dossier",), log=lambda m: print(m, flush=True))
        answered = [(i, c, cur, flags[c]["in_force"]) for i, c, cur in rows if c in flags]
        changes = [(i, new) for i, c, cur, new in answered if new is not None and new != cur]
        to_true = sum(1 for _, new in changes if new)
        print(f"[INFO] {len(rows)} laws | Cellar answered for {len(answered)} ({len(answered) / max(len(rows), 1):.1%}), "
              f"with a flag for {sum(1 for *_, f in answered if f is not None)} | to change: {len(changes)} "
              f"(now in force {to_true}, no longer or not yet in force {len(changes) - to_true})")
        for i, new in changes[:5]:
            print(f"[INFO]   id {i} -> in_force {new}")
        if a.apply and changes:
            done = 0
            for j in range(0, len(changes), CHUNK):
                cur = db.connection().connection.cursor()
                done += len(execute_values(cur, UPDATE, changes[j:j + CHUNK], template="(%s, %s::boolean)",
                                           page_size=CHUNK, fetch=True))
                db.commit()
            print(f"[OK] in_force written on {done} laws (updated_at moved on each)")
        elif not a.apply:
            print("[DRY-RUN] nothing written")
        if len(answered) < MIN_ANSWERED * len(rows):
            print(f"[ERROR] Cellar answered for under {MIN_ANSWERED:.0%} of the laws: run again", file=sys.stderr)
            return 1
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
