"""
Hugging Face Service

Provides AI capabilities using Hugging Face models:
- Text summarization (for RSS entries)
- Named Entity Recognition (MEPs, legislation, etc.)
- Multilingual embeddings (for semantic search)
- Text classification (policy areas, sentiment)
- Zero-shot classification
- Legal text analysis

Uses the Hugging Face Inference API for scalability.
Can switch to local models for cost savings (requires GPU).
"""

import logging
from typing import List, Dict, Any, Optional, Union
import httpx
from datetime import datetime

from core.config import settings

logger = logging.getLogger(__name__)


class HuggingFaceService:
    """
    Hugging Face AI service for My EU Bubble.

    Features:
    - Text summarization for RSS entries
    - Multilingual embeddings for semantic search
    - Named Entity Recognition (NER)
    - Policy area classification
    - Sentiment analysis

    Example:
        hf = HuggingFaceService()

        # Summarize RSS entry
        summary = await hf.summarize_text(long_article_text)

        # Generate embeddings for search
        embeddings = await hf.get_embeddings(["text1", "text2"])

        # Extract entities
        entities = await hf.extract_entities(article_text)
    """

    # API endpoints
    INFERENCE_API_BASE = "https://router.huggingface.co/hf-inference/models/"

    # Recommended models for EU legislative content
    MODELS = {
        # Summarization - works well with news articles
        "summarization": "facebook/bart-large-cnn",

        # Multilingual embeddings (already configured)
        "embeddings": settings.HF_EMBEDDING_MODEL,  # "BAAI/bge-m3"

        # Named Entity Recognition
        "ner": "dslim/bert-base-NER",

        # Zero-shot classification (for policy areas)
        "classification": "facebook/bart-large-mnli",

        # Legal LLM (already configured)
        "legal_llm": settings.HF_DEFAULT_MODEL,  # "Equall/Saul-7B-Instruct-v1"

        # Sentiment analysis
        "sentiment": "distilbert-base-uncased-finetuned-sst-2-english",
    }

    # EU policy areas for classification
    EU_POLICY_AREAS = [
        "Agriculture and Rural Development",
        "Budget",
        "Climate Action",
        "Competition",
        "Consumer Affairs",
        "Culture and Media",
        "Customs",
        "Development and Cooperation",
        "Digital Economy and Society",
        "Economic and Monetary Affairs",
        "Education and Training",
        "Employment and Social Affairs",
        "Energy",
        "Enlargement",
        "Environment",
        "External Relations",
        "Financial Stability and Services",
        "Fisheries",
        "Food Safety",
        "Foreign and Security Policy",
        "Fraud Prevention",
        "Health",
        "Home Affairs",
        "Humanitarian Aid",
        "Internal Market",
        "Justice and Fundamental Rights",
        "Maritime Affairs",
        "Migration",
        "Public Health",
        "Regional Policy",
        "Research and Innovation",
        "Taxation",
        "Trade",
        "Transport"
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_local: bool = False
    ):
        """
        Initialize Hugging Face service.

        Args:
            api_key: HF API key (uses settings.HUGGINGFACE_API_KEY if None)
            use_local: Use local models instead of API (requires GPU)
        """
        self.api_key = api_key or settings.HUGGINGFACE_API_KEY
        self.use_local = use_local or settings.HF_USE_LOCAL

        if not self.api_key and not self.use_local:
            logger.warning("No Hugging Face API key found. Service will be limited.")

        # HTTP client for API calls
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0
        )

        logger.info(f"Initialized Hugging Face service (use_local: {self.use_local})")

    async def summarize_text(
        self,
        text: str,
        max_length: int = 130,
        min_length: int = 30,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Summarize text using Hugging Face summarization model.

        Perfect for RSS entries and long articles.

        Args:
            text: Text to summarize (truncated if too long)
            max_length: Maximum summary length
            min_length: Minimum summary length
            model: Model to use (defaults to MODELS["summarization"])

        Returns:
            Summary text or None if failed

        Example:
            >>> summary = await hf.summarize_text(long_article)
            >>> print(summary)
            "The European Parliament adopted new AI regulations..."
        """
        if not text or len(text) < 100:
            return text  # Too short to summarize

        model_id = model or self.MODELS["summarization"]

        # Truncate if too long (BART max is ~1024 tokens ≈ 4000 chars)
        max_input_chars = 4000
        truncated_text = text[:max_input_chars]

        try:
            logger.info(f"Summarizing text ({len(text)} chars) with {model_id}")

            response = await self.client.post(
                f"{self.INFERENCE_API_BASE}{model_id}",
                json={
                    "inputs": truncated_text,
                    "parameters": {
                        "max_length": max_length,
                        "min_length": min_length,
                        "do_sample": False
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                summary = result[0]["summary_text"] if isinstance(result, list) else result.get("summary_text", "")
                logger.info(f"Successfully generated summary ({len(summary)} chars)")
                return summary
            else:
                logger.error(f"Summarization failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Summarization error: {str(e)}")
            return None

    async def get_embeddings(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None
    ) -> Optional[List[List[float]]]:
        """
        Generate embeddings for semantic search.

        Uses multilingual model (BAAI/bge-m3) that works with all 24 EU languages.

        Args:
            texts: Text or list of texts to embed
            model: Model to use (defaults to MODELS["embeddings"])

        Returns:
            List of embedding vectors or None if failed

        Example:
            >>> embeddings = await hf.get_embeddings([
            ...     "AI Act regulation",
            ...     "Digital Services Act"
            ... ])
            >>> print(len(embeddings[0]))  # Vector dimension
            1024
        """
        if isinstance(texts, str):
            texts = [texts]

        model_id = model or self.MODELS["embeddings"]

        try:
            logger.info(f"Generating embeddings for {len(texts)} texts with {model_id}")

            response = await self.client.post(
                f"{self.INFERENCE_API_BASE}{model_id}",
                json={
                    "inputs": texts,
                    "options": {"wait_for_model": True}
                }
            )

            if response.status_code == 200:
                embeddings = response.json()
                logger.info(f"Successfully generated {len(embeddings)} embeddings")
                return embeddings
            else:
                logger.error(f"Embedding generation failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            return None

    async def extract_entities(
        self,
        text: str,
        model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract named entities (people, organizations, locations).

        Useful for identifying MEPs, committees, legislation in text.

        Args:
            text: Text to analyze
            model: NER model to use

        Returns:
            List of entities with type and score:
            [
                {"entity": "PER", "word": "Ursula von der Leyen", "score": 0.99},
                {"entity": "ORG", "word": "European Commission", "score": 0.98}
            ]

        Example:
            >>> entities = await hf.extract_entities(article_text)
            >>> meps = [e for e in entities if e["entity"] == "PER"]
        """
        model_id = model or self.MODELS["ner"]

        try:
            logger.info(f"Extracting entities from text ({len(text)} chars)")

            response = await self.client.post(
                f"{self.INFERENCE_API_BASE}{model_id}",
                json={"inputs": text}
            )

            if response.status_code == 200:
                entities = response.json()
                logger.info(f"Extracted {len(entities)} entities")
                return entities
            else:
                logger.error(f"NER failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Entity extraction error: {str(e)}")
            return []

    async def classify_policy_area(
        self,
        text: str,
        candidate_labels: Optional[List[str]] = None,
        model: Optional[str] = None,
        multi_label: bool = True
    ) -> List[Dict[str, float]]:
        """
        Classify text into EU policy areas using zero-shot classification.

        Args:
            text: Text to classify (e.g., RSS entry, legislation summary)
            candidate_labels: Policy areas to consider (defaults to EU_POLICY_AREAS)
            model: Classification model
            multi_label: Allow multiple policy areas

        Returns:
            List of policy areas with confidence scores:
            [
                {"label": "Digital Economy and Society", "score": 0.89},
                {"label": "Consumer Affairs", "score": 0.67}
            ]

        Example:
            >>> classifications = await hf.classify_policy_area(
            ...     "New regulation on AI systems and data protection"
            ... )
            >>> top_area = classifications[0]["label"]
        """
        model_id = model or self.MODELS["classification"]
        labels = candidate_labels or self.EU_POLICY_AREAS[:10]  # Use top 10 for speed

        try:
            logger.info(f"Classifying text into {len(labels)} policy areas")

            response = await self.client.post(
                f"{self.INFERENCE_API_BASE}{model_id}",
                json={
                    "inputs": text,
                    "parameters": {
                        "candidate_labels": labels,
                        "multi_label": multi_label
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                # Format output
                classifications = [
                    {"label": label, "score": score}
                    for label, score in zip(result["labels"], result["scores"])
                ]
                logger.info(f"Top policy area: {classifications[0]['label']} ({classifications[0]['score']:.2f})")
                return classifications
            else:
                logger.error(f"Classification failed: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Classification error: {str(e)}")
            return []

    async def analyze_sentiment(
        self,
        text: str,
        model: Optional[str] = None
    ) -> Optional[Dict[str, float]]:
        """
        Analyze sentiment of text (positive/negative).

        Useful for analyzing public opinion in EU news.

        Args:
            text: Text to analyze
            model: Sentiment model

        Returns:
            Sentiment dict:
            {
                "label": "POSITIVE" or "NEGATIVE",
                "score": 0.95
            }

        Example:
            >>> sentiment = await hf.analyze_sentiment(news_article)
            >>> if sentiment["label"] == "NEGATIVE":
            ...     print("Controversial topic")
        """
        model_id = model or self.MODELS["sentiment"]

        try:
            logger.info("Analyzing sentiment")

            response = await self.client.post(
                f"{self.INFERENCE_API_BASE}{model_id}",
                json={"inputs": text[:512]}  # Truncate for BERT
            )

            if response.status_code == 200:
                result = response.json()
                sentiment = result[0][0] if isinstance(result, list) else result
                logger.info(f"Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")
                return sentiment
            else:
                logger.error(f"Sentiment analysis failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return None

    async def query_legal_llm(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Query legal LLM (Saul-7B-Instruct) for legal text analysis.

        Specialized for legal questions about EU legislation.

        Args:
            prompt: Question or instruction
            max_tokens: Maximum response length
            temperature: Sampling temperature (0-1)
            model: Legal LLM model

        Returns:
            Generated text response

        Example:
            >>> response = await hf.query_legal_llm(
            ...     "Summarize Article 5 of the GDPR"
            ... )
        """
        model_id = model or self.MODELS["legal_llm"]

        try:
            logger.info(f"Querying legal LLM: {model_id}")

            response = await self.client.post(
                f"{self.INFERENCE_API_BASE}{model_id}",
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": max_tokens,
                        "temperature": temperature,
                        "return_full_text": False
                    },
                    "options": {"wait_for_model": True}  # Wait for model to load (cold start)
                },
                timeout=180.0  # 3 min timeout for large model cold start
            )

            if response.status_code == 200:
                result = response.json()
                generated_text = result[0]["generated_text"] if isinstance(result, list) else result.get("generated_text", "")
                logger.info(f"Legal LLM response: {len(generated_text)} chars")
                return generated_text
            else:
                logger.error(f"Legal LLM query failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Legal LLM error: {str(e)}")
            return None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client"""
        await self.client.aclose()


# Global singleton
_huggingface_service: Optional[HuggingFaceService] = None


def get_huggingface_service() -> HuggingFaceService:
    """
    Get global Hugging Face service instance.

    Returns:
        HuggingFaceService instance

    Example:
        >>> hf = get_huggingface_service()
        >>> summary = await hf.summarize_text(article)
    """
    global _huggingface_service

    if _huggingface_service is None:
        _huggingface_service = HuggingFaceService()

    return _huggingface_service
