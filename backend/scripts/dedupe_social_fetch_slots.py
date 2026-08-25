#!/usr/bin/env python3.12
"""Stop fetching the same social feed twice.

WHY (audit, 25 August 2026)

23 (platform, handle) pairs had MORE THAN ONE `content_fetch_enabled` row, so
the drip spent two slots per cycle pulling one feed. 21 of the 23 were on X --
the platform whose refresh frontier had reached 17 days, with 820 of 1,155
accounts unchecked for a week or more. Deduplicating is therefore not tidiness;
it hands slots back to the queue that is starving.

The duplicates are the name-spelling problem migration 219 documented: the EP
roster writes surnames in caps and Wikidata uses title case, so the same person
arrives twice --

    "Bernd LANGE"                 and  "Q65437"
    "Emmanouil KEFALOGIANNIS"     and  "Manolis Kefalogiannis"
    "Juan Fernando LOPEZ AGUILAR" and  "Q941950"

Note the QIDs: some rows carry a Wikidata identifier in `entity_name`, which is
not a name at all.

WHAT THIS DOES

Keeps exactly one fetch-enabled row per (platform, lower(handle)) and clears
`content_fetch_enabled` on the rest. It does NOT delete anything -- a duplicate
row still records a real mapping, and deleting other loaders' rows blindly is
how mappings get silently lost.

Which row survives, in order:
  1. `verified` is true
  2. `entity_name` is a name, not a bare Wikidata QID
  3. most recently checked (it is the one the drip is actually using)
  4. lowest id, so the choice is deterministic

    python3.12 scripts/dedupe_social_fetch_slots.py            # dry run
    python3.12 scripts/dedupe_social_fetch_slots.py --apply
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

_QID_RE = re.compile(r"^Q\d+$")


def _rank(row):
    """Lower sorts first = kept."""
    return (
        0 if row.verified else 1,
        1 if _QID_RE.match((row.entity_name or "").strip()) else 0,
        -(row.last_checked_at.timestamp() if row.last_checked_at else 0),
        str(row.id),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    freed = 0
    try:
        groups = db.execute(text("""
            SELECT platform, lower(handle) AS h
            FROM social_accounts
            WHERE content_fetch_enabled AND handle IS NOT NULL AND handle <> ''
            GROUP BY 1, 2 HAVING count(*) > 1
            ORDER BY 1, 2
        """)).fetchall()

        print(f"groups fetching the same feed more than once: {len(groups)}\n")
        by_platform: dict[str, int] = {}

        for g in groups:
            rows = db.execute(text("""
                SELECT id, entity_name, verified, last_checked_at, discovery_source
                FROM social_accounts
                WHERE content_fetch_enabled AND platform = :p AND lower(handle) = :h
            """), {"p": g.platform, "h": g.h}).fetchall()

            keep, *drop = sorted(rows, key=_rank)
            print(f"  {g.platform:9} @{g.h[:30]:30}")
            print(f"     KEEP {str(keep.entity_name)[:34]:34} verified={keep.verified} "
                  f"src={keep.discovery_source}")
            for d in drop:
                print(f"     stop {str(d.entity_name)[:34]:34} verified={d.verified} "
                      f"src={d.discovery_source}")
                if args.apply:
                    db.execute(text("UPDATE social_accounts SET content_fetch_enabled=false, "
                                    "updated_at=now() WHERE id=:i"), {"i": d.id})
                freed += 1
                by_platform[g.platform] = by_platform.get(g.platform, 0) + 1

        if args.apply:
            db.commit()

        print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {freed} redundant fetch slot(s) "
              f"released")
        for p, n in sorted(by_platform.items(), key=lambda kv: -kv[1]):
            print(f"    {p}: {n}")
        print("Rows are NOT deleted -- they keep recording a real mapping, they just "
              "stop consuming a drip slot.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
