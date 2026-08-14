"""
Search Services

Semantic and hybrid search over EU documents.
Part of Phase 13: AI Context Injection - Task 13.3

Components:
- SemanticSearch: Pure vector similarity search
- HybridSearch: Combines semantic + BM25 keyword search with recency/authority boosting

--------------------------------------------------------------------------
Imports here are LAZY (PEP 562), the same fix applied to services/ai and
services/tenders. This file used to eagerly import semantic_search, which
imports services.vector_db.vector_store (chromadb + onnxruntime + scikit-learn +
scipy). So importing hybrid_search -- which api/chat.py does at boot via
context_builder -- ran this file first and pulled the whole vector stack, even
though in production the store is empty and hybrid_search runs keyword-only.

The exports resolve on first attribute access. Importing the submodules directly
(`from services.search.hybrid_search import get_hybrid_search`) no longer drags
in semantic_search, so hybrid_search stays light unless a populated store makes
it build the semantic backend on demand.
"""

from typing import TYPE_CHECKING

# attribute name -> submodule it lives in
_EXPORTS = {
    # Light: pure dataclasses, no vector deps.
    "SearchResult": "search_types",
    "SearchResponse": "search_types",
    # Hybrid search (light after the gating change; builds semantic on demand).
    "HybridSearch": "hybrid_search",
    "BM25Scorer": "hybrid_search",
    "get_hybrid_search": "hybrid_search",
    # Semantic search (HEAVY: pulls services.vector_db -> chromadb). Lazy.
    "SemanticSearch": "semantic_search",
    "get_semantic_search": "semantic_search",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve an export on first access (PEP 562)."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value          # cache, so the next access is a plain lookup
    return value


def __dir__():
    return sorted(__all__)


if TYPE_CHECKING:  # pragma: no cover
    from .search_types import SearchResult, SearchResponse
    from .hybrid_search import HybridSearch, BM25Scorer, get_hybrid_search
    from .semantic_search import SemanticSearch, get_semantic_search
