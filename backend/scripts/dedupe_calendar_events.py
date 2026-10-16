"""Remove calendar events stored twice, keeping the one that describes the event (16 Oct 2026).

/api/v2/calendar/events served 561 extra rows in 86 same-title same-day groups:

  * commissioner_agenda  504: on 5-6 June 2026 every Commissioner's page served the whole
    College's agenda, so "Commissioner Dombrovskis meets ..." was stored 16 times, each copy
    with another Commissioner's page and DG. The copy whose agenda it is stays: the one whose
    title opens with that Commissioner's name (names_another_commissioner is the sync's guard).
  * euagenda             8: the site lists some events twice, the second slug ending
    "-2026-06". The plain slug stays.
  * ft_portal            6: the Funding & Tenders portal re-published events under a new id;
    the old id stopped being returned (its last sighting is before the new id's first). The
    new one stays.
  * ep_calendar_json     9: rows keyed as plenary days that now carry another activity, beside
    the date-keyed row of that activity, and one recess loaded from two calendar years.
  * dg_events            4: one event listed by two DGs, same id. The first stored stays.
  * college meeting      1: the same meeting from the tentative agenda and from a register
    search. The SEC detail stays.

A deleted event's user subscriptions and archives move to the copy that stays.

    python3.12 scripts/dedupe_calendar_events.py            # dry run
    python3.12 scripts/dedupe_calendar_events.py --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from services.scrapers.eu_calendar_sync_service import names_another_commissioner  # noqa: E402

ROWS = text("""SELECT id::text, source, external_id, event_type, lower(btrim(title)) AS t,
                      start_date::date AS d, first_seen, last_updated, source_url
               FROM eu_calendar_events""")
_SUFFIX = re.compile(r"-20\d\d-\d\d$")


def plan(rows) -> list[tuple[str, str, str]]:
    """(delete_id, keep_id, rule) for every duplicate found."""
    out = []
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["t"], r["d"])].append(r)
    for (_t, _d), g in groups.items():
        if len(g) < 2:
            continue
        cm = [r for r in g if r["source"] == "commissioner_agenda"]
        if len(cm) > 1:
            slugs = sorted({r["external_id"].split(":")[1] for r in cm})
            own = [r for r in cm if not names_another_commissioner(
                r["t"], r["external_id"].split(":")[1], [s for s in slugs if s != r["external_id"].split(":")[1]])]
            if len(own) == 1:
                out += [(r["id"], own[0]["id"], "another Commissioner's agenda") for r in cm if r is not own[0]]
        eu = [r for r in g if r["source"] == "euagenda"]
        for r in eu:
            base = _SUFFIX.sub("", r["external_id"] or "")
            twin = [x for x in eu if x is not r and x["external_id"] == base]
            if base != r["external_id"] and twin:
                out.append((r["id"], twin[0]["id"], "euagenda listed it twice"))
        ft = [r for r in g if r["source"] == "ft_portal"]
        if len(ft) > 1:
            newest = max(ft, key=lambda r: r["first_seen"])
            out += [(r["id"], newest["id"], "portal re-published it under a new id") for r in ft
                    if r is not newest and r["last_updated"] < newest["first_seen"]]
        ep = [r for r in g if r["source"] == "ep_calendar_json"]
        if len(ep) > 1:
            dated = [r for r in ep if not re.match(r"ep_\d{4}_plenary_", r["external_id"] or "")
                     and (r["external_id"] or "").startswith(f"ep_{r['d'].year}_")]
            keep = dated[0] if dated else min(ep, key=lambda r: r["first_seen"])
            out += [(r["id"], keep["id"], "EP calendar row keyed twice") for r in ep if r is not keep]
        dg = [r for r in g if (r["source"] or "").startswith("dg_events:")]
        if len(dg) > 1 and len({r["external_id"] for r in dg}) == 1:
            keep = min(dg, key=lambda r: r["first_seen"])
            out += [(r["id"], keep["id"], "listed by two DGs") for r in dg if r is not keep]
        col = [r for r in g if r["event_type"] == "commission_college_meeting"]
        if len(col) > 1:
            sec = [r for r in col if "detail?ref=SEC" in (r["source_url"] or "") or "/detail/" in (r["source_url"] or "")]
            if len(sec) == 1:
                out += [(r["id"], sec[0]["id"], "college meeting from two lists") for r in col if r is not sec[0]]
    return out


MOVE_SUBS = text("""UPDATE user_calendar_subscriptions s SET event_id = CAST(:keep AS uuid)
                    WHERE s.event_id = CAST(:gone AS uuid) AND NOT EXISTS (
                      SELECT 1 FROM user_calendar_subscriptions k
                      WHERE k.event_id = CAST(:keep AS uuid) AND k.user_id = s.user_id)""")
MOVE_ARCH = text("""UPDATE user_calendar_event_archives a SET event_id = CAST(:keep AS uuid)
                    WHERE a.event_id = CAST(:gone AS uuid) AND NOT EXISTS (
                      SELECT 1 FROM user_calendar_event_archives k
                      WHERE k.event_id = CAST(:keep AS uuid) AND k.user_id = a.user_id)""")
DELETE = text("DELETE FROM eu_calendar_events WHERE id = CAST(:gone AS uuid)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(ROWS)]
    todo = plan(rows)
    print(f"[INFO] {len(rows)} events; {len(todo)} duplicate(s): "
          + ", ".join(f"{k} {v}" for k, v in collections.Counter(r for _, _, r in todo).most_common()))
    if not args.apply:
        print("[DRY RUN] nothing deleted")
        return 0
    with engine.begin() as c:
        for gone, keep, _ in todo:
            c.execute(MOVE_SUBS, {"gone": gone, "keep": keep})
            c.execute(MOVE_ARCH, {"gone": gone, "keep": keep})
            c.execute(DELETE, {"gone": gone})
    print(f"[DONE] deleted {len(todo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
