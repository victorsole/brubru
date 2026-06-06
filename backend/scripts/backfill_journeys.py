#!/usr/bin/env python3
"""
Bulk-backfill the legislative-journey AI analysis across the whole universe of
dossiers that have substantive EP committee documents (~750), using the cheap
open-source HF Qwen engine (GPT-4o fallback). Resumable: skips dossiers whose
analysis is already ready and fresh (doc-set hash unchanged), so it can be re-run
or interrupted safely. After this one pass, new files fill in on-demand + via the
cron.

Usage:
    cd backend
    python3.12 scripts/backfill_journeys.py --concurrency 3            # full run
    python3.12 scripts/backfill_journeys.py --limit 20                 # first 20 only
    python3.12 scripts/backfill_journeys.py --tracked-only             # tracked files only
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from models.legislative_train import LegislativeCarriage  # noqa: E402
from services.analysis.legislative_journey_service import (  # noqa: E402
    generate_journey, get_journey, current_doc_set_hash,
)

_SUBSTANTIVE = ("draft_report", "amendment", "compromise_amendments",
                "voting_list", "opinion", "draft_opinion", "commission_document")


def _candidate_ids(tracked_only: bool) -> list[str]:
    """Carriage ids whose procedure has substantive committee documents."""
    db = SessionLocal()
    try:
        kinds = ", ".join(f"'{k}'" for k in _SUBSTANTIVE)
        if tracked_only:
            sql = f"""
                SELECT DISTINCT c.id::text
                FROM user_carriage_tracks t
                JOIN legislative_carriages c ON c.id = t.carriage_id
                WHERE t.archived_at IS NULL AND c.oeil_procedure_ref IS NOT NULL
                  AND EXISTS (SELECT 1 FROM ep_emeeting_documents d
                              WHERE d.procedure_ref = c.oeil_procedure_ref
                                AND d.doc_kind IN ({kinds}))
            """
        else:
            sql = f"""
                SELECT DISTINCT c.id::text
                FROM legislative_carriages c
                WHERE c.oeil_procedure_ref IS NOT NULL
                  AND EXISTS (SELECT 1 FROM ep_emeeting_documents d
                              WHERE d.procedure_ref = c.oeil_procedure_ref
                                AND d.doc_kind IN ({kinds}))
            """
        return [r[0] for r in db.execute(text(sql)).all()]
    finally:
        db.close()


async def _one(carriage_id: str, sem: asyncio.Semaphore, counters: dict) -> None:
    async with sem:
        db = SessionLocal()
        try:
            carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == carriage_id).first()
            if not carriage or not carriage.oeil_procedure_ref:
                counters["skipped"] += 1
                return
            ref = carriage.oeil_procedure_ref
            existing = get_journey(db, ref)
            if existing and existing["status"] == "ready" and existing["doc_set_hash"] == current_doc_set_hash(db, ref):
                counters["fresh"] += 1
                return
            res = await generate_journey(db, carriage)
            if res and res.get("status") == "ready":
                counters["done"] += 1
                print(f"[OK]  {ref:18s} {res.get('engine'):11s} layers={res.get('source_doc_count')} "
                      f"({counters['done']} done / {counters['total']})", flush=True)
            else:
                counters["failed"] += 1
                print(f"[ERR] {ref:18s} no result", flush=True)
        except Exception as e:
            counters["failed"] += 1
            print(f"[ERR] {carriage_id}: {e}", flush=True)
            db.rollback()
        finally:
            db.close()


async def main() -> None:
    ap = argparse.ArgumentParser()
    # Default 1: the HF (featherless) shared tier 429s under parallel load, so
    # sequential generation keeps most files on the cheap HF engine. Raise it to
    # go faster at the cost of more GPT-4o fallback.
    ap.add_argument("--concurrency", type=int, default=1, help="parallel generations (default 1, for HF reliability)")
    ap.add_argument("--limit", type=int, default=0, help="max dossiers to process (0 = all)")
    ap.add_argument("--tracked-only", action="store_true", help="only files tracked by a user")
    args = ap.parse_args()

    ids = _candidate_ids(args.tracked_only)
    if args.limit:
        ids = ids[:args.limit]
    counters = {"total": len(ids), "done": 0, "fresh": 0, "skipped": 0, "failed": 0}
    print(f"[BACKFILL] {len(ids)} candidate dossiers, concurrency={args.concurrency}", flush=True)

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.time()
    await asyncio.gather(*[_one(cid, sem, counters) for cid in ids])

    mins = (time.time() - t0) / 60
    print(f"[BACKFILL] done in {mins:.1f} min — generated={counters['done']} "
          f"fresh-skipped={counters['fresh']} no-procedure={counters['skipped']} "
          f"failed={counters['failed']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
