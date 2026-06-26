#!/usr/bin/env python3.12
"""
Backfill document_date on event rows that were ingested before their scraper
extracted dates. Cedefop is 95% of the gap (its date sits in a Drupal daterange
field the generic walker missed); the date is read from each event's detail page.

Usage:
    python3.12 scripts/backfill_event_dates.py --body cedefop            # apply
    python3.12 scripts/backfill_event_dates.py --body cedefop --dry-run  # count only
    python3.12 scripts/backfill_event_dates.py --body cedefop --limit 20 # sample
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import psycopg2  # noqa: E402

# Per-body detail-page date resolvers (extend as the tail of bodies is fixed).
from services.scrapers.cedefop_content import cedefop_event_date  # noqa: E402

_RESOLVERS = {
    "cedefop": cedefop_event_date,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=sorted(_RESOLVERS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap rows processed (0 = all)")
    ap.add_argument("--pace", type=float, default=0.25, help="seconds between fetches")
    args = ap.parse_args()

    resolver = _RESOLVERS[args.body]
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("[ERROR] DATABASE_URL not set")
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, public_url FROM economy_items "
        "WHERE body_code=%s AND item_type='event' AND document_date IS NULL "
        "ORDER BY id",
        (args.body,),
    )
    rows = cur.fetchall()
    if args.limit:
        rows = rows[: args.limit]
    print(f"[INFO] {args.body}: {len(rows)} dateless event rows to resolve"
          f"{' (dry-run)' if args.dry_run else ''}")

    updated = missed = 0
    for i, (row_id, url) in enumerate(rows, 1):
        dt = resolver(url)
        if dt is None:
            missed += 1
        else:
            updated += 1
            if not args.dry_run:
                cur.execute(
                    "UPDATE economy_items SET document_date=%s WHERE id=%s", (dt, row_id)
                )
                if updated % 50 == 0:
                    conn.commit()
        if i % 100 == 0:
            print(f"  {i}/{len(rows)}  resolved={updated}  missed={missed}")
        time.sleep(args.pace)

    if not args.dry_run:
        conn.commit()
    print(f"[DONE] {args.body}: resolved={updated}  missed={missed}"
          f"{' (no writes, dry-run)' if args.dry_run else ' (committed)'}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
