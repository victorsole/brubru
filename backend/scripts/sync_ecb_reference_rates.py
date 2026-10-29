"""
Fill ecb_reference_rates (migration 318): the ECB's euro foreign exchange reference rates, which the
funding lists use to give an amount in another currency in euros (`amount_eur`, funding standard
Phase 2 step 6). Read from the ECB Data Portal (services/funding/ecb_rates.py).

Runs daily in the daily tier (api/cron.py) over the last 10 days, so a missed run or a late
publication is caught; the first fill reads from 1 Jan 2020. A rate already held is rewritten only if
the ECB's value changed (the touch trigger then moves last_updated). The tier records this job's run.
A run that reads no rate fails: the ECB publishes every TARGET working day.

Run: python3.12 scripts/sync_ecb_reference_rates.py [--apply] [--since YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import collections
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_funding_sedia import get_env  # noqa: E402
from services.funding.ecb_rates import fetch_rates  # noqa: E402

FIRST_DAY = date(2020, 1, 1)
DAILY_WINDOW = 10
COLUMNS = ("currency", "rate_date", "rate", "series_key", "source_url")
UPSERT = (
    f"INSERT INTO ecb_reference_rates ({', '.join(COLUMNS)}) VALUES %s "
    "ON CONFLICT (currency, rate_date) DO UPDATE SET rate = EXCLUDED.rate, series_key = EXCLUDED.series_key, "
    "source_url = EXCLUDED.source_url, scraped_at = now() "
    "WHERE (ecb_reference_rates.rate, ecb_reference_rates.series_key, ecb_reference_rates.source_url) "
    "IS DISTINCT FROM (EXCLUDED.rate, EXCLUDED.series_key, EXCLUDED.source_url)"
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--since", type=date.fromisoformat, default=None,
                    help=f"first day to read (default: {DAILY_WINDOW} days before the newest rate held, "
                         f"or {FIRST_DAY} when none is)")
    args = ap.parse_args(argv)

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        return 1
    conn = psycopg2.connect(db.replace("postgresql+psycopg2://", "postgresql://"))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT max(rate_date) FROM ecb_reference_rates")
            newest = cur.fetchone()[0]
        since = args.since or (newest - timedelta(days=DAILY_WINDOW) if newest else FIRST_DAY)
        rows = fetch_rates(since)
        if not rows:
            print(f"[ERROR] the ECB returned no reference rate since {since}")
            return 1
        by_currency = collections.Counter(r["currency"] for r in rows)
        last = max(r["rate_date"] for r in rows)
        print(f"[ECB] {len(rows)} rates since {since}, {len(by_currency)} currencies, newest {last}")
        if not args.apply:
            print("[DRY RUN] nothing written")
            return 0
        values = [tuple(r[c] for c in COLUMNS) for r in rows]
        written = 0
        with conn.cursor() as cur:
            for start in range(0, len(values), 1000):
                # one statement per chunk, so rowcount is that chunk's: new or changed rates only
                psycopg2.extras.execute_values(cur, UPSERT, values[start:start + 1000], page_size=1000)
                written += cur.rowcount
        conn.commit()
        print(f"[DONE] rates read={len(rows)} written={written} (new or changed)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
