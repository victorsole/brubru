"""
Phase 1 Test Script: EPRS Full Content Extraction

Tests the complete Phase 1 pipeline:
1. PDF download
2. Text extraction
3. Entity extraction (CELEX, procedures, MEPs)
4. Document structure parsing
5. EPRSPublication enrichment

Usage:
    python backend/scripts/test_phase1_eprs_extraction.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.scrapers.think_tank_scraper import ThinkTankScraper
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_latest_publications():
    """Test: Get latest EPRS publications with full extraction"""
    print("\n" + "="*80)
    print("TEST 1: Latest Publications with Full Content Extraction")
    print("="*80 + "\n")

    scraper = ThinkTankScraper(enable_full_extraction=True)

    try:
        # Get latest 3 publications
        results = await scraper.get_latest_publications_enriched(
            hours=720,  # Last 30 days
            limit=3,
            publication_type="briefings"  # Try briefings first
        )

        print(f"\n✓ Successfully enriched {len(results)} publications\n")

        for i, result in enumerate(results, 1):
            pub = result.publication

            print(f"{'─'*80}")
            print(f"Publication {i}: {pub.title}")
            print(f"{'─'*80}")
            print(f"  Type: {pub.publication_type.value}")
            print(f"  Published: {pub.publication_date}")
            print(f"  HTML URL: {pub.html_url}")
            print(f"  PDF URL: {pub.pdf_url}")
            print(f"\n  📄 Content Stats:")
            print(f"     Words: {pub.word_count:,}")
            print(f"     Pages: {pub.page_count}")
            print(f"     Sections: {len(pub.sections)}")
            print(f"     Extraction Quality: {pub.extraction_quality}")

            print(f"\n  🔗 Extracted Entities:")
            print(f"     CELEX Numbers: {len(pub.related_celex_numbers)}")
            if pub.related_celex_numbers:
                for celex in pub.related_celex_numbers[:3]:
                    print(f"       - {celex}")

            print(f"     Procedures: {len(pub.related_procedures)}")
            if pub.related_procedures:
                for proc in pub.related_procedures[:3]:
                    print(f"       - {proc}")

            print(f"     MEPs Mentioned: {len(pub.related_meps)}")
            if pub.related_meps:
                for mep in pub.related_meps[:3]:
                    print(f"       - {mep}")

            print(f"     Committees: {', '.join(pub.committees) if pub.committees else 'None'}")
            print(f"     Policy Areas: {', '.join(pub.policy_areas) if pub.policy_areas else 'None'}")

            if pub.summary:
                print(f"\n  📝 Summary:")
                print(f"     {pub.summary[:200]}...")

            if pub.key_findings:
                print(f"\n  💡 Key Findings:")
                for finding in pub.key_findings[:2]:
                    print(f"     - {finding[:150]}...")

            if pub.sections:
                print(f"\n  📚 Document Structure:")
                for section in pub.sections[:3]:
                    heading = section.get('heading', 'Unknown')
                    words = section.get('word_count', 0)
                    print(f"     - {heading} ({words} words)")

            print(f"\n  ⚙️  Processing:")
            print(f"     Quality: {result.extraction_quality}")
            print(f"     Time: {result.processing_time_seconds:.2f}s")
            print(f"     Errors: {len(result.errors)}")
            print(f"     Warnings: {len(result.warnings)}")

            print("")

    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        await scraper.close()


async def test_search_with_full_content():
    """Test: Search publications and extract full content"""
    print("\n" + "="*80)
    print("TEST 2: Search with Full Content Extraction")
    print("="*80 + "\n")

    scraper = ThinkTankScraper(enable_full_extraction=True)

    try:
        # Search for AI-related publications
        results = await scraper.search_with_full_content(
            keyword="artificial intelligence",
            hours=720,  # Last 30 days
            limit=2
        )

        print(f"\n✓ Found and enriched {len(results)} publications about 'artificial intelligence'\n")

        for i, result in enumerate(results, 1):
            pub = result.publication

            print(f"{'─'*80}")
            print(f"Result {i}: {pub.title}")
            print(f"{'─'*80}")
            print(f"  Content: {pub.word_count:,} words, {pub.page_count} pages")
            print(f"  CELEX refs: {pub.related_celex_numbers}")
            print(f"  Procedures: {pub.related_procedures}")
            print(f"  Quality: {pub.extraction_quality}")
            print("")

    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        await scraper.close()


async def test_single_publication():
    """Test: Extract single publication by URL"""
    print("\n" + "="*80)
    print("TEST 3: Single Publication Extraction (Manual URL)")
    print("="*80 + "\n")

    scraper = ThinkTankScraper(enable_full_extraction=True)

    try:
        # Example: You can replace this with a real EPRS publication URL
        # For now, we'll skip this test if no URL provided
        print("  ℹ️  This test requires a specific EPRS publication URL")
        print("  Example usage:")
        print("     result = await scraper.get_publication_with_full_content(")
        print("         publication_url='https://epthinktank.eu/2024/.../ai-act/',")
        print("         pdf_url='https://.../document.pdf'")
        print("     )")

    finally:
        await scraper.close()


async def main():
    """Run all Phase 1 tests"""
    print("\n" + "="*80)
    print("PHASE 1: EPRS FULL CONTENT EXTRACTION - TEST SUITE")
    print("="*80)
    print("\nThis test suite demonstrates:")
    print("  1. PDF download and text extraction")
    print("  2. Entity extraction (CELEX, procedures, MEPs, committees)")
    print("  3. Document structure parsing (sections, headings)")
    print("  4. Full EPRSPublication enrichment")
    print("  5. Reusable blueprint for JRC and other sources")
    print("\n")

    # Run tests
    await test_latest_publications()
    await test_search_with_full_content()
    await test_single_publication()

    print("\n" + "="*80)
    print("TESTS COMPLETED")
    print("="*80)
    print("\nNext Steps:")
    print("  • Phase 2: Add enriched publications to ChromaDB vector database")
    print("  • Phase 3: Implement intelligent CELEX-to-EPRS matching")
    print("  • Phase 4: Build historical archive (bulk download)")
    print("  • Phase 5: Apply this blueprint to JRC publications")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
