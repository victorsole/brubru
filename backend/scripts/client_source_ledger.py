#!/usr/bin/env python3.12
"""Per-client source ledger: is every source a client depends on fresh?

Why (23 September 2026): Joana Castella (Terraqui, LIFE DPP-TEX) found a TRIS
notification that Brubru had not seen. The TRIS feed had been frozen for six
and a half months and nothing measured it, because our source list for her was
drawn from our side only. A ledger lists every source bearing on a client's
remit, who supplied it, and a freshness test, and it lists what we do NOT
ingest as a gap instead of leaving it out.

States: OK, STALE (older than its threshold), NOT INGESTED (a known gap),
UNMEASURED (the freshness query failed: never read as fresh).

Usage (from backend/):
    python3.12 scripts/client_source_ledger.py                      # every ledger
    python3.12 scripts/client_source_ledger.py --client terraqui_dpp_tex
Exit code 1 when an ingested source is STALE or UNMEASURED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import logging
from pathlib import Path

logging.disable(logging.WARNING)

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

LEDGER_DIR = BACKEND_DIR / "data" / "client_sources"


def _age(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        value = value.date()
    return (dt.date.today() - value).days


def check(db, source: dict) -> dict:
    from sqlalchemy import text
    out = {"key": source["key"], "name": source["name"], "supplied_by": source.get("supplied_by", "")}
    if not source.get("ingested"):
        return out | {"state": "NOT INGESTED", "newest": None, "age_days": None}
    try:
        newest = db.execute(text(source["sql"])).scalar()
    except Exception as exc:  # noqa: BLE001 -- a broken query is UNMEASURED, never fresh
        db.rollback()
        return out | {"state": "UNMEASURED", "newest": None, "age_days": None,
                      "error": str(exc).split("\n")[0][:160]}
    age = _age(newest)
    if age is None:
        state = "UNMEASURED"
    else:
        state = "OK" if age <= source["stale_after_days"] else "STALE"
    return out | {"state": state, "newest": str(newest)[:10] if newest else None,
                  "age_days": age, "threshold": source["stale_after_days"]}


def run(client: str | None) -> tuple[list[dict], bool]:
    from core.database import SessionLocal
    files = [LEDGER_DIR / f"{client}.json"] if client else sorted(LEDGER_DIR.glob("*.json"))
    results, bad = [], False
    db = SessionLocal()
    try:
        for f in files:
            ledger = json.loads(f.read_text())
            rows = [check(db, s) for s in ledger["sources"]]
            bad |= any(r["state"] in ("STALE", "UNMEASURED") for r in rows)
            results.append({"client": ledger["client"], "rows": rows})
    finally:
        db.close()
    return results, bad


def _record(results: list[dict]) -> None:
    """A daily job, not a reminder (23 Sep 2026): the ledger used to run only
    when someone ran /news. Degraded when any ingested source is STALE or
    UNMEASURED, naming them, so the health endpoint shows it."""
    from core.database import SessionLocal
    from services.sync.freshness import record_run
    bad = [f"{r['client'].split(' (')[0]}: {row['key']} {row['state']}"
           for r in results for row in r["rows"] if row["state"] in ("STALE", "UNMEASURED")]
    db = SessionLocal()
    try:
        record_run(db, source_key="client_source_ledger", tier="daily",
                   status="degraded" if bad else "success",
                   items_added=sum(len(r["rows"]) for r in results),
                   error="; ".join(bad)[:1900] or None)
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record", action="store_true",
                    help="write one sync_runs row (the daily cron passes this)")
    a = ap.parse_args()
    results, bad = run(a.client)
    if a.record:
        _record(results)
    if a.json:
        print(json.dumps(results, indent=2, default=str))
        return 1 if bad else 0
    for r in results:
        print(f"\nSOURCE LEDGER: {r['client']}")
        for row in r["rows"]:
            age = f"{row['age_days']}d" if row.get("age_days") is not None else "--"
            lim = f"(max {row['threshold']}d)" if row.get("threshold") else ""
            sup = f"  [supplied by {row['supplied_by']}]" if row.get("supplied_by") else ""
            print(f"   {row['state']:<12} {str(row.get('newest') or ''):<10} {age:>6} {lim:<10} {row['name'][:70]}{sup}")
            if row.get("error"):
                print(f"   {'':<12} error: {row['error']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
