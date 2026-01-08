"""
Hugging Face Embedding Function for ChromaDB

Custom embedding function that uses Hugging Face's BAAI/bge-m3 model
for multilingual semantic search across all 23 EU languages.

This replaces the default OpenAI embeddings with:
- BAAI/bge-m3: Multilingual embeddings (100+ languages including all EU languages)
- Free (no API costs)
- Can run locally or via HF Inference API
- 1024 dimensions
- Better for legal/multilingual content
"""

import logging
from typing import List
from chromadb import Documents, EmbeddingFunction, Embeddings
import numpy as np

from ..embeddings.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


class HuggingFaceEmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB embedding function using Hugging Face models.

    Wraps the HF EmbeddingService to provide embeddings for ChromaDB's vector store.
    Supports BAAI/bge-m3 and other sentence-transformers models.
    """

    def __init__(self, model_name: str = None):
        """
        Initialize HF embedding function.

        Args:
            model_name: HF model to use (defaults to BAAI/bge-m3)
        """
        self.embedding_service = get_embedding_service(model_name=model_name)
        self.model_name = self.embedding_service.model_name

        logger.info(f"Initialized HuggingFaceEmbeddingFunction with {self.model_name}")

    def __call__(self, input: Documents) -> Embeddings:
        """
        Generate embeddings for documents.

        Args:
            input: List of text documents

        Returns:
            List of embedding vectors
        """
        # Generate embeddings using HF service
        embeddings_np = self.embedding_service.encode_texts(input)

        # Convert numpy array to list of lists for ChromaDB
        embeddings = embeddings_np.tolist()

        logger.debug(f"Generated {len(embeddings)} embeddings using {self.model_name}")

        return embeddings


def get_hf_embedding_function(model_name: str = None) -> HuggingFaceEmbeddingFunction:
    """
    Get HF embedding function for ChromaDB.

    Args:
        model_name: Optional model name (defaults to BAAI/bge-m3)

    Returns:
        HuggingFaceEmbeddingFunction instance
    """
    return HuggingFaceEmbeddingFunction(model_name=model_name)
