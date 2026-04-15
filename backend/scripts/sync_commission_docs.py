"""
Sync EC Register of Commission Documents.

Fetches latest COM proposals, OJ legislation, SWD, and JOIN documents via
CommissionDocRegisterClient (RegDoc API with EUR-Lex/SPARQL fallback) and
writes them to the commission_documents table.

Usage:
    python scripts/sync_commission_docs.py [--days N] [--force]

Options:
    --days N    Number of days to look back (default: 7)
    --force     Update existing entries instead of skipping them
"""

import asyncio
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from services.scrapers.commission_doc_sync_service import CommissionDocSyncService


def log(msg: str) -> None:
    print(msg, flush=True)


async def main(days: int = 7, force: bool = False) -> int:
    log("=" * 70)
    log("EC Register of Commission Documents Sync")
    log("=" * 70)
    log(f"Parameters: days={days}, force={force}")

    service = CommissionDocSyncService()
    try:
        result = await service.sync_all(days=days, skip_existing=not force)
    except Exception as exc:
        log(f"[ERROR] Commission doc sync failed: {exc}")
        return 1

    log("")
    log("=" * 70)
    log("Summary:")
    log(f"   Added:   {result.get('added', 0)}")
    log(f"   Updated: {result.get('updated', 0)}")
    log(f"   Skipped: {result.get('skipped', 0)}")
    log(f"   Errors:  {result.get('errors', 0)}")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync EC Register of Commission Documents")
    parser.add_argument("--days", type=int, default=7, help="Days back to search (default: 7)")
    parser.add_argument("--force", action="store_true", help="Update existing entries")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(days=args.days, force=args.force)))
