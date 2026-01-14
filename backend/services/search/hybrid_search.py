"""
Hybrid Search Service

Combines semantic (vector) + keyword (BM25) search with recency and authority boosting.
Part of Phase 13: AI Context Injection - Task 13.3

Features:
- BM25 keyword scoring
- Semantic vector similarity
- Weighted combination of both approaches
- Recency boosting (newer documents rank higher)
- Authority boosting (official sources rank higher)
- Reciprocal Rank Fusion (RRF) for result merging
"""

import logging
import math
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import Counter
import re

from .semantic_search import SemanticSearch, SearchResult, SearchResponse, get_semantic_search
from services.vector_db.vector_store import VectorStore

logger = logging.getLogger(__name__)


class BM25Scorer:
    """
    BM25 (Best Matching 25) algorithm for keyword search.

    BM25 is a probabilistic ranking function used for keyword-based search.
    It considers term frequency, document length, and inverse document frequency.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 scorer.

        Args:
            k1: Term frequency saturation parameter (typical: 1.2-2.0)
            b: Length normalization parameter (typical: 0.75)
        """
        self.k1 = k1
        self.b = b

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into terms.

        Args:
            text: Input text

        Returns:
            List of tokens (lowercase, alphanumeric)
        """
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def score(
        self,
        query_terms: List[str],
        document: str,
        avg_doc_length: float,
        doc_count: int,
        term_doc_counts: Dict[str, int]
    ) -> float:
        """
        Calculate BM25 score for a document given a query.

        Args:
            query_terms: Query tokens
            document: Document text
            avg_doc_length: Average document length in corpus
            doc_count: Total number of documents in corpus
            term_doc_counts: Number of documents containing each term

        Returns:
            BM25 score (higher is better)
        """
        doc_terms = self.tokenize(document)
        doc_length = len(doc_terms)
        doc_term_counts = Counter(doc_terms)

        score = 0.0

        for term in query_terms:
            if term not in doc_term_counts:
                continue

            # Term frequency in document
            tf = doc_term_counts[term]

            # Inverse document frequency
            doc_freq = term_doc_counts.get(term, 0)
            if doc_freq == 0:
                continue

            idf = math.log((doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avg_doc_length))

            score += idf * (numerator / denominator)

        return score


class HybridSearch:
    """
    Hybrid search combining semantic and keyword search.

    Strategy:
    1. Semantic search via embeddings (finds conceptually similar documents)
    2. BM25 keyword search (finds exact term matches)
    3. Reciprocal Rank Fusion to combine both result sets
    4. Recency boosting (newer documents get higher scores)
    5. Authority boosting (official sources get higher scores)
    """

    # Authority scores by source type
    AUTHORITY_SCORES = {
        'eur-lex': 1.0,      # Official EUR-Lex legislation
        'parliament': 0.9,    # European Parliament
        'council': 0.9,       # Council of the EU
        'commission': 0.9,    # European Commission
        'court': 1.0,         # Court of Justice
        'oeil': 0.8,          # Legislative procedures
        'think_tank': 0.6,    # Think tanks
        'jrc': 0.7,           # Joint Research Centre
        'rss': 0.5            # RSS feeds (external)
    }

    def __init__(
        self,
        semantic_search: SemanticSearch,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        recency_weight: float = 0.1,
        authority_weight: float = 0.1,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid search.

        Args:
            semantic_search: Semantic search instance
            semantic_weight: Weight for semantic scores (0-1)
            keyword_weight: Weight for keyword scores (0-1)
            recency_weight: Weight for recency boost (0-1)
            authority_weight: Weight for authority boost (0-1)
            rrf_k: RRF parameter (typical: 60)
        """
        self.semantic_search = semantic_search
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.recency_weight = recency_weight
        self.authority_weight = authority_weight
        self.rrf_k = rrf_k

        self.bm25 = BM25Scorer()

        logger.info(
            f"Initialized HybridSearch "
            f"(semantic={semantic_weight}, keyword={keyword_weight}, "
            f"recency={recency_weight}, authority={authority_weight})"
        )

    async def search(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_recency_boost: bool = True,
        use_authority_boost: bool = True
    ) -> SearchResponse:
        """
        Hybrid search across collections.

        Args:
            query: Search query
            collections: Collections to search (default: all)
            limit: Maximum results
            filters: Metadata filters
            use_recency_boost: Apply recency boosting
            use_authority_boost: Apply authority boosting

        Returns:
            SearchResponse with hybrid-ranked results

        Example:
            >>> results = await hybrid_search.search(
            ...     query="artificial intelligence regulation",
            ...     limit=10,
            ...     use_recency_boost=True
            ... )
        """
        start_time = datetime.now()

        # 1. Semantic search
        semantic_results = await self.semantic_search.search_all(
            query=query,
            limit_per_collection=limit * 2,  # Get more results for reranking
            collections=collections
        )

        if not semantic_results.results:
            logger.info(f"No semantic results for: {query}")
            return semantic_results

        # 2. BM25 keyword scoring
        keyword_scores = self._compute_keyword_scores(
            query=query,
            documents=semantic_results.results
        )

        # 3. Combine scores
        combined_results = self._combine_scores(
            semantic_results=semantic_results.results,
            keyword_scores=keyword_scores,
            use_recency_boost=use_recency_boost,
            use_authority_boost=use_authority_boost
        )

        # 4. Sort by combined score and limit
        combined_results.sort(key=lambda x: x.score, reverse=True)
        final_results = combined_results[:limit]

        # Reassign ranks
        for i, result in enumerate(final_results):
            result.rank = i + 1

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Hybrid search: '{query}' -> {len(final_results)} results in {search_time:.2f}ms"
        )

        return SearchResponse(
            query=query,
            results=final_results,
            total_found=len(final_results),
            search_time_ms=search_time,
            collections_searched=semantic_results.collections_searched
        )

    async def search_with_rrf(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> SearchResponse:
        """
        Hybrid search using Reciprocal Rank Fusion (RRF).

        RRF is a simple but effective method for combining ranked lists:
        score = sum(1 / (k + rank_i)) for each ranked list

        Args:
            query: Search query
            collections: Collections to search
            limit: Maximum results
            filters: Metadata filters

        Returns:
            SearchResponse with RRF-ranked results
        """
        start_time = datetime.now()

        # Get semantic results
        semantic_results = await self.semantic_search.search_all(
            query=query,
            limit_per_collection=limit * 2,
            collections=collections
        )

        if not semantic_results.results:
            return semantic_results

        # Compute keyword scores
        keyword_scores = self._compute_keyword_scores(
            query=query,
            documents=semantic_results.results
        )

        # Rank by keyword scores
        keyword_ranked = sorted(
            semantic_results.results,
            key=lambda x: keyword_scores.get(x.id, 0.0),
            reverse=True
        )

        # Apply RRF
        rrf_scores = {}
        for result in semantic_results.results:
            # Semantic rank contribution
            semantic_rank = result.rank
            semantic_contribution = 1 / (self.rrf_k + semantic_rank)

            # Keyword rank contribution
            keyword_rank = next(
                (i + 1 for i, r in enumerate(keyword_ranked) if r.id == result.id),
                len(keyword_ranked)
            )
            keyword_contribution = 1 / (self.rrf_k + keyword_rank)

            # Combined RRF score
            rrf_scores[result.id] = semantic_contribution + keyword_contribution

        # Update result scores with RRF scores
        for result in semantic_results.results:
            result.score = rrf_scores.get(result.id, 0.0)

        # Sort and limit
        semantic_results.results.sort(key=lambda x: x.score, reverse=True)
        final_results = semantic_results.results[:limit]

        # Reassign ranks
        for i, result in enumerate(final_results):
            result.rank = i + 1

        search_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(f"RRF search: '{query}' -> {len(final_results)} results in {search_time:.2f}ms")

        return SearchResponse(
            query=query,
            results=final_results,
            total_found=len(final_results),
            search_time_ms=search_time,
            collections_searched=semantic_results.collections_searched
        )

    def _compute_keyword_scores(
        self,
        query: str,
        documents: List[SearchResult]
    ) -> Dict[str, float]:
        """
        Compute BM25 keyword scores for documents.

        Args:
            query: Search query
            documents: List of documents to score

        Returns:
            Dict mapping document ID to BM25 score
        """
        if not documents:
            return {}

        query_terms = self.bm25.tokenize(query)
        if not query_terms:
            return {}

        # Calculate corpus statistics
        doc_lengths = [len(self.bm25.tokenize(doc.text)) for doc in documents]
        avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0
        doc_count = len(documents)

        # Count documents containing each term
        term_doc_counts = Counter()
        for doc in documents:
            doc_terms = set(self.bm25.tokenize(doc.text))
            for term in query_terms:
                if term in doc_terms:
                    term_doc_counts[term] += 1

        # Score each document
        scores = {}
        for doc in documents:
            score = self.bm25.score(
                query_terms=query_terms,
                document=doc.text,
                avg_doc_length=avg_doc_length,
                doc_count=doc_count,
                term_doc_counts=term_doc_counts
            )
            scores[doc.id] = score

        # Normalize scores to 0-1
        max_score = max(scores.values()) if scores else 1.0
        if max_score > 0:
            scores = {doc_id: score / max_score for doc_id, score in scores.items()}

        return scores

    def _combine_scores(
        self,
        semantic_results: List[SearchResult],
        keyword_scores: Dict[str, float],
        use_recency_boost: bool,
        use_authority_boost: bool
    ) -> List[SearchResult]:
        """
        Combine semantic and keyword scores with optional boosts.

        Args:
            semantic_results: Results from semantic search
            keyword_scores: BM25 keyword scores
            use_recency_boost: Apply recency boost
            use_authority_boost: Apply authority boost

        Returns:
            List of results with updated combined scores
        """
        combined = []

        for result in semantic_results:
            # Base scores
            semantic_score = result.score
            keyword_score = keyword_scores.get(result.id, 0.0)

            # Weighted combination
            base_score = (
                self.semantic_weight * semantic_score +
                self.keyword_weight * keyword_score
            )

            # Recency boost
            recency_boost = 0.0
            if use_recency_boost:
                recency_boost = self._calculate_recency_boost(result)

            # Authority boost
            authority_boost = 0.0
            if use_authority_boost:
                authority_boost = self._calculate_authority_boost(result)

            # Final score
            final_score = base_score + (
                self.recency_weight * recency_boost +
                self.authority_weight * authority_boost
            )

            # Create new result with combined score
            combined_result = SearchResult(
                id=result.id,
                text=result.text,
                score=final_score,
                metadata={
                    **result.metadata,
                    'score_breakdown': {
                        'semantic': semantic_score,
                        'keyword': keyword_score,
                        'recency_boost': recency_boost,
                        'authority_boost': authority_boost,
                        'final': final_score
                    }
                },
                collection=result.collection,
                rank=result.rank
            )
            combined.append(combined_result)

        return combined

    def _calculate_recency_boost(self, result: SearchResult) -> float:
        """
        Calculate recency boost for a document.

        Newer documents get higher boost (exponential decay).

        Args:
            result: Search result

        Returns:
            Recency boost score (0-1)
        """
        try:
            # Try to get date from metadata
            date_str = result.metadata.get('date') or result.metadata.get('published')
            if not date_str:
                return 0.0

            # Parse date
            if isinstance(date_str, str):
                try:
                    doc_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    # Try other formats
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y']:
                        try:
                            doc_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        return 0.0
            else:
                doc_date = date_str

            # Calculate age in days
            age_days = (datetime.now() - doc_date).days

            # Exponential decay: boost = exp(-age / half_life)
            # Half-life = 180 days (6 months)
            half_life = 180
            boost = math.exp(-age_days / half_life)

            return boost

        except Exception as e:
            logger.debug(f"Failed to calculate recency boost: {str(e)}")
            return 0.0

    def _calculate_authority_boost(self, result: SearchResult) -> float:
        """
        Calculate authority boost based on source.

        Official EU sources get higher boost.

        Args:
            result: Search result

        Returns:
            Authority boost score (0-1)
        """
        try:
            # Determine source from collection or metadata
            if result.collection == VectorStore.COLLECTION_LEGISLATION:
                source = 'eur-lex'
            elif result.collection == VectorStore.COLLECTION_MEPS:
                source = 'parliament'
            elif result.collection == VectorStore.COLLECTION_PROCEDURES:
                source = 'oeil'
            elif result.collection == VectorStore.COLLECTION_RSS:
                # Check RSS source
                rss_source = result.metadata.get('source', '').lower()
                if 'parliament' in rss_source:
                    source = 'parliament'
                elif 'council' in rss_source:
                    source = 'council'
                elif 'commission' in rss_source:
                    source = 'commission'
                else:
                    source = 'rss'
            else:
                source = 'unknown'

            boost = self.AUTHORITY_SCORES.get(source, 0.5)
            return boost

        except Exception as e:
            logger.debug(f"Failed to calculate authority boost: {str(e)}")
            return 0.5


# Global singleton
_hybrid_search: Optional[HybridSearch] = None


def get_hybrid_search(
    semantic_search: Optional[SemanticSearch] = None,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
    recency_weight: float = 0.1,
    authority_weight: float = 0.1
) -> HybridSearch:
    """
    Get global hybrid search instance.

    Args:
        semantic_search: Semantic search instance
        semantic_weight: Weight for semantic scores
        keyword_weight: Weight for keyword scores
        recency_weight: Weight for recency boost
        authority_weight: Weight for authority boost

    Returns:
        HybridSearch instance
    """
    global _hybrid_search

    if _hybrid_search is None:
        _hybrid_search = HybridSearch(
            semantic_search=semantic_search or get_semantic_search(),
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            recency_weight=recency_weight,
            authority_weight=authority_weight
        )

    return _hybrid_search
