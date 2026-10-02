#!/usr/bin/env python3.12
"""Re-read the notification message of TRIS rows that were stored with no text.

A full walk of /api/v2/commission/tris-notifications (237 rows, both windows) found
every datapoint present but 57 bodies under 400 characters. 55 of 237 rows hold NO text
in main_content, full_text_summary or short_summary, so the API falls back to a
title/country/date stub. The page has the text: 2026/0080/FR carries a full notification
message (field 8 content, field 9 grounds) of about 3,000 characters.

The scraper already extracts those fields; these rows predate it. This re-reads each one
through the same scraper and writes through the same upsert the daily sync uses, so there
is one writer and no second parser to drift. Rows stay untouched when the page yields
nothing.

    python3.12 scripts/backfill_tris_message_text.py --rehearse
    python3.12 scripts/backfill_tris_message_text.py --apply
"""
from __future__ import annotations

import argparse, asyncio, pathlib, re, sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

PICK = text("""
    SELECT notification_number, source_url FROM tris_notifications
     WHERE coalesce(main_content,'')='' AND coalesce(full_text_summary,'')=''
       AND coalesce(short_summary,'')='' AND source_url ~ '/notification/[0-9]+'
     ORDER BY notification_number DESC""")
GAP = text("""SELECT count(*) FROM tris_notifications
     WHERE coalesce(main_content,'')='' AND coalesce(full_text_summary,'')=''
       AND coalesce(short_summary,'')=''""")


def _db_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


async def run(apply: bool) -> int:
    from services.scrapers.dg_grow.dg_grow_sync_service import DGGrowSyncService
    engine = create_engine(_db_url(), pool_pre_ping=True)
    with engine.connect() as c:
        rows = list(c.execute(PICK))
        before = c.execute(GAP).scalar_one()
    print(f"[INFO] TRIS rows with no text: {before}  (re-readable: {len(rows)})")
    if not apply:
        print("[INFO] rehearsal only"); return 0
    # _write_tris counts into these keys; a missing "synced" raised KeyError on the first
    # run and logged three rows as "Failed to sync" while the loop still counted them.
    stats = {"new": 0, "updated": 0, "errors": 0, "synced": 0}
    got = miss = 0
    with Session(engine) as db:
        svc = DGGrowSyncService(db)
        for r in rows:
            nid = int(re.search(r"/notification/(\d+)", r.source_url).group(1))
            notif = await svc.tris._safe_notification(nid)
            if not notif or not (notif.get("main_content") or notif.get("grounds")):
                miss += 1; continue
            svc._write_tris(db, notif, stats)
            got += 1
        db.commit()
    with engine.connect() as c:
        after = c.execute(GAP).scalar_one()
    print(f"[INFO] re-read with text: {got} | page yielded none: {miss} | gap {before} -> {after}")
    if rows and got == 0:
        print("[ERROR] nothing recovered; this run proves nothing"); return 1
    print("[OK] written through the daily sync's own upsert"); return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true"); g.add_argument("--apply", action="store_true")
    sys.exit(asyncio.run(run(ap.parse_args().apply)))
