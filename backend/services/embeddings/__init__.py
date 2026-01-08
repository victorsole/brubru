"""
Embeddings Package

Services for generating and managing vector embeddings for semantic search.
"""

from .embedding_service import EmbeddingService, get_embedding_service
from .vector_search_service import VectorSearchService

__all__ = [
    'EmbeddingService',
    'get_embedding_service',
    'VectorSearchService',
]
