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


def _safe_load(fn, year):
    try:
        return fn(year)
    except FileNotFoundError:
        return []


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

    # Keep exactly the rows the loader emits TODAY; everything else from this
    # source is stale (23 Sep 2026). The first version kept the earliest row of
    # each (title, date) group and re-keyed it to the per-day PLENARY id,
    # whatever the row was. A committee week re-keyed that way never matches the
    # loader's `<date>_committee_week` id, so the next sync inserted it again:
    # the script recreated the duplicates it removed. It also could not see a
    # stale row that shares no title with its replacement, which is how four
    # plenary days on 2-5 Nov and four on 7-10 Dec survived the 21 July calendar
    # correction. The loader's JSON is the EP's own PDF; it decides.
    _backend = os.path.join(_REPO_ROOT, "backend")
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
    from services.scrapers.ep_calendar_loader import load_ep_calendar
    emitted = {e["external_id"] for y in (2025, 2026, 2027) for e in _safe_load(load_ep_calendar, y)}
    if not emitted:
        print("[ERROR] the loader emitted nothing; refusing to treat every row as stale.")
        return 2
    cur.execute(
        """
        SELECT id::text, external_id, title, start_date::date
        FROM eu_calendar_events
        WHERE source = 'ep_calendar_json'
          AND start_date >= CURRENT_DATE
        ORDER BY start_date
        """
    )
    stale = [r for r in cur.fetchall() if r[1] not in emitted]
    if not stale:
        print("[OK] every future ep_calendar_json row is one the loader emits; nothing to do.")
        return 0
    to_delete = [r[0] for r in stale]
    groups = [(r[2], r[3], [r[0]]) for r in stale]
    to_rekey: list[tuple[str, str]] = []

    print(f"stale future rows (not emitted by the loader): {len(to_delete)}")
    for _id, ext, title, day in stale:
        print(f"  {day}  {title:34s} {ext}")

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
        "SELECT external_id FROM eu_calendar_events "
        "WHERE source = 'ep_calendar_json' AND start_date >= CURRENT_DATE"
    )
    remaining = sum(1 for (ext,) in cur.fetchall() if ext not in emitted)
    print(f"[OK] deleted {deleted}, re-keyed {rekeyed}. Redundant rows remaining: {remaining}")
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
