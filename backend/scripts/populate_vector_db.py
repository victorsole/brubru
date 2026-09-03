"""
Populate Vector Database with EU Data

This script:
1. Runs all EU scrapers to fetch data
2. Processes and validates the data
3. Generates embeddings
4. Stores everything in ChromaDB

Usage:
    python3.12 -m backend.scripts.populate_vector_db [--source SOURCE] [--limit LIMIT]

Examples:
    # Populate all sources
    python3.12 -m backend.scripts.populate_vector_db

    # Populate only EUR-Lex
    python3.12 -m backend.scripts.populate_vector_db --source eurlex --limit 100

    # Quick test with 10 items
    python3.12 -m backend.scripts.populate_vector_db --limit 10
"""

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import asyncio
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, _REPO_ROOT)

from backend.services.scrapers.scraper_orchestrator import ScraperOrchestrator
from backend.services.vector_db.vector_store import get_vector_store
from backend.services.vector_db.embeddings_service import get_embeddings_service
from backend.services.indexing.document_indexer import DocumentIndexer
from backend.core.config import settings


async def populate_legislation(orchestrator: ScraperOrchestrator, limit: int = 100):
    """Fetch and index legislative documents from EUR-Lex"""
    logger.info(f"📜 Fetching legislative documents (limit: {limit})...")

    try:
        # Fetch latest legislation
        eurlex_scraper = orchestrator.scrapers['eurlex']
        documents = await eurlex_scraper.get_latest_updates(limit=limit)

        if not documents:
            logger.warning("No legislative documents found")
            return 0

        logger.info(f"✓ Fetched {len(documents)} legislative documents")

        # Prepare for indexing
        vector_store = get_vector_store()
        embeddings_service = get_embeddings_service()

        # Convert to indexable format
        texts = []
        metadatas = []
        ids = []

        for i, doc in enumerate(documents):
            if isinstance(doc, dict):
                # Extract text content
                text = f"{doc.get('title', '')} {doc.get('summary', '')} {doc.get('text', '')}"
                texts.append(text.strip())

                # Extract metadata
                metadatas.append({
                    'celex': doc.get('celex', f'unknown_{i}'),
                    'document_type': doc.get('document_type', 'unknown'),
                    'title': doc.get('title', ''),
                    'date': doc.get('date', datetime.now().isoformat()),
                    'url': doc.get('url', ''),
                })

                ids.append(doc.get('celex', f'doc_{i}'))

        # Generate embeddings
        logger.info("🔄 Generating embeddings...")
        embeddings = await embeddings_service.generate_batch_embeddings(texts)

        # Add to vector store
        logger.info("💾 Storing in ChromaDB...")
        vector_store.add_legislation(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )

        logger.info(f"✅ Indexed {len(documents)} legislative documents")
        return len(documents)

    except Exception as e:
        logger.error(f"Failed to populate legislation: {e}")
        import traceback
        traceback.print_exc()
        return 0


async def populate_meps(orchestrator: ScraperOrchestrator, limit: int = 100):
    """Fetch and index MEP profiles"""
    logger.info(f"👥 Fetching MEP profiles (limit: {limit})...")

    try:
        # Fetch MEPs
        parliament_scraper = orchestrator.scrapers['european_parliament']
        meps = await parliament_scraper.search_meps(query="", limit=limit)

        if not meps:
            logger.warning("No MEP profiles found")
            return 0

        logger.info(f"✓ Fetched {len(meps)} MEP profiles")

        vector_store = get_vector_store()
        embeddings_service = get_embeddings_service()

        texts = []
        metadatas = []
        ids = []

        for i, mep in enumerate(meps):
            if isinstance(mep, dict):
                # Create searchable text
                text = f"{mep.get('name', '')} {mep.get('country', '')} {mep.get('political_group', '')} {', '.join(mep.get('committees', []))}"
                texts.append(text.strip())

                metadatas.append({
                    'name': mep.get('name', ''),
                    'country': mep.get('country', ''),
                    'political_group': mep.get('political_group', ''),
                    'committees': ','.join(mep.get('committees', [])),
                })

                ids.append(mep.get('id', f'mep_{i}'))

        logger.info("🔄 Generating embeddings...")
        embeddings = await embeddings_service.generate_batch_embeddings(texts)

        logger.info("💾 Storing in ChromaDB...")
        vector_store.add_mep_profiles(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )

        logger.info(f"✅ Indexed {len(meps)} MEP profiles")
        return len(meps)

    except Exception as e:
        logger.error(f"Failed to populate MEPs: {e}")
        import traceback
        traceback.print_exc()
        return 0


async def populate_procedures(orchestrator: ScraperOrchestrator, limit: int = 100):
    """Fetch and index legislative procedures from OEIL"""
    logger.info(f"⚖️  Fetching legislative procedures (limit: {limit})...")

    try:
        oeil_scraper = orchestrator.scrapers['oeil']
        procedures = await oeil_scraper.get_latest_updates(limit=limit)

        if not procedures:
            logger.warning("No procedures found")
            return 0

        logger.info(f"✓ Fetched {len(procedures)} procedures")

        vector_store = get_vector_store()
        embeddings_service = get_embeddings_service()

        texts = []
        metadatas = []
        ids = []

        for i, proc in enumerate(procedures):
            if isinstance(proc, dict):
                text = f"{proc.get('title', '')} {proc.get('reference', '')} {proc.get('stage', '')}"
                texts.append(text.strip())

                metadatas.append({
                    'reference': proc.get('reference', ''),
                    'title': proc.get('title', ''),
                    'stage': proc.get('stage', ''),
                    'type': proc.get('type', ''),
                })

                ids.append(proc.get('reference', f'proc_{i}'))

        logger.info("🔄 Generating embeddings...")
        embeddings = await embeddings_service.generate_batch_embeddings(texts)

        logger.info("💾 Storing in ChromaDB...")
        vector_store.add_procedures(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )

        logger.info(f"✅ Indexed {len(procedures)} procedures")
        return len(procedures)

    except Exception as e:
        logger.error(f"Failed to populate procedures: {e}")
        import traceback
        traceback.print_exc()
        return 0


async def populate_rss_feeds(orchestrator: ScraperOrchestrator, limit: int = 100):
    """Fetch and index RSS feed entries"""
    logger.info(f"📰 Fetching RSS feed entries (limit: {limit})...")

    try:
        # Get RSS feeds from multiple sources
        sources = ['council', 'think_tank', 'european_parliament']
        all_entries = []

        for source in sources:
            try:
                scraper = orchestrator.scrapers[source]
                entries = await scraper.get_latest_updates(limit=limit // len(sources))
                all_entries.extend(entries)
                logger.info(f"  ✓ Fetched {len(entries)} entries from {source}")
            except Exception as e:
                logger.warning(f"  ✗ Failed to fetch from {source}: {e}")

        if not all_entries:
            logger.warning("No RSS entries found")
            return 0

        vector_store = get_vector_store()
        embeddings_service = get_embeddings_service()

        texts = []
        metadatas = []
        ids = []

        for i, entry in enumerate(all_entries):
            if isinstance(entry, dict):
                text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                texts.append(text.strip())

                metadatas.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'source': entry.get('source', 'unknown'),
                })

                ids.append(f"rss_{i}_{entry.get('link', '').split('/')[-1]}")

        logger.info("🔄 Generating embeddings...")
        embeddings = await embeddings_service.generate_batch_embeddings(texts)

        logger.info("💾 Storing in ChromaDB...")
        vector_store.add_rss_entries(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )

        logger.info(f"✅ Indexed {len(all_entries)} RSS entries")
        return len(all_entries)

    except Exception as e:
        logger.error(f"Failed to populate RSS feeds: {e}")
        import traceback
        traceback.print_exc()
        return 0


async def main(source: str = None, limit: int = 100):
    """Main function to populate vector database"""
    start_time = datetime.now()

    logger.info("=" * 80)
    logger.info("🚀 Starting Vector Database Population")
    logger.info("=" * 80)
    logger.info(f"Source filter: {source or 'ALL'}")
    logger.info(f"Item limit per source: {limit}")
    logger.info("")

    # Initialize orchestrator
    logger.info("Initializing scraper orchestrator...")
    orchestrator = ScraperOrchestrator(max_concurrent_scrapers=3)

    total_indexed = 0

    # Populate based on source filter
    if source is None or source == 'eurlex':
        count = await populate_legislation(orchestrator, limit)
        total_indexed += count
        logger.info("")

    if source is None or source == 'parliament':
        count = await populate_meps(orchestrator, limit)
        total_indexed += count
        logger.info("")

    if source is None or source == 'oeil':
        count = await populate_procedures(orchestrator, limit)
        total_indexed += count
        logger.info("")

    if source is None or source == 'rss':
        count = await populate_rss_feeds(orchestrator, limit)
        total_indexed += count
        logger.info("")

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 80)
    logger.info(f"✅ COMPLETED")
    logger.info(f"Total items indexed: {total_indexed}")
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info("=" * 80)

    # Show collection stats
    vector_store = get_vector_store()
    stats = vector_store.get_all_stats()

    logger.info("\n📊 Vector Store Statistics:")
    for collection_name, collection_stats in stats['collections'].items():
        logger.info(f"  {collection_name}: {collection_stats['count']} documents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Populate vector database with EU data')
    parser.add_argument('--source', type=str, help='Specific source to populate (eurlex, parliament, oeil, rss)', default=None)
    parser.add_argument('--limit', type=int, help='Number of items to fetch per source', default=100)

    args = parser.parse_args()

    asyncio.run(main(source=args.source, limit=args.limit))
