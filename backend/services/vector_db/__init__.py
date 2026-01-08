"""
Vector Database Services

ChromaDB + OpenAI Embeddings for semantic search over EU data.
Part of Phase 13: AI Context Injection - Task 13.1
"""

from .vector_store import VectorStore, get_vector_store
from .embeddings_service import EmbeddingsService, get_embeddings_service

__all__ = [
    'VectorStore',
    'get_vector_store',
    'EmbeddingsService',
    'get_embeddings_service'
]
