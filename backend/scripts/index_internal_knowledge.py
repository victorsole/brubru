"""
Index Internal Knowledge Base

Script to index templates from knowledge_base into ChromaDB.
Run this after adding or updating knowledge base content.

Usage:
    python -m backend.scripts.index_internal_knowledge
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.knowledge_base.knowledge_loader import get_knowledge_loader
from backend.services.vector_db.vector_store import get_vector_store

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def index_internal_knowledge():
    """Index internal knowledge base into ChromaDB"""

    logger.info("=" * 60)
    logger.info("INDEXING INTERNAL KNOWLEDGE BASE")
    logger.info("=" * 60)

    # 1. Load knowledge base
    logger.info("\n1. Loading knowledge base...")
    knowledge_loader = get_knowledge_loader()
    stats = knowledge_loader.load_all()

    logger.info(f"   ✓ Loaded {stats['calendars']} calendars")
    logger.info(f"   ✓ Loaded {stats['institutions']} institution files")
    logger.info(f"   ✓ Loaded {stats['templates']} templates")
    logger.info(f"   ✓ Load time: {stats['load_time_seconds']:.2f}s")

    # 2. Initialize vector store
    logger.info("\n2. Connecting to ChromaDB...")
    vector_store = get_vector_store()
    logger.info("   ✓ Connected to vector store")

    # 3. Prepare templates for embedding
    logger.info("\n3. Preparing templates for indexing...")
    documents = knowledge_loader.prepare_templates_for_embedding()
    logger.info(f"   ✓ Prepared {len(documents)} documents")

    # 4. Index into ChromaDB
    logger.info("\n4. Indexing into ChromaDB...")
    try:
        result = vector_store.add_internal_knowledge(documents)
        logger.info(f"   ✓ Indexed {result['added']} documents")
    except Exception as e:
        logger.error(f"   ✗ Indexing failed: {str(e)}")
        return False

    # 5. Verify indexing
    logger.info("\n5. Verifying indexing...")
    collection_stats = vector_store.get_collection_stats(
        vector_store.COLLECTION_INTERNAL_KNOWLEDGE
    )
    logger.info(f"   ✓ Collection now has {collection_stats['count']} documents")

    # 6. Test query
    logger.info("\n6. Testing search...")
    test_query = ["I need a template for a briefing note"]
    test_results = vector_store.query_internal_knowledge(
        query_texts=test_query,
        n_results=3
    )

    if test_results and test_results.get('ids') and test_results['ids'][0]:
        logger.info(f"   ✓ Search working! Found {len(test_results['ids'][0])} results")
        for i, doc_id in enumerate(test_results['ids'][0][:3], 1):
            metadata = test_results['metadatas'][0][i-1]
            logger.info(f"      {i}. {metadata.get('title', doc_id)}")
    else:
        logger.warning("   ! No search results (this may be normal if no templates match)")

    logger.info("\n" + "=" * 60)
    logger.info("✓ INDEXING COMPLETE!")
    logger.info("=" * 60)

    return True


def show_knowledge_stats():
    """Show current knowledge base statistics"""
    logger.info("\n" + "=" * 60)
    logger.info("KNOWLEDGE BASE STATISTICS")
    logger.info("=" * 60)

    knowledge_loader = get_knowledge_loader()
    stats = knowledge_loader.get_stats()

    logger.info(f"\nCalendars: {stats['calendars']}")
    logger.info(f"Institutions: {stats['institutions']}")
    logger.info(f"Templates: {stats['templates']}")
    logger.info(f"\nTemplate categories:")
    for category, count in stats.get('template_categories', {}).items():
        logger.info(f"  - {category}: {count}")

    vector_store = get_vector_store()
    all_stats = vector_store.get_all_stats()

    logger.info(f"\nVector Store Collections:")
    for name, coll_stats in all_stats['collections'].items():
        logger.info(f"  - {name}: {coll_stats['count']} documents")

    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Index internal knowledge base')
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show knowledge base statistics only'
    )

    args = parser.parse_args()

    if args.stats:
        show_knowledge_stats()
    else:
        success = index_internal_knowledge()
        sys.exit(0 if success else 1)
