"""
Backfill missing legislative_carriages rows for committee_work_items refs.

Tier B of the work-items metadata fix. The committee_work_items table tracks
EP committee scrape coverage; legislative_carriages tracks per-procedure
OEIL state. The two tables drift because the CWI scraper indexes more
procedures than the LC sync covers — leaving 235/403 work-items with no LC
row, which means the API fallback to LC's OEIL JSON blobs can't fire.

This script:
  1. Finds all CWI procedure_refs that don't have a matching LC row.
  2. For each, fetches the OEIL procedure file via OEILScraper.
  3. Creates a minimal LC row with oeil_procedure_data + oeil_key_events
     populated. Title pulled from OEIL when present, else from the CWI row.
  4. Source flag CARRIAGE_SOURCE = OEIL_DIRECT (distinguishes from
     LEGISLATIVE_TRAIN scraper origin).

Run:
    python3.12 backend/scripts/backfill_lc_for_committee_work_items.py             # dry-run
    python3.12 backend/scripts/backfill_lc_for_committee_work_items.py --apply
    python3.12 backend/scripts/backfill_lc_for_committee_work_items.py --apply --limit 20

Idempotent: re-running over existing refs is a no-op (skipped). Concurrency
capped at 4 OEIL requests in flight to be a polite scraper.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.committee_work import CommitteeWorkItem
from models.legislative_train import (
    CarriageSourceEnum,
    CarriageStatusEnum,
    LegislativeCarriage,
    TextTypeEnum,
)
from services.scrapers.oeil_scraper import OEILScraper


def _file_id_from_ref(ref: str) -> str:
    """Build a stable, unique file_id from an OEIL procedure ref."""
    return ref.lower().replace("/", "-").replace("(", "-").replace(")", "")


def _gather_missing_refs(db: Session) -> List[str]:
    """Return CWI refs that have no LC row.

    Uses a LEFT JOIN to detect the gap, then de-duplicates.
    """
    rows = (
        db.query(CommitteeWorkItem.procedure_ref)
        .outerjoin(
            LegislativeCarriage,
            LegislativeCarriage.oeil_procedure_ref == CommitteeWorkItem.procedure_ref,
        )
        .filter(
            CommitteeWorkItem.procedure_ref.isnot(None),
            CommitteeWorkItem.procedure_ref != "",
            LegislativeCarriage.id.is_(None),
        )
        .distinct()
        .all()
    )
    return sorted({r[0] for r in rows if r[0]})


def _cwi_title_for_ref(db: Session, ref: str) -> Optional[str]:
    cwi = (
        db.query(CommitteeWorkItem)
        .filter(CommitteeWorkItem.procedure_ref == ref)
        .order_by(CommitteeWorkItem.last_updated.desc().nullslast())
        .first()
    )
    return cwi.title if cwi else None


async def _fetch_one(scraper: OEILScraper, ref: str):
    try:
        return await scraper.get_procedure_full(ref)
    except Exception as exc:  # noqa: BLE001
        return ("error", str(exc))


async def _process_batch(
    refs: List[str],
    apply: bool,
    concurrency: int = 4,
) -> dict:
    db: Session = SessionLocal()
    scraper = OEILScraper()
    sem = asyncio.Semaphore(concurrency)

    inserted = 0
    skipped_existing = 0
    errors = 0
    no_oeil = 0

    async def handle_ref(ref: str):
        nonlocal inserted, skipped_existing, errors, no_oeil

        # Per-ref try/except so one bad ref never cancels the whole gather.
        try:
            async with sem:
                existing = (
                    db.query(LegislativeCarriage)
                    .filter(LegislativeCarriage.oeil_procedure_ref == ref)
                    .first()
                )
                if existing:
                    skipped_existing += 1
                    return

                print(f"[FETCH] {ref}", flush=True)
                result = await _fetch_one(scraper, ref)

                if isinstance(result, tuple) and result[0] == "error":
                    errors += 1
                    print(f"   [ERR] {ref}: {result[1][:120]}", flush=True)
                    return

                oeil = result
                if not oeil:
                    no_oeil += 1
                    print(f"   [WARN] {ref}: OEIL returned no data — skipping", flush=True)
                    return

                title = None
                try:
                    title = (oeil.basic_info.title or "").strip() if oeil.basic_info else None
                except Exception:
                    title = None
                if not title:
                    title = _cwi_title_for_ref(db, ref) or ref

                now = datetime.now(timezone.utc)
                carriage = LegislativeCarriage(
                    id=uuid.uuid4(),
                    file_id=_file_id_from_ref(ref),
                    title=title[:500],
                    description=None,
                    current_status=CarriageStatusEnum.TABLED,
                    text_type=TextTypeEnum.UNKNOWN,
                    oeil_procedure_ref=ref,
                    policy_areas=[],
                    source=CarriageSourceEnum.OEIL_DIRECT,
                    first_seen=now,
                    scraped_at=now,
                    last_updated=now,
                    enriched_at=now,
                    enrichment_quality="high",
                    url=f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={ref}",
                )

                try:
                    if oeil.key_events and getattr(oeil.key_events, "events", None):
                        events_json = []
                        for e in oeil.key_events.events:
                            events_json.append({
                                "date": e.date.isoformat() if getattr(e, "date", None) else None,
                                "event_type": getattr(e, "event_type", None),
                                "description": getattr(e, "description", None),
                            })
                        carriage.oeil_key_events = events_json
                except Exception as exc:  # noqa: BLE001
                    print(f"   [WARN] {ref}: key_events serialise failed: {exc}", flush=True)

                try:
                    carriage.oeil_procedure_data = oeil.model_dump(mode="json")
                except Exception as exc:  # noqa: BLE001
                    print(f"   [WARN] {ref}: procedure_data serialise failed: {exc}", flush=True)

                if apply:
                    db.add(carriage)
                    try:
                        db.commit()
                        inserted += 1
                        print(f"   [OK] inserted LC for {ref}", flush=True)
                    except Exception as exc:  # noqa: BLE001
                        db.rollback()
                        errors += 1
                        print(f"   [ERR] {ref}: commit: {str(exc)[:120]}", flush=True)
                else:
                    inserted += 1
                    print(f"   [DRY] would insert LC for {ref}", flush=True)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            import traceback
            print(f"   [ERR] {ref}: handler crashed: {exc}", flush=True)
            print(traceback.format_exc(), flush=True)

    await asyncio.gather(*[handle_ref(ref) for ref in refs], return_exceptions=True)

    try:
        await scraper.close()
    except Exception:
        pass
    db.close()

    return {
        "total_refs": len(refs),
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "errors": errors,
        "no_oeil_data": no_oeil,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually insert rows. Without it, dry-run.")
    ap.add_argument("--limit", type=int, default=0, help="Cap number of refs processed (0 = all).")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    db = SessionLocal()
    refs = _gather_missing_refs(db)
    db.close()
    print(f"[INFO] Found {len(refs)} CWI procedure_refs without an LC row")
    if args.limit and len(refs) > args.limit:
        refs = refs[: args.limit]
        print(f"[INFO] Limited to first {args.limit} for this run")

    if not refs:
        print("[DONE] Nothing to backfill.")
        return

    print(f"[INFO] apply={args.apply} concurrency={args.concurrency}")
    result = asyncio.run(_process_batch(refs, args.apply, args.concurrency))
    print()
    print("=" * 70)
    print(f"[DONE] {result}")


if __name__ == "__main__":
    main()
