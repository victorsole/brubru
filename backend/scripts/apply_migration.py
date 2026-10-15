#!/usr/bin/env python3.12
"""Apply one SQL migration file to the database in a single transaction (all or nothing).

The file is sent as written through the driver's own cursor, so ':' casts and '%' are not read as parameters.
Prints [OK] with the elapsed time, or the error and a rollback; exits non-zero on failure.

Usage (repo root):  PYTHONPATH=.:backend python3.12 -m backend.scripts.apply_migration backend/migrations/<file>.sql
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.database import engine  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    path = path if path.is_absolute() else ROOT / path
    if path.suffix != ".sql" or path.parent.name != "migrations" or not path.exists():
        print(f"[ERROR] not a migration file: {path}")
        return 2
    sql = path.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    t0 = time.time()
    try:
        cur = raw.cursor()
        cur.execute(sql)
        raw.commit()
        print(f"[OK] {path.name} applied in {time.time() - t0:.1f}s")
        return 0
    except Exception as e:
        raw.rollback()
        print(f"[ERROR] {path.name} rolled back: {type(e).__name__}: {str(e).strip()[:300]}")
        return 1
    finally:
        raw.close()


if __name__ == "__main__":
    sys.exit(main())
