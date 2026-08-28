#!/usr/bin/env python3.12
"""
Per-body ingestion freshness for the MEUB News store (`eu_news_items`).

WHY THIS EXISTS (28 August 2026, /news Phase 4)
-----------------------------------------------
`/api/sync/health` reported the FAST tier as `runs_24h: 40, failures_24h: 0,
healthy: True` on the same morning that 29 of 51 bodies in the table that tier
feeds had received no item for more than a fortnight, and three of them (ERA,
EDPS, FRA) for more than eight months.

Both statements were true. The tier really did run forty times and really did
not raise. It just did not PERSIST anything for those bodies. The health check
counts runs that did not throw, not rows that landed, so a sync that fetches
nothing is indistinguishable from a sync that fetches everything.

That is the failure this script exists to make visible, and it is the same one
`feedback_silent_failure_reports_success` names: count PERSISTED changes, not
attempts.

TWO RULES THIS SCRIPT OBEYS
---------------------------
1. Rank by the EFFECTIVE date, `COALESCE(news_date, created_at::date)` -- the
   same expression `api/eu_news.py` orders by. Several upstream feeds (Europol,
   ESMA, EIB, Eurojust, ECHA ...) carry no date at all; their rows are undated
   BY DESIGN and `created_at` is what the product actually sorts them on.
   Ranking on `max(news_date)` instead reports those bodies as "no dated items
   at all" and sends you hunting a parser bug that does not exist. That mistake
   was made, and corrected, on the morning this file was written.

2. Three states, never two. A body with no rows at all is UNKNOWN, not fresh
   and not stale -- we have never successfully ingested it, which is a different
   defect from an ingest that stopped. `feedback_zero_denominator_is_not_a_pass`.

Exit codes: 0 ok / 1 stale bodies found / 2 dead bodies found (>90d).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STALE_DAYS = 14
DEAD_DAYS = 90


def _rows(conn, stale_days: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT institution,
               count(*)                                                AS n,
               max(COALESCE(news_date, created_at::date))              AS effective,
               max(news_date)                                          AS true_newest,
               count(*) FILTER (WHERE news_date IS NULL)               AS undated
        FROM eu_news_items
        WHERE institution IS NOT NULL
        GROUP BY 1
        ORDER BY max(COALESCE(news_date, created_at::date)) ASC NULLS FIRST
        """
    )
    today = _dt.date.today()
    out = []
    for inst, n, eff, true_newest, undated in cur.fetchall():
        age = (today - eff).days if eff else None
        if age is None:
            state = "unknown"          # rows exist but no usable date anywhere
        elif age > DEAD_DAYS:
            state = "dead"
        elif age > stale_days:
            state = "stale"
        else:
            state = "fresh"
        out.append({
            "institution": inst,
            "rows": n,
            "effective_newest": eff.isoformat() if eff else None,
            "true_newest": true_newest.isoformat() if true_newest else None,
            "undated_rows": undated,
            "age_days": age,
            "state": state,
            # An all-undated body is not a defect: the feed carries no date.
            "undated_by_design": undated == n,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS)
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg2

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("[ERROR] DATABASE_URL not set", file=sys.stderr)
        return 2
    conn = psycopg2.connect(dsn)
    rows = _rows(conn, args.stale_days)

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        dead = [r for r in rows if r["state"] == "dead"]
        stale = [r for r in rows if r["state"] == "stale"]
        unknown = [r for r in rows if r["state"] == "unknown"]
        fresh = [r for r in rows if r["state"] == "fresh"]

        print(f"MEUB NEWS INGESTION FRESHNESS  {_dt.date.today()}   "
              f"(stale >{args.stale_days}d, dead >{DEAD_DAYS}d)")
        print("=" * 78)
        for label, group in (("DEAD", dead), ("STALE", stale), ("UNKNOWN", unknown)):
            if not group:
                continue
            print(f"\n{label} ({len(group)})")
            for r in group:
                mark = " [undated feed]" if r["undated_by_design"] else ""
                print(f"   {r['institution']:<12} {str(r['age_days']):>4}d  "
                      f"newest={r['effective_newest']}  rows={r['rows']}{mark}")
        print(f"\nFRESH ({len(fresh)}): " + ", ".join(r["institution"] for r in fresh))

        print("\nVERDICT")
        if dead:
            print(f"  {len(dead)} body(ies) DEAD -- no item in over {DEAD_DAYS} days.")
        if stale:
            print(f"  {len(stale)} body(ies) STALE -- no item in over {args.stale_days} days.")
        if unknown:
            print(f"  {len(unknown)} body(ies) UNKNOWN -- rows present, no usable date. "
                  f"Not the same as fresh.")
        if not (dead or stale or unknown):
            print("  Every body ingested within the window.")
        print("  NOTE: /api/sync/health can report the FAST tier healthy while these "
              "stall.\n        It counts runs that did not throw, not rows that landed.")

    if any(r["state"] == "dead" for r in rows):
        return 2
    if any(r["state"] == "stale" for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
