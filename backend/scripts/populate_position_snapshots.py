"""
Populate file_position_snapshots for all "implementable" legislative carriages.

A carriage is implementable if it has at least:
  - An OEIL procedure ref AND
  - Either (a) mep_amendments rows, or (b) a Commission document (COM/JOIN),
    or (c) OEIL key events.

Usage:
    python3.12 scripts/populate_position_snapshots.py
    python3.12 scripts/populate_position_snapshots.py --limit 50
    python3.12 scripts/populate_position_snapshots.py --only 2022/0196(COD) --force

Runs aggregator for each eligible carriage; upserts the snapshot. Skips
carriages whose snapshot is fresh (<24h) unless --force is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from sqlalchemy import func  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from models.commission_document import CommissionDocument  # noqa: E402
from models.file_position import FilePositionSnapshot  # noqa: E402
from models.legislative_train import LegislativeCarriage  # noqa: E402
from models.mep_amendment import MEPAmendment  # noqa: E402
from services.positions import get_position_aggregator  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logger = logging.getLogger("populate-positions")


def _eligible_carriages(db: Session, only: Optional[str] = None) -> list[LegislativeCarriage]:
    q = db.query(LegislativeCarriage).filter(LegislativeCarriage.oeil_procedure_ref.isnot(None))
    if only:
        q = q.filter(LegislativeCarriage.oeil_procedure_ref == only)
    return q.all()


def _has_signal(db: Session, c: LegislativeCarriage) -> bool:
    if db.query(MEPAmendment).filter(
        MEPAmendment.procedure_reference == c.oeil_procedure_ref
    ).limit(1).first():
        return True
    if c.celex_numbers and db.query(CommissionDocument).filter(
        CommissionDocument.celex.in_(c.celex_numbers)
    ).limit(1).first():
        return True
    if c.oeil_key_events:
        return True
    return False


async def run(only: Optional[str], limit: Optional[int], force: bool) -> None:
    db = SessionLocal()
    try:
        carriages = _eligible_carriages(db, only=only)
        print(f"[info] {len(carriages)} carriages with OEIL ref; filtering for signal presence...", flush=True)

        eligible = [c for c in carriages if _has_signal(db, c)]
        print(f"[info] {len(eligible)} eligible (have amendments, COM doc, or OEIL events)", flush=True)

        if limit:
            eligible = eligible[:limit]
            print(f"[info] limit={limit} -> {len(eligible)} to process", flush=True)

        agg = get_position_aggregator(db=db)

        stats = {"aggregated": 0, "skipped_fresh": 0, "failed": 0}
        for idx, c in enumerate(eligible, 1):
            snap = agg.get_cached(c.id)
            if snap and agg.is_fresh(snap) and not force:
                stats["skipped_fresh"] += 1
                continue
            try:
                await agg.aggregate_and_cache(c)
                stats["aggregated"] += 1
                if idx % 10 == 0:
                    print(f"  [{idx}/{len(eligible)}] done", flush=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("aggregation failed for %s (%s): %s", c.oeil_procedure_ref, c.id, exc)
                stats["failed"] += 1
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass

        print("\n=== Summary ===", flush=True)
        for k, v in stats.items():
            print(f"  {k}: {v}")
        total = db.query(func.count(FilePositionSnapshot.id)).scalar()
        print(f"  total snapshots in DB: {total}")
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", default=None, help="Restrict to a single OEIL procedure reference")
    p.add_argument("--limit", type=int, default=None, help="Process at most N carriages")
    p.add_argument("--force", action="store_true", help="Refresh even fresh snapshots")
    args = p.parse_args()
    asyncio.run(run(args.only, args.limit, args.force))
    return 0


if __name__ == "__main__":
    sys.exit(main())
