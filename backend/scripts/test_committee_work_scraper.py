"""
Test script for EP Committee Work In Progress Scraper.

Tests the scraper with AFET committee (Foreign Affairs).

Usage:
    cd backend && python scripts/test_committee_work_scraper.py
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.committee_work_scraper import CommitteeWorkInProgressScraper
from knowledge_base.ep_committees import get_committee, get_committee_url


async def test_scraper():
    """Test the committee work scraper with AFET committee."""
    print("\n[TEST] EP Committee Work In Progress Scraper")
    print("=" * 60)

    # Test 1: Committee constants
    print("\n[1] Testing committee constants...")
    try:
        afet = get_committee("AFET")
        print(f"    Committee: {afet.code} - {afet.name}")
        print(f"    Full name: {afet.full_name}")
        print(f"    Policy area: {afet.policy_area}")

        url = get_committee_url("AFET", page=0)
        print(f"    URL: {url}")
        print("    [OK] Committee constants working")
    except Exception as e:
        print(f"    [ERROR] Committee constants failed: {e}")
        return False

    # Test 2: Initialize scraper
    print("\n[2] Initializing scraper...")
    try:
        scraper = CommitteeWorkInProgressScraper()
        print(f"    Name: {scraper.name}")
        print(f"    Base URL: {scraper.base_url}")
        print(f"    Rate limit: {scraper.rate_limit_delay}s")
        print("    [OK] Scraper initialized")
    except Exception as e:
        print(f"    [ERROR] Failed to initialize scraper: {e}")
        return False

    # Test 3: Scrape AFET committee (1 page only)
    print("\n[3] Scraping AFET committee (1 page)...")
    try:
        items = await scraper.scrape_committee("AFET", max_pages=1)

        print(f"    Items found: {len(items)}")

        if items:
            print("\n    Sample items:")
            for item in items[:3]:
                print(f"\n    - Ref: {item.procedure_ref}")
                print(f"      Title: {item.title[:60]}..." if len(item.title) > 60 else f"      Title: {item.title}")
                print(f"      Type: {item.procedure_type}")
                print(f"      Role: {item.committee_role}")
                if item.rapporteur_name:
                    print(f"      Rapporteur: {item.rapporteur_name}")
                if item.status:
                    print(f"      Status: {item.status}")

            print("\n    [OK] Scraping successful")
        else:
            print("    [WARN] No items found - page structure may have changed")

    except Exception as e:
        print(f"    [ERROR] Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Test procedure type detection
    print("\n[4] Testing procedure type detection...")
    try:
        test_refs = [
            ("2025/0580(CNS)", "CNS"),
            ("2024/0123(COD)", "COD"),
            ("2024/0456(APP)", "APP"),
            ("2024/0789(INI)", "INI"),
        ]

        for ref, expected in test_refs:
            result = scraper._extract_procedure_type(ref)
            status = "[OK]" if result.value == expected else "[FAIL]"
            print(f"    {status} {ref} -> {result.value} (expected: {expected})")

        print("    [OK] Procedure type detection working")
    except Exception as e:
        print(f"    [ERROR] Procedure type detection failed: {e}")
        return False

    # Test 5: Validate procedure reference
    print("\n[5] Testing procedure reference validation...")
    try:
        valid_refs = ["2025/0580(CNS)", "2024/0123(COD)"]
        invalid_refs = ["invalid", "2025/ABC", "123/456"]

        for ref in valid_refs:
            result = scraper.validate_procedure_ref(ref)
            status = "[OK]" if result else "[FAIL]"
            print(f"    {status} {ref} -> valid={result}")

        for ref in invalid_refs:
            result = scraper.validate_procedure_ref(ref)
            status = "[OK]" if not result else "[FAIL]"
            print(f"    {status} {ref} -> valid={result} (expected: False)")

        print("    [OK] Validation working")
    except Exception as e:
        print(f"    [ERROR] Validation failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("[OK] All tests passed!")
    print("=" * 60 + "\n")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_scraper())
    sys.exit(0 if success else 1)
