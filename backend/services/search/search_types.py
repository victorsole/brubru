"""Lightweight search result types, shared by semantic_search and hybrid_search.

These two dataclasses used to live in semantic_search.py, which imports
services.vector_db.vector_store (chromadb + onnxruntime + scikit-learn + scipy).
hybrid_search needs the TYPES to build an empty response when the vector store
is absent, but must not pull that stack to do so. Extracting them here, with no
heavy imports, is what lets hybrid_search return an empty SearchResponse in
production without importing chromadb. semantic_search re-exports them, so
`from services.search.semantic_search import SearchResult` still works.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class SearchResult:
    """Single search result."""
    id: str
    text: str
    score: float  # Similarity score (0-1, higher is better)
    metadata: Dict[str, Any]
    collection: str  # Source collection
    rank: int  # Position in results (1-indexed)


@dataclass
class SearchResponse:
    """Complete search response."""
    query: str
    results: List[SearchResult]
    total_found: int
    search_time_ms: float
    collections_searched: List[str]
