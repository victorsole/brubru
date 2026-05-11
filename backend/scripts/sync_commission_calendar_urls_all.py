"""
Broad sync of commission_calendar_urls — loops over all 27 commissioners,
calling CommissionerAgendaClient.fetch_agenda() so each commissioner's
calendar page is scraped AND the global RSS feed is persisted.

This lifts public_url coverage on /api/v1/commissioners/{name}/agenda from
4 of 27 leaders to as many as the RSS feed + HTML scrape currently surface.

Run:
    python3.12 backend/scripts/sync_commission_calendar_urls_all.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


async def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from core.database import SessionLocal
    from services.api_clients.commissioner_agenda_client import (
        get_commissioner_agenda_client,
    )

    client = get_commissioner_agenda_client()
    profs = client.profiles if isinstance(client.profiles, list) else list(client.profiles)
    print(f"[INFO] Syncing {len(profs)} commissioners", flush=True)

    db = SessionLocal()
    counts = {"ok": 0, "no_leader_id": 0, "errors": 0, "events_returned": 0}
    start = time.time()
    try:
        for i, p in enumerate(profs, 1):
            try:
                profile, items = await client.fetch_agenda(p.slug, db=db)
                if not profile or not getattr(profile, "leader_id", None):
                    counts["no_leader_id"] += 1
                    print(f"  [{i:2}/{len(profs)}] {p.slug:<22}  no leader_id", flush=True)
                else:
                    counts["ok"] += 1
                    counts["events_returned"] += len(items)
                    print(f"  [{i:2}/{len(profs)}] {p.slug:<22}  leader_id={profile.leader_id} "
                          f"items={len(items)}", flush=True)
            except Exception as e:
                counts["errors"] += 1
                print(f"  [{i:2}/{len(profs)}] {p.slug:<22}  ERROR {type(e).__name__}: {e}", flush=True)
            # Soft throttle so we don't hammer commission.europa.eu
            await asyncio.sleep(1.0)
    finally:
        db.close()

    elapsed = time.time() - start
    print(f"\n[DONE] elapsed={elapsed:.0f}s {counts}", flush=True)

    # Snapshot the cache state
    from sqlalchemy import create_engine, text
    e = create_engine(os.environ['DATABASE_URL'])
    with e.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM commission_calendar_urls")).scalar()
        nl = c.execute(text("SELECT COUNT(DISTINCT leader_id) FROM commission_calendar_urls")).scalar()
        print(f"\n  commission_calendar_urls: {n} rows / {nl} distinct leader_ids")


if __name__ == "__main__":
    asyncio.run(main())
