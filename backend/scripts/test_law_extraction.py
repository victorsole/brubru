"""
Test Law Extraction

Test script to validate XML parsing and metadata extraction
on sample files from LEG_2025-11.

Usage:
    python -m backend.scripts.test_law_extraction
"""

import asyncio
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.law_database.xml_parser import get_xml_parser
from backend.services.law_database.law_indexer import get_law_indexer


def test_xml_parser():
    """Test XML parser on sample files"""
    print("=" * 80)
    print("TEST 1: XML Parser - Sample Files")
    print("=" * 80)

    parser = get_xml_parser()

    # Test files (we saw this one in the directory listing)
    test_files = [
        "docs/LEG_2025-11/1a1e8486-a474-11e9-9d01-01aa75ed71a1/fmx4/L_2019187EN.01004101.xml",
        "docs/LEG_2025-11/65a9ddff-3e78-403b-ab34-98d7973be2b3/fmx4/L_2010117EN.01006001.xml",
        "docs/LEG_2025-11/a4d26b15-882d-11e9-9369-01aa75ed71a1/fmx4/L_2019148EN.01000101.xml",
    ]

    results = []

    for xml_path in test_files:
        if not Path(xml_path).exists():
            print(f"\n❌ File not found: {xml_path}")
            continue

        print(f"\n📄 Parsing: {xml_path}")
        print("-" * 80)

        metadata = parser.parse_file(xml_path)

        if metadata:
            print(f"✅ SUCCESS")
            print(f"   UUID: {metadata['uuid']}")
            print(f"   CELEX: {metadata.get('celex', 'N/A')}")
            print(f"   Type: {metadata.get('doc_type', 'Unknown')}")
            print(f"   Title: {metadata.get('title', 'N/A')[:100]}...")
            print(f"   Date: {metadata.get('date', 'N/A')}")
            print(f"   OJ Ref: {metadata.get('oj_reference', 'N/A')}")
            print(f"   Legal Basis: {', '.join(metadata.get('legal_basis', [])[:3])}")
            print(f"   Citations: {len(metadata.get('citations', []))} found")
            print(f"   Subject Matter: {', '.join(metadata.get('subject_matter', []))}")
            print(f"   Articles: {len(metadata.get('articles', []))} extracted")
            print(f"   Full Text Length: {len(metadata.get('full_text', ''))} chars")

            results.append({
                'file': xml_path,
                'success': True,
                'metadata': metadata
            })
        else:
            print(f"❌ FAILED to parse")
            results.append({
                'file': xml_path,
                'success': False
            })

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    successful = sum(1 for r in results if r['success'])
    print(f"✅ Successful: {successful}/{len(test_files)}")
    print(f"❌ Failed: {len(test_files) - successful}/{len(test_files)}")

    return results


async def test_law_indexer():
    """Test law indexer on small sample"""
    print("\n\n" + "=" * 80)
    print("TEST 2: Law Indexer - Sample Indexing")
    print("=" * 80)

    indexer = get_law_indexer()

    # Index first 10 laws only
    print("\n📊 Indexing first 10 laws...")
    stats = await indexer.index_all_laws(max_laws=10)

    print("\n✅ Indexing complete!")
    print(f"   Processed: {stats['processed']}")
    print(f"   Successful: {stats['successful']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Skipped: {stats['skipped']}")
    print(f"   Duration: {stats['duration_seconds']:.2f}s")
    print(f"   Speed: {stats['laws_per_second']:.2f} laws/sec")

    if stats['errors']:
        print(f"\n⚠️  Errors ({len(stats['errors'])}):")
        for error in stats['errors'][:5]:
            print(f"   - {error['uuid']}: {error['error']}")

    return stats


async def test_search():
    """Test search functionality"""
    print("\n\n" + "=" * 80)
    print("TEST 3: Search Functionality")
    print("=" * 80)

    indexer = get_law_indexer()

    # Test searches
    test_queries = [
        {"query": "chemical", "desc": "Search for 'chemical'"},
        {"query": "Commission Decision", "desc": "Search for 'Commission Decision'"},
        {"query": "2019", "desc": "Search for '2019'"},
    ]

    for test in test_queries:
        print(f"\n🔍 {test['desc']}")
        print("-" * 80)

        results = await indexer.search_laws(
            query=test['query'],
            limit=5
        )

        if results:
            print(f"Found {len(results)} results:")
            for i, law in enumerate(results, 1):
                print(f"\n{i}. {law.get('title', 'Untitled')[:100]}...")
                print(f"   CELEX: {law.get('celex', 'N/A')}")
                print(f"   Type: {law.get('doc_type', 'Unknown')}")
                print(f"   Date: {law.get('date', 'N/A')}")
                print(f"   Policy Area: {law.get('policy_area', 'Unclassified')}")
        else:
            print("No results found")


async def test_statistics():
    """Test statistics"""
    print("\n\n" + "=" * 80)
    print("TEST 4: Database Statistics")
    print("=" * 80)

    indexer = get_law_indexer()

    stats = await indexer.get_statistics()

    print(f"\n📊 Total laws indexed: {stats.get('total_laws', 0)}")
    print(f"   Laws with CELEX: {stats.get('laws_with_celex', 0)}")

    if stats.get('date_range'):
        print(f"\n📅 Date range:")
        print(f"   Earliest: {stats['date_range'].get('earliest', 'N/A')}")
        print(f"   Latest: {stats['date_range'].get('latest', 'N/A')}")

    if stats.get('by_policy_area'):
        print(f"\n📂 By Policy Area (top 10):")
        sorted_areas = sorted(
            stats['by_policy_area'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        for area, count in sorted_areas:
            print(f"   {area}: {count}")

    if stats.get('by_doc_type'):
        print(f"\n📝 By Document Type (top 10):")
        for doc_type, count in stats['by_doc_type'].items():
            print(f"   {doc_type}: {count}")


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("EU LAW EXTRACTION - TEST SUITE")
    print("=" * 80)

    # Test 1: XML Parser
    parser_results = test_xml_parser()

    # Check if we should continue
    if not any(r['success'] for r in parser_results):
        print("\n❌ XML parser tests failed. Stopping.")
        return

    # Test 2: Indexer (only if parser works)
    try:
        await test_law_indexer()
    except Exception as e:
        print(f"\n❌ Indexer test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Search
    try:
        await test_search()
    except Exception as e:
        print(f"\n❌ Search test failed: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test 4: Statistics
    try:
        await test_statistics()
    except Exception as e:
        print(f"\n❌ Statistics test failed: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
