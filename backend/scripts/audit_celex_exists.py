"""Do the CELEX values we publish exist in EUR-Lex? Ask the Publications Office.

GovClipping found 9.8% of ours missing on 25 September 2026, and nothing on our side had
noticed, because a fabricated CELEX looks exactly like a real one: it is well formed, it
builds a plausible EUR-Lex URL, and the URL simply 404s for whoever follows it.

This samples eu_laws (newest first, since new rows are the ones a bad parser would be
producing now) and asks Cellar which of the sampled CELEX exist. It records the run in
`sync_runs` and FAILS when the miss rate goes above the threshold, so the next time this
starts happening we hear it from our own ledger rather than from a customer.

Usage (from backend/):
    python3.12 scripts/audit_celex_exists.py                    # 500 newest, report only
    python3.12 scripts/audit_celex_exists.py --sample 2000 --record
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

XSD = "^^<http://www.w3.org/2001/XMLSchema#string>"
BATCH = 80
# Measured 25 Sep 2026: 1,897 of 19,081 (9.9%) did not exist. After the correction the
# remainder are acts Cellar genuinely does not hold (ECB acts, agency board decisions,
# EEA declarations), so a NEW rise above this is a parser producing rubbish again.
DEFAULT_MAX_MISS_PCT = 6.0


async def _exists(celexes: list[str]) -> set[str]:
    client, found = CellarSPARQLClient(), set()
    for i in range(0, len(celexes), BATCH):
        vals = " ".join(f'"{c}"{XSD}' for c in celexes[i:i + BATCH])
        q = (f"PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
             f"SELECT ?celex WHERE {{ VALUES ?celex {{ {vals} }} "
             f"?w cdm:resource_legal_id_celex ?celex . }}")
        try:
            for r in await client.select(q):
                v = r["celex"]
                found.add(v["value"] if isinstance(v, dict) else v)
        except Exception as exc:  # a failed batch is reported, never counted as "all missing"
            print(f"  [ERROR] batch {i // BATCH + 1}: {type(exc).__name__}: {exc}", flush=True)
            raise
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=500)
    ap.add_argument("--max-miss-pct", type=float, default=DEFAULT_MAX_MISS_PCT)
    ap.add_argument("--record", action="store_true", help="write the outcome to sync_runs")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    db = SessionLocal()
    error, miss_pct, missing = None, 0.0, []
    try:
        celexes = [r[0] for r in db.execute(text(
            "SELECT celex FROM eu_laws WHERE celex IS NOT NULL "
            "ORDER BY created_at DESC NULLS LAST, id DESC LIMIT :n"), {"n": args.sample}).fetchall()]
        celexes = sorted(set(celexes))
        print(f"[INFO] checking {len(celexes):,} CELEX (newest first)")
        try:
            found = asyncio.run(_exists(celexes))
            missing = sorted(set(celexes) - found)
            miss_pct = 100.0 * len(missing) / len(celexes) if celexes else 0.0
            print(f"[RESULT] {len(missing):,} of {len(celexes):,} do not exist in Cellar "
                  f"({miss_pct:.1f}%)")
            for c in missing[:10]:
                print(f"   missing: {c}")
            if miss_pct > args.max_miss_pct:
                error = (f"{miss_pct:.1f}% of sampled CELEX do not exist in EUR-Lex "
                         f"(threshold {args.max_miss_pct}%)")
                print(f"[FAIL] {error}")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print(f"[ERROR] {error}")

        if args.record:
            try:
                from services.sync.freshness import record_run
                record_run(db, source_key="celex_exists_audit", tier="weekly",
                           status="failed" if error else "success",
                           items_added=len(missing), error=error,
                           started_at=started, finished_at=datetime.now(timezone.utc))
                db.commit()
                print("[INFO] outcome recorded in sync_runs")
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] could not record the run: {type(exc).__name__}: {exc}")
        return 1 if error else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
