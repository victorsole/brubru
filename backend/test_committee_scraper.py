"""
Test script for EP Committee scraping
Run with: python -m backend.test_committee_scraper
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from services.scrapers.european_parliament_scraper import EuropeanParliamentScraper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_committee_scraping():
    """Test committee scraping functionality"""

    scraper = EuropeanParliamentScraper()

    try:
        # Test 1: Get all committees
        logger.info("=" * 60)
        logger.info("TEST 1: Fetching all committees")
        logger.info("=" * 60)
        committees = await scraper.get_all_committees()
        logger.info(f"Found {len(committees)} committees")

        # Print first 5 committees
        for committee in committees[:5]:
            logger.info(f"  - {committee['code']}: {committee['name']}")

        # Test 2: Get ENVI committee details
        logger.info("\n" + "=" * 60)
        logger.info("TEST 2: Fetching ENVI committee details")
        logger.info("=" * 60)

        envi_details = await scraper.get_committee_details('ENVI')

        logger.info(f"Committee: {envi_details['name']}")
        logger.info(f"Code: {envi_details['code']}")
        logger.info(f"Total Members: {envi_details['member_count']}")
        logger.info(f"URL: {envi_details['url']}")

        # Print members by role
        chairs = [m for m in envi_details['members'] if m['role'] == 'Chair']
        vice_chairs = [m for m in envi_details['members'] if m['role'] == 'Vice-Chair']
        members = [m for m in envi_details['members'] if m['role'] == 'Member']
        substitutes = [m for m in envi_details['members'] if m['role'] == 'Substitute']

        logger.info(f"\nChairs: {len(chairs)}")
        for chair in chairs:
            logger.info(f"  - {chair['name']} ({chair['country']}) - {chair['political_group']}")

        logger.info(f"\nVice-Chairs: {len(vice_chairs)}")
        for vc in vice_chairs[:3]:  # Show first 3
            logger.info(f"  - {vc['name']} ({vc['country']}) - {vc['political_group']}")

        logger.info(f"\nMembers: {len(members)}")
        for member in members[:5]:  # Show first 5
            logger.info(f"  - {member['name']} ({member['country']}) - {member['political_group']}")

        logger.info(f"\nSubstitutes: {len(substitutes)}")

        # Save to file for inspection
        output_file = "envi_committee_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(envi_details, f, indent=2, ensure_ascii=False)

        logger.info(f"\n✅ Full ENVI data saved to: {output_file}")

        # Test 3: Quick test of another committee (ITRE)
        logger.info("\n" + "=" * 60)
        logger.info("TEST 3: Fetching ITRE committee members (quick check)")
        logger.info("=" * 60)

        itre_members = await scraper.get_committee_members('ITRE')
        logger.info(f"ITRE Committee has {len(itre_members)} members")

        logger.info("\n✅ All tests completed successfully!")

    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(test_committee_scraping())
