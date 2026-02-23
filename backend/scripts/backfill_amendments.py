"""
CLI script to backfill EP amendments from the EP Open Data API.

Usage:
    # Backfill all AM+PR documents for current parliament term
    python scripts/backfill_amendments.py --years 2024 2025 2026

    # Backfill specific doc types only
    python scripts/backfill_amendments.py --years 2025 --types AM PR

    # Force re-parse everything
    python scripts/backfill_amendments.py --years 2025 --force

    # Dry run (enumerate only, no parsing)
    python scripts/backfill_amendments.py --years 2025 --dry-run

Created: February 2026
"""

import asyncio
import argparse
import logging
import sys
import os
import time

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Map CLI shortcodes to EP Open Data work types
TYPE_MAP = {
    "AM": "AMENDMENTS",
    "PR": "REPORT_DRAFT",
    "PA": "OPINION_DRAFT",
}


def progress_callback(current: int, total: int, message: str):
    """Print progress updates."""
    print(f"  [{current}/{total}] {message}")


async def run_enumerate_only(years: list, work_types: list):
    """Enumerate documents without parsing (dry run)."""
    from services.api_clients.ep_open_data_client import EPOpenDataClient

    client = EPOpenDataClient()
    try:
        documents = await client.enumerate_all_documents(
            work_types=work_types,
            years=years,
            progress_callback=progress_callback,
        )

        print(f"\n[INFO] Found {len(documents)} documents:")

        # Summary by type
        type_counts = {}
        committee_counts = {}
        for doc in documents:
            dt = doc.get("document_type", "?")
            type_counts[dt] = type_counts.get(dt, 0) + 1
            cc = doc.get("committee_code", "?")
            committee_counts[cc] = committee_counts.get(cc, 0) + 1

        print("\nBy type:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

        print("\nBy committee (top 15):")
        for cc, c in sorted(committee_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"  {cc}: {c}")

        # Sample documents
        print("\nSample documents:")
        for doc in documents[:5]:
            print(
                f"  {doc.get('identifier', '?')} | "
                f"{doc.get('committee_code', '?')}-{doc.get('document_type', '?')} | "
                f"PE: {doc.get('pe_reference', 'N/A')} | "
                f"Proc: {doc.get('procedure_reference', 'N/A')}"
            )

    finally:
        await client.close()


async def run_backfill(years: list, work_types: list, force: bool):
    """Run full backfill: enumerate + download + parse."""
    from core.database import SessionLocal
    from services.scrapers.bulk_amendment_sync_service import BulkAmendmentSyncService

    db = SessionLocal()
    try:
        service = BulkAmendmentSyncService(db=db)

        print(f"\n[START] Backfilling amendments: years={years}, types={work_types}, force={force}")
        start = time.time()

        result = await service.sync_all(
            years=years,
            work_types=work_types,
            force_refetch=force,
            progress_callback=progress_callback,
        )

        elapsed = time.time() - start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print(f"\n{'=' * 60}")
        print(f"[OK] Backfill complete ({minutes}m {seconds}s)")
        print(f"  Documents discovered: {result.documents_discovered}")
        print(f"  Documents skipped:    {result.documents_skipped}")
        print(f"  Documents parsed:     {result.documents_parsed}")
        print(f"  Documents failed:     {result.documents_failed}")
        print(f"  Amendments stored:    {result.amendments_stored}")

        if result.errors:
            print(f"\n  Errors ({len(result.errors)}):")
            for err in result.errors[:20]:
                print(f"    - {err}")
            if len(result.errors) > 20:
                print(f"    ... and {len(result.errors) - 20} more")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill EP amendments from EP Open Data API"
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2025],
        help="Years to backfill (default: 2025)"
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=["AM", "PR"],
        choices=["AM", "PR", "PA"],
        help="Document types to fetch (default: AM PR)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-parse of already-parsed documents"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Enumerate documents only, do not download or parse"
    )

    args = parser.parse_args()

    # Convert CLI type codes to EP Open Data work types
    work_types = [TYPE_MAP[t] for t in args.types]

    print(f"[INFO] EP Amendment Backfill")
    print(f"[INFO] Years: {args.years}")
    print(f"[INFO] Types: {args.types} -> {work_types}")
    print(f"[INFO] Force: {args.force}")
    print(f"[INFO] Dry run: {args.dry_run}")

    if args.dry_run:
        asyncio.run(run_enumerate_only(args.years, work_types))
    else:
        asyncio.run(run_backfill(args.years, work_types, args.force))


if __name__ == "__main__":
    main()
