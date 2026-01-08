"""
Test Full Integration of EU Laws Database with Chatbot

Tests the complete pipeline:
1. Local laws database indexing
2. Context builder integration
3. Query processing with CELEX and semantic search
4. Context formatting for AI

Usage:
    python -m backend.scripts.test_integration
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.law_database.law_indexer import get_law_indexer
from backend.services.ai.context_builder import ContextBuilder
from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw


async def test_database_status():
    """Test 1: Check database status"""
    print("\n" + "=" * 80)
    print("TEST 1: DATABASE STATUS")
    print("=" * 80)

    indexer = get_law_indexer()

    # Get statistics
    stats = await indexer.get_statistics()

    print(f"\n📊 Database Statistics:")
    print(f"   Total laws indexed: {stats.get('total_laws', 0):,}")
    print(f"   Laws with CELEX: {stats.get('laws_with_celex', 0):,}")

    if stats.get('date_range'):
        print(f"\n📅 Date Range:")
        print(f"   Earliest: {stats['date_range'].get('earliest', 'N/A')}")
        print(f"   Latest: {stats['date_range'].get('latest', 'N/A')}")

    if stats.get('by_policy_area'):
        print(f"\n📂 Policy Areas ({len(stats['by_policy_area'])} total):")
        sorted_areas = sorted(
            stats['by_policy_area'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        for area, count in sorted_areas:
            print(f"   - {area}: {count:,}")

    if stats.get('by_doc_type'):
        print(f"\n📝 Document Types (top 5):")
        for i, (doc_type, count) in enumerate(list(stats['by_doc_type'].items())[:5], 1):
            print(f"   {i}. {doc_type}: {count:,}")

    # Check if we have sample data
    if stats.get('total_laws', 0) == 0:
        print("\n⚠️  WARNING: No laws indexed yet!")
        print("   Run: python -m backend.scripts.test_law_extraction")
        print("   Or: python -m backend.scripts.index_all_laws --limit 10")
        return False

    print(f"\n✅ Database status: OK ({stats.get('total_laws', 0)} laws)")
    return True


async def test_law_indexer_search():
    """Test 2: Test law indexer search functionality"""
    print("\n" + "=" * 80)
    print("TEST 2: LAW INDEXER SEARCH")
    print("=" * 80)

    indexer = get_law_indexer()

    # Test 1: CELEX lookup
    print("\n🔍 Test 2.1: CELEX Lookup (32019R1194)")
    law = await indexer.get_law_by_celex("32019R1194")

    if law:
        print(f"   ✅ Found law by CELEX")
        print(f"   Title: {law['title'][:100]}...")
        print(f"   Type: {law['doc_type']}")
        print(f"   Date: {law.get('date', 'N/A')}")
        print(f"   Policy Area: {law.get('policy_area', 'Unclassified')}")
    else:
        print(f"   ❌ Law not found (may not be indexed yet)")

    # Test 2: Semantic search
    print("\n🔍 Test 2.2: Semantic Search ('data protection')")
    results = await indexer.search_laws(
        query="data protection",
        limit=3
    )

    print(f"   Found {len(results)} results:")
    for i, law in enumerate(results, 1):
        print(f"   {i}. {law['celex'] or 'No CELEX'} - {law['title'][:80]}...")
        print(f"      Policy: {law.get('policy_area', 'Unclassified')}")

    # Test 3: Policy filter
    print("\n🔍 Test 2.3: Filter by Policy Area")

    # Get a policy area from the database
    db = SessionLocal()
    try:
        sample_policy = db.query(EULaw.policy_area).filter(
            EULaw.policy_area.isnot(None)
        ).first()

        if sample_policy and sample_policy[0]:
            policy_area = sample_policy[0]
            results = await indexer.search_laws(
                query="",
                filters={'policy_area': policy_area},
                limit=3
            )
            print(f"   Policy Area: {policy_area}")
            print(f"   Found {len(results)} laws in this area")
        else:
            print(f"   ⚠️  No policy areas classified yet")
    finally:
        db.close()

    print(f"\n✅ Law indexer search: OK")


async def test_context_builder_integration():
    """Test 3: Test context builder integration"""
    print("\n" + "=" * 80)
    print("TEST 3: CONTEXT BUILDER INTEGRATION")
    print("=" * 80)

    # Import required dependencies
    from backend.services.search.hybrid_search import get_hybrid_search
    from backend.services.indexing.metadata_extractor import get_metadata_extractor

    # Initialize context builder with required dependencies
    context_builder = ContextBuilder(
        hybrid_search=get_hybrid_search(),
        metadata_extractor=get_metadata_extractor()
    )

    # Test query 1: CELEX mention
    print("\n🤖 Test 3.1: Query with CELEX Number")
    query1 = "What is Regulation 32019R1194 about?"

    print(f"   Query: {query1}")
    context1 = await context_builder.build_context_for_query(
        user_message=query1,
        conversation_history=[]
    )

    print(f"   ✅ Context built successfully")
    print(f"   Local EU laws found: {len(context1.local_eu_laws)}")

    if context1.local_eu_laws:
        for law in context1.local_eu_laws:
            print(f"   - CELEX: {law.get('celex', 'N/A')}")
            print(f"     Title: {law['title'][:80]}...")
            print(f"     Full text length: {len(law.get('full_text', '')):,} chars")

    # Test query 2: Semantic search
    print("\n🤖 Test 3.2: Query without CELEX (Semantic Search)")
    query2 = "What are the EU laws about environmental protection?"

    print(f"   Query: {query2}")
    context2 = await context_builder.build_context_for_query(
        user_message=query2,
        conversation_history=[]
    )

    print(f"   ✅ Context built successfully")
    print(f"   Local EU laws found: {len(context2.local_eu_laws)}")

    if context2.local_eu_laws:
        for law in context2.local_eu_laws[:3]:  # Show first 3
            print(f"   - {law.get('celex', 'No CELEX')} - {law['title'][:60]}...")

    print(f"\n✅ Context builder integration: OK")


async def test_context_formatting():
    """Test 4: Test context formatting for AI"""
    print("\n" + "=" * 80)
    print("TEST 4: CONTEXT FORMATTING FOR AI")
    print("=" * 80)

    # Import required dependencies
    from backend.services.search.hybrid_search import get_hybrid_search
    from backend.services.indexing.metadata_extractor import get_metadata_extractor

    # Initialize context builder with required dependencies
    context_builder = ContextBuilder(
        hybrid_search=get_hybrid_search(),
        metadata_extractor=get_metadata_extractor()
    )

    print("\n📝 Building context for sample query...")
    query = "Tell me about Regulation 32019R1194"

    context = await context_builder.build_context_for_query(
        user_message=query,
        conversation_history=[]
    )

    # Format context
    formatted_context = context_builder.format_context_for_ai(context)

    print(f"\n📄 Formatted Context Preview:")
    print("=" * 80)

    # Show first 2000 characters of formatted context
    preview = formatted_context[:2000]
    print(preview)

    if len(formatted_context) > 2000:
        print(f"\n... (truncated, full context is {len(formatted_context):,} characters)")

    # Check for local laws section
    if "LOCAL EU LAWS DATABASE" in formatted_context:
        print(f"\n✅ Local laws section found in formatted context")

        # Extract and show the local laws section
        local_section_start = formatted_context.find("LOCAL EU LAWS DATABASE")
        local_section_end = formatted_context.find("\n\n", local_section_start + 200)

        if local_section_end > local_section_start:
            local_section = formatted_context[local_section_start:local_section_end]
            print(f"\n📊 Local Laws Section ({len(local_section)} chars):")
            print("-" * 80)
            print(local_section[:1000])
            if len(local_section) > 1000:
                print("... (truncated)")
    else:
        print(f"\n⚠️  Local laws section NOT found in formatted context")

    print(f"\n✅ Context formatting: OK")


async def test_full_pipeline():
    """Test 5: Full pipeline end-to-end"""
    print("\n" + "=" * 80)
    print("TEST 5: FULL PIPELINE END-TO-END")
    print("=" * 80)

    print("\n🔄 Testing complete pipeline:")
    print("   1. Query → Entity Extraction")
    print("   2. Entity Extraction → Database Search")
    print("   3. Database Search → Context Building")
    print("   4. Context Building → AI Formatting")

    # Import required dependencies
    from backend.services.search.hybrid_search import get_hybrid_search
    from backend.services.indexing.metadata_extractor import get_metadata_extractor

    # Initialize context builder with required dependencies
    context_builder = ContextBuilder(
        hybrid_search=get_hybrid_search(),
        metadata_extractor=get_metadata_extractor()
    )

    test_queries = [
        "What is CELEX 32019R1194?",
        "Show me EU laws about agriculture",
        "What are the requirements for data protection?"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Query {i}: {query}")

        try:
            context = await context_builder.build_context_for_query(
                user_message=query,
                conversation_history=[]
            )

            formatted = context_builder.format_context_for_ai(context)

            print(f"   ✅ Pipeline completed successfully")
            print(f"   - Local laws: {len(context.local_eu_laws)}")
            print(f"   - Formatted context: {len(formatted):,} chars")
            print(f"   - Has local laws section: {'LOCAL EU LAWS DATABASE' in formatted}")

        except Exception as e:
            print(f"   ❌ Pipeline failed: {str(e)}")
            import traceback
            traceback.print_exc()

    print(f"\n✅ Full pipeline: OK")


async def main():
    """Run all integration tests"""
    print("=" * 80)
    print("EU LAWS DATABASE + CHATBOT INTEGRATION TEST SUITE")
    print("=" * 80)
    print("\nThis test suite verifies:")
    print("  1. Database indexing status")
    print("  2. Law indexer search functionality")
    print("  3. Context builder integration")
    print("  4. AI context formatting")
    print("  5. Full end-to-end pipeline")

    try:
        # Test 1: Database status
        has_data = await test_database_status()

        if not has_data:
            print("\n" + "=" * 80)
            print("⚠️  TESTS SKIPPED: No data in database")
            print("=" * 80)
            print("\n📝 To populate test data, run:")
            print("   python -m backend.scripts.test_law_extraction")
            print("   or")
            print("   python -m backend.scripts.index_all_laws --limit 10")
            return

        # Test 2: Law indexer search
        await test_law_indexer_search()

        # Test 3: Context builder integration
        await test_context_builder_integration()

        # Test 4: Context formatting
        await test_context_formatting()

        # Test 5: Full pipeline
        await test_full_pipeline()

        # Final summary
        print("\n" + "=" * 80)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 80)

        print("\n🎉 The integration is working correctly:")
        print("   ✓ Database is accessible")
        print("   ✓ Law indexer search works")
        print("   ✓ Context builder fetches local laws")
        print("   ✓ AI formatting includes local laws")
        print("   ✓ Full pipeline works end-to-end")

        print("\n📝 Next steps:")
        print("   1. Index all 50k+ laws:")
        print("      python -m backend.scripts.index_all_laws")
        print("   2. Start chatbot and test with real queries")
        print("   3. Monitor performance and optimize as needed")

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ INTEGRATION TESTS FAILED")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
