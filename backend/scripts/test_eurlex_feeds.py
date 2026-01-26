"""
Test EUR-Lex Predefined RSS Feeds

Verifies that the new EUR-Lex RSS feed integration works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from services.api_clients.eurlex_client import EURLexClient


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


async def test_eurlex_feeds():
    """Test EUR-Lex predefined RSS feeds."""

    log("=" * 70)
    log("EUR-Lex Predefined RSS Feed Test")
    log("=" * 70)

    client = EURLexClient()

    try:
        # Test 1: Get latest legislation
        log("\n1. Testing Parliament & Council Legislation feed...")
        legislation = await client.get_latest_legislation(days=3)
        log(f"   Found {len(legislation)} legislation entries")

        if legislation:
            log("   Sample entries:")
            for item in legislation[:3]:
                log(f"   - CELEX: {item['celex']}")
                log(f"     Type: {item['doc_type']}")
                log(f"     Title: {item['title'][:60]}...")

        # Test 2: Get Commission proposals
        log("\n2. Testing Commission Proposals feed...")
        proposals = await client.get_latest_commission_proposals(days=7)
        log(f"   Found {len(proposals)} proposal entries")

        if proposals:
            log("   Sample entries:")
            for item in proposals[:3]:
                log(f"   - CELEX: {item['celex']}")
                log(f"     COM: {item['com_number']}")
                log(f"     Title: {item['title'][:60]}...")

        # Test 3: Test individual predefined feed
        log("\n3. Testing Official Journal L feed...")
        oj_feed = await client.get_predefined_rss_feed("official_journal_l")
        log(f"   Feed title: {oj_feed.title}")
        log(f"   Entries: {len(oj_feed.entries)}")

        # Summary
        log("\n" + "=" * 70)
        log("Summary:")
        log(f"   Parliament & Council Legislation: {len(legislation)} entries")
        log(f"   Commission Proposals: {len(proposals)} entries")
        log(f"   Official Journal L: {len(oj_feed.entries)} entries")
        log("=" * 70)
        log("[OK] EUR-Lex RSS feeds working correctly!")

    except Exception as e:
        log(f"\n[ERROR] Test failed: {e}")
        raise

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_eurlex_feeds())
