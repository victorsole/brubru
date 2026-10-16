"""Commissioner-level meetings name their host, not the register's link text (16 Oct 2026).

/api/v2/commission/meetings served host_name "Information on meetings held by Commissioner
Jessika Roswall" on every meeting of a Commissioner's own page (3,477 rows): that page has no
"Commission representative" column, so the ingest fell back to the page's link text. The
ingest now writes member_name(); this rewrites the stored rows the same way. meeting_key is
generated from host_name, so it follows; run this only once the fixed ingest is deployed, or
the old one inserts the meetings again under the old name.

    python3.12 scripts/backfill_meeting_host_names.py            # dry run
    python3.12 scripts/backfill_meeting_host_names.py --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from scripts.ingest_transparency_meetings import member_name  # noqa: E402

ROWS = text("""SELECT DISTINCT host_name FROM transparency_meetings
               WHERE host_name ILIKE 'Information on meetings held by%'""")
STORE = text("""UPDATE transparency_meetings SET host_name = :new, last_updated = now()
                WHERE host_name = :old""")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        names = [r[0] for r in c.execute(ROWS)]
    plan = [(old, member_name(old)) for old in names]
    for old, new in plan:
        print(f"   {old[:70]!r} -> {new!r}")
    if not args.apply:
        print(f"[DRY RUN] {len(plan)} host name(s)")
        return 0
    n = 0
    with engine.begin() as c:
        for old, new in plan:
            n += c.execute(STORE, {"old": old, "new": new}).rowcount
    print(f"[DONE] {n} meetings renamed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
