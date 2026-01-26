"""
Sync OEIL XML Feeds

Fetches latest procedures, documents, and reports from OEIL XML feeds
and adds them to the legislative carriages database.

Usage:
    python scripts/sync_oeil_feeds.py [--days N] [--force]

Options:
    --days N    Number of days to look back (default: 7)
    --force     Update existing entries instead of skipping them
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from services.scrapers.oeil_sync_service import OEILSyncService


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


async def main(days: int = 7, force: bool = False):
    """Run OEIL sync."""

    log("=" * 70)
    log("OEIL XML Feed Sync")
    log("=" * 70)
    log(f"Parameters: days={days}, force={force}")
    log("=" * 70)

    service = OEILSyncService()

    try:
        result = await service.sync_all(
            procedures_days=days,
            documents_days=days,
            reports_days=30,
            skip_existing=not force
        )

        log("\n" + "=" * 70)
        log("Summary:")
        log(f"   Added: {result['added']}")
        log(f"   Updated: {result['updated']}")
        log(f"   Skipped: {result['skipped']}")
        log(f"   Errors: {result['errors']}")

        if result['items']:
            log("\nNew items added:")
            for item in result['items'][:20]:  # Show first 20
                if item['action'] == 'added':
                    log(f"   + {item['reference']}: {item.get('title', '')[:50]}...")

            if len(result['items']) > 20:
                log(f"   ... and {len(result['items']) - 20} more")

        log("=" * 70)

        return result

    except Exception as e:
        log(f"\n[ERROR] Sync failed: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync OEIL XML feeds")
    parser.add_argument("--days", type=int, default=7, help="Days to look back")
    parser.add_argument("--force", action="store_true", help="Update existing entries")
    args = parser.parse_args()

    asyncio.run(main(days=args.days, force=args.force))
