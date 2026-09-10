#!/usr/bin/env python3.12
"""Which OJ acts are still waiting for a Catalan full text, and for how long.

WHY
---
On 10 September 2026 the day's 127 L-series acts could not be translated: the
Publications Office had not yet ingested them, so Cellar 404'd every one and
EUR-Lex was behind its WAF. `translate_oj_daily_acts.py` records each failure and
retries after a 3-hour cooldown, so they translate themselves as Cellar catches
up -- usually within one or two working days.

The gap this closes: nothing would ever say if they DIDN'T. A pending act simply
stays pending, and the daily run reports success on the acts it could do. Silence
is not success. This makes the backlog visible and ageing, so an act that never
arrives becomes a question instead of a permanent absence.

Exit code 1 when anything has been waiting longer than --max-age-days, so it can
be wired into the morning routine as a real check rather than a printout.

    python3.12 -m backend.scripts.oj_catalan_backlog_report [--max-age-days 3]
"""
import argparse
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT + "/backend" not in sys.path:
    sys.path.insert(0, _REPO_ROOT + "/backend")

from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=3)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT e.oj_date,
                   count(*) AS total,
                   count(*) FILTER (WHERE ct.id IS NOT NULL) AS translated,
                   count(*) FILTER (WHERE ct.id IS NULL) AS pending,
                   (current_date - e.oj_date) AS age_days
              FROM oj_entries e
              LEFT JOIN catalan_translations ct
                     ON ct.celex = COALESCE(e.celex, e.oj_id)
             WHERE e.series = 'L'
               AND e.oj_date >= current_date - 21
             GROUP BY e.oj_date
             ORDER BY e.oj_date DESC
        """)).mappings().all()
    finally:
        db.close()

    print(f"{'OJ date':12} {'age':>4} {'acts':>5} {'Catalan':>8} {'pending':>8}")
    print("-" * 44)
    overdue = []
    for r in rows:
        flag = ""
        if r["pending"] and r["age_days"] > args.max_age_days:
            flag = "  <== OVERDUE"
            overdue.append((r["oj_date"], r["pending"], r["age_days"]))
        print(f"{str(r['oj_date']):12} {r['age_days']:>3}d {r['total']:>5} "
              f"{r['translated']:>8} {r['pending']:>8}{flag}")

    if overdue:
        print(f"\n[FAIL] {len(overdue)} OJ date(s) still missing Catalan full texts after "
              f"{args.max_age_days} days:")
        for d, p, a in overdue:
            print(f"         {d}: {p} acts pending, {a} days old")
        print("       Cellar ingestion normally takes 1-2 working days. Longer than that "
              "means the fetch path is broken, not that the source is late.")
        return 1

    print(f"\n[OK] nothing pending beyond {args.max_age_days} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
