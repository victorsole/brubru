"""
Index All EU Laws

Management script to index all 50k+ laws from LEG_2025-11 directory.

This is a long-running operation (estimated 2-3 hours for full indexing).

Usage:
    # Full indexing
    python -m backend.scripts.index_all_laws

    # Resume from specific UUID (if interrupted)
    python -m backend.scripts.index_all_laws --resume <uuid>

    # Test with limited number
    python -m backend.scripts.index_all_laws --limit 100

    # Skip policy classification (faster)
    python -m backend.scripts.index_all_laws --no-policy-classification
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.law_database.law_indexer import get_law_indexer


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


async def main():
    """Main indexing function"""
    parser = argparse.ArgumentParser(
        description="Index all EU laws from LEG_2025-11",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full indexing
  python -m backend.scripts.index_all_laws

  # Resume from interrupted indexing
  python -m backend.scripts.index_all_laws --resume 1a1e8486-a474-11e9-9d01-01aa75ed71a1

  # Test with first 100 laws
  python -m backend.scripts.index_all_laws --limit 100

  # Skip policy classification for speed
  python -m backend.scripts.index_all_laws --no-policy-classification
        """
    )

    parser.add_argument(
        '--resume',
        type=str,
        help='UUID to resume from (for interrupted indexing)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of laws to index (for testing)'
    )

    parser.add_argument(
        '--no-policy-classification',
        action='store_true',
        help='Skip policy area classification (faster but less useful)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for database commits (default: 100)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("EU LAW INDEXING - FULL INDEXING SCRIPT")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.resume:
        print(f"📍 Resuming from UUID: {args.resume}")

    if args.limit:
        print(f"⚠️  LIMITED MODE: Indexing only {args.limit} laws")
    else:
        print(f"📊 FULL MODE: Indexing all 50k+ laws (estimated 2-3 hours)")

    if args.no_policy_classification:
        print(f"⚠️  Policy classification DISABLED")
    else:
        print(f"✅ Policy classification ENABLED (33 policy areas)")

    print(f"   Batch size: {args.batch_size}")

    # Initialize indexer
    indexer = get_law_indexer()

    # Confirmation prompt (only for full indexing)
    if not args.limit and not args.resume:
        print("\n" + "⚠️  " * 20)
        print("WARNING: This will index 50k+ laws and may take 2-3 hours!")
        print("⚠️  " * 20)
        response = input("\nContinue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Aborted by user")
            return

    print("\n" + "=" * 80)
    print("STARTING INDEXING...")
    print("=" * 80 + "\n")

    start_time = datetime.now()

    try:
        # Run indexing
        stats = await indexer.index_all_laws(
            resume_from=args.resume,
            max_laws=args.limit
        )

        # Print final statistics
        print("\n" + "=" * 80)
        print("INDEXING COMPLETE!")
        print("=" * 80)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\n📊 FINAL STATISTICS:")
        print(f"   Total directories scanned: {stats['total_directories']}")
        print(f"   Laws processed: {stats['processed']}")
        print(f"   Successfully indexed: {stats['successful']}")
        print(f"   Failed: {stats['failed']}")
        print(f"   Skipped (already indexed): {stats['skipped']}")
        print(f"\n⏱️  TIME:")
        print(f"   Duration: {format_duration(duration)}")
        print(f"   Speed: {stats['laws_per_second']:.2f} laws/second")

        if stats['failed'] > 0:
            print(f"\n⚠️  ERRORS ({len(stats['errors'])}):")
            for error in stats['errors'][:10]:
                print(f"   - {error['uuid']}: {error['error']}")
            if len(stats['errors']) > 10:
                print(f"   ... and {len(stats['errors']) - 10} more errors")

        # Save statistics to file
        stats_file = Path(f"law_indexing_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        print(f"\n💾 Statistics saved to: {stats_file}")

        # Get database statistics
        print("\n" + "=" * 80)
        print("DATABASE STATISTICS")
        print("=" * 80)

        db_stats = await indexer.get_statistics()

        print(f"\n📊 Total laws in database: {db_stats.get('total_laws', 0):,}")
        print(f"   Laws with CELEX: {db_stats.get('laws_with_celex', 0):,}")

        if db_stats.get('date_range'):
            print(f"\n📅 Date range:")
            print(f"   Earliest: {db_stats['date_range'].get('earliest', 'N/A')}")
            print(f"   Latest: {db_stats['date_range'].get('latest', 'N/A')}")

        if db_stats.get('by_policy_area'):
            print(f"\n📂 Top 10 Policy Areas:")
            sorted_areas = sorted(
                db_stats['by_policy_area'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            for i, (area, count) in enumerate(sorted_areas, 1):
                print(f"   {i}. {area}: {count:,}")

        if db_stats.get('by_doc_type'):
            print(f"\n📝 Top 10 Document Types:")
            for i, (doc_type, count) in enumerate(db_stats['by_doc_type'].items(), 1):
                print(f"   {i}. {doc_type}: {count:,}")

        print("\n" + "=" * 80)
        print("✅ INDEXING SUCCESSFULLY COMPLETED!")
        print("=" * 80)

        print("\n🎉 Next steps:")
        print("   1. The chatbot can now access these 50k+ laws")
        print("   2. Use EU Law Comply to create law clusters")
        print("   3. Extract requirements for compliance checking")

    except KeyboardInterrupt:
        print("\n\n⚠️  INTERRUPTED BY USER")
        print(f"   Processed: {stats.get('processed', 0)} laws")
        print(f"   Successful: {stats.get('successful', 0)} laws")
        print(f"\nTo resume indexing, run:")
        print(f"   python -m backend.scripts.index_all_laws --resume <last-uuid>")

    except Exception as e:
        print(f"\n\n❌ INDEXING FAILED")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()

        print(f"\nTo retry, run:")
        print(f"   python -m backend.scripts.index_all_laws --resume <last-uuid>")

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
