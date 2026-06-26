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
from services.scrapers.cedefop_content import (  # noqa: E402
    cedefop_event_date, cedefop_event_dates_bulk,
)
from services.scrapers import tail_event_dates as _tail  # noqa: E402

_RESOLVERS = {
    "cedefop": cedefop_event_date,
    "eca": _tail.eca_event_date,
    "eda": _tail.eda_event_date,
    "sesar": _tail.sesar_event_date,
    "euiss": _tail.euiss_event_date,
    "eige": _tail.eige_event_date,
    "cinea": _tail.cinea_event_date,
}
# Bodies with a one-browser bulk resolver (rate-limited sites: a persistent
# Playwright context is throttled far less than per-row requests).
_BULK_RESOLVERS = {
    "cedefop": cedefop_event_dates_bulk,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=sorted(_RESOLVERS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap rows processed (0 = all)")
    ap.add_argument("--pace", type=float, default=0.25, help="seconds between fetches")
    ap.add_argument("--engine", choices=["requests", "playwright"], default="requests",
                    help="playwright = one-browser bulk resolver for rate-limited sites")
    args = ap.parse_args()

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
          f" via {args.engine}{' (dry-run)' if args.dry_run else ''}")

    stats = {"updated": 0, "missed": 0, "seen": 0}
    by_url = {url: row_id for row_id, url in rows}

    def apply(url, dt):
        stats["seen"] += 1
        if dt is None:
            stats["missed"] += 1
        else:
            stats["updated"] += 1
            if not args.dry_run:
                cur.execute("UPDATE economy_items SET document_date=%s WHERE id=%s",
                            (dt, by_url[url]))
                if stats["updated"] % 25 == 0:
                    conn.commit()
        if stats["seen"] % 50 == 0:
            print(f"  {stats['seen']}/{len(rows)}  resolved={stats['updated']}  "
                  f"missed={stats['missed']}", flush=True)

    if args.engine == "playwright":
        _BULK_RESOLVERS[args.body]([url for _, url in rows], apply)
    else:
        resolver = _RESOLVERS[args.body]
        for _, url in rows:
            apply(url, resolver(url))
            time.sleep(args.pace)

    if not args.dry_run:
        conn.commit()
    print(f"[DONE] {args.body}: resolved={stats['updated']}  missed={stats['missed']}"
          f"{' (no writes, dry-run)' if args.dry_run else ' (committed)'}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
