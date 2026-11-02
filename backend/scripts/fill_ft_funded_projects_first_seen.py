#!/usr/bin/env python3.12
"""Fill ft_funded_projects.first_seen once (migration 324, register O140), with the earliest stamp each row
holds: LEAST(scraped_at, last_updated). Nothing in the project changes, so each transaction sets
brubru.keep_change_signal and `last_updated` (the items' updated_date) does not move.

    python3.12 scripts/fill_ft_funded_projects_first_seen.py            # dry run: counts
    python3.12 scripts/fill_ft_funded_projects_first_seen.py --apply
"""
from __future__ import annotations

import argparse
import os
import time

from sqlalchemy import create_engine, text

BATCH = 1000
_FILL = text("""
    UPDATE ft_funded_projects SET first_seen = LEAST(scraped_at, last_updated)
     WHERE id IN (SELECT id FROM ft_funded_projects WHERE first_seen IS NULL LIMIT :n)""")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--pause", type=float, default=0.3, help="seconds between batches")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        left = c.execute(text("SELECT count(*) FROM ft_funded_projects WHERE first_seen IS NULL")).scalar()
    print(f"[INFO] rows to fill: {left}")
    if not args.apply:
        return 0
    done = 0
    while True:
        with engine.begin() as c:
            c.execute(text("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)"))
            n = c.execute(_FILL, {"n": BATCH}).rowcount
        done += n
        if not n:
            break
        if done % 10000 == 0:
            print(f"[INFO] filled {done}", flush=True)
        time.sleep(args.pause)
    print(f"[OK] filled {done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
