#!/usr/bin/env python3.12
"""Give calendar events their missing public_url from the authoritative agenda row.

/api/v2/calendar/events exposes `public_url = source_url or agenda_url`. 71 of
5,262 events carried neither, so the contracted datapoint came back empty — the
defect GovClipping would hit on a full walk (it is invisible on page 1).

The URL is never constructed here. For EP committee meetings the authoritative
agenda already exists in `ep_emeeting_agendas`, fetched from the EP's own
eMeeting JSON API, and it carries the real Official Journal PDF in `public_url`.
This script only copies that value onto the matching calendar row.

A committee can hold two meetings on one day (CONT 2026-09-07 has _1 and _2) and
a joint meeting files under a CJ** code (ENVI 2026-09-10 also matches
CJ59(2026)0910_1). The pick is therefore deterministic: an agenda whose
oj_reference starts with the event's own committee code wins over a joint one,
then the lowest oj_reference. Without that ordering the same run could write a
different URL each time, which is exactly the inconsistency we are fixing.

Only an agenda whose public_url is the meeting's own Official Journal PDF
(/meetdocs/) is copied. 313 of 1,217 agendas fell back to the generic eMeeting
timeline landing page, which does not identify any particular meeting; writing
that onto an event would make public_url look populated while telling a client
nothing about that event. Those stay empty until the agenda ingest extracts the
real OJ document, which is tracked separately.

Rows with no authoritative match (hand-entered events, news-verified entries)
are left NULL. An invented URL would be worse than an empty one.

    python3.12 scripts/backfill_calendar_event_urls.py --rehearse
    python3.12 scripts/backfill_calendar_event_urls.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

# One row per calendar event that has no URL but does have an agenda we fetched
# from the EP. DISTINCT ON + ORDER BY is what makes the choice reproducible.
SELECT_RESOLVABLE = text(
    """
    SELECT DISTINCT ON (ev.id)
           ev.id                AS event_id,
           ev.source            AS source,
           ev.ep_committee_code AS committee,
           ev.start_date        AS start_date,
           a.oj_reference       AS oj_reference,
           a.public_url         AS public_url
      FROM eu_calendar_events ev
      JOIN ep_emeeting_agendas a
        ON a.committee_code = ev.ep_committee_code
       AND a.meeting_date   = ev.start_date
     WHERE coalesce(ev.source_url, '') = ''
       AND coalesce(ev.agenda_url, '') = ''
       AND a.public_url LIKE '%/meetdocs/%'
     ORDER BY ev.id,
              (a.oj_reference LIKE ev.ep_committee_code || '%') DESC,
              a.oj_reference ASC
    """
)

# COALESCE so a concurrent writer that filled the column first always wins; this
# job only ever turns an empty cell into a value, it never overwrites one.
UPDATE_ONE = text(
    """
    UPDATE eu_calendar_events
       SET agenda_url   = COALESCE(NULLIF(agenda_url, ''), :url),
           last_updated = now()
     WHERE id = :event_id
       AND coalesce(source_url, '') = ''
       AND coalesce(agenda_url, '') = ''
    """
)

COUNT_GAP = text(
    """
    SELECT count(*) FROM eu_calendar_events
     WHERE coalesce(source_url, '') = '' AND coalesce(agenda_url, '') = ''
    """
)


def _database_url() -> str:
    env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true", help="show what would change, write nothing")
    g.add_argument("--apply", action="store_true", help="write the URLs")
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.begin() as conn:
        before = conn.execute(COUNT_GAP).scalar_one()
        rows = list(conn.execute(SELECT_RESOLVABLE))

        print(f"[INFO] events with no public_url : {before}")
        print(f"[INFO] resolvable from an agenda : {len(rows)}")
        by_source: dict[str, int] = {}
        for r in rows:
            by_source[r.source] = by_source.get(r.source, 0) + 1
        for src, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
            print(f"         {src:<26} {n}")

        if args.rehearse:
            print("\n[INFO] sample of the writes this would make:")
            for r in rows[:8]:
                print(f"  {r.committee:<5} {r.start_date}  {r.oj_reference:<18} -> {r.public_url[-52:]}")
            print("\n[INFO] rehearsal only, nothing written")
            return 0

        written = 0
        for r in rows:
            written += conn.execute(
                UPDATE_ONE, {"event_id": r.event_id, "url": r.public_url}
            ).rowcount

        after = conn.execute(COUNT_GAP).scalar_one()

    # Count PERSISTED changes, not attempts, and make the arithmetic prove itself.
    print(f"\n[INFO] rows written : {written}")
    print(f"[INFO] gap before    : {before}")
    print(f"[INFO] gap after     : {after}")
    if before - after != written:
        print(f"[ERROR] gap moved by {before - after} but {written} rows were written")
        return 1
    if written != len(rows):
        print(f"[ERROR] {len(rows)} resolvable but only {written} written")
        return 1
    print("[OK] every resolvable event now carries a public_url")
    return 0


if __name__ == "__main__":
    sys.exit(main())
