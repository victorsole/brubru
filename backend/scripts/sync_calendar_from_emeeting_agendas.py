"""Create My EU Calendar events for EP committee meetings that eMeeting knows about
and the calendar does not.

Why this exists (audit, 7 September 2026)
-----------------------------------------
`eu_calendar_events` has a source `ep_committee_agenda`, fed by
`scripts/sync_committee_agendas.py`, which scrapes the EP "latest documents" HTML
page. **That scraper is dead.** On 7 September 2026 it fetched the page
successfully (HTTP 200, 2,431 bytes), parsed **0 draft agendas**, logged
"[INFO] No committee agendas found", and exited **0**. Its newest calendar row is
2 September while `ep_emeeting_agendas` reaches 10 September. Nothing-fetched was
reported as nothing-found -- see [[feedback_silent_failure_reports_success]].

The data is not missing. Brubru already holds it in `ep_emeeting_agendas`, from
the eMeeting **open JSON API** (no WAF, plain httpx). So the calendar is fed from
the store rather than from a broken HTML scrape.

Matching is by committee AND date, never by date alone. A date-only join was what
made the 7 September /news run report "11 of 12 committees have no calendar event"
when in fact every one of them did.

Run:
    python3.12 scripts/sync_calendar_from_emeeting_agendas.py                 # dry run
    python3.12 scripts/sync_calendar_from_emeeting_agendas.py --apply
    python3.12 scripts/sync_calendar_from_emeeting_agendas.py --back 30 --ahead 30 --apply
"""
import argparse
import os
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))

SOURCE = "ep_emeeting_agenda"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    ap.add_argument("--back", type=int, default=7, help="days back from today")
    ap.add_argument("--ahead", type=int, default=21, help="days ahead of today")
    args = ap.parse_args()

    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
    engine = create_engine(url)

    with engine.connect() as conn:
        # The institution enum is DERIVED, never hand-copied: a previous session
        # invented 'summit' and 'PARLIAMENT' from memory and both failed on insert.
        vals = {r[0] for r in conn.execute(
            text("SELECT unnest(enum_range(NULL::institution_enum))::text"))}
        if "EP" not in vals:
            print(f"[ABORT] 'EP' is not in institution_enum ({len(vals)} values)")
            return 1
        etypes = {r[0] for r in conn.execute(
            text("SELECT unnest(enum_range(NULL::event_type_enum))::text"))}
        event_type = next((e for e in ("committee_meeting", "COMMITTEE_MEETING",
                                       "committee", "meeting") if e in etypes), None)
        if not event_type:
            print(f"[ABORT] no committee-meeting event_type in enum: {sorted(etypes)[:12]}")
            return 1
        print(f"[schema] institution='EP', event_type='{event_type}' (both derived from the enums)")

        rows = conn.execute(text("""
            SELECT a.committee_code, a.meeting_date, a.committee_name,
                   a.agenda_pdf_url, a.oj_reference
              FROM ep_emeeting_agendas a
             WHERE a.meeting_date BETWEEN CURRENT_DATE - :back AND CURRENT_DATE + :ahead
               AND NOT EXISTS (
                   SELECT 1 FROM eu_calendar_events e
                    WHERE e.start_date = a.meeting_date
                      AND (e.ep_committee_code = a.committee_code
                           OR e.title       ILIKE '%' || a.committee_code || '%'
                           OR e.description ILIKE '%' || a.committee_code || '%'))
             ORDER BY a.meeting_date, a.committee_code
        """), {"back": args.back, "ahead": args.ahead}).mappings().all()

    print(f"{'APPLY' if args.apply else 'DRY RUN'} -- committee meetings with no calendar event: {len(rows)}")
    for r in rows:
        print(f"   {r['meeting_date']}  {r['committee_code']:<6} {str(r['committee_name'] or '')[:44]}")
    if not rows:
        print("[OK] the calendar already covers every committee meeting in the window.")
        return 0
    if not args.apply:
        print("\nDry run only. Re-run with --apply.")
        return 0

    written = 0
    with engine.begin() as conn:
        for r in rows:
            name = r["committee_name"] or r["committee_code"]
            conn.execute(text("""
                INSERT INTO eu_calendar_events
                    (id, institution, event_type, title, description, start_date,
                     ep_committee_code, source, external_id, agenda_url,
                     first_seen, last_updated, scraped_at)
                VALUES
                    (gen_random_uuid(), 'EP', :et, :title, :descr, :d,
                     :cc, :src, :ext, :agenda, NOW(), NOW(), NOW())
                ON CONFLICT DO NOTHING
            """), {
                "et": event_type,
                "title": f"{r['committee_code']} committee meeting",
                "descr": f"European Parliament {name} ({r['committee_code']}) committee meeting. "
                         f"Source: EP eMeeting agenda {r['oj_reference'] or ''}".strip(),
                "d": r["meeting_date"], "cc": r["committee_code"], "src": SOURCE,
                "ext": f"{SOURCE}:{r['committee_code']}:{r['meeting_date']}",
                "agenda": r["agenda_pdf_url"],
            })
            written += 1
    print(f"\n[OK] inserted {written} calendar event(s) with source '{SOURCE}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
