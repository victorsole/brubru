"""
Fill ft_partner_search_orgs + ft_partner_search_announcements (migration 316): the F&T Portal's
Partner Search, organisations only (services/scrapers/ft_partner_search.py).

Each run reads every organisation profile with Partner Search (11,537 on 27 Oct 2026, read country
by country: the index serves 10,000 results per query), the announcements requested in the last
14 days, and one seventh of the older months in turn, so every announcement is read again each
week. An announcement or a profile no longer in the index is deleted, but only from a range read
completely. --full reads every month (the first fill: 358,356 announcements since 2018).

A row is written only when what the source says changed: the rotation re-reads a seventh of
the announcements every day (358,356 / 7 = about 51,000 on 27 Oct 2026) and would otherwise rewrite them all.

Runs daily in the daily tier (api/cron.py); the tier records this job's run.

Run: python3.12 scripts/sync_ft_partner_search.py [--apply] [--full] [--since YYYY-MM-DD]
     [--until YYYY-MM-DD] [--no-profiles] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_funding_sedia import get_env  # noqa: E402
from services.scrapers.ft_partner_search import FIRST_DAY, PartnerSearch, compose_body  # noqa: E402

RECENT_DAYS = 14
ROTATION = 7
BATCH = 500
ANNOUNCEMENT_COLUMNS = (
    "pic", "organisation_name", "country", "organisation_type", "expertise", "topic_id", "topic_ids",
    "topic_title", "summary", "summary_cut", "requested_date", "indexed_at", "public_url", "body_txt", "body_html",
)
ORG_COLUMNS = ("name", "city", "country", "organisation_type", "projects", "portal_announcements", "topics", "public_url")


def _upsert(table: str, key: str, columns: tuple) -> str:
    """Insert, or update only when a column the source gives has changed."""
    changed = " OR ".join(f"t.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in columns)
    return (f"INSERT INTO {table} AS t ({key}, {', '.join(columns)}) VALUES %s "
            f"ON CONFLICT ({key}) DO UPDATE SET " + ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)
            + f", scraped_at = now() WHERE {changed}")


UPSERT_ANNOUNCEMENTS = _upsert("ft_partner_search_announcements", "announcement_id", ANNOUNCEMENT_COLUMNS)
UPSERT_ORGS = _upsert("ft_partner_search_orgs", "pic", ORG_COLUMNS)
DELETE_ANNOUNCEMENTS = ("DELETE FROM ft_partner_search_announcements WHERE requested_date >= %s AND requested_date < %s "
                        "AND NOT (announcement_id = ANY(%s))")
DELETE_ORGS = "DELETE FROM ft_partner_search_orgs WHERE NOT (pic = ANY(%s))"
HELD_IN_RANGE = "SELECT count(*) FROM ft_partner_search_announcements WHERE requested_date >= %s AND requested_date < %s"
# An index that answers nothing, or far less than Brubru holds, is broken or moved, not emptied:
# a range loses at most this share of its rows in one run (more is reported, not deleted).
MAX_DELETE_SHARE = 0.10


def months(start: date, end: date) -> list:
    """[first day, next first day) for each month from start's to the one before end's."""
    out, m = [], date(start.year, start.month, 1)
    while m < end:
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        out.append((m, min(nxt, end)))
        m = nxt
    return out


def ranges_for(today: date, full: bool, since=None, until=None) -> list:
    """The requested-date ranges this run reads: given, all, or the recent days plus this turn's months."""
    end = (until or today) + timedelta(days=1)
    if since:
        return [(since, end)]
    recent = today - timedelta(days=RECENT_DAYS)
    if full:
        return [(FIRST_DAY, end)]
    turn = today.toordinal() % ROTATION
    older = [m for i, m in enumerate(months(FIRST_DAY, recent)) if i % ROTATION == turn]
    return older + [(recent, end)]


def store(conn, table_sql: str, rows: list) -> int:
    written = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), BATCH):
            psycopg2.extras.execute_values(cur, table_sql, rows[i:i + BATCH], page_size=BATCH)
            written += cur.rowcount
            conn.commit()
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write (default: dry run; it still reads the index).")
    ap.add_argument("--full", action="store_true", help="Read every month since 2018 (the first fill).")
    ap.add_argument("--since", type=date.fromisoformat, help="Read announcements requested from this day only.")
    ap.add_argument("--until", type=date.fromisoformat, help="... up to this day (default today).")
    ap.add_argument("--no-profiles", action="store_true", help="Leave the organisation profiles alone.")
    ap.add_argument("--limit", type=int, help="Store at most N announcements (a sample; deletes nothing).")
    ap.add_argument("--sleep", type=float, default=0.3, help="Seconds between index requests.")
    args = ap.parse_args(argv)
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        return 1
    session = requests.Session()
    session.headers["User-Agent"] = "Brubru EU data (hello@beresol.eu)"
    started = time.time()
    ps = PartnerSearch(session, sleep=args.sleep)

    profiles, prof_expected, prof_complete = ([], 0, False) if args.no_profiles else ps.profiles()
    read_ranges, ann_rows, ann_expected, deletable = ranges_for(date.today(), args.full, args.since, args.until), {}, 0, []
    for a, b in read_ranges:
        rows, n, complete = ps.announcements(a, b)
        ann_expected += n
        for r in rows:
            ann_rows[r["announcement_id"]] = r
        if complete:
            # The ids read in this range: the rows it holds after the upsert that are not among them are gone.
            deletable.append((a, b, [r["announcement_id"] for r in rows]))
        print(f"[INFO] {a} to {b}: {len(rows)} of {n} announcement(s) read{'' if complete else ' (incomplete: nothing deleted here)'}",
              flush=True)
    rows = list(ann_rows.values())
    if args.limit is not None:
        rows, deletable = rows[:args.limit], []
    values = []
    for r in rows:
        txt, page = compose_body(r)
        values.append((r["announcement_id"], *(dict(r, body_txt=txt, body_html=page)[c] for c in ANNOUNCEMENT_COLUMNS)))
    org_values = [(p["pic"], *(p[c] for c in ORG_COLUMNS)) for p in profiles]

    written = orgs_written = ann_deleted = orgs_deleted = 0
    held_back = []
    if not args.no_profiles and not profiles:
        print("[ERROR] the index gave no organisation profile: nothing written or deleted")
        return 1
    if args.apply:
        conn = psycopg2.connect(db.replace("postgresql+psycopg2://", "postgresql://"))
        try:
            orgs_written = store(conn, UPSERT_ORGS, org_values)
            written = store(conn, UPSERT_ANNOUNCEMENTS, values)
            with conn.cursor() as cur:
                for a, b, ids in deletable:
                    if not ids:
                        continue                       # the index listed nothing here
                    cur.execute(HELD_IN_RANGE, (a, b))
                    held = cur.fetchone()[0]
                    if held - len(ids) > max(20, held * MAX_DELETE_SHARE):
                        held_back.append(f"{a} to {b}: {held} held, {len(ids)} listed")
                        continue
                    cur.execute(DELETE_ANNOUNCEMENTS, (a, b, ids))
                    ann_deleted += cur.rowcount
                # A profile read incompletely, or a run that found none, deletes nothing.
                if prof_complete and profiles and args.limit is None:
                    cur.execute(DELETE_ORGS, ([p["pic"] for p in profiles],))
                    orgs_deleted = cur.rowcount
            conn.commit()
        finally:
            conn.close()
    verb = "written" if args.apply else "readable (dry run)"
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] profiles: {len(profiles)} of {prof_expected} read, {orgs_written if args.apply else len(org_values)} {verb}, "
          f"{orgs_deleted} deleted; announcements: {len(rows)} of {ann_expected} read in {len(read_ranges)} range(s), "
          f"{written if args.apply else len(values)} {verb}, {ann_deleted} deleted; {time.time() - started:.0f}s")
    if held_back:
        print(f"[SYNC_STATUS] degraded: deletions held back where the index lists far fewer than held: {'; '.join(held_back[:5])}")
    if ann_expected and not ann_rows:
        print("[ERROR] the index listed announcements but none was read")
        return 1
    if (not args.no_profiles and not prof_complete) or len(deletable) < len(read_ranges):
        print("[SYNC_STATUS] degraded: a range or the profiles were read incompletely (nothing deleted there)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
