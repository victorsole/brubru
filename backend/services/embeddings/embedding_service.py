"""
Embedding Service

Generates vector embeddings for EU laws and requirements.
Uses OpenAI embeddings API (light) or Hugging Face models (if torch available).
"""

import logging
import numpy as np
import asyncio
from typing import List, Dict, Optional, Union

from core.config import settings
from models.eu_law import EULaw, LawRequirement

logger = logging.getLogger(__name__)

# Try to import torch/sentence_transformers (optional - heavy dependencies)
try:
    from sentence_transformers import SentenceTransformer
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.info("torch/sentence_transformers not available - using OpenAI embeddings")

# OpenAI for API-based embeddings
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class EmbeddingService:
    """
    Service for generating and managing embeddings for semantic search.

    Uses OpenAI embeddings API (light/fast) or sentence-transformers (if torch available).
    """

    def __init__(self, model_name: str = None):
        """
        Initialize embedding service.

        Args:
            model_name: Model to use (HF model or OpenAI model name)
        """
        self.use_openai = not TORCH_AVAILABLE and OPENAI_AVAILABLE
        self.model = None
        self.device = "cpu"

        if self.use_openai:
            self.model_name = "text-embedding-3-small"
            self.embedding_dim = 1536
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("Using OpenAI embeddings API (light mode)")
        else:
            self.model_name = model_name or getattr(settings, 'HF_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            self.embedding_dim = None
            self.device = self._get_device()
            logger.info(f"Using local model: {self.model_name} on {self.device}")

    def _get_device(self) -> str:
        """Determine best available device for embeddings."""
        if not TORCH_AVAILABLE:
            return "cpu"

        if hasattr(settings, 'HF_DEVICE') and settings.HF_DEVICE != "cpu":
            return settings.HF_DEVICE

        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def load_model(self):
        """Load the embedding model (lazy loading)."""
        if self.use_openai:
            return  # OpenAI doesn't need model loading

        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")

            try:
                self.model = SentenceTransformer(
                    self.model_name,
                    device=self.device
                )
                self.embedding_dim = self.model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")

            except Exception as e:
                logger.error(f"Failed to load model: {str(e)}")
                logger.info("Falling back to all-MiniLM-L6-v2")
                self.model_name = "all-MiniLM-L6-v2"
                self.model = SentenceTransformer(self.model_name, device=self.device)
                self.embedding_dim = self.model.get_sentence_embedding_dimension()

    def encode_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array
        """
        if self.use_openai:
            response = self.openai_client.embeddings.create(
                input=text,
                model=self.model_name
            )
            return np.array(response.data[0].embedding)

        if self.model is None:
            self.load_model()

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

    def encode_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for multiple texts (batched for efficiency).

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            Array of embeddings (shape: [len(texts), embedding_dim])
        """
        if self.use_openai:
            # OpenAI API supports batch embedding
            response = self.openai_client.embeddings.create(
                input=texts,
                model=self.model_name
            )
            return np.array([d.embedding for d in response.data])

        if self.model is None:
            self.load_model()

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100
        )

        return embeddings

    def encode_law(self, law: EULaw) -> np.ndarray:
        """
        Generate embedding for an EU law.

        Combines title and summary for comprehensive representation.

        Args:
            law: EULaw object

        Returns:
            Embedding vector
        """
        # Create rich text representation
        text_parts = []

        if law.title:
            text_parts.append(f"Title: {law.title}")

        if law.subject_matter:
            # subject_matter is typically a list
            if isinstance(law.subject_matter, list):
                text_parts.append(f"Subject: {', '.join(law.subject_matter)}")
            else:
                text_parts.append(f"Subject: {law.subject_matter}")

        if law.policy_area:
            text_parts.append(f"Policy Area: {law.policy_area}")

        # Combine into single text
        text = " | ".join(text_parts)

        return self.encode_text(text)

    def encode_requirement(self, requirement: LawRequirement) -> np.ndarray:
        """
        Generate embedding for a legal requirement.

        Args:
            requirement: LawRequirement object

        Returns:
            Embedding vector
        """
        # Create rich text representation
        text_parts = [requirement.requirement_text]

        if requirement.applicable_entity:
            text_parts.append(f"Applicable to: {requirement.applicable_entity}")

        if requirement.criticality:
            text_parts.append(f"Criticality: {requirement.criticality}")

        text = " | ".join(text_parts)

        return self.encode_text(text)

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)

        return float(similarity)

    def search_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Find most similar embeddings to query.

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: Array of candidate embeddings
            top_k: Number of results to return

        Returns:
            List of dicts with 'index' and 'score'
        """
        # Compute similarities
        similarities = []
        for idx, candidate in enumerate(candidate_embeddings):
            score = self.compute_similarity(query_embedding, candidate)
            similarities.append({
                'index': idx,
                'score': score
            })

        # Sort by score (descending)
        similarities.sort(key=lambda x: x['score'], reverse=True)

        # Return top-k
        return similarities[:top_k]

    def get_embedding_dim(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        if self.model is None:
            self.load_model()
        return self.embedding_dim

    # =========================================================================
    # Async Methods (for compatibility with semantic search)
    # =========================================================================

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Async wrapper for encode_text - generates embedding for single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        # Run encoding in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embedding_np = await loop.run_in_executor(None, self.encode_text, text)

        # Convert to list for compatibility with OpenAI-style API
        return embedding_np.tolist()

    async def generate_batch_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        Async wrapper for encode_texts - generates embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            List of embedding vectors
        """
        # Run encoding in thread pool
        loop = asyncio.get_event_loop()
        embeddings_np = await loop.run_in_executor(
            None,
            lambda: self.encode_texts(texts, batch_size)
        )

        # Convert to list of lists
        return embeddings_np.tolist()


# Global embedding service instance (singleton)
_embedding_service = None


def get_embedding_service(model_name: str = None) -> EmbeddingService:
    """
    Get or create embedding service instance.

    Args:
        model_name: Optional model name (uses settings default if not provided)

    Returns:
        EmbeddingService instance
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name=model_name)

    return _embedding_service
