#!/usr/bin/env python3.12
"""Notify users when a legislative file they track changes status.

Brubru had 613 carriage tracks and had never sent one of these. See
services/notifications/carriage_status_notifier.py for why, and migration 220
for the baseline column this depends on.

FIRST RUN MUST SEED
-------------------
    python3.12 scripts/notify_carriage_status.py --seed-baseline --dry-run
    python3.12 scripts/notify_carriage_status.py --seed-baseline

Seeding fills each track's baseline from the file's current status WITHOUT
notifying. Skipping it would fire 613 notifications at once, most about changes
nobody was watching for. After seeding, run without the flag:

    python3.12 scripts/notify_carriage_status.py

Restrict to one account (used for the Terraqui backfill):

    python3.12 scripts/notify_carriage_status.py --user-id <uuid>

Exit codes: 0 = clean, 1 = at least one track failed or the commit did not
land. A job that can fail must not exit 0.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from services.notifications.carriage_status_notifier import CarriageStatusNotifier  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed-baseline", action="store_true",
                        help="fill NULL baselines from current status without notifying")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute everything, persist nothing")
    # action="append", never nargs="+": three confirmed incidents in this repo
    # where a repeated flag silently overwrote its earlier values.
    parser.add_argument("--user-id", action="append", default=None,
                        help="restrict to one user; repeatable")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    user_ids = args.user_id or [None]
    failed = False
    for uid in user_ids:
        db = SessionLocal()
        try:
            run = CarriageStatusNotifier(db).run(
                seed_baseline=args.seed_baseline,
                dry_run=args.dry_run,
                user_id=uid,
            )
            scope = f" user={uid}" if uid else ""
            print(f"[carriage-notify]{scope} {run.summary()}")
            if run.skipped_no_baseline and not args.seed_baseline:
                print(f"  NOTE: {run.skipped_no_baseline} track(s) have no baseline yet. "
                      f"Run once with --seed-baseline before expecting notifications.")
            for err in run.errors:
                print(f"  ERROR {err}", file=sys.stderr)
            if not run.ok:
                failed = True
        finally:
            db.close()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
