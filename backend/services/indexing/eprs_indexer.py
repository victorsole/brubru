"""
EPRS Publications Indexer

Phase 2: Vector Database Population
Indexes EPRS Think Tank publications into ChromaDB for semantic search.

This indexer:
1. Takes enriched EPRSPublication objects from Phase 1
2. Chunks them intelligently (by section or paragraph)
3. Adds them to the eprs_publications collection in ChromaDB
4. Stores rich metadata for filtering and cross-referencing
5. Enables the AI to find and use EPRS content in context

Blueprint for JRC and other EU institutional research publications.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict

from ...schemas.scrapers.scraper_schemas import EPRSPublication, EPRSExtractionResult
from ..vector_db.vector_store import VectorStore, get_vector_store
from .document_chunker import DocumentChunker, DocumentChunk

logger = logging.getLogger(__name__)


class EPRSIndexer:
    """
    Index EPRS publications into vector database.

    Takes enriched EPRSPublication objects and indexes them for semantic search.

    Usage:
        indexer = EPRSIndexer()

        # Index single publication
        result = await indexer.index_publication(publication)

        # Index multiple publications
        results = await indexer.index_publications([pub1, pub2, pub3])

        # Search indexed publications
        results = await indexer.search(
            query="artificial intelligence regulation",
            limit=5,
            filters={"publication_type": "briefing"}
        )
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        chunker: Optional[DocumentChunker] = None,
        use_sections: bool = True
    ):
        """
        Initialize EPRS indexer.

        Args:
            vector_store: VectorStore instance (creates if None)
            chunker: DocumentChunker instance (creates if None)
            use_sections: Chunk by sections if True, else by paragraphs
        """
        self.vector_store = vector_store or get_vector_store()
        self.chunker = chunker or DocumentChunker(
            max_chunk_size=1000,  # ~200 words
            min_chunk_size=100,
            overlap_size=100
        )
        self.use_sections = use_sections

        logger.info(
            f"Initialized EPRSIndexer "
            f"(chunking_strategy={'sections' if use_sections else 'paragraphs'})"
        )

    async def index_publication(
        self,
        publication: EPRSPublication,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index single EPRS publication into vector database.

        Args:
            publication: Enriched EPRSPublication from Phase 1
            force_reindex: If True, reindex even if already exists

        Returns:
            Dict with indexing results:
                - success: bool
                - chunks_indexed: int
                - publication_id: str
                - errors: List[str]

        Example:
            publication = EPRSPublication(...)  # From Phase 1
            result = await indexer.index_publication(publication)

            if result['success']:
                print(f"Indexed {result['chunks_indexed']} chunks")
        """
        logger.info(f"Indexing EPRS publication: {publication.title}")

        try:
            # Check if already indexed
            if not force_reindex:
                existing = await self._check_existing(publication.publication_id)
                if existing:
                    logger.info(f"Publication {publication.publication_id} already indexed")
                    return {
                        'success': True,
                        'chunks_indexed': 0,
                        'publication_id': publication.publication_id,
                        'skipped': True,
                        'errors': []
                    }

            # Validate publication has content
            if not publication.full_text or len(publication.full_text) < 100:
                error_msg = f"Publication {publication.publication_id} has insufficient content"
                logger.warning(error_msg)
                return {
                    'success': False,
                    'chunks_indexed': 0,
                    'publication_id': publication.publication_id,
                    'errors': [error_msg]
                }

            # Step 1: Chunk the document
            chunks = self._chunk_publication(publication)

            if not chunks:
                error_msg = f"No chunks created for {publication.publication_id}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'chunks_indexed': 0,
                    'publication_id': publication.publication_id,
                    'errors': [error_msg]
                }

            logger.debug(f"Created {len(chunks)} chunks for {publication.publication_id}")

            # Step 2: Prepare metadata for all chunks
            base_metadata = self._build_metadata(publication)

            # Step 3: Add chunks to vector database
            chunk_ids = []
            chunk_texts = []
            chunk_metadatas = []

            for chunk in chunks:
                # Combine base metadata with chunk-specific metadata
                chunk_metadata = {
                    **base_metadata,
                    'chunk_id': chunk.chunk_id,
                    'chunk_index': chunk.chunk_index,
                    'chunk_type': chunk.chunk_type,
                    'word_count': chunk.word_count,
                }

                # Add section heading if available
                if chunk.heading:
                    chunk_metadata['section_heading'] = chunk.heading

                if chunk.page_number:
                    chunk_metadata['page_number'] = chunk.page_number

                chunk_ids.append(chunk.chunk_id)
                chunk_texts.append(chunk.text)
                chunk_metadatas.append(chunk_metadata)

            # Add to vector database
            collection = self.vector_store.collections.get(
                VectorStore.COLLECTION_EPRS_PUBLICATIONS
            )

            if not collection:
                raise ValueError("EPRS publications collection not initialized")

            # Add documents in batch
            collection.add(
                ids=chunk_ids,
                documents=chunk_texts,
                metadatas=chunk_metadatas
            )

            logger.info(
                f"Successfully indexed {len(chunks)} chunks for {publication.publication_id}"
            )

            return {
                'success': True,
                'chunks_indexed': len(chunks),
                'publication_id': publication.publication_id,
                'errors': []
            }

        except Exception as e:
            error_msg = f"Failed to index publication {publication.publication_id}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'chunks_indexed': 0,
                'publication_id': publication.publication_id,
                'errors': [error_msg]
            }

    async def index_publications(
        self,
        publications: List[EPRSPublication],
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index multiple EPRS publications.

        Args:
            publications: List of EPRSPublication objects
            force_reindex: If True, reindex existing publications

        Returns:
            Dict with batch results:
                - total: int
                - success: int
                - failed: int
                - skipped: int
                - total_chunks: int
                - errors: List[str]
        """
        logger.info(f"Batch indexing {len(publications)} EPRS publications")

        total_chunks = 0
        success_count = 0
        failed_count = 0
        skipped_count = 0
        all_errors = []

        for pub in publications:
            result = await self.index_publication(pub, force_reindex=force_reindex)

            if result['success']:
                if result.get('skipped'):
                    skipped_count += 1
                else:
                    success_count += 1
                    total_chunks += result['chunks_indexed']
            else:
                failed_count += 1
                all_errors.extend(result['errors'])

        logger.info(
            f"Batch indexing complete: {success_count} success, "
            f"{failed_count} failed, {skipped_count} skipped, "
            f"{total_chunks} total chunks"
        )

        return {
            'total': len(publications),
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'total_chunks': total_chunks,
            'errors': all_errors
        }

    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search EPRS publications by semantic similarity.

        Args:
            query: Search query
            limit: Maximum results
            filters: Metadata filters:
                - publication_type: "briefing", "study", etc.
                - policy_areas: List of policy areas
                - date_from/date_to: Date range
                - committees: List of committee codes

        Returns:
            List of search results with text and metadata

        Example:
            results = await indexer.search(
                query="AI regulation impact assessment",
                limit=3,
                filters={
                    "publication_type": "in_depth_analysis",
                    "policy_areas": "digital"
                }
            )
        """
        collection = self.vector_store.collections.get(
            VectorStore.COLLECTION_EPRS_PUBLICATIONS
        )

        if not collection:
            logger.error("EPRS publications collection not found")
            return []

        # Build where clause for metadata filtering
        where = {}
        if filters:
            for key, value in filters.items():
                if value is not None:
                    where[key] = value

        # Query vector database
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=where if where else None
        )

        # Format results
        formatted_results = []

        if results and results['ids'] and len(results['ids']) > 0:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })

        logger.info(f"Search for '{query}' returned {len(formatted_results)} results")
        return formatted_results

    def _chunk_publication(self, publication: EPRSPublication) -> List[DocumentChunk]:
        """
        Chunk publication based on configured strategy.

        Args:
            publication: EPRSPublication object

        Returns:
            List of DocumentChunk objects
        """
        # Use sections if available and strategy is sections
        if self.use_sections and publication.sections and len(publication.sections) > 0:
            logger.debug(f"Chunking by sections: {len(publication.sections)} sections")
            return self.chunker.chunk_by_sections(
                document_id=publication.publication_id,
                sections=publication.sections,
                metadata={'source': 'eprs', 'chunking_strategy': 'sections'}
            )

        # Fallback to paragraph chunking
        if publication.full_text:
            logger.debug("Chunking by paragraphs")
            return self.chunker.chunk_by_paragraphs(
                document_id=publication.publication_id,
                text=publication.full_text,
                metadata={'source': 'eprs', 'chunking_strategy': 'paragraphs'}
            )

        # Last resort: full document
        logger.warning(f"Using full document chunking for {publication.publication_id}")
        return self.chunker.chunk_full_document(
            document_id=publication.publication_id,
            text=publication.full_text or publication.summary or publication.title,
            metadata={'source': 'eprs', 'chunking_strategy': 'full'}
        )

    def _build_metadata(self, publication: EPRSPublication) -> Dict[str, Any]:
        """
        Build metadata dict for vector database.

        Includes all important fields for filtering and cross-referencing.
        """
        metadata = {
            # Core identifiers
            'publication_id': publication.publication_id,
            'publication_type': publication.publication_type.value,
            'source': 'eprs',

            # URLs
            'html_url': str(publication.html_url) if publication.html_url else None,
            'pdf_url': str(publication.pdf_url) if publication.pdf_url else None,

            # Content metadata
            'title': publication.title,
            'authors': ','.join(publication.authors) if publication.authors else None,
            'publication_date': publication.publication_date.isoformat() if publication.publication_date else None,
            'word_count': publication.word_count,
            'page_count': publication.page_count,

            # Categorization
            'policy_areas': ','.join(publication.policy_areas) if publication.policy_areas else None,
            'committees': ','.join(publication.committees) if publication.committees else None,
            'categories': ','.join(publication.categories) if publication.categories else None,

            # Cross-references (CRITICAL for Phase 3)
            'related_celex_numbers': ','.join(publication.related_celex_numbers) if publication.related_celex_numbers else None,
            'related_procedures': ','.join(publication.related_procedures) if publication.related_procedures else None,
            'related_meps': ','.join(publication.related_meps) if publication.related_meps else None,

            # Quality
            'extraction_quality': publication.extraction_quality,
            'has_full_text': publication.has_full_text,
        }

        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        return metadata

    async def _check_existing(self, publication_id: str) -> bool:
        """
        Check if publication is already indexed.

        Args:
            publication_id: Publication ID to check

        Returns:
            True if exists, False otherwise
        """
        try:
            collection = self.vector_store.collections.get(
                VectorStore.COLLECTION_EPRS_PUBLICATIONS
            )

            if not collection:
                return False

            # Query for any chunk with this publication_id
            results = collection.get(
                where={"publication_id": publication_id},
                limit=1
            )

            return len(results['ids']) > 0 if results and 'ids' in results else False

        except Exception as e:
            logger.error(f"Error checking existing publication: {str(e)}")
            return False

    async def delete_publication(self, publication_id: str) -> bool:
        """
        Delete publication and all its chunks from vector database.

        Args:
            publication_id: Publication ID to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            collection = self.vector_store.collections.get(
                VectorStore.COLLECTION_EPRS_PUBLICATIONS
            )

            if not collection:
                return False

            # Get all chunks for this publication
            results = collection.get(
                where={"publication_id": publication_id}
            )

            if results and 'ids' in results and len(results['ids']) > 0:
                # Delete all chunks
                collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} chunks for {publication_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting publication: {str(e)}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about indexed EPRS publications.

        Returns:
            Dict with stats:
                - total_chunks: int
                - unique_publications: int
                - by_type: Dict[str, int]
                - by_quality: Dict[str, int]
        """
        try:
            collection = self.vector_store.collections.get(
                VectorStore.COLLECTION_EPRS_PUBLICATIONS
            )

            if not collection:
                return {'error': 'Collection not found'}

            # Get all metadata
            results = collection.get()

            if not results or 'metadatas' not in results:
                return {'total_chunks': 0, 'unique_publications': 0}

            metadatas = results['metadatas']

            # Count unique publications
            pub_ids = set(m.get('publication_id') for m in metadatas if 'publication_id' in m)

            # Count by type
            by_type = {}
            for m in metadatas:
                pub_type = m.get('publication_type', 'unknown')
                by_type[pub_type] = by_type.get(pub_type, 0) + 1

            # Count by quality
            by_quality = {}
            for m in metadatas:
                quality = m.get('extraction_quality', 'unknown')
                by_quality[quality] = by_quality.get(quality, 0) + 1

            return {
                'total_chunks': len(metadatas),
                'unique_publications': len(pub_ids),
                'by_type': by_type,
                'by_quality': by_quality
            }

        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return {'error': str(e)}


# Global singleton
_eprs_indexer: Optional[EPRSIndexer] = None


def get_eprs_indexer(
    vector_store: Optional[VectorStore] = None,
    use_sections: bool = True
) -> EPRSIndexer:
    """
    Get global EPRS indexer instance.

    Args:
        vector_store: VectorStore instance (optional)
        use_sections: Chunk by sections if True

    Returns:
        EPRSIndexer instance
    """
    global _eprs_indexer

    if _eprs_indexer is None:
        _eprs_indexer = EPRSIndexer(
            vector_store=vector_store,
            use_sections=use_sections
        )

    return _eprs_indexer
