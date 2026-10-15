#!/usr/bin/env python3.12
"""Read Have Your Say consultation dates from the Commission's own API.

A full walk of /api/v2/commission/consultations (2 Oct 2026) found document_date
empty on 3,007 of 4,881 rows. document_date is start_date, and 2,612 Have Your Say
initiatives were stored without one (2,674 closed, 333 upcoming across both sources).

The initiative API states each publication's dates: publishedDate (when it went
live for feedback) and endDate (when feedback closed). Initiative 2016 publishes
2018-12-13 and closes 2019-03-11, which is what its page shows. The start is the
EARLIEST publishedDate across the initiative's publications, the end the endDate of
that same publication. Only empty columns are written; an initiative with no
published publication (most upcoming ones) is left NULL.

Why it writes published_date and not start_date (15 Oct 2026): run on 2 Oct, it wrote
start_date and left 148 consultations undated. The nightly sync owns start_date (the
current feedback period's opening) and empties it when the portal shows no current
period: its run of 3 Oct erased 2,474 of those dates, and GovClipping found 2,488
consultations dated only by the day Brubru stored them. Two writers, two meanings, one
column. Now this job alone writes published_date (migration 293), the sync never names
it, and the API serves document_date = coalesce(published_date, start_date). It runs
nightly after the sync (api/cron.py, daily tier) for the rows still without one.

GovClipping, the same day: every consultation must carry its publication date, the day
feedback opened and the day it closed. A closed initiative has no current period, so the
sync leaves start_date/end_date empty; this job also keeps the LAST period that took
feedback (the latest publication with an endDate: its publishedDate and endDate) in
feedback_start_date / feedback_end_date. Initiative 1859: published 18 Jul 2018, last
feedback period 8 May to 11 Sep 2020 (its public consultation). Rows the sync changed
in the last day are asked again, since a period that just closed moves that pair.

    python3.12 scripts/backfill_consultation_dates.py --limit 20 --rehearse
    python3.12 scripts/backfill_consultation_dates.py --limit 5000 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

API = "https://ec.europa.eu/info/law/better-regulation/brpapi/groupInitiatives/{iid}?language=EN"
HEADERS = {"Accept": "application/json",
           "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"}
_IID = re.compile(r"/initiatives/(\d+)[-/_]")

# Rows the API serves with no document_date first, then newest first.
PICK = text("""SELECT id, portal_url FROM public_consultations
                WHERE portal_url LIKE '%%/initiatives/%%'
                  AND (published_date IS NULL OR last_updated > now() - interval '20 hours')
                ORDER BY (start_date IS NULL AND published_date IS NULL) DESC, first_seen DESC, id
                LIMIT :lim""")
# The first fill (15 Oct 2026) asked every initiative once; --all asks them all again.
PICK_ALL = text("""SELECT id, portal_url FROM public_consultations
                    WHERE portal_url LIKE '%%/initiatives/%%' ORDER BY first_seen DESC, id LIMIT :lim""")
# last_updated is the trigger's (migration 245): it moves only when a value changed.
STORE = text("""UPDATE public_consultations
                   SET published_date = :p, feedback_start_date = :fs, feedback_end_date = :fe
                 WHERE id = :i AND (published_date, feedback_start_date, feedback_end_date)
                       IS DISTINCT FROM (:p, :fs, :fe)""")
# What a caller sees: rows with no document_date at all.
GAP = text("SELECT count(*) FROM public_consultations WHERE start_date IS NULL AND published_date IS NULL")


def _db() -> str:
    # The environment first: on Railway there is no .env file (it runs nightly from 15 Oct 2026).
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = BACKEND / ".env"
        m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M) if env.exists() else None
        if not m:
            raise SystemExit("[ERROR] DATABASE_URL missing")
        url = m.group(1).strip()
    return url


def _d(v):
    try:
        return datetime.strptime(v[:19], "%Y/%m/%d %H:%M:%S") if v else None
    except ValueError:
        return None


def _dates(iid: str, ctx):
    try:
        req = urllib.request.Request(API.format(iid=iid), headers=HEADERS)
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except Exception as e:  # noqa: BLE001
        return type(e).__name__
    pubs = [(_d(p.get("publishedDate")), _d(p.get("endDate"))) for p in d.get("publications") or []]
    pubs = [p for p in pubs if p[0]]
    if not pubs:
        return None
    published = min(p[0] for p in pubs)
    windows = [p for p in pubs if p[1]]
    last = max(windows, key=lambda p: p[0]) if windows else (None, None)
    return published, last[0], last[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.3)
    ap.add_argument("--all", action="store_true", help="ask every initiative, not only new or changed ones")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="stop asking after this long (0 = no limit); the rest are asked next run")
    a = ap.parse_args()
    deadline = time.monotonic() + a.max_seconds if a.max_seconds else None

    eng = create_engine(_db(), pool_pre_ping=True, pool_recycle=300)
    with eng.connect() as c:
        rows = list(c.execute(PICK_ALL if a.all else PICK, {"lim": a.limit}))
        before = c.execute(GAP).scalar_one()
    print(f"[INFO] consultations with no date at all: {before} | Have Your Say this run: {len(rows)}")
    ctx = ssl.create_default_context(cafile=certifi.where())
    stored = 0
    why: Counter = Counter()
    for r in rows:
        if deadline and time.monotonic() > deadline:
            why["left for the next run (time budget)"] += 1
            continue
        m = _IID.search(r.portal_url or "")
        if not m:
            why["no id in url"] += 1
            continue
        got = _dates(m.group(1), ctx)
        if got is None:
            why["no published publication"] += 1
        elif isinstance(got, str):
            why[got] += 1
        elif a.rehearse:
            if stored < 5:
                print(f"   {m.group(1)}: published {got[0]:%Y-%m-%d}; last feedback "
                      + (f"{got[1]:%Y-%m-%d} -> {got[2]:%Y-%m-%d}" if got[2] else "none"))
            stored += 1
        else:
            for n in range(4):
                try:
                    with eng.begin() as c:
                        stored += c.execute(STORE, {
                            "p": got[0].date(), "fs": got[1].date() if got[1] else None,
                            "fe": got[2].date() if got[2] else None, "i": r.id}).rowcount
                    break
                except Exception:  # noqa: BLE001
                    eng.dispose(); time.sleep(2 * (n + 1))
        time.sleep(a.pause)
    with eng.connect() as c:
        after = c.execute(GAP).scalar_one()
    print(f"[INFO] {'would store' if a.rehearse else 'stored'}: {stored} | not: {dict(why)} | gap {before} -> {after}")
    # Upcoming initiatives have no publication yet and are asked again each night: an
    # answer of "none yet" is not a failure. Only a run the API never answered is.
    answered = stored + why.get("no published publication", 0) + why.get("no id in url", 0)
    if a.apply and rows and answered == 0:
        print("[ERROR] the API answered none of the requests; this run proves nothing")
        return 1
    print("[OK] every date is the API's own: earliest publishedDate; last publishedDate/endDate pair")
    return 0


if __name__ == "__main__":
    sys.exit(main())
