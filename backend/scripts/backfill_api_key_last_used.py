#!/usr/bin/env python3.12
"""Repair `api_keys.last_used_at` from the usage ledger.

Why this exists
---------------
`api/auth_api_key.py` (REST) has always stamped `last_used_at` via a background
task. `api/mcp_http.py` never did, so a key used ONLY through MCP read
`last_used_at = NULL` no matter how much traffic it carried. One client's key
showed "never used" against 178 recorded `mcp:ask_dpp` calls.

The write path was fixed on 25 Aug 2026 (`d5bdf18a`), but history was not, so the
column still under-reports. That matters beyond tidiness: any "revoke keys nobody
uses" cleanup built on this column would revoke live keys.

`api_usage_events` is the system of record and has the answer -- one row per
metered call, with `created_at`. This copies the max of those per key.

Deliberate choices
------------------
* **`GREATEST(existing, ledger_max)`**, never a blind overwrite. A key used since
  the fix has a live timestamp that may be NEWER than anything in the ledger
  window; moving it backwards would be a fresh lie in the other direction.
* **Probes are included.** `is_probe` marks a call as *ours*, not as *not a call*.
  The key really was used; excluding probes would recreate "never used" for a key
  with traffic, which is the exact defect being repaired.
* **Idempotent.** Re-running changes nothing once converged, so it is safe in a
  cron or after a restore.

Usage:
    python3.12 scripts/backfill_api_key_last_used.py            # dry-run
    python3.12 scripts/backfill_api_key_last_used.py --apply
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")


# Rows needing repair: the ledger knows about a call the column does not reflect.
# `IS DISTINCT FROM` rather than `<` so a NULL column is included -- `NULL < x` is
# NULL, which would have silently excluded the very rows this script exists for.
_PENDING = """
    SELECT k.id,
           k.name,
           k.last_used_at            AS current_value,
           agg.max_seen              AS ledger_max,
           agg.calls
    FROM api_keys k
    JOIN (
        SELECT api_key_id, max(created_at) AS max_seen, count(*) AS calls
        FROM api_usage_events
        WHERE api_key_id IS NOT NULL
        GROUP BY api_key_id
    ) agg ON agg.api_key_id = k.id
    WHERE k.last_used_at IS NULL OR k.last_used_at < agg.max_seen
    ORDER BY agg.calls DESC
"""

_APPLY = """
    UPDATE api_keys k
    SET last_used_at = GREATEST(COALESCE(k.last_used_at, agg.max_seen), agg.max_seen)
    FROM (
        SELECT api_key_id, max(created_at) AS max_seen
        FROM api_usage_events
        WHERE api_key_id IS NOT NULL
        GROUP BY api_key_id
    ) agg
    WHERE agg.api_key_id = k.id
      AND (k.last_used_at IS NULL OR k.last_used_at < agg.max_seen)
"""


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    args = ap.parse_args()

    with _engine().connect() as conn:
        pending = conn.execute(text(_PENDING)).mappings().all()

        # Report the whole population, not just the delta, so a run that changes
        # nothing is distinguishable from a run that could not see anything.
        totals = conn.execute(text("""
            SELECT (SELECT count(DISTINCT api_key_id) FROM api_usage_events
                      WHERE api_key_id IS NOT NULL)              AS keys_with_usage,
                   (SELECT count(*) FROM api_keys
                      WHERE last_used_at IS NOT NULL)            AS keys_with_timestamp
        """)).mappings().one()

        print(f"[INFO] keys with usage events : {totals['keys_with_usage']}")
        print(f"[INFO] keys with last_used_at : {totals['keys_with_timestamp']}")
        print(f"[INFO] keys needing repair    : {len(pending)}")

        if not pending:
            print("[OK] nothing to do -- column already agrees with the ledger.")
            return 0

        print(f"\n{'key name':38} {'calls':>6}  {'current':<26} -> ledger max")
        for r in pending:
            cur = str(r["current_value"]) if r["current_value"] else "NULL (never used?)"
            print(f"{(r['name'] or '(unnamed)')[:38]:38} {r['calls']:>6}  {cur:<26} -> {r['ledger_max']}")

        if not args.apply:
            print(f"\n[DRY-RUN] {len(pending)} key(s) would be repaired. Re-run with --apply.")
            return 0

        result = conn.execute(text(_APPLY))
        conn.commit()
        print(f"\n[APPLIED] {result.rowcount} key(s) repaired.")

        # Verify from the database, not from rowcount -- rowcount says what the
        # statement claims it touched, not what the table now holds.
        left = conn.execute(text(_PENDING)).mappings().all()
        if left:
            print(f"[FAIL] {len(left)} key(s) still stale after the update.")
            return 1
        print("[OK] verified: every key with usage now carries a last_used_at.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
