#!/usr/bin/env python3.12
"""Delete the 6 LEG_2025-11 rows that are not laws and are absent from the October 2026 export (15 Oct 2026).

Found by the audit of fix_eu_laws_2025_leftovers.py (same rule, Victor's choice "delete all 6", 15 Oct 2026):
  - 4 corrigenda still marked 'active': 32024D05865R(01) and R(02) (a 2024 Council decision appointing members
    of an advisory committee), 32025R0612R(01), 32025R0219R(01) (the 2025 fishing opportunities);
  - 2 acts that are not binding acts by the canonical definition, marked 'repealed': 32004E0493 (a CFSP common
    position, ended 31 Jan 2026 at Cellar) and 32025B0031 (the 2025 budget, ended 31 Dec 2025).
None has an EU Law Comply link. Their xml_path points at the deleted docs/LEG_2025-11 copy.

Dry run by default. --apply writes a JSON backup (all columns), checks that no other column holds the rows'
uuids or ids (the scan of fix_eu_laws_2025_leftovers.py), deletes in one transaction and re-measures.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.delete_eu_laws_2025_non_laws [--apply]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from backend.core.database import SessionLocal  # noqa: E402
from backend.models.eu_law import EULaw  # noqa: E402
from backend.scripts.fix_eu_laws_2025_leftovers import check, other_references  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ROOT / "backend/data/leg_2026-10_table/leg_2026-10_folders.csv"
DROP = {239: "32024D05865R(01)", 391: "32004E0493", 3495: "32025B0031",
        13959: "32025R0612R(01)", 16073: "32024D05865R(02)", 18680: "32025R0219R(01)"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        ids = list(DROP)
        rows = db.execute(text("SELECT id, uuid, celex, corpus_version FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).fetchall()
        check(len(rows) == len(DROP) and all(DROP[i] == c and v == "LEG_2025-11" for i, _, c, v in rows), f"the rows moved: {rows}")
        in_export = {r["celex"] for r in csv.DictReader(FOLDERS.open(encoding="utf-8-sig"))} & set(DROP.values())
        hits, n_cols = other_references(db, [u for _, u, _, _ in rows], ids)
        print(f"[INFO] delete {len(rows)}: {sorted(DROP.values())} | in the October export: {sorted(in_export)} | references in {n_cols} columns: {hits}")
        check(not in_export, f"in the October export: {in_export}")
        check(not hits, f"referenced: {hits}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0

        cols = [c.name for c in EULaw.__table__.columns if c.name != "search_vector"]
        before = [dict(r) for r in db.execute(text(f"SELECT {', '.join(cols)} FROM eu_laws WHERE id = ANY(:i)"), {"i": ids}).mappings()]
        backup = ROOT / f"backend/data/backups/eu_laws_2025_non_laws_before_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        backup.write_text(json.dumps({"rows_before": before}, default=str, indent=1))
        print(f"[OK] backup of {len(before)} rows -> {backup.relative_to(ROOT)}")
        n0 = db.execute(text("SELECT count(*) FROM eu_laws")).scalar()
        n = db.execute(text("DELETE FROM eu_laws WHERE id = ANY(:i) AND corpus_version = 'LEG_2025-11'"), {"i": ids}).rowcount
        n1 = db.execute(text("SELECT count(*) FROM eu_laws")).scalar()
        check(n == len(DROP) and n0 - n1 == len(DROP), f"deleted {n}, count {n0} -> {n1}: rolled back")
        db.commit()
        left = db.execute(text("SELECT corpus_status, count(*) FROM eu_laws WHERE corpus_version = 'LEG_2025-11' GROUP BY 1 ORDER BY 1")).fetchall()
        print(f"[VERIFY] eu_laws {n1} | LEG_2025-11 left: {left}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
