#!/usr/bin/env python3.12
"""Remove the second copies of in_force, eli and entry_into_force from eu_laws.extra_metadata (17 Oct 2026).

sync_eu_laws_from_cellar.py wrote them there before the columns existed (migrations 301, 302), storing a missing
in-force flag as false: on 17 Oct 2026, 2,129 rows carried them and the in_force copy contradicted the column on 228.
The columns are the authority (backfill of 16 Oct, refreshed daily for in_force). Measured before removing: no side
ELI fills an empty column, the 7 that differ are the older publications.europa.eu/resource/eli form of the column's
data.europa.eu ELI, and the 2 side dates the columns lack are the placeholder 1001-01-01. Nothing reads the keys
since backfill_dpp_folder.py reads the column.

Removing them is not a change of the record (no served field changes), so the change signal is kept
(brubru.keep_change_signal, migration 302), as for the backfill. Dry run by default; --apply writes a JSON backup
of the removed values, updates in chunks of 500 rows in their own transactions, checks no updated_at moved, and
re-measures.

Usage (from backend/):  python3.12 scripts/drop_eu_laws_metadata_side_copies.py [--apply]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND.parent / ".env")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

KEYS = ("in_force", "eli", "entry_into_force")
CHUNK = 500
HAS = "extra_metadata ?| array['in_force', 'eli', 'entry_into_force']"
DROP = text("UPDATE eu_laws SET extra_metadata = extra_metadata - 'in_force' - 'eli' - 'entry_into_force' "
            f"WHERE id = ANY(:ids) AND {HAS} RETURNING id, updated_at")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        rows = db.execute(text(f"SELECT id, celex, updated_at, extra_metadata FROM eu_laws WHERE {HAS} ORDER BY id")).fetchall()
        db.rollback()
        print(f"[INFO] {len(rows)} rows carry a side copy of {', '.join(KEYS)}")
        if not a.apply or not rows:
            print("[INFO] dry run: nothing written" if not a.apply else "[OK] nothing to remove")
            return 0
        backup = BACKEND / "data" / "backups" / f"eu_laws_metadata_side_copies_{dt.datetime.now():%Y%m%d_%H%M}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(json.dumps([{"id": r.id, "celex": r.celex, **{k: (r.extra_metadata or {}).get(k) for k in KEYS
                                       if k in (r.extra_metadata or {})}} for r in rows], indent=1))
        print(f"[INFO] backup: {backup}")
        before = {r.id: r.updated_at for r in rows}
        done, moved = 0, []
        ids = [r.id for r in rows]
        for i in range(0, len(ids), CHUNK):
            db.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
            for rid, upd in db.execute(DROP, {"ids": ids[i:i + CHUNK]}).fetchall():
                done += 1
                if upd != before[rid]:
                    moved.append(rid)
            db.commit()
        left = db.execute(text(f"SELECT count(*) FROM eu_laws WHERE {HAS}")).scalar()
        db.rollback()
        print(f"[OK] removed from {done} rows; rows still carrying a copy: {left}; updated_at moved on {len(moved)}")
        if left or moved:
            print(f"[ERROR] expected 0 and 0 (moved: {moved[:10]})", file=sys.stderr)
            return 1
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
