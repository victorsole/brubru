"""
Batch per-procedure amendment population via OEIL Documentation Gateway.

Unlike backfill_amendments.py (which uses the EP Open Data API and only finds PR docs),
this script uses the OEIL Documentation Gateway per procedure to discover ALL document
types (AM, PR, PA) and parses them with political group enrichment from the EP MEP API.

Usage:
    # Dry run: show which procedures would be fetched
    python scripts/backfill_amendments_oeil.py --dry-run

    # Fetch all procedures (default 3s delay between each)
    python scripts/backfill_amendments_oeil.py

    # Fetch first 10 procedures only
    python scripts/backfill_amendments_oeil.py --limit 10

    # Force re-parse already-parsed documents
    python scripts/backfill_amendments_oeil.py --force --limit 5

    # Custom delay (seconds between procedures)
    python scripts/backfill_amendments_oeil.py --delay 5

    # Fetch a single procedure
    python scripts/backfill_amendments_oeil.py --procedure "2024/0035(COD)"

    # Resume from a specific procedure (alphabetically)
    python scripts/backfill_amendments_oeil.py --resume-from "2024/0100(COD)"

Created: February 2026
"""

import asyncio
import argparse
import logging
import sys
import os
import time
from typing import Optional

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy logs before any SQLAlchemy import
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

# Silence SQLAlchemy echo after engine creation
def _silence_sqlalchemy():
    """Disable SQL query logging for cleaner batch output."""
    try:
        from core.database import engine
        engine.echo = False
    except Exception:
        pass


def get_procedures_with_oeil_refs(
    db,
    resume_from: Optional[str] = None,
) -> list:
    """Query legislative_carriages for all procedures with OEIL refs."""
    from models.legislative_train import LegislativeCarriage

    query = db.query(
        LegislativeCarriage.oeil_procedure_ref
    ).filter(
        LegislativeCarriage.oeil_procedure_ref.isnot(None),
        LegislativeCarriage.oeil_procedure_ref != '',
    ).distinct().order_by(
        LegislativeCarriage.oeil_procedure_ref
    )

    rows = query.all()
    refs = [r[0] for r in rows if r[0]]

    if resume_from:
        try:
            idx = refs.index(resume_from)
            refs = refs[idx:]
        except ValueError:
            # If exact match not found, find first ref >= resume_from
            refs = [r for r in refs if r >= resume_from]

    return refs


def get_already_fetched_procedures(db) -> set:
    """
    Return procedure refs that already have AM documents parsed.
    PR-only procedures (from bulk sync) are NOT considered fully fetched.
    """
    from models.mep_amendment import AmendmentDocument

    rows = db.query(
        AmendmentDocument.procedure_reference
    ).filter(
        AmendmentDocument.document_type == 'AM',
        AmendmentDocument.status == 'parsed',
    ).distinct().all()

    return {r[0] for r in rows}


async def run_dry_run(
    procedures: list,
    already_fetched: set,
    limit: Optional[int],
):
    """Show what would be fetched without doing it."""
    to_fetch = [p for p in procedures if p not in already_fetched]

    if limit:
        to_fetch = to_fetch[:limit]

    print(f"\n[INFO] Total procedures with OEIL refs: {len(procedures)}")
    print(f"[INFO] Already have AM docs parsed:     {len(already_fetched)}")
    print(f"[INFO] Procedures to fetch:             {len(to_fetch)}")

    if to_fetch:
        print(f"\nProcedures that would be fetched:")
        for i, ref in enumerate(to_fetch, 1):
            marker = " (has PR only)" if ref not in already_fetched else ""
            print(f"  {i:3d}. {ref}{marker}")
    else:
        print("\n[OK] All procedures already have AM documents. Nothing to do.")


async def run_backfill(
    procedures: list,
    already_fetched: set,
    limit: Optional[int],
    force: bool,
    delay: float,
):
    """Run per-procedure fetch for all eligible procedures."""
    _silence_sqlalchemy()
    from core.database import SessionLocal
    from services.scrapers.ep_amendment_sync_service import EPAmendmentSyncService

    if force:
        to_fetch = procedures
    else:
        to_fetch = [p for p in procedures if p not in already_fetched]

    if limit:
        to_fetch = to_fetch[:limit]

    if not to_fetch:
        print("\n[OK] All procedures already have AM documents. Nothing to do.")
        print("[INFO] Use --force to re-parse existing documents.")
        return

    total = len(to_fetch)
    print(f"\n[START] Batch OEIL amendment fetch")
    print(f"  Procedures to process: {total}")
    print(f"  Force re-parse: {force}")
    print(f"  Delay between procedures: {delay}s")
    print(f"{'=' * 60}")

    overall_start = time.time()
    total_docs_parsed = 0
    total_amendments = 0
    total_errors = 0
    failed_procedures = []

    db = SessionLocal()
    try:
        service = EPAmendmentSyncService(db=db)

        for i, proc_ref in enumerate(to_fetch, 1):
            print(f"\n[{i}/{total}] {proc_ref}")
            proc_start = time.time()

            try:
                result = await service.sync_amendments_for_procedure(
                    procedure_ref=proc_ref,
                    force_refetch=force,
                )

                docs = result.get('documents_parsed', 0)
                ams = result.get('amendments_stored', 0)
                errs = result.get('errors', [])
                dur = result.get('duration_seconds', 0)

                total_docs_parsed += docs
                total_amendments += ams
                total_errors += len(errs)

                status = "[OK]" if not errs else f"[WARN] {len(errs)} errors"
                print(
                    f"  {status} {docs} docs parsed, {ams} amendments stored ({dur:.1f}s)"
                )

                if errs:
                    for err in errs[:3]:
                        print(f"    - {err}")
                    failed_procedures.append((proc_ref, errs))

            except Exception as e:
                total_errors += 1
                failed_procedures.append((proc_ref, [str(e)]))
                print(f"  [ERROR] {str(e)}")

            # Rate limit between procedures (not after the last one)
            if i < total and delay > 0:
                await asyncio.sleep(delay)

    finally:
        db.close()

    elapsed = time.time() - overall_start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'=' * 60}")
    print(f"[OK] Batch OEIL fetch complete ({minutes}m {seconds}s)")
    print(f"  Procedures processed: {total}")
    print(f"  Documents parsed:     {total_docs_parsed}")
    print(f"  Amendments stored:    {total_amendments}")
    print(f"  Errors:               {total_errors}")

    if failed_procedures:
        print(f"\n  Failed procedures ({len(failed_procedures)}):")
        for proc_ref, errs in failed_procedures[:20]:
            print(f"    {proc_ref}: {errs[0][:80]}")
        if len(failed_procedures) > 20:
            print(f"    ... and {len(failed_procedures) - 20} more")


async def run_single(procedure_ref: str, force: bool):
    """Fetch amendments for a single procedure."""
    _silence_sqlalchemy()
    from core.database import SessionLocal
    from services.scrapers.ep_amendment_sync_service import EPAmendmentSyncService

    db = SessionLocal()
    try:
        service = EPAmendmentSyncService(db=db)
        result = await service.sync_amendments_for_procedure(
            procedure_ref=procedure_ref,
            force_refetch=force,
        )

        docs = result.get('documents_found', 0)
        parsed = result.get('documents_parsed', 0)
        ams = result.get('amendments_stored', 0)
        errs = result.get('errors', [])
        dur = result.get('duration_seconds', 0)

        print(f"\n[OK] {procedure_ref}")
        print(f"  Documents found:  {docs}")
        print(f"  Documents parsed: {parsed}")
        print(f"  Amendments stored: {ams}")
        print(f"  Duration: {dur:.1f}s")

        if errs:
            print(f"\n  Errors ({len(errs)}):")
            for err in errs:
                print(f"    - {err}")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Batch fetch EP amendments per procedure via OEIL Documentation Gateway"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which procedures would be fetched, without fetching"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of procedures to process (default: all)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-parse of already-parsed documents"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Seconds to wait between procedures (default: 3.0)"
    )
    parser.add_argument(
        "--procedure",
        type=str,
        default=None,
        help="Fetch a single procedure instead of batch (e.g. '2024/0035(COD)')"
    )
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume from a specific procedure reference (alphabetical)"
    )

    args = parser.parse_args()

    # Single procedure mode
    if args.procedure:
        print(f"[INFO] Single procedure mode: {args.procedure}")
        asyncio.run(run_single(args.procedure, args.force))
        return

    # Batch mode: load procedures from database
    _silence_sqlalchemy()
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        procedures = get_procedures_with_oeil_refs(db, args.resume_from)
        already_fetched = get_already_fetched_procedures(db)
    finally:
        db.close()

    print(f"[INFO] OEIL Amendment Batch Fetch")
    print(f"[INFO] Procedures with OEIL refs: {len(procedures)}")
    print(f"[INFO] Already have AM docs:      {len(already_fetched)}")

    if args.resume_from:
        print(f"[INFO] Resuming from: {args.resume_from}")

    if args.dry_run:
        asyncio.run(run_dry_run(procedures, already_fetched, args.limit))
    else:
        asyncio.run(run_backfill(
            procedures, already_fetched, args.limit, args.force, args.delay
        ))


if __name__ == "__main__":
    main()
