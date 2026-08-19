"""
Scraper-health detector — the "self-healing fleet" canary (built 2026-08-17).

The EU's rolling ECL CMS migration silently broke 14+ economy scrapers this
year; each just started returning 0 and it took a manual fetched_at audit to
find them. This detector turns that audit into a repeatable check so a break is
caught the day it happens, not weeks later.

Two signals, cheap-then-definitive:
  1. DB scan (fast, always): per registered (body, item_type) scraper, the row
     count and days since max(fetched_at). A broken scraper stops upserting, so
     its rows stop being touched and fetched_at goes stale.
  2. Live confirm (only for stale/empty candidates): run the ingest fn and count
     what it parses. This separates a real break from a mere cron gap.

Classification (empty-vs-broken is the hard 20% — resolved via the DB baseline):
  HEALTHY  : parses > 0 (works), fetched recently.
  CRON-GAP : parses > 0 but fetched_at is stale -> scraper fine, cron behind. low.
  BROKEN   : parses 0 (or raised) AND the pair has historical rows -> regression. HIGH.
  ERROR    : the ingest fn raised. HIGH.
  EMPTY?   : parses 0 AND 0 historical rows -> never populated / maybe genuinely
             empty (e.g. an agency with no open tenders). review, low.
  STALE    : (fast mode only) stale fetched_at, not yet live-confirmed.

Usage:
  python3.12 scripts/scraper_health.py                 # confirm mode (default)
  python3.12 scripts/scraper_health.py --fast          # DB-only, no live runs
  python3.12 scripts/scraper_health.py --full          # live-run every scraper
  python3.12 scripts/scraper_health.py --body eppo cedefop   # scope to bodies
  python3.12 scripts/scraper_health.py --json out.json # also write JSON
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

# Allow `python3.12 scripts/scraper_health.py` from the repo root or backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")
for _n in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    _lg = logging.getLogger(_n)
    _lg.setLevel(logging.CRITICAL)
    _lg.disabled = True

from core.database import SessionLocal
from sqlalchemy import text
import scripts.sync_economy as se

STALE_DAYS = 10          # fetched_at older than this = candidate for a live check
RETRIES = 3              # retry a 0/error live-run — transient blips (rate-limits,
RETRY_DELAY = 2.5        # network) must not raise a BROKEN false-positive. First >0 wins.
SEVERITY = {"BROKEN": 0, "ERROR": 0, "CRON-GAP": 1, "STALE": 1,
            "EMPTY?": 2, "HEALTHY": 3, "OK": 3}


def _db_state(db):
    rows = db.execute(text(
        "SELECT body_code, item_type, count(*) n, max(fetched_at) f "
        "FROM economy_items GROUP BY body_code, item_type")).fetchall()
    return {(r.body_code, r.item_type): (r.n, r.f) for r in rows}


def _classify(n_rows, last_sync, days, parse_count, err):
    if parse_count is None and err is None:      # fast mode, not live-run
        if last_sync is None:
            return "EMPTY?", "no rows, not live-checked"
        return ("STALE", f"{days}d stale") if (days is not None and days > STALE_DAYS) \
            else ("OK", f"{days}d")
    if err is not None:
        return "ERROR", err
    if parse_count > 0:
        stale = days is not None and days > STALE_DAYS
        return ("CRON-GAP", f"parses {parse_count}, {days}d stale") if stale \
            else ("HEALTHY", f"parses {parse_count}")
    # parses 0 -> empty-vs-broken via the DB baseline
    if n_rows and n_rows > 0:
        return "BROKEN", f"parses 0 but has {n_rows} rows (regression)"
    return "EMPTY?", "parses 0, no historical rows"


def run(mode="confirm", bodies=None):
    # Read DB state up front and CLOSE the connection before the (slow, minutes-
    # long) live scraper runs — otherwise the idle Supabase connection is dropped
    # and db.close() later raises SSL-closed.
    db = SessionLocal()
    try:
        state = _db_state(db)
    finally:
        db.close()
    today = datetime.now(timezone.utc).date()
    results = []
    for (body, itype), fn in sorted(se.INGESTORS.items()):
        if bodies and body not in bodies:
            continue
        n_rows, last_sync = state.get((body, itype), (0, None))
        days = (today - last_sync.date()).days if last_sync else None
        stale = (last_sync is None) or (days is not None and days > STALE_DAYS)
        do_live = mode == "full" or (mode == "confirm" and (stale or n_rows == 0))
        parse_count, err, ms, attempts = None, None, None, 0
        if do_live:
            t0 = time.time()
            parse_count = 0
            for attempt in range(RETRIES):        # first >0 wins; retry filters blips
                attempts = attempt + 1
                try:
                    pc = len(fn(fetch_bodies=False))
                    if pc > 0:
                        parse_count, err = pc, None
                        break
                    parse_count, err = 0, None
                except Exception as e:            # noqa: BLE001 — record any failure
                    err = f"{type(e).__name__}: {str(e)[:90]}"
                if attempt < RETRIES - 1:
                    time.sleep(RETRY_DELAY)
            ms = round((time.time() - t0) * 1000)
        cls, detail = _classify(n_rows, last_sync, days, parse_count, err)
        results.append({"body": body, "type": itype, "rows": n_rows,
                        "days_since_sync": days, "parse": parse_count,
                        "attempts": attempts, "ms": ms, "cls": cls, "detail": detail})
    results.sort(key=lambda r: (SEVERITY.get(r["cls"], 9), r["body"], r["type"]))
    return results


def main():
    ap = argparse.ArgumentParser(description="Detect broken/stale economy scrapers.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--fast", action="store_true", help="DB-only (fetched_at); no live runs")
    g.add_argument("--full", action="store_true", help="live-run EVERY scraper (slow, definitive)")
    ap.add_argument("--body", nargs="*", help="scope to these body codes")
    ap.add_argument("--json", help="also write results to this JSON path")
    ap.add_argument("--alerts-only", action="store_true", help="print only BROKEN/ERROR")
    args = ap.parse_args()
    mode = "fast" if args.fast else ("full" if args.full else "confirm")

    results = run(mode=mode, bodies=set(args.body) if args.body else None)
    from collections import Counter
    counts = Counter(r["cls"] for r in results)
    print(f"[scraper_health mode={mode}] {len(results)} scrapers | {dict(counts)}")
    print(f"{'STATUS':9} {'body':14} {'type':22} {'rows':>7} {'parse':>6}  detail")
    for r in results:
        if args.alerts_only and r["cls"] not in ("BROKEN", "ERROR"):
            continue
        if r["cls"] in ("HEALTHY", "OK") and not args.full:
            continue  # keep the report to what needs attention unless --full
        print(f"{r['cls']:9} {r['body']:14} {r['type']:22} {r['rows']:>7} "
              f"{str(r['parse']) if r['parse'] is not None else '-':>6}  {r['detail']}")
    alerts = [r for r in results if r["cls"] in ("BROKEN", "ERROR")]
    print(f"\n>>> {len(alerts)} ACTIONABLE (BROKEN/ERROR)")
    if args.json:
        import json
        json.dump(results, open(args.json, "w"), default=str)
    return 1 if alerts else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
