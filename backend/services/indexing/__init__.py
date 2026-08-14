"""
Data Indexing Services

Indexes EU documents into vector database for semantic search.
Part of Phase 13: AI Context Injection - Task 13.2

Components:
- MetadataExtractor: Extract structured metadata from EU documents (light)
- DocumentIndexer: Index documents into ChromaDB with embeddings (heavy)

--------------------------------------------------------------------------
Imports here are LAZY (PEP 562), the same fix applied to services/ai,
services/search and services/tenders. This file used to eagerly import
document_indexer, which imports services.vector_db.vector_store (chromadb +
onnxruntime). context_builder needs only MetadataExtractor from here, but
importing it ran this file first and dragged in the whole vector stack at boot,
even though production runs the chat keyword-only on an empty store.

DocumentIndexer resolves on first access, so the indexer (used by the manual
scripts/populate_vector_db.py, never at request time) still works, while
`from services.indexing.metadata_extractor import ...` stays light.
"""

from typing import TYPE_CHECKING

# attribute name -> submodule it lives in
_EXPORTS = {
    # Light: pure metadata extraction, no vector deps.
    "MetadataExtractor": "metadata_extractor",
    "get_metadata_extractor": "metadata_extractor",
    # Heavy: pulls services.vector_db -> chromadb + onnxruntime. Lazy.
    "DocumentIndexer": "document_indexer",
    "get_document_indexer": "document_indexer",
    "IndexingResult": "document_indexer",
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
    from .metadata_extractor import MetadataExtractor, get_metadata_extractor
    from .document_indexer import DocumentIndexer, get_document_indexer, IndexingResult
