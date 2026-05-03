"""
Ingest committee opinions (AD/PA documents) and reports/recommendations
(PR/RD) from OEIL Documentation Gateway for a list of procedures.

This is the missing piece for /api/v1/opinions: amendment_documents was only
being populated with AM/PR/PA types, never AD. After
ep_amendment_sync_service was widened to include AD/RD, we need a one-shot
backfill across recent procedures so the table actually contains AD rows.

Run:
    python3.12 backend/scripts/ingest_committee_opinions.py [--limit 30]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def get_env(key: str) -> str:
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)
    os.environ["DATABASE_URL"] = db_url

    import psycopg2
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    # Prefer procedures where committee work has actually started — INI/COD
    # files in early "announced" status have no docs yet. We pick by earlier
    # publication and the presence of some timeline activity.
    cur.execute("""
        SELECT oeil_procedure_ref FROM legislative_carriages
        WHERE oeil_procedure_ref ~ '^\\d{4}/\\d{4}\\(COD\\)$'
          AND lead_committee IS NOT NULL
          AND last_updated > NOW() - INTERVAL '90 days'
        ORDER BY last_updated DESC
        LIMIT %s
    """, (args.limit,))
    procedures = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    print(f"[INFO] {len(procedures)} procedures queued")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from services.scrapers.ep_amendment_sync_service import EPAmendmentSyncService

    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()
    service = EPAmendmentSyncService(db)

    totals = {"docs_parsed": 0, "amendments_stored": 0, "errors": 0}
    for ref in procedures:
        try:
            print(f"\n=== {ref} ===")
            res = await service.sync_amendments_for_procedure(ref)
            totals["docs_parsed"] += res.get("documents_parsed", 0)
            totals["amendments_stored"] += res.get("amendments_stored", 0)
            totals["errors"] += len(res.get("errors", []))
            print(f"  docs_parsed={res.get('documents_parsed', 0)} amendments_stored={res.get('amendments_stored', 0)}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERR] {ref}: {exc}")
            totals["errors"] += 1
    db.close()
    print(f"\n[DONE] {totals}")


if __name__ == "__main__":
    asyncio.run(main())
