"""
Data Indexing Services

Indexes EU documents into vector database for semantic search.
Part of Phase 13: AI Context Injection - Task 13.2

Components:
- MetadataExtractor: Extract structured metadata from EU documents
- DocumentIndexer: Index documents into ChromaDB with embeddings
"""

from .metadata_extractor import MetadataExtractor, get_metadata_extractor
from .document_indexer import DocumentIndexer, get_document_indexer, IndexingResult

__all__ = [
    'MetadataExtractor',
    'get_metadata_extractor',
    'DocumentIndexer',
    'get_document_indexer',
    'IndexingResult'
]
