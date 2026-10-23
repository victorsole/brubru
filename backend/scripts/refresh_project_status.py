"""
Set the status of every EU-funded project from its source word and its own dates.

Runs in the daily tier (api/cron.py, _TENDERATOR_CHAIN): phases change as dates pass, while the
project loaders run rarely. The rule lives in services/funding/project_status.py. The tier records this
job's run; the script records none itself.

Run: python3.12 -m scripts.refresh_project_status [--apply]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal  # noqa: E402
from services.funding.project_status import refresh  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write (default: dry run).")
    args = ap.parse_args(argv)
    db = SessionLocal()
    try:
        moves = refresh(db, apply=args.apply)
    finally:
        db.close()
    for (old, new), n in sorted(moves.items(), key=lambda kv: -kv[1]):
        print(f"  {old or '(none)'} -> {new}: {n}")
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] {sum(moves.values())} project(s) "
          f"{'set' if args.apply else 'would change'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
