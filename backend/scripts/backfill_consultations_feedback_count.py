"""
Backfill feedback_count on public_consultations rows that have a numeric
initiative_id by querying the EC HYS feedback summary endpoint.

The legacy HYS detail API (`groupInitiativesByType`) is dead — it only
returns the SPA HTML wrapper. But the feedback API
(`/api/allFeedback?publicationId={id}&pageSize=1`) still returns JSON with
`totalElements`, which IS the live feedback count for that publication.

The publicationId == initiative_id for all rows we hold (verified for
13693, 15912, 13174).

Run:
    python3.12 backend/scripts/backfill_consultations_feedback_count.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_consultations_feedback_count.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
FEEDBACK_API = "https://ec.europa.eu/info/law/better-regulation/api/allFeedback"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0)"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


async def fetch_total(client: httpx.AsyncClient, pub_id: int) -> Optional[int]:
    try:
        r = await client.get(
            FEEDBACK_API,
            params={"publicationId": pub_id, "page": 0, "pageSize": 1, "sort": "desc"},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return int(data.get("totalElements", 0))
    except Exception:
        return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, initiative_id, feedback_count
          FROM public_consultations
         WHERE initiative_id ~ '^[0-9]+$'
         ORDER BY last_updated DESC
         LIMIT %s
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    cur.close()
    print(f"[INFO] {len(rows)} rows queued (apply={args.apply})")

    updated = unchanged = failed = 0
    async with httpx.AsyncClient(
        timeout=15.0,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        for row_id, init_id, current_count in rows:
            total = await fetch_total(client, int(init_id))
            if total is None:
                print(f"  [ERR] {init_id}: API failed")
                failed += 1
                continue

            current_count = int(current_count or 0)
            if total == current_count:
                print(f"  [.] {init_id}: count={total} (unchanged)")
                unchanged += 1
                continue

            print(f"  [OK] {init_id}: count={current_count} -> {total}")
            if args.apply:
                upd = conn.cursor()
                upd.execute(
                    "UPDATE public_consultations SET feedback_count = %s, last_updated = NOW() WHERE id = %s",
                    (total, row_id),
                )
                conn.commit()
                upd.close()
            updated += 1

            # Be polite to the upstream — 200ms between calls
            time.sleep(0.2)

    conn.close()
    print(f"[DONE] updated={updated} unchanged={unchanged} failed={failed}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    asyncio.run(main())
