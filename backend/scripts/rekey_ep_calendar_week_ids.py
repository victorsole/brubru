"""
Re-key the EP calendar rows that still carry a week-number external_id.

Companion to dedup_ep_calendar_plenary.py (3 September 2026). That script fixed
the per-day PLENARY rows. Two other branches of ep_calendar_loader.py built the
id the same unstable way:

    ep_{year}_w{week_num}_{day}_{activity}    mixed weeks, one row per day
    ep_{year}_w{week_num}_{activity}          whole-week rows (recess, committee
                                              week, group week)

`week_num` comes from the source JSON, not from the date. When the EP relabels a
week the id changes, the unique index sees an unseen key, and the same event is
inserted a second time. That is how 133 duplicate rows accumulated.

The loader now derives all three from the date. This re-keys the rows written
under the old scheme so the next sync UPDATES them instead of inserting a third
copy. Without this step the code fix makes things worse, not better.

Usage:
    python3.12 scripts/rekey_ep_calendar_week_ids.py --dry-run   # default
    python3.12 scripts/rekey_ep_calendar_week_ids.py --apply
"""
import argparse
import os
import pathlib
import re
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import psycopg2
from dotenv import load_dotenv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[ERROR] DATABASE_URL not set; aborting rather than guessing.")
        return 2

    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, external_id, start_date::date, ep_activity_type, title
        FROM eu_calendar_events
        WHERE source = 'ep_calendar_json' AND external_id ~ '_w[0-9]+_'
        ORDER BY start_date
        """
    )
    rows = cur.fetchall()
    print(f"rows still on the week-number scheme: {len(rows)}")

    plan, skipped = [], []
    for rid, ext, day, activity, title in rows:
        if not activity or not day:
            skipped.append((ext, "no activity or date"))
            continue
        # mixed-week per-day rows carry a weekday name; whole-week rows do not
        m = re.match(r"^ep_(\d{4})_w\d+_([a-z]+)_(.+)$", ext)
        year = day.year
        if m and m.group(2) in ("monday", "tuesday", "wednesday", "thursday",
                               "friday", "saturday", "sunday"):
            new = f"ep_{year}_{day.isoformat()}_{activity}"
        else:
            new = f"ep_{year}_{day.isoformat()}_{activity}"
        if new == ext:
            continue
        plan.append((rid, ext, new, day, title))

    print(f"  re-keyable: {len(plan)}   skipped: {len(skipped)}")
    # A collision means two old rows map to one new id: that is a duplicate the
    # dedup step should have caught. Report rather than silently overwrite.
    seen, collisions = {}, []
    for rid, ext, new, day, title in plan:
        if new in seen:
            collisions.append((new, seen[new], ext))
        seen[new] = ext
    if collisions:
        print(f"  [WARN] {len(collisions)} collisions (two rows would share one new id):")
        for new, a, b in collisions[:6]:
            print(f"     {new}  <-  {a}  AND  {b}")

    for _rid, ext, new, day, title in plan[:10]:
        print(f"   {day}  {str(title)[:38]:40} {ext}  ->  {new}")

    if not args.apply:
        print("\n[DRY-RUN] nothing written. Re-run with --apply.")
        return 0
    if collisions:
        print("\n[ABORT] resolve the collisions first; they are duplicate rows, not re-keys.")
        return 1

    n = 0
    for rid, _ext, new, _day, _title in plan:
        cur.execute("UPDATE eu_calendar_events SET external_id=%s WHERE id::text=%s", (new, rid))
        n += cur.rowcount
    conn.commit()

    cur.execute(
        "SELECT count(*) FROM eu_calendar_events WHERE source='ep_calendar_json' AND external_id ~ '_w[0-9]+_'"
    )
    left = cur.fetchone()[0]
    print(f"[OK] re-keyed {n}. Rows still on the old scheme: {left}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
