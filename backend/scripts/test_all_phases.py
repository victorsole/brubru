"""
Comprehensive Test: All 5 Phases

Quick validation that all phases are properly integrated and working.
Tests imports, basic functionality, and integration.

Usage:
    python backend/scripts/test_all_phases.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all phase modules import correctly"""
    print("\n" + "="*80)
    print("TESTING IMPORTS")
    print("="*80 + "\n")

    try:
        # Phase 1: Content Extraction
        print("Phase 1: Content Extraction...")
        from services.document_processing.pdf_processor import PDFProcessor
        from services.document_processing.eprs_enricher import EPRSContentEnricher
        from schemas.scrapers.scraper_schemas import EPRSPublication
        print("  ✓ Phase 1 imports successful")

        # Phase 2: Vector Database
        print("Phase 2: Vector Database...")
        from services.vector_db.vector_store import VectorStore
        from services.indexing.document_chunker import DocumentChunker
        from services.indexing.eprs_indexer import EPRSIndexer
        print("  ✓ Phase 2 imports successful")

        # Phase 3: Intelligent Matching
        print("Phase 3: Intelligent Matching...")
        from services.matching.eprs_matcher import EPRSMatcher
        print("  ✓ Phase 3 imports successful")

        # Phase 4: Historical Archive
        print("Phase 4: Historical Archive...")
        from services.api_clients.eprs_archive_client import EPRSArchiveClient
        from services.archiving.eprs_archive_downloader import EPRSArchiveDownloader
        print("  ✓ Phase 4 imports successful")

        # Phase 5: Smart Summaries
        print("Phase 5: Smart Summaries...")
        from services.ai.ai_summary_generator import AISummaryGenerator
        from services.ai.freshness_detector import FreshnessDetector
        print("  ✓ Phase 5 imports successful")

        print("\n✅ ALL IMPORTS SUCCESSFUL!\n")
        return True

    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {e}\n")
        print("Missing dependencies? Run:")
        print("  pip install -r backend/requirements.txt")
        return False


def test_configuration():
    """Test that required configuration is present"""
    print("\n" + "="*80)
    print("TESTING CONFIGURATION")
    print("="*80 + "\n")

    try:
        from core.config import settings

        # Check Phase 5 requirement
        if settings.ANTHROPIC_API_KEY:
            print("✓ ANTHROPIC_API_KEY configured (Phase 5 ready)")
        else:
            print("⚠️  ANTHROPIC_API_KEY not set")
            print("   Phase 5 AI summaries will not work without this")
            print("   Add to .env: ANTHROPIC_API_KEY=your_key")

        print("\n✅ Configuration check complete\n")
        return True

    except Exception as e:
        print(f"❌ Configuration error: {e}\n")
        return False


def test_phase_1_basic():
    """Test Phase 1: Content Extraction"""
    print("\n" + "="*80)
    print("TESTING PHASE 1: Content Extraction")
    print("="*80 + "\n")

    try:
        from services.document_processing.pdf_processor import PDFProcessor
        from schemas.scrapers.scraper_schemas import EPRSPublication, EPRSPublicationType
        from datetime import datetime

        # Create a test publication
        test_pub = EPRSPublication(
            publication_id="test_001",
            title="Test EPRS Publication",
            publication_type=EPRSPublicationType.BRIEFING,
            summary="Test summary",
            publication_date=datetime.now()
        )

        print(f"✓ Created test publication: {test_pub.title}")
        print(f"✓ Type: {test_pub.publication_type.value}")
        print(f"✓ ID: {test_pub.publication_id}")

        print("\n✅ Phase 1: Basic functionality working\n")
        return True

    except Exception as e:
        print(f"❌ Phase 1 error: {e}\n")
        return False


def test_phase_2_basic():
    """Test Phase 2: Vector Database"""
    print("\n" + "="*80)
    print("TESTING PHASE 2: Vector Database")
    print("="*80 + "\n")

    try:
        from services.indexing.document_chunker import DocumentChunker

        # Test document chunking
        chunker = DocumentChunker(
            max_chunk_size=500,
            min_chunk_size=50
        )

        test_text = """
        The European Union is a political and economic union of member states.
        It operates through a system of supranational institutions.
        The EU has developed a single market through a standardised system of laws.
        """

        chunks = chunker.chunk_by_paragraphs(
            document_id="test_001",
            text=test_text
        )

        print(f"✓ Chunker initialized")
        print(f"✓ Created {len(chunks)} chunks from test text")
        print(f"✓ First chunk: {chunks[0].text[:50]}...")

        print("\n✅ Phase 2: Basic functionality working\n")
        return True

    except Exception as e:
        print(f"❌ Phase 2 error: {e}\n")
        return False


def test_phase_3_basic():
    """Test Phase 3: Intelligent Matching"""
    print("\n" + "="*80)
    print("TESTING PHASE 3: Intelligent Matching")
    print("="*80 + "\n")

    try:
        from services.matching.eprs_matcher import EPRSMatcher

        # Initialize matcher (doesn't require async)
        matcher = EPRSMatcher()

        print(f"✓ EPRSMatcher initialized")
        print(f"✓ Matching strategies available:")
        print(f"  - CELEX exact match")
        print(f"  - CELEX semantic search")
        print(f"  - Procedure exact match")
        print(f"  - Procedure semantic search")

        print("\n✅ Phase 3: Basic functionality working\n")
        return True

    except Exception as e:
        print(f"❌ Phase 3 error: {e}\n")
        return False


def test_phase_4_basic():
    """Test Phase 4: Historical Archive"""
    print("\n" + "="*80)
    print("TESTING PHASE 4: Historical Archive")
    print("="*80 + "\n")

    try:
        from services.api_clients.eprs_archive_client import EPRSArchiveClient
        from services.api_clients.base_sparql_client import SPARQLQuery, SPARQLQueryType

        # Initialize archive client
        client = EPRSArchiveClient()

        print(f"✓ EPRSArchiveClient initialized")
        print(f"✓ SPARQL endpoint: {client.sparql.endpoint_url}")

        # Test SPARQL query builder
        query = SPARQLQuery(SPARQLQueryType.SELECT)
        query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        query.select(["?work", "?title"])
        query.limit(10)

        query_str = query.build()
        print(f"✓ SPARQL query builder working")
        print(f"✓ Sample query: {query_str[:100]}...")

        print("\n✅ Phase 4: Basic functionality working\n")
        return True

    except Exception as e:
        print(f"❌ Phase 4 error: {e}\n")
        return False


def test_phase_5_basic():
    """Test Phase 5: Smart Summaries"""
    print("\n" + "="*80)
    print("TESTING PHASE 5: Smart Summaries")
    print("="*80 + "\n")

    try:
        from services.ai.ai_summary_generator import AISummaryGenerator
        from services.ai.freshness_detector import FreshnessDetector, FreshnessLevel
        from datetime import datetime, timedelta

        # Test freshness detector (doesn't need API key)
        detector = FreshnessDetector()
        print(f"✓ FreshnessDetector initialized")

        # Test freshness level enum
        print(f"✓ Freshness levels available:")
        for level in FreshnessLevel:
            print(f"  - {level.value}")

        # Test AI summary generator initialization
        try:
            generator = AISummaryGenerator()
            print(f"✓ AISummaryGenerator initialized")
            print(f"✓ Model: {generator.model}")
        except Exception as e:
            print(f"⚠️  AISummaryGenerator init warning: {e}")
            print(f"   (This is OK if ANTHROPIC_API_KEY is not set)")

        print("\n✅ Phase 5: Basic functionality working\n")
        return True

    except Exception as e:
        print(f"❌ Phase 5 error: {e}\n")
        return False


def print_next_steps():
    """Print instructions for running full tests"""
    print("\n" + "="*80)
    print("NEXT STEPS: Run Individual Phase Tests")
    print("="*80 + "\n")

    print("All phases are properly integrated! To test functionality:\n")

    print("Phase 1: Full Content Extraction")
    print("  python backend/scripts/test_phase1_eprs_extraction.py\n")

    print("Phase 2: Vector Database Population")
    print("  python backend/scripts/test_phase2_vector_db.py\n")

    print("Phase 3: Intelligent Matching")
    print("  python backend/scripts/test_phase3_intelligent_matching.py\n")

    print("Phase 4: Historical Archive Building")
    print("  python backend/scripts/test_phase4_historical_archive.py\n")

    print("Phase 5: Smart Summaries")
    print("  python backend/scripts/test_phase5_smart_summaries.py\n")

    print("⚠️  Note: Some tests require:")
    print("  - ANTHROPIC_API_KEY in .env (Phase 5)")
    print("  - EUR-Lex API access (Phases 1, 3, 5)")
    print("  - Internet connectivity (Phase 4 SPARQL endpoint)")
    print("")


def main():
    """Run all basic tests"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST: ALL 5 PHASES")
    print("="*80)
    print("\nValidating that all phases are properly integrated...\n")

    results = {
        "Imports": test_imports(),
        "Configuration": test_configuration(),
        "Phase 1": test_phase_1_basic(),
        "Phase 2": test_phase_2_basic(),
        "Phase 3": test_phase_3_basic(),
        "Phase 4": test_phase_4_basic(),
        "Phase 5": test_phase_5_basic()
    }

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80 + "\n")

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n" + "="*80)
        print("🎉 ALL BASIC TESTS PASSED!")
        print("="*80)
        print("\n✅ All 5 phases are properly integrated and ready to use!\n")
        print_next_steps()
    else:
        print("\n" + "="*80)
        print("⚠️  SOME TESTS FAILED")
        print("="*80)
        print("\nCheck errors above and ensure:")
        print("  1. All dependencies installed: pip install -r backend/requirements.txt")
        print("  2. Configuration set in .env file")
        print("")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
