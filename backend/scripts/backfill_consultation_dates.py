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

    python3.12 scripts/backfill_consultation_dates.py --limit 20 --rehearse
    python3.12 scripts/backfill_consultation_dates.py --limit 3000 --apply
"""
from __future__ import annotations

import argparse
import json
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

PICK = text("""SELECT id, portal_url FROM public_consultations
                WHERE start_date IS NULL AND portal_url LIKE '%%/initiatives/%%'
                ORDER BY id LIMIT :lim""")
STORE = text("""UPDATE public_consultations
                   SET start_date = coalesce(start_date, :s), end_date = coalesce(end_date, :e),
                       last_updated = now()
                 WHERE id = :i AND start_date IS NULL""")
GAP = text("SELECT count(*) FROM public_consultations WHERE start_date IS NULL")


def _db() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


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
    start, end = min(pubs, key=lambda p: p[0])
    return start, end


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.3)
    a = ap.parse_args()

    eng = create_engine(_db(), pool_pre_ping=True, pool_recycle=300)
    with eng.connect() as c:
        rows = list(c.execute(PICK, {"lim": a.limit}))
        before = c.execute(GAP).scalar_one()
    print(f"[INFO] consultations with no start date: {before} | Have Your Say this run: {len(rows)}")
    ctx = ssl.create_default_context(cafile=certifi.where())
    stored = 0
    why: Counter = Counter()
    for r in rows:
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
                print(f"   {m.group(1)}: {got[0]:%Y-%m-%d} -> {got[1]:%Y-%m-%d}" if got[1] else f"   {m.group(1)}: {got[0]:%Y-%m-%d}")
            stored += 1
        else:
            for n in range(4):
                try:
                    with eng.begin() as c:
                        stored += c.execute(STORE, {"s": got[0], "e": got[1], "i": r.id}).rowcount
                    break
                except Exception:  # noqa: BLE001
                    eng.dispose(); time.sleep(2 * (n + 1))
        time.sleep(a.pause)
    with eng.connect() as c:
        after = c.execute(GAP).scalar_one()
    print(f"[INFO] {'would store' if a.rehearse else 'stored'}: {stored} | not: {dict(why)} | gap {before} -> {after}")
    if a.apply and rows and stored == 0:
        print("[ERROR] nothing stored; this run proves nothing")
        return 1
    print("[OK] every date is the publication's own publishedDate/endDate from the API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
