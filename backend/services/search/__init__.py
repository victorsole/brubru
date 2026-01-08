"""
Search Services

Semantic and hybrid search over EU documents.
Part of Phase 13: AI Context Injection - Task 13.3

Components:
- SemanticSearch: Pure vector similarity search
- HybridSearch: Combines semantic + BM25 keyword search with recency/authority boosting
"""

from .semantic_search import (
    SemanticSearch,
    SearchResult,
    SearchResponse,
    get_semantic_search
)
from .hybrid_search import (
    HybridSearch,
    BM25Scorer,
    get_hybrid_search
)

__all__ = [
    'SemanticSearch',
    'SearchResult',
    'SearchResponse',
    'get_semantic_search',
    'HybridSearch',
    'BM25Scorer',
    'get_hybrid_search'
]
