"""
Semantic Search Service

Vector similarity search over EU documents using ChromaDB.
Part of Phase 13: AI Context Injection - Task 13.3

Features:
- Pure semantic search via embeddings
- Multi-collection search
- Metadata filtering (date ranges, document types, committees)
- Result ranking and scoring
- Aggregated search across all EU data sources
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass

from services.vector_db.vector_store import VectorStore, get_vector_store
from services.embeddings.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result"""
    id: str
    text: str
    score: float  # Similarity score (0-1, higher is better)
    metadata: Dict[str, Any]
    collection: str  # Source collection
    rank: int  # Position in results (1-indexed)


@dataclass
class SearchResponse:
    """Complete search response"""
    query: str
    results: List[SearchResult]
    total_found: int
    search_time_ms: float
    collections_searched: List[str]


class SemanticSearch:
    """
    Semantic search over EU documents using vector embeddings.

    Supports:
    - Single collection search
    - Multi-collection aggregated search
    - Metadata filtering (dates, types, committees)
    - Similarity threshold filtering
    - Result reranking and deduplication
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings_service: EmbeddingService
    ):
        """
        Initialize semantic search.

        Args:
            vector_store: Vector database instance
            embeddings_service: Embeddings generation service (HF-based)
        """
        self.vector_store = vector_store
        self.embeddings_service = embeddings_service

        logger.info(f"Initialized SemanticSearch with {embeddings_service.model_name}")

    async def search_legislation(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Search EUR-Lex legislation.

        Args:
            query: Search query (natural language)
            limit: Maximum results to return
            filters: Metadata filters:
                - date_from: Start date (YYYY-MM-DD)
                - date_to: End date (YYYY-MM-DD)
                - doc_type: Document type (Regulation, Directive, etc.)
                - in_force: Boolean - only in-force legislation
                - subjects: List of subject areas
            min_score: Minimum similarity score (0-1)

        Returns:
            SearchResponse with legislation results

        Example:
            >>> results = await search.search_legislation(
            ...     query="AI regulation requirements",
            ...     limit=5,
            ...     filters={"date_from": "2020-01-01", "in_force": True}
            ... )
        """
        start_time = datetime.now()

        # Generate query embedding
        query_embedding = await self.embeddings_service.generate_embedding(query)

        # Build ChromaDB where clause from filters
        where_clause = self._build_where_clause(filters) if filters else None

        # Search vector store
        results = self.vector_store.search_legislation(
            query_embedding=query_embedding,
            n_results=limit,
            where=where_clause
        )

        # Convert to SearchResult objects
        search_results = self._process_results(
            results,
            collection=VectorStore.COLLECTION_LEGISLATION,
            min_score=min_score
        )

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Legislation search: '{query}' -> {len(search_results)} results in {search_time:.2f}ms"
        )

        return SearchResponse(
            query=query,
            results=search_results,
            total_found=len(search_results),
            search_time_ms=search_time,
            collections_searched=[VectorStore.COLLECTION_LEGISLATION]
        )

    async def search_meps(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Search MEP profiles.

        Args:
            query: Search query (e.g., "climate policy expert", "German MEP")
            limit: Maximum results to return
            filters: Metadata filters:
                - country: Country code (e.g., "DE", "FR")
                - party: Political party
                - group: Political group
                - committees: List of committee codes
                - active: Boolean - only active MEPs
            min_score: Minimum similarity score

        Returns:
            SearchResponse with MEP results

        Example:
            >>> results = await search.search_meps(
            ...     query="environment committee chair",
            ...     filters={"committees": ["ENVI"], "active": True}
            ... )
        """
        start_time = datetime.now()

        query_embedding = await self.embeddings_service.generate_embedding(query)
        where_clause = self._build_where_clause(filters) if filters else None

        results = self.vector_store.search_mep_profiles(
            query_embedding=query_embedding,
            n_results=limit,
            where=where_clause
        )

        search_results = self._process_results(
            results,
            collection=VectorStore.COLLECTION_MEPS,
            min_score=min_score
        )

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"MEP search: '{query}' -> {len(search_results)} results in {search_time:.2f}ms")

        return SearchResponse(
            query=query,
            results=search_results,
            total_found=len(search_results),
            search_time_ms=search_time,
            collections_searched=[VectorStore.COLLECTION_MEPS]
        )

    async def search_procedures(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Search OEIL legislative procedures.

        Args:
            query: Search query
            limit: Maximum results
            filters: Metadata filters:
                - status: Procedure status
                - type: Procedure type
                - date_from: Start date
                - date_to: End date
                - committees: Committee codes
            min_score: Minimum similarity score

        Returns:
            SearchResponse with procedure results
        """
        start_time = datetime.now()

        query_embedding = await self.embeddings_service.generate_embedding(query)
        where_clause = self._build_where_clause(filters) if filters else None

        results = self.vector_store.search_procedures(
            query_embedding=query_embedding,
            n_results=limit,
            where=where_clause
        )

        search_results = self._process_results(
            results,
            collection=VectorStore.COLLECTION_PROCEDURES,
            min_score=min_score
        )

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Procedure search: '{query}' -> {len(search_results)} results in {search_time:.2f}ms"
        )

        return SearchResponse(
            query=query,
            results=search_results,
            total_found=len(search_results),
            search_time_ms=search_time,
            collections_searched=[VectorStore.COLLECTION_PROCEDURES]
        )

    async def search_terminology(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Search IATE terminology.

        Args:
            query: Search query (term or definition)
            limit: Maximum results
            filters: Metadata filters:
                - domain: Subject domain
                - subdomain: Subject subdomain
                - languages: List of language codes
            min_score: Minimum similarity score

        Returns:
            SearchResponse with terminology results
        """
        start_time = datetime.now()

        query_embedding = await self.embeddings_service.generate_embedding(query)
        where_clause = self._build_where_clause(filters) if filters else None

        results = self.vector_store.search_terminology(
            query_embedding=query_embedding,
            n_results=limit,
            where=where_clause
        )

        search_results = self._process_results(
            results,
            collection=VectorStore.COLLECTION_TERMINOLOGY,
            min_score=min_score
        )

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Terminology search: '{query}' -> {len(search_results)} results in {search_time:.2f}ms"
        )

        return SearchResponse(
            query=query,
            results=search_results,
            total_found=len(search_results),
            search_time_ms=search_time,
            collections_searched=[VectorStore.COLLECTION_TERMINOLOGY]
        )

    async def search_rss(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Search RSS feed entries.

        Args:
            query: Search query
            limit: Maximum results
            filters: Metadata filters:
                - source: RSS feed source
                - published_from: Start date
                - published_to: End date
                - categories: List of categories
            min_score: Minimum similarity score

        Returns:
            SearchResponse with RSS results
        """
        start_time = datetime.now()

        query_embedding = await self.embeddings_service.generate_embedding(query)
        where_clause = self._build_where_clause(filters) if filters else None

        results = self.vector_store.search_rss_entries(
            query_embedding=query_embedding,
            n_results=limit,
            where=where_clause
        )

        search_results = self._process_results(
            results,
            collection=VectorStore.COLLECTION_RSS,
            min_score=min_score
        )

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"RSS search: '{query}' -> {len(search_results)} results in {search_time:.2f}ms")

        return SearchResponse(
            query=query,
            results=search_results,
            total_found=len(search_results),
            search_time_ms=search_time,
            collections_searched=[VectorStore.COLLECTION_RSS]
        )

    async def search_all(
        self,
        query: str,
        limit_per_collection: int = 5,
        collections: Optional[List[str]] = None,
        min_score: float = 0.0
    ) -> SearchResponse:
        """
        Search across all collections (aggregated search).

        Args:
            query: Search query
            limit_per_collection: Max results per collection
            collections: List of collection names to search (default: all)
            min_score: Minimum similarity score

        Returns:
            SearchResponse with combined results from all collections

        Example:
            >>> results = await search.search_all(
            ...     query="carbon border adjustment mechanism",
            ...     limit_per_collection=3
            ... )
            # Returns legislation, procedures, MEPs, RSS entries, all mixed
        """
        start_time = datetime.now()

        # Default to all collections
        if collections is None:
            collections = [
                VectorStore.COLLECTION_LEGISLATION,
                VectorStore.COLLECTION_MEPS,
                VectorStore.COLLECTION_PROCEDURES,
                VectorStore.COLLECTION_TERMINOLOGY,
                VectorStore.COLLECTION_RSS
            ]

        # Generate query embedding once.
        # FAIL-SOFT: if the embeddings provider is unavailable (e.g. OpenAI
        # account inactive / billing 429, or no working embeddings key), do NOT
        # crash the whole chat request. Degrade gracefully to keyword + guide-
        # trigger retrieval by returning an empty semantic result set. The chat
        # path (build_context_for_query -> hybrid_search.search) already handles
        # an empty SearchResponse and continues with the non-vector context.
        try:
            query_embedding = await self.embeddings_service.generate_embedding(query)
        except Exception as e:  # noqa: BLE001
            search_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(
                f"Embedding generation failed for query '{query[:80]}' "
                f"({type(e).__name__}: {e}). Degrading to keyword/guide retrieval; "
                f"semantic layer skipped."
            )
            return SearchResponse(
                query=query,
                results=[],
                total_found=0,
                search_time_ms=search_time,
                collections_searched=[],
            )

        # Search each collection
        all_results = []
        for collection_name in collections:
            try:
                if collection_name == VectorStore.COLLECTION_LEGISLATION:
                    results = self.vector_store.search_legislation(
                        query_embedding=query_embedding,
                        n_results=limit_per_collection
                    )
                elif collection_name == VectorStore.COLLECTION_MEPS:
                    results = self.vector_store.search_mep_profiles(
                        query_embedding=query_embedding,
                        n_results=limit_per_collection
                    )
                elif collection_name == VectorStore.COLLECTION_PROCEDURES:
                    results = self.vector_store.search_procedures(
                        query_embedding=query_embedding,
                        n_results=limit_per_collection
                    )
                elif collection_name == VectorStore.COLLECTION_TERMINOLOGY:
                    results = self.vector_store.search_terminology(
                        query_embedding=query_embedding,
                        n_results=limit_per_collection
                    )
                elif collection_name == VectorStore.COLLECTION_RSS:
                    results = self.vector_store.search_rss_entries(
                        query_embedding=query_embedding,
                        n_results=limit_per_collection
                    )
                else:
                    logger.warning(f"Unknown collection: {collection_name}")
                    continue

                # Process results
                processed = self._process_results(
                    results,
                    collection=collection_name,
                    min_score=min_score
                )
                all_results.extend(processed)

            except Exception as e:
                logger.error(f"Error searching {collection_name}: {str(e)}")

        # Sort by score (descending)
        all_results.sort(key=lambda x: x.score, reverse=True)

        # Reassign ranks
        for i, result in enumerate(all_results):
            result.rank = i + 1

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Multi-collection search: '{query}' -> {len(all_results)} results "
            f"across {len(collections)} collections in {search_time:.2f}ms"
        )

        return SearchResponse(
            query=query,
            results=all_results,
            total_found=len(all_results),
            search_time_ms=search_time,
            collections_searched=collections
        )

    def _process_results(
        self,
        raw_results: Dict[str, Any],
        collection: str,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        Convert ChromaDB results to SearchResult objects.

        Args:
            raw_results: Raw results from ChromaDB query
            collection: Collection name
            min_score: Minimum score threshold

        Returns:
            List of SearchResult objects
        """
        if not raw_results or not raw_results.get('ids'):
            return []

        results = []
        ids = raw_results['ids'][0] if raw_results['ids'] else []
        documents = raw_results['documents'][0] if raw_results.get('documents') else []
        metadatas = raw_results['metadatas'][0] if raw_results.get('metadatas') else []
        distances = raw_results['distances'][0] if raw_results.get('distances') else []

        for i, doc_id in enumerate(ids):
            # Convert distance to similarity score (1 - distance for L2, higher is better)
            # ChromaDB returns L2 distance, where 0 = perfect match
            distance = distances[i] if i < len(distances) else 1.0
            score = max(0.0, 1.0 - distance)

            # Filter by minimum score
            if score < min_score:
                continue

            text = documents[i] if i < len(documents) else ""
            metadata = metadatas[i] if i < len(metadatas) else {}

            results.append(SearchResult(
                id=doc_id,
                text=text,
                score=score,
                metadata=metadata,
                collection=collection,
                rank=i + 1
            ))

        return results

    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build ChromaDB where clause from filters.

        Args:
            filters: Filter dict

        Returns:
            ChromaDB where clause

        Examples:
            {"country": "DE"} -> {"country": "DE"}
            {"in_force": True} -> {"in_force": True}
            {"date_from": "2020-01-01"} -> {"date": {"$gte": "2020-01-01"}}
        """
        where = {}

        for key, value in filters.items():
            # Date range filters
            if key == "date_from":
                where["date"] = where.get("date", {})
                where["date"]["$gte"] = value
            elif key == "date_to":
                where["date"] = where.get("date", {})
                where["date"]["$lte"] = value
            elif key == "published_from":
                where["published"] = where.get("published", {})
                where["published"]["$gte"] = value
            elif key == "published_to":
                where["published"] = where.get("published", {})
                where["published"]["$lte"] = value
            # List filters (must contain at least one)
            elif key in ["committees", "categories", "subjects", "languages"]:
                # ChromaDB doesn't support direct array matching, so we'd need to
                # handle this differently (e.g., post-filtering or denormalized data)
                # For now, skip list filters in where clause
                pass
            # Direct equality filters
            else:
                where[key] = value

        return where if where else None

    async def get_similar_documents(
        self,
        document_id: str,
        collection: str,
        limit: int = 5
    ) -> List[SearchResult]:
        """
        Find documents similar to a given document.

        Args:
            document_id: ID of document to find similar to
            collection: Collection containing the document
            limit: Maximum similar documents to return

        Returns:
            List of similar documents (excluding the input document)

        Example:
            >>> similar = await search.get_similar_documents(
            ...     document_id="32016R0679",
            ...     collection="eu_legislation",
            ...     limit=5
            ... )
        """
        try:
            # Get the document's embedding
            coll = self.vector_store.collections[collection]
            doc_data = coll.get(ids=[document_id], include=['embeddings'])

            if not doc_data['ids'] or not doc_data['embeddings']:
                logger.warning(f"Document {document_id} not found in {collection}")
                return []

            embedding = doc_data['embeddings'][0]

            # Search for similar documents
            if collection == VectorStore.COLLECTION_LEGISLATION:
                results = self.vector_store.search_legislation(
                    query_embedding=embedding,
                    n_results=limit + 1  # +1 to account for self-match
                )
            elif collection == VectorStore.COLLECTION_MEPS:
                results = self.vector_store.search_mep_profiles(
                    query_embedding=embedding,
                    n_results=limit + 1
                )
            elif collection == VectorStore.COLLECTION_PROCEDURES:
                results = self.vector_store.search_procedures(
                    query_embedding=embedding,
                    n_results=limit + 1
                )
            elif collection == VectorStore.COLLECTION_TERMINOLOGY:
                results = self.vector_store.search_terminology(
                    query_embedding=embedding,
                    n_results=limit + 1
                )
            elif collection == VectorStore.COLLECTION_RSS:
                results = self.vector_store.search_rss_entries(
                    query_embedding=embedding,
                    n_results=limit + 1
                )
            else:
                logger.error(f"Unknown collection: {collection}")
                return []

            # Process and filter out the original document
            similar = self._process_results(results, collection)
            similar = [r for r in similar if r.id != document_id][:limit]

            logger.info(f"Found {len(similar)} similar documents to {document_id}")
            return similar

        except Exception as e:
            logger.error(f"Failed to find similar documents: {str(e)}")
            return []


# Global singleton
_semantic_search: Optional[SemanticSearch] = None


def get_semantic_search(
    vector_store: Optional[VectorStore] = None,
    embeddings_service: Optional[EmbeddingService] = None
) -> SemanticSearch:
    """
    Get global semantic search instance.

    Args:
        vector_store: Vector store (default: global singleton)
        embeddings_service: Embeddings service (default: global singleton)

    Returns:
        SemanticSearch instance
    """
    global _semantic_search

    if _semantic_search is None:
        _semantic_search = SemanticSearch(
            vector_store=vector_store or get_vector_store(),
            embeddings_service=embeddings_service or get_embedding_service()
        )

    return _semantic_search
