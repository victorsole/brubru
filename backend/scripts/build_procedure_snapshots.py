"""Phase 3, step 3.3 — daily procedure-snapshot CLI / cron entrypoint.

Builds + upserts one `procedure_snapshots` row per carriage for a given day.
Idempotent: safe to re-run; ON CONFLICT (carriage_id, snapshot_date) refreshes the row.

Usage:
    python3.12 scripts/build_procedure_snapshots.py                  # all carriages, today
    python3.12 scripts/build_procedure_snapshots.py --dry-run        # build only, no writes
    python3.12 scripts/build_procedure_snapshots.py --limit 50
    python3.12 scripts/build_procedure_snapshots.py --only "2022/0196(COD)" --force
    python3.12 scripts/build_procedure_snapshots.py --on 2026-06-27
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from core.database import SessionLocal  # noqa: E402
from services.snapshots.snapshot_writer import write_daily_snapshots  # noqa: E402
from services.snapshots.snapshot_bootstrap import bootstrap_from_oeil_events  # noqa: E402

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build daily procedure snapshots")
    ap.add_argument("--on", help="snapshot date YYYY-MM-DD (default today)")
    ap.add_argument("--only", help="single OEIL procedure ref, e.g. 2022/0196(COD)")
    ap.add_argument("--limit", type=int, help="cap number of carriages (testing)")
    ap.add_argument("--dry-run", action="store_true", help="build only, no DB writes")
    ap.add_argument("--bootstrap", action="store_true",
                    help="seed historical 'bootstrap' rows from oeil_key_events first")
    args = ap.parse_args()

    on = None
    if args.on:
        on = datetime.strptime(args.on, "%Y-%m-%d").date()

    db = SessionLocal()
    try:
        if args.bootstrap:
            boot = bootstrap_from_oeil_events(
                db, only=args.only, limit=args.limit, dry_run=args.dry_run
            )
            print(f"[OK] bootstrap {boot}")
        result = write_daily_snapshots(
            db, on=on, only=args.only, limit=args.limit, dry_run=args.dry_run
        )
    finally:
        db.close()

    print(f"[OK] daily {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
