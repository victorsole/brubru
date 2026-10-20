#!/usr/bin/env python3.12
"""Re-read TRIS notifications whose stored title is not the notification's English title.

/api/v2/commission/tris-notifications served 43 notifications titled "Stakeholders
Contributions" (a section heading the scraper took for the title) and 129 titles in the
notifying country's language: TRIS shows the original title until its English translation
arrives, and the sync never read the page again ("Lufttüchtigkeitshinweis Nr. 40B" is now
"Airworthiness Notice No. 40B – Inspection of On-Board Equipment"). This re-reads those
pages through the daily sync's own scraper and upsert, a few per run (TRIS throttles), so a
translation published later reaches the API (16 Oct 2026).

    python3.12 scripts/refresh_tris_titles.py                 # dry run: what would be re-read
    python3.12 scripts/refresh_tris_titles.py --apply --limit 40 --max-seconds 600
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import re
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services.scrapers.dg_grow.tris_scraper import SECTION_HEADINGS, TrisRateLimited  # noqa: E402

_ENGLISH = set("the of and for on to in amending amendment regulation regulations draft decree law "
               "act order rules concerning on requirements technical with by ordinance bill".split())
# Words that mark another language: a title with one of them and no English word is the
# notifying country's own ("Besluit van (datum) tot wijziging van het Besluit ...").
_FOREIGN = set("van het tot een voor der die das und zur des von mit les la le du et relatif portant "
               "el los las por que del di della per il sprawie na do da para privind si och om af til fra "
               "zakon zakona nariadenie vyhlaska asetus maarus rozporzadzenie".split())
ROWS = text("""SELECT notification_number, title, source_url FROM tris_notifications
               WHERE source_url ~ '/notification/[0-9]+' ORDER BY notification_date DESC NULLS LAST""")


def needs_title(title: str | None) -> bool:
    """A section heading, a reference stand-in, or a title with no English word."""
    t = (title or "").strip()
    if not t or t.lower() in SECTION_HEADINGS or t.startswith("TRIS Notification"):
        return True
    if "confidential, no title published" in t:
        return False
    words = re.findall(r"[^\W\d_]+", t.lower())
    if any(w in _ENGLISH for w in words):
        return False
    non_ascii = any(ord(ch) > 127 for ch in t)
    return len(t) > 25 and (non_ascii or any(w in _FOREIGN for w in words))


def _db_url() -> str:
    """The environment first (Railway has no .env file), then backend/.env."""
    import os
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = BACKEND / ".env"
    m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M) if env.exists() else None
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


async def run(apply: bool, limit: int, max_seconds: int) -> int:
    from services.scrapers.dg_grow.dg_grow_sync_service import DGGrowSyncService
    engine = create_engine(_db_url(), pool_pre_ping=True)
    with engine.connect() as c:
        rows = [r for r in c.execute(ROWS) if needs_title(r.title)]
    print(f"[INFO] {len(rows)} notification(s) without their English title")
    if not apply:
        for r in rows[:5]:
            print(f"   {r.notification_number}: {r.title[:80]!r}")
        return 0
    started, read, fixed, still = time.monotonic(), 0, 0, 0
    stats = {"new": 0, "updated": 0, "errors": 0, "synced": 0}
    with Session(engine) as db:
        svc = DGGrowSyncService(db)
        for r in rows[:limit]:
            if max_seconds and time.monotonic() - started > max_seconds:
                print("[INFO] time budget reached")
                break
            nid = int(re.search(r"/notification/(\d+)", r.source_url).group(1))
            try:
                notif = await svc.tris._safe_notification(nid)
            except TrisRateLimited:
                # TRIS refused us and Scrape.do could not read the page either. The titles
                # wait for the next run; refusing access is not a failure of this job.
                print(f"[SYNC_STATUS] degraded: TRIS throttled at notification {nid} (directly and via "
                      f"Scrape.do); read {read}, {fixed} fixed, the rest wait for the next run")
                break
            read += 1
            if not notif or needs_title(notif.get("title")):
                still += 1
                continue
            svc._write_tris(db, notif, stats)
            db.commit()
            fixed += 1
    print(f"[DONE] read {read}: {fixed} now carry their English title, {still} not yet translated at TRIS")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-seconds", type=int, default=0)
    a = ap.parse_args()
    sys.exit(asyncio.run(run(a.apply, a.limit, a.max_seconds)))
