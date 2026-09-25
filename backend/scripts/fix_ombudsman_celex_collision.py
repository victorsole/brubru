"""Two acts, one CELEX: 32013D0377 held the wrong one (GovClipping, 25 September 2026).

They reported: "/laws/32013D0377 returns the European Ombudsman election decision
(2013/377/EU, Euratom), but in EUR-Lex 32013D0377 is Decision No 377/2013/EU, which you
store under 32013L0377."

Both halves check out against Cellar:
  * the Ombudsman election decision of 3 July 2013 is 32013D0377(01), not 32013D0377
  * Decision No 377/2013/EU is 32013D0377, and we stored it under a Directive letter

So it is a swap, and it could not be done by the bulk correction: moving 32013L0377 to
32013D0377 was refused there because 32013D0377 was occupied. The occupant has to move
first, and only to the CELEX Cellar actually gives it.

Both rows are matched on their TITLE as well as their CELEX, so the script cannot touch a
different act if the data shifts under it, and both are backed up before anything changes.

Usage (from backend/):
    python3.12 scripts/fix_ombudsman_celex_collision.py            # dry run
    python3.12 scripts/fix_ombudsman_celex_collision.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

BACKUP_DIR = BACKEND.parent / "docs" / "backups"

MOVES = [
    # (current celex, title must contain, new celex, why)
    ("32013D0377", "electing the European Ombudsman", "32013D0377(01)",
     "Cellar gives the Ombudsman election decision the (01) suffix"),
    ("32013L0377", "Decision No 377/2013/EU", "32013D0377",
     "Decision No 377/2013/EU is a Decision, and this is its CELEX in Cellar"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        plan = []
        for old, needle, new, why in MOVES:
            rows = db.execute(text(
                "SELECT id, celex, left(coalesce(title,''),110) FROM eu_laws "
                "WHERE celex = :old AND title ILIKE :needle"),
                {"old": old, "needle": f"%{needle}%"}).fetchall()
            if len(rows) != 1:
                print(f"[ERROR] {old}: matched {len(rows)} row(s) on '{needle}', expected 1")
                return 1
            plan.append((rows[0][0], old, new, rows[0][2], why))
            print(f"   {old} -> {new}   ({why})\n        {rows[0][2][:88]}")

        if not args.apply:
            print("[DRY-RUN] re-run with --apply")
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out = BACKUP_DIR / f"eu_laws_ombudsman_swap_{stamp}.json"
        out.write_text(json.dumps(
            [{"id": i, "old_celex": o, "new_celex": n, "title": t} for i, o, n, t, _ in plan],
            indent=1), encoding="utf-8")
        print(f"[BACKUP] {out}")

        # The occupant moves first, by row id, so the second move has a free CELEX.
        for row_id, old, new, _title, _why in plan:
            db.execute(text("UPDATE eu_laws SET celex = :new, updated_at = now() WHERE id = :id"),
                       {"new": new, "id": row_id})
        db.commit()

        after = db.execute(text(
            "SELECT celex, left(coalesce(title,''),70) FROM eu_laws "
            "WHERE celex LIKE '32013D0377%' OR celex = '32013L0377' ORDER BY celex")).fetchall()
        print("[VERIFY]")
        for celex, title in after:
            print(f"   {celex:16} {title}")
        ok = {c for c, _ in after} == {"32013D0377", "32013D0377(01)"}
        print("[VERIFY] both acts now hold their own CELEX" if ok else "[ERROR] unexpected state")
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
