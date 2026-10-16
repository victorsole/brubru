#!/usr/bin/env python3.12
"""Keep eu_laws.in_force equal to Cellar's in-force flag, daily; the column's only writer once it is set.

Audit of 16 Oct 2026: in_force was a snapshot of the LEG_2026-10 export (11 Oct) that nothing refreshed; 10 laws it
flagged in force had expired by 16 Oct (32021R1413...), and laws flagged not in force enter into force within weeks
(32026R2301 on 4 Nov). This job reads Cellar's resource_legal_in-force for every law with a CELEX (leg_export_metadata
.cellar_facts, 80 per call, each call checked by a control law), slice by slice, and writes each slice as it comes:
  - a flag that differs from the stored one: a change of the record (a law entering or leaving force), so updated_at
    moves and brubru_change_log records 'in_force';
  - a flag where the column is empty (a new act Cellar has now flagged): a fill, so the change signal is kept, the
    rule of the backfill (Victor, 16 Oct 2026);
  - no flag from Cellar: the stored value stays (unknown is not false).
It stops with a reason, keeping what it wrote, when Cellar fails the control on several calls in a row or the time
budget (20 min, under the cron's 30) runs out, and exits 1 then or when Cellar returned under 90% of the laws.

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
from scripts.leg_export_metadata import Budget, CellarDown, cellar_facts  # noqa: E402

SLICE = 2000
BUDGET_SECONDS = 1200
MIN_ANSWERED = 0.90
UPDATE = ("UPDATE eu_laws e SET in_force = v.f FROM (VALUES %s) AS v (id, f) "
          "WHERE e.id = v.id AND e.in_force IS DISTINCT FROM v.f RETURNING e.id")


def write(db, pairs: list, keep_signal: bool) -> int:
    """One transaction per call; keep_signal sets the switch of migration 302 for this transaction only."""
    if not pairs:
        return 0
    if keep_signal:
        db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
    cur = db.connection().connection.cursor()
    n = len(execute_values(cur, UPDATE, pairs, template="(%s, %s::boolean)", page_size=len(pairs), fetch=True))
    db.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N laws (a test run)")
    a = ap.parse_args()
    db = SessionLocal()
    budget = Budget(BUDGET_SECONDS)
    seen = changed = filled = to_true = 0
    stopped = None
    try:
        rows = db.execute(text("SELECT id, celex, in_force FROM eu_laws WHERE coalesce(celex, '') <> '' ORDER BY id")).fetchall()
        db.rollback()  # no transaction open while Cellar is read
        rows = rows[:a.limit] if a.limit else rows
        print(f"[INFO] {len(rows)} laws to check against Cellar", flush=True)
        for j in range(0, len(rows), SLICE):
            part = rows[j:j + SLICE]
            try:
                flags = cellar_facts([c for _, c, _ in part], groups=("dossier",), budget=budget, log=lambda m: None)
            except CellarDown as e:
                stopped = str(e)
                break
            seen += sum(1 for _, c, _ in part if (flags.get(c) or {}).get("seen"))
            news = [(i, cur, flags[c]["in_force"]) for i, c, cur in part if c in flags and flags[c]["in_force"] is not None]
            changes = [(i, f) for i, cur, f in news if cur is not None and f != cur]
            fills = [(i, f) for i, cur, f in news if cur is None]
            to_true += sum(1 for _, f in changes if f)
            if a.apply:
                changed += write(db, changes, keep_signal=False)
                filled += write(db, fills, keep_signal=True)
            else:
                changed, filled = changed + len(changes), filled + len(fills)
            print(f"[INFO]   {min(j + SLICE, len(rows))} of {len(rows)} checked", flush=True)
        verb = "written" if a.apply else "to write (dry run)"
        print(f"[INFO] Cellar returned {seen} of {len(rows)} laws ({seen / max(len(rows), 1):.1%}) | in_force {verb}: "
              f"{changed} changed (now in force {to_true}, no longer or not yet in force {changed - to_true}; updated_at "
              f"moved), {filled} filled (updated_at kept)")
        if stopped:
            print(f"[ERROR] stopped early: {stopped}; what was written stays", file=sys.stderr)
            return 1
        if seen < MIN_ANSWERED * len(rows):
            print(f"[ERROR] Cellar returned under {MIN_ANSWERED:.0%} of the laws: run again", file=sys.stderr)
            return 1
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
