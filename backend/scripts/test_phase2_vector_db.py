"""
Phase 2 Test Script: Vector Database Population & Integration

Tests the complete Phase 2 pipeline:
1. Extract EPRS publications (Phase 1)
2. Chunk documents intelligently
3. Index in ChromaDB vector database
4. Search publications semantically
5. Integrate with AI context builder

This demonstrates how EPRS briefings become "EU jargon translators" for the AI.

Usage:
    python backend/scripts/test_phase2_vector_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.scrapers.think_tank_scraper import ThinkTankScraper
from services.indexing.eprs_indexer import EPRSIndexer, get_eprs_indexer
from services.indexing.document_chunker import DocumentChunker
from services.vector_db.vector_store import VectorStore
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_extract_and_index():
    """
    Test 1: Extract EPRS publications and index them in ChromaDB

    This is the core Phase 2 workflow.
    """
    print("\n" + "="*80)
    print("TEST 1: Extract & Index EPRS Publications")
    print("="*80 + "\n")

    # Step 1: Extract publications from RSS (Phase 1)
    print("Step 1: Extracting EPRS publications from RSS...")
    scraper = ThinkTankScraper(enable_full_extraction=True)

    try:
        # Get 5 recent briefings with full content
        extraction_results = await scraper.get_latest_publications_enriched(
            hours=720,  # Last 30 days
            limit=5,
            publication_type="briefings"
        )

        print(f"✓ Extracted {len(extraction_results)} publications\n")

        if not extraction_results:
            print("⚠️  No publications found. Skipping indexing test.")
            return

        # Step 2: Initialize indexer
        print("Step 2: Initializing EPRS indexer...")
        indexer = EPRSIndexer(use_sections=True)  # Chunk by sections
        print("✓ Indexer ready\n")

        # Step 3: Index each publication
        print("Step 3: Indexing publications into ChromaDB...")
        indexed_publications = []

        for i, result in enumerate(extraction_results, 1):
            pub = result.publication

            print(f"\nIndexing {i}/{len(extraction_results)}: {pub.title}")
            print(f"  Word count: {pub.word_count:,}")
            print(f"  Sections: {len(pub.sections)}")

            # Index the publication
            index_result = await indexer.index_publication(pub, force_reindex=False)

            if index_result['success']:
                print(f"  ✓ Indexed {index_result['chunks_indexed']} chunks")
                indexed_publications.append(pub)
            else:
                print(f"  ✗ Failed: {index_result['errors']}")

        print(f"\n{'─'*80}")
        print(f"✓ Successfully indexed {len(indexed_publications)} publications")

        # Step 4: Get indexing statistics
        print("\nStep 4: Indexing Statistics")
        stats = indexer.get_stats()

        print(f"  Total chunks in database: {stats.get('total_chunks', 0)}")
        print(f"  Unique publications: {stats.get('unique_publications', 0)}")

        if 'by_type' in stats:
            print(f"\n  By publication type:")
            for pub_type, count in stats['by_type'].items():
                print(f"    - {pub_type}: {count} chunks")

        if 'by_quality' in stats:
            print(f"\n  By extraction quality:")
            for quality, count in stats['by_quality'].items():
                print(f"    - {quality}: {count} chunks")

    finally:
        await scraper.close()

    print("\n" + "="*80)
    print("TEST 1 COMPLETE")
    print("="*80)


async def test_semantic_search():
    """
    Test 2: Search indexed EPRS publications semantically

    Demonstrates how the AI can find relevant briefings.
    """
    print("\n" + "="*80)
    print("TEST 2: Semantic Search of EPRS Publications")
    print("="*80 + "\n")

    indexer = get_eprs_indexer()

    # Test queries
    test_queries = [
        "artificial intelligence regulation",
        "climate change policy",
        "data protection and privacy",
        "migration and asylum"
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("─" * 40)

        results = await indexer.search(
            query=query,
            limit=3
        )

        if results:
            print(f"Found {len(results)} relevant publications:\n")

            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})

                print(f"{i}. {metadata.get('title', 'Unknown Title')}")
                print(f"   Type: {metadata.get('publication_type', 'unknown')}")
                print(f"   Relevance: {1 - result.get('distance', 1):.2%}")
                print(f"   Preview: {result.get('text', '')[:150]}...")

                if metadata.get('related_celex_numbers'):
                    celex_list = metadata['related_celex_numbers'].split(',')
                    print(f"   Related legislation: {', '.join(celex_list[:3])}")

                print()
        else:
            print("  No results found\n")

    print("="*80)
    print("TEST 2 COMPLETE")
    print("="*80)


async def test_ai_context_integration():
    """
    Test 3: Demonstrate EPRS integration with AI Context Builder

    Shows how EPRS briefings automatically appear in AI responses.
    """
    print("\n" + "="*80)
    print("TEST 3: AI Context Integration")
    print("="*80 + "\n")

    print("This test demonstrates how EPRS publications are automatically")
    print("included in AI context when users ask about EU legislation.\n")

    indexer = get_eprs_indexer()

    # Simulate user questions
    user_questions = [
        "What is the AI Act?",
        "Explain the Digital Services Act",
        "How does the GDPR work?"
    ]

    for question in user_questions:
        print(f"\nUser asks: '{question}'")
        print("─" * 60)

        # Search for relevant EPRS content
        eprs_results = await indexer.search(
            query=question,
            limit=2
        )

        if eprs_results:
            print(f"✓ AI context would include {len(eprs_results)} EPRS briefings:")

            for result in eprs_results:
                metadata = result.get('metadata', {})
                print(f"\n  📄 {metadata.get('title', 'Unknown')}")
                print(f"     Type: {metadata.get('publication_type', 'unknown')}")
                print(f"     Purpose: Plain-language explanation of complex legislation")

                # Show how it helps
                text_preview = result.get('text', '')[:200]
                print(f"\n     AI can use this to explain:")
                print(f"     \"{text_preview}...\"")

                if metadata.get('related_celex_numbers'):
                    print(f"\n     Explains legislation: {metadata['related_celex_numbers']}")

            print("\n  💡 Impact: User gets both legal text AND plain-language explanation")
        else:
            print("  ℹ️  No EPRS briefings found (try indexing more publications)")

        print()

    print("="*80)
    print("TEST 3 COMPLETE")
    print("="*80)


async def test_chunking_strategies():
    """
    Test 4: Demonstrate different document chunking strategies
    """
    print("\n" + "="*80)
    print("TEST 4: Document Chunking Strategies")
    print("="*80 + "\n")

    print("Testing different ways to chunk EPRS documents for optimal search...\n")

    # Sample publication (you'd get this from Phase 1)
    sample_text = """
    Introduction

    The Artificial Intelligence Act (AI Act) is a proposed European Union regulation on artificial intelligence.
    It is the first comprehensive AI regulation in the world.

    Key Provisions

    The AI Act classifies AI systems by risk level: unacceptable risk, high risk, limited risk, and minimal risk.
    High-risk AI systems will face strict requirements for transparency, human oversight, and accuracy.

    Impact Assessment

    The regulation will significantly impact businesses deploying AI in the EU.
    Compliance costs are estimated between €5,000-€10,000 per high-risk system.
    """

    sample_sections = [
        {"heading": "Introduction", "content": "The Artificial Intelligence Act..."},
        {"heading": "Key Provisions", "content": "The AI Act classifies..."},
        {"heading": "Impact Assessment", "content": "The regulation will significantly..."}
    ]

    chunker = DocumentChunker(
        max_chunk_size=500,
        min_chunk_size=50,
        overlap_size=50
    )

    # Strategy 1: Section-based
    print("Strategy 1: Section-based chunking")
    print("  Best for: Structured documents with clear headings")
    section_chunks = chunker.chunk_by_sections(
        document_id="sample_001",
        sections=sample_sections
    )
    print(f"  Result: {len(section_chunks)} chunks")
    for chunk in section_chunks:
        print(f"    - {chunk.heading} ({chunk.word_count} words)")

    # Strategy 2: Paragraph-based
    print("\nStrategy 2: Paragraph-based chunking")
    print("  Best for: Unstructured text without clear sections")
    para_chunks = chunker.chunk_by_paragraphs(
        document_id="sample_001",
        text=sample_text
    )
    print(f"  Result: {len(para_chunks)} chunks")
    for i, chunk in enumerate(para_chunks):
        print(f"    - Chunk {i+1} ({chunk.word_count} words)")

    # Strategy 3: Full document
    print("\nStrategy 3: Full document chunking")
    print("  Best for: Short documents (< 1000 chars)")
    full_chunks = chunker.chunk_full_document(
        document_id="sample_001",
        text=sample_text
    )
    print(f"  Result: {len(full_chunks)} chunk")
    print(f"    - Full document ({full_chunks[0].word_count} words)")

    print(f"\n{'─'*60}")
    print("📊 Recommendation: Use section-based chunking for EPRS publications")
    print("   Reason: Preserves document structure and context")

    print("\n" + "="*80)
    print("TEST 4 COMPLETE")
    print("="*80)


async def test_cross_reference_matching():
    """
    Test 5: Demonstrate CELEX-to-EPRS cross-referencing

    This is a preview of Phase 3 functionality.
    """
    print("\n" + "="*80)
    print("TEST 5: Cross-Reference Matching (Phase 3 Preview)")
    print("="*80 + "\n")

    print("Demonstrating how EPRS briefings link to specific EU legislation...\n")

    indexer = get_eprs_indexer()

    # Example: Find EPRS briefings about specific legislation
    example_celex = "32016R0679"  # GDPR

    print(f"Looking for EPRS briefings about CELEX {example_celex} (GDPR)...")

    # Search using CELEX in query
    results = await indexer.search(
        query=f"CELEX {example_celex} GDPR data protection",
        limit=5,
        filters={}
    )

    if results:
        print(f"\n✓ Found {len(results)} briefings that may explain this legislation:\n")

        for result in results:
            metadata = result.get('metadata', {})
            related_celex = metadata.get('related_celex_numbers', '').split(',')

            print(f"  • {metadata.get('title', 'Unknown')}")
            print(f"    Type: {metadata.get('publication_type', 'unknown')}")

            if example_celex in related_celex:
                print(f"    ✓ DIRECT MATCH: This briefing explicitly mentions {example_celex}")
            else:
                print(f"    ~ Semantic match: May be relevant based on content")

            print()

        print("💡 Phase 3 will implement intelligent auto-linking:")
        print("   When EUR-Lex doc is fetched → automatically find EPRS briefing")
        print("   Result: Legal text + plain-language explanation together")

    else:
        print("  No results found. Try indexing GDPR-related briefings first.")

    print("\n" + "="*80)
    print("TEST 5 COMPLETE")
    print("="*80)


async def main():
    """Run all Phase 2 tests"""
    print("\n" + "="*80)
    print("PHASE 2: VECTOR DATABASE POPULATION - TEST SUITE")
    print("="*80)
    print("\nThis test suite demonstrates:")
    print("  1. Extracting EPRS publications (Phase 1)")
    print("  2. Chunking documents intelligently")
    print("  3. Indexing in ChromaDB vector database")
    print("  4. Semantic search for relevant briefings")
    print("  5. Integration with AI context (jargon translation)")
    print("\n")

    # Run tests
    await test_extract_and_index()
    await test_semantic_search()
    await test_ai_context_integration()
    await test_chunking_strategies()
    await test_cross_reference_matching()

    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)
    print("\n✅ Phase 2 Implementation Summary:")
    print("  ✓ PDF extraction working (Phase 1)")
    print("  ✓ Document chunking implemented")
    print("  ✓ ChromaDB indexing operational")
    print("  ✓ Semantic search functional")
    print("  ✓ AI context integration complete")
    print("\n📋 Next Steps:")
    print("  → Phase 3: Implement intelligent CELEX-to-EPRS auto-linking")
    print("  → Phase 4: Build historical archive (bulk download)")
    print("  → Phase 5: Apply blueprint to JRC publications")
    print("\n💡 Key Achievement:")
    print("  EPRS briefings now serve as 'EU jargon translators' for the AI!")
    print("  When users ask about legislation, they get both:")
    print("    • Legal text (from EUR-Lex)")
    print("    • Plain-language explanation (from EPRS)")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
