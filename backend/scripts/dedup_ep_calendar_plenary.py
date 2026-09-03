"""
Dedup the EP plenary/committee-week rows that My EU Calendar shows twice, and
re-key the survivors onto a stable external_id.

Why these rows exist (calendar audit, 3 September 2026)
-------------------------------------------------------
`ep_calendar_loader.py` built the external_id as
    f"ep_{year}_w{week_num}_plenary_{day_name.lower()}"
and `week_num` comes from the SOURCE JSON, not from the date. When the EP
relabelled the September plenary week 37 -> 38 between the 21 July and
24 August runs, every day of that session got a new external_id, the
`uq_calendar_source_external_id` index saw an unseen key, and a second row was
inserted. Result: 15 September 2026 appears twice as "EP Plenary Session
(Day 2)". A date is stable identity; an upstream week label is not.

The loader is fixed to derive the id from the date. This script cleans the rows
that the old scheme already created and re-keys the survivors to the new scheme,
so the next sync updates them instead of inserting a third copy.

NOT in scope, deliberately -- both are different defects, not duplicates:
  * `euagenda`  126 rows whose TITLE is a bare topic category ("Agriculture",
    "Energy"). Distinct events, different external_ids, different URLs. Deleting
    on (title, date) would destroy real events.
  * `commissioner_agenda`  529 extra rows from writing one meeting once per
    attending Commissioner. That needs an attendees column, not a delete.

Usage:
    python3.12 scripts/dedup_ep_calendar_plenary.py --dry-run   # default
    python3.12 scripts/dedup_ep_calendar_plenary.py --apply
"""
import argparse
import os
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import psycopg2
from dotenv import load_dotenv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the writes (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()
    apply = args.apply

    load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[ERROR] DATABASE_URL not set; aborting rather than guessing.")
        return 2

    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT title, start_date::date, array_agg(id::text ORDER BY scraped_at)
        FROM eu_calendar_events
        WHERE source = 'ep_calendar_json'
        GROUP BY 1, 2
        HAVING count(*) > 1
        ORDER BY 2
        """
    )
    groups = cur.fetchall()
    if not groups:
        print("[OK] no duplicate ep_calendar_json rows; nothing to do.")
        return 0

    # array_agg on a uuid column can come back as a STRING rather than a list,
    # in which case ids[1:] silently slices CHARACTERS and the delete list is
    # nonsense (28 groups produced a 2072-entry list before this check existed).
    # Assert the shape rather than trust it.
    if not isinstance(groups[0][2], list):
        print(f"[ERROR] array_agg returned {type(groups[0][2]).__name__}, expected list. Aborting.")
        return 2

    to_delete: list[str] = []
    to_rekey: list[tuple[str, str]] = []
    for title, day, ids in groups:
        if not all(len(i) == 36 for i in ids):
            print(f"[ERROR] non-UUID ids in group {title} {day}: {ids[:2]}. Aborting.")
            return 2
        to_delete += ids[1:]                       # keep the earliest-scraped row
        to_rekey.append((f"ep_{day.year}_plenary_{day.isoformat()}", ids[0]))

    print(f"groups: {len(groups)}   rows to delete: {len(to_delete)}   rows to re-key: {len(to_rekey)}")
    for title, day, ids in groups[:8]:
        print(f"  {day}  {title}  keep 1 of {len(ids)}")

    # A tracked event is a promise to a user. Never delete a row someone is
    # subscribed to; move the subscription or abort.
    cur.execute(
        "SELECT count(*) FROM user_calendar_subscriptions WHERE event_id::text = ANY(%s)",
        (to_delete,),
    )
    blocked = cur.fetchone()[0]
    print(f"user subscriptions pointing at a row to delete: {blocked}")
    if blocked:
        print("[ABORT] a user is subscribed to a row this would delete. Re-point first.")
        return 1

    if not apply:
        print("\n[DRY-RUN] nothing written. Re-run with --apply to perform the writes.")
        return 0

    cur.execute("DELETE FROM eu_calendar_events WHERE id::text = ANY(%s)", (to_delete,))
    deleted = cur.rowcount
    rekeyed = 0
    for new_ext, keep_id in to_rekey:
        cur.execute(
            "UPDATE eu_calendar_events SET external_id = %s WHERE id::text = %s",
            (new_ext, keep_id),
        )
        rekeyed += cur.rowcount
    conn.commit()

    # Verify by query, not by the counters above. Silence is not success.
    cur.execute(
        """
        SELECT coalesce(sum(c - 1), 0) FROM (
          SELECT institution, title, start_date, count(*) c
          FROM eu_calendar_events WHERE source = 'ep_calendar_json'
          GROUP BY 1, 2, 3 HAVING count(*) > 1) x
        """
    )
    remaining = cur.fetchone()[0]
    print(f"[OK] deleted {deleted}, re-keyed {rekeyed}. Redundant rows remaining: {remaining}")
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
