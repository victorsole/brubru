"""
Hybrid Embedding Function for ChromaDB

Strategically uses both OpenAI and Hugging Face embeddings:
- HF (BAAI/bge-m3): For EU legislative content, multilingual queries
- OpenAI (text-embedding-3-large): For general content, high precision needs

Benefits:
- Best of both worlds
- Cost optimization (use free HF when appropriate)
- Performance optimization (OpenAI for precision, HF for speed)
- Multilingual support via HF
"""

import logging
from typing import List
from chromadb import Documents, EmbeddingFunction, Embeddings

from services.embeddings.embedding_service import EmbeddingService, get_embedding_service
from core.config import settings

logger = logging.getLogger(__name__)


class HybridEmbeddingFunction(EmbeddingFunction):
    """
    Hybrid embedding function using both OpenAI and HF strategically.

    Selection Strategy:
    - EU legislative content → HF (multilingual, legal-optimized)
    - General content → OpenAI (high precision)
    - Configurable via EMBEDDING_PROVIDER setting
    """

    def __init__(self, provider: str = None):
        """
        Initialize hybrid embedding function.

        Args:
            provider: "openai", "huggingface", or "hybrid" (default from settings)
        """
        self.provider = provider or settings.EMBEDDING_PROVIDER

        # Initialize HF service (multilingual, optimized for EU content)
        self.hf_service = get_embedding_service()

        # Note: Currently using HF embeddings only (BAAI/bge-m3)
        # OpenAI embeddings integration can be added later if needed
        # For now, HF provides better multilingual support for EU content
        if self.provider in ["openai", "hybrid"]:
            logger.warning(f"OpenAI embeddings not yet implemented, using HF (BAAI/bge-m3)")
            self.provider = "huggingface"

        logger.info(f"Initialized HybridEmbeddingFunction (mode: {self.provider})")

    def _is_eu_content(self, text: str) -> bool:
        """
        Detect if content is EU legislative/regulatory.

        Args:
            text: Text to analyze

        Returns:
            True if EU content
        """
        import re

        eu_indicators = {
            # Legal
            'regulation', 'directive', 'decision', 'recommendation',
            'celex', 'eur-lex', 'official journal',

            # Institutions
            'european parliament', 'european commission', 'council of the european union',
            'european council', 'court of justice', 'ecj', 'cjeu',

            # Procedures
            'ordinary legislative procedure', 'codecision', 'cod',
            'consultation', 'consent', 'trilogue',

            # Policy
            'common agricultural policy', 'cap', 'cohesion policy',
            'single market', 'schengen', 'eurozone',

            # Treaties
            'treaty', 'tfeu', 'teu', 'lisbon', 'maastricht'
        }

        text_lower = text.lower()

        # Check for EU keywords
        keyword_match = any(indicator in text_lower for indicator in eu_indicators)

        # Check for CELEX pattern (e.g., 32024R1689)
        celex_pattern = r'\b\d{5}[A-Z]\d{4}\b'
        has_celex = bool(re.search(celex_pattern, text))

        # Check for article references (e.g., "Article 5(2)")
        article_pattern = r'\barticle\s+\d+\b'
        has_article = bool(re.search(article_pattern, text_lower))

        return keyword_match or has_celex or has_article

    def __call__(self, input: Documents) -> Embeddings:
        """
        Generate embeddings for documents.

        Args:
            input: List of text documents

        Returns:
            List of embedding vectors
        """
        # Currently using HF exclusively (provider is always "huggingface" after __init__)
        return self._embed_with_hf(input)

    def _embed_with_openai(self, texts: List[str]) -> Embeddings:
        """Embed using OpenAI."""
        import asyncio

        async def embed():
            return await self.openai_service.generate_batch_embeddings(texts)

        embeddings = asyncio.run(embed())
        logger.debug(f"Generated {len(embeddings)} embeddings using OpenAI")
        return embeddings

    def _embed_with_hf(self, texts: List[str]) -> Embeddings:
        """Embed using Hugging Face."""
        embeddings_np = self.hf_service.encode_texts(texts)
        embeddings = embeddings_np.tolist()
        logger.debug(f"Generated {len(embeddings)} embeddings using HF")
        return embeddings

    def _embed_hybrid(self, texts: List[str]) -> Embeddings:
        """
        Hybrid embedding: choose provider based on content.

        Strategy:
        - EU content → HF (multilingual, legal-optimized)
        - General content → OpenAI (high precision)
        """
        # Classify each text
        use_hf = []
        use_openai = []

        for i, text in enumerate(texts):
            if self._is_eu_content(text):
                use_hf.append((i, text))
            else:
                use_openai.append((i, text))

        # Initialize result list
        embeddings = [None] * len(texts)

        # Embed EU content with HF
        if use_hf:
            hf_texts = [text for _, text in use_hf]
            hf_embeddings = self._embed_with_hf(hf_texts)

            for (idx, _), emb in zip(use_hf, hf_embeddings):
                embeddings[idx] = emb

            logger.info(f"Embedded {len(use_hf)} EU texts with HF")

        # Embed general content with OpenAI
        if use_openai and self.openai_service:
            openai_texts = [text for _, text in use_openai]
            openai_embeddings = self._embed_with_openai(openai_texts)

            for (idx, _), emb in zip(use_openai, openai_embeddings):
                embeddings[idx] = emb

            logger.info(f"Embedded {len(use_openai)} general texts with OpenAI")

        # Fallback: if OpenAI not available, use HF for all
        elif use_openai and not self.openai_service:
            logger.warning("OpenAI not available, using HF for all content")
            openai_texts = [text for _, text in use_openai]
            hf_embeddings = self._embed_with_hf(openai_texts)

            for (idx, _), emb in zip(use_openai, hf_embeddings):
                embeddings[idx] = emb

        return embeddings


def get_hybrid_embedding_function(provider: str = None) -> HybridEmbeddingFunction:
    """
    Get hybrid embedding function for ChromaDB.

    Args:
        provider: Optional override ("openai", "huggingface", or "hybrid")

    Returns:
        HybridEmbeddingFunction instance
    """
    return HybridEmbeddingFunction(provider=provider)
