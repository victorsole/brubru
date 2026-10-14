#!/usr/bin/env python3.12
"""Make eu_laws.celex_year / celex_type / celex_number agree with eu_laws.celex on every row.

The three columns are a copy of the identifier and nothing kept them in step: older imports filled them from
the document text (some swapped year and number, some took the type from the wrong act), later CELEX fixes left
them stale, and the simple splitter left every suffixed identifier blank. Measured 14 Oct 2026: 26,199 rows
agree, 2,381 are blank, 2,074 disagree, 2 cannot be split (sector 5, two-letter type).

Rule (CELEX sector 3, the only shape these columns can hold): 3 + year (4 digits) + one type letter + number
(1 to 6 digits), optionally a sequence suffix "(NN)" and corrigendum suffixes "R(NN)". The parts are those of the
act the identifier names: 32021R0404R(05) -> 2021, R, 404; 32018D1004(02) -> 2018, D, 1004.
Rows whose CELEX does not fit are reported and left alone.

Safety: dry run by default. --apply writes a backup CSV of every row it changes first, updates in ONE
transaction only rows whose CELEX is still the one read (no race with the sync), asserts the row count, then
re-reads every row and stops with an error if any disagreement is left.

Usage (repo root):  python3.12 backend/scripts/fix_eu_laws_celex_parts.py [--apply]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import re
import sys
from collections import Counter

from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text

ROOT = pathlib.Path(__file__).resolve().parents[2]
PARTS = re.compile(r"^3(\d{4})([A-Z])(\d{1,6})(?:\(\d{2}\))?(?:R\(\d{2}\))*$")


def celex_parts(celex: str):
    m = PARTS.match(celex or "")
    return (int(m.group(1)), m.group(2), int(m.group(3))) if m else None


def classify(rows):
    out, changes = Counter(), []
    for uuid, celex, y, t, n in rows:
        want = celex_parts(celex)
        have = (y, t.strip() if t else None, n)
        if want is None:
            out["cannot be split"] += 1
        elif have == want:
            out["agree"] += 1
        else:
            out["blank" if have == (None, None, None) else "disagree"] += 1
            changes.append((uuid, celex, have, want))
    return out, changes


def database_url():
    return next(l.split("=", 1)[1].strip().strip('"') for l in (ROOT / ".env").read_text().splitlines() if l.startswith("DATABASE_URL="))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    eng = create_engine(database_url())
    q = "SELECT uuid, celex, celex_year, celex_type, celex_number FROM eu_laws WHERE celex IS NOT NULL AND celex <> ''"
    with eng.connect() as c:
        rows = c.execute(text(q)).fetchall()
    stats, changes = classify(rows)
    print(f"[INFO] rows with a CELEX: {len(rows)} | {dict(stats)} | to change: {len(changes)}")
    for u, cx, have, want in changes[:6]:
        print(f"  {cx:18s} {have} -> {want}")
    odd = [r[1] for r in rows if celex_parts(r[1]) is None]
    print(f"[INFO] left alone (cannot be split): {odd}")
    if not a.apply:
        print("[DRY-RUN] nothing written")
        return 0

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
    backup = ROOT / f"backend/data/backups/celex_parts_before_{ts}.csv"
    with backup.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["uuid", "celex", "old_year", "old_type", "old_number", "new_year", "new_type", "new_number"])
        for u, cx, have, want in changes:
            w.writerow([u, cx, *have, *want])
    print(f"[OK] backup of {len(changes)} rows -> {backup.relative_to(ROOT)}")

    raw = eng.raw_connection()
    try:
        cur = raw.cursor()
        execute_values(cur, """
            UPDATE eu_laws AS e SET celex_year = v.y, celex_type = v.t, celex_number = v.n
            FROM (VALUES %s) AS v(uuid, celex, y, t, n)
            WHERE e.uuid = v.uuid AND e.celex = v.celex""",
                       [(u, cx, want[0], want[1], want[2]) for u, cx, _, want in changes], page_size=len(changes) + 1)  # one statement, so rowcount is the total
        updated = cur.rowcount
        assert updated == len(changes), f"updated {updated}, expected {len(changes)}: rolled back"
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    print(f"[OK] updated {updated} rows in one transaction")

    with eng.connect() as c:
        after, left = classify(c.execute(text(q)).fetchall())
    print(f"[VERIFY] after: {dict(after)}")
    assert not left, f"{len(left)} rows still disagree after the update"
    print("[OK] every splittable CELEX now agrees with its year, type and number")
    return 0


if __name__ == "__main__":
    sys.exit(main())
