"""
Remove eu_news_items rows that repeat a story already stored under another URL.

The Commission publishes most releases on the presscorner AND on the DG's own site,
and DG newsrooms link either one, so the same story was stored twice (see
services/news/same_story.py). sync_dg_news now refuses the second copy at write
time; this clears the stock written before that guard existed.

Keeps the OLDEST row of each group (first seen), deletes the rest. Restricted by
default to COMMISSION (see DEFAULT_INSTITUTIONS): other bodies' groups have different causes (EEA's feed links internal hosts such as
10.140.162.18 and localhost:3000, 21 copies per story) and must be fixed at their
ingest, not hidden here.

No foreign key references eu_news_items (pg_constraint read 15 Sep 2026) and no
table holds its id or entry_key as a soft reference, but the script re-checks
pg_constraint on every run and refuses to delete if that has changed.

Usage:
    python3.12 -m scripts.dedupe_eu_news_same_story              # dry run
    python3.12 -m scripts.dedupe_eu_news_same_story --apply
    python3.12 -m scripts.dedupe_eu_news_same_story --institution COMMISSION --apply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text

from core.database import SessionLocal
from services.news.same_story import DUPLICATE_GROUPS_SQL

# COMMISSION only by default: it is where the presscorner/DG-site double publication
# happens. The one FRA "group" on 15 Sep 2026 was a Drupal `-0` twin dated 1 January,
# a placeholder date, so "same title, same day" is not evidence there.
DEFAULT_INSTITUTIONS = ["COMMISSION"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Delete (default: dry run).")
    ap.add_argument("--institution", action="append",
                    help="Institution to dedupe (repeatable). Default: COMMISSION.")
    args = ap.parse_args(argv)
    insts = args.institution or DEFAULT_INSTITUTIONS

    db = SessionLocal()
    try:
        fks = db.execute(text(
            "SELECT conrelid::regclass::text FROM pg_constraint "
            "WHERE confrelid = 'eu_news_items'::regclass")).fetchall()
        if fks:
            print(f"[ERROR] eu_news_items is referenced by {[r[0] for r in fks]}; "
                  "re-point those rows before deleting duplicates", file=sys.stderr)
            return 1

        groups = db.execute(text(
            f"SELECT * FROM ({DUPLICATE_GROUPS_SQL}) g WHERE institution = ANY(:insts) "
            "ORDER BY news_date DESC"), {"insts": insts}).fetchall()
        doomed = [i for g in groups for i in g.ids[1:]]
        print(f"[INFO] {len(groups)} duplicate groups, {len(doomed)} surplus rows "
              f"({', '.join(insts)})")
        for g in groups[:15]:
            print(f"  {g.news_date} {g.institution} keep {g.keys[0]}")
            for k in g.keys[1:]:
                print(f"      drop {k}")
        if not args.apply:
            print("[INFO] dry run; pass --apply to delete")
            return 0
        if not doomed:
            print("[OK] nothing to delete")
            return 0
        deleted = db.execute(text(
            "DELETE FROM eu_news_items WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": doomed}).rowcount
        db.commit()
        # Count what PERSISTED, not what was attempted.
        left = db.execute(text(
            f"SELECT count(*) FROM ({DUPLICATE_GROUPS_SQL}) g WHERE institution = ANY(:insts)"),
            {"insts": insts}).scalar()
        print(f"[OK] deleted {deleted} rows; duplicate groups remaining: {left}")
        if left:
            print("[ERROR] duplicate groups remain after delete", file=sys.stderr)
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
