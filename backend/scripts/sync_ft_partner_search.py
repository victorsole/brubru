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
from services.funding.organisations import may_be_a_person  # noqa: E402
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
# An organisation stays while it carries the flag or has an announcement held.
DELETE_ORGS = ("DELETE FROM ft_partner_search_orgs o WHERE NOT (o.pic = ANY(%s)) "
               "AND NOT EXISTS (SELECT 1 FROM ft_partner_search_announcements a WHERE a.pic = o.pic)")
UNFLAGGED_PICS = "SELECT DISTINCT pic FROM ft_partner_search_announcements WHERE NOT (pic = ANY(%s)) ORDER BY pic"
FALLBACK = "SELECT pic, name, country, organisation_type FROM ft_partner_search_orgs"
# What an announcement may take from its organisation's profile when the index gives it none
# (544 of 358,427 on 27 Oct 2026, from 2018-2022, had no name and no country).
FALLBACK_FIELDS = ("organisation_name", "country", "organisation_type")
HELD_IN_RANGE = "SELECT count(*) FROM ft_partner_search_announcements WHERE requested_date >= %s AND requested_date < %s"
# An index that answers nothing, or far less than Brubru holds, is broken or moved, not emptied:
# a range loses at most this share of its rows in one run (more is reported, not deleted).
MAX_DELETE_SHARE = 0.10
# Victor's rule (27 Oct 2026): a profile that may be a person's is left out with its announcements
# (services/funding/organisations.py). Measured: 1,544 of 11,539 flagged profiles. A run that would
# leave out more than this share of the profiles it read is wrong, not careful: nothing is deleted.
MAX_LEFT_OUT_SHARE = 0.30
DELETE_LEFT_OUT_ANNOUNCEMENTS = "DELETE FROM ft_partner_search_announcements WHERE pic = ANY(%s)"
DELETE_LEFT_OUT_ORGS = "DELETE FROM ft_partner_search_orgs WHERE pic = ANY(%s)"


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
    if args.until and not args.since:
        ap.error("--until needs --since")
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        return 1
    session = requests.Session()
    session.headers["User-Agent"] = "Brubru EU data (hello@beresol.eu)"
    started = time.time()
    ps = PartnerSearch(session, sleep=args.sleep)

    profiles, prof_expected, prof_complete = ([], 0, False) if args.no_profiles else ps.profiles()
    if not args.no_profiles and not profiles:
        print("[ERROR] the index gave no organisation profile: nothing written or deleted")
        return 1
    profiles, left_out = _split(profiles)
    org_values = [(p["pic"], *(p[c] for c in ORG_COLUMNS)) for p in profiles]
    read_ranges = ranges_for(date.today(), args.full, args.since, args.until)
    n = dict(read=0, expected=0, written=0, deleted=0, orgs_written=0, orgs_deleted=0, slices=0, incomplete=0)
    held_back, left = [], args.limit
    conn = psycopg2.connect(db.replace("postgresql+psycopg2://", "postgresql://")) if args.apply else None
    fallback = {p["pic"]: (p["name"], p["country"], p["organisation_type"]) for p in profiles}
    extra, late_out = [], set()
    n["profiles_left_out"] = len(left_out)
    try:
        if conn is not None:
            n["orgs_written"] = store(conn, UPSERT_ORGS, org_values)
            # The profiles of the organisations that announced but no longer carry the flag.
            if not args.no_profiles:
                with conn.cursor() as cur:
                    cur.execute(UNFLAGGED_PICS, ([p["pic"] for p in profiles] + sorted(left_out),))
                    unflagged = [r[0] for r in cur.fetchall()]
                extra, extra_out = _split(ps.profiles_for(unflagged))
                left_out |= extra_out
                n["orgs_written"] += store(conn, UPSERT_ORGS, [(p["pic"], *(p[c] for c in ORG_COLUMNS)) for p in extra])
            n["profiles_left_out"] = len(left_out)
            share = len(left_out) / max(1, len(profiles) + len(extra) + len(left_out))
            if share > MAX_LEFT_OUT_SHARE:
                print(f"[ERROR] the person rule would leave out {share:.0%} of the profiles read: nothing deleted")
                return 1
            n["deleted"] += _delete_left_out(conn, left_out)
            with conn.cursor() as cur:
                cur.execute(FALLBACK)
                fallback = {r[0]: r[1:] for r in cur.fetchall()}
        # Each slice is written as soon as it is read (at most 10,000 rows in hand), and only a slice
        # read completely deletes: the rows it holds that the index no longer lists.
        for a, b in read_ranges:
            got = expected = 0
            for sa, sb, count, rows, complete in ps.announcement_slices(a, b):
                n["slices"] += 1
                n["incomplete"] += not complete
                got, expected = got + len(rows), expected + count
                if left is not None:
                    rows, complete = rows[:left], False          # a sample deletes nothing
                    left -= len(rows)
                rows, out_here = _kept(rows, left_out, fallback)
                late_out |= out_here
                values = [_values(_filled(r, fallback)) for r in rows]
                if conn is None:
                    n["written"] += len(values)
                else:
                    n["written"] += store(conn, UPSERT_ANNOUNCEMENTS, values)
                    if complete and rows:
                        n["deleted"] += _delete_gone(conn, sa, sb, [r["announcement_id"] for r in rows], held_back)
                if left == 0:
                    break
            n["read"] += got
            n["expected"] += expected
            print(f"[INFO] {a} to {b}: {got} of {expected} announcement(s) read", flush=True)
            if left == 0:
                break
        # Organisations with no profile whose announcements the rule left out: their stored rows go too.
        if conn is not None and late_out - left_out:
            n["deleted"] += _delete_left_out(conn, late_out - left_out)
        # A profile read incompletely, or a sample, deletes no organisation.
        if conn is not None and prof_complete and args.limit is None:
            with conn.cursor() as cur:
                cur.execute(DELETE_ORGS, ([p["pic"] for p in profiles + extra],))
                n["orgs_deleted"] = cur.rowcount
            conn.commit()
    finally:
        if conn is not None:
            conn.close()
    verb = "written" if args.apply else "readable (dry run)"
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] profiles: {len(profiles)} of {prof_expected} read, {len(extra)} more by PIC, "
          f"{n['orgs_written'] if args.apply else len(org_values)} {verb}, {n['orgs_deleted']} deleted; announcements: "
          f"{n['read']} of {n['expected']} read in {n['slices']} slice(s) of {len(read_ranges)} range(s), {n['written']} {verb}, "
          f"{n['deleted']} deleted; left out as possibly a person's: {n['profiles_left_out']} profile(s), "
          f"{len(late_out - left_out)} more organisation(s) without a profile; {time.time() - started:.0f}s")
    if held_back:
        print(f"[SYNC_STATUS] degraded: deletions held back where the index lists far fewer than held: {'; '.join(held_back[:5])}")
    if n["expected"] and not n["read"]:
        print("[ERROR] the index listed announcements but none was read")
        return 1
    if (not args.no_profiles and not prof_complete) or n["incomplete"]:
        print("[SYNC_STATUS] degraded: a slice or the profiles were read incompletely (nothing deleted there)")
    return 0


def _split(profiles: list) -> tuple:
    """(the profiles kept, the PICs left out as possibly a person's)."""
    out = {p["pic"] for p in profiles if may_be_a_person(p["name"], p["organisation_type"], p.get("registration_status"))}
    return [p for p in profiles if p["pic"] not in out], out


def _kept(rows: list, left_out: set, profiled: dict) -> tuple:
    """The announcements kept, and the PICs left out here: an organisation with no profile is judged by
    the announcement's own name and type, as a self-registered one."""
    kept, out = [], set()
    for r in rows:
        if r["pic"] in left_out:
            continue
        if r["pic"] not in profiled and may_be_a_person(r["organisation_name"], r["organisation_type"], None):
            out.add(r["pic"])
            continue
        kept.append(r)
    return kept, out


def _delete_left_out(conn, pics: set) -> int:
    if not pics:
        return 0
    with conn.cursor() as cur:
        cur.execute(DELETE_LEFT_OUT_ANNOUNCEMENTS, (sorted(pics),))
        gone = cur.rowcount
        cur.execute(DELETE_LEFT_OUT_ORGS, (sorted(pics),))
    conn.commit()
    return gone


def _filled(r: dict, fallback: dict) -> dict:
    """The announcement, with its organisation's name, country and type from the profile where the
    index gives none: one writer for the column, the same answer every run."""
    known = fallback.get(r["pic"])
    if not known or all(r.get(f) for f in FALLBACK_FIELDS):
        return r
    return dict(r, **{f: r.get(f) or v for f, v in zip(FALLBACK_FIELDS, known)})


def _values(r: dict) -> tuple:
    txt, page = compose_body(r)
    full = dict(r, body_txt=txt, body_html=page)
    return (r["announcement_id"], *(full[c] for c in ANNOUNCEMENT_COLUMNS))


def _delete_gone(conn, a: date, b: date, ids: list, held_back: list) -> int:
    """Delete the rows of [a, b) the index no longer lists, unless that would remove more than
    MAX_DELETE_SHARE of them (an index answering far less than it holds is broken, not emptied)."""
    with conn.cursor() as cur:
        cur.execute(HELD_IN_RANGE, (a, b))
        held = cur.fetchone()[0]
        if held - len(ids) > max(20, held * MAX_DELETE_SHARE):
            held_back.append(f"{a} to {b}: {held} held, {len(ids)} listed")
            return 0
        cur.execute(DELETE_ANNOUNCEMENTS, (a, b, ids))
        gone = cur.rowcount
    conn.commit()
    return gone

if __name__ == "__main__":
    sys.exit(main())
