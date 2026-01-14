"""
Hugging Face Requirement Extractor Service

Uses open-source models from Hugging Face for legal requirement extraction.
Supports multiple models with automatic fallback and cost tracking.
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

from core.config import settings
from models.eu_law import EULaw, LawRequirement

logger = logging.getLogger(__name__)

# Optional imports for local model support (heavy dependencies)
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.info("torch/transformers not available - local models disabled, using API only")


class HuggingFaceRequirementExtractor:
    """
    Extract legal requirements using Hugging Face models.

    Supports:
    - Saul-7B-Instruct: Legal instruction-following model
    - Llama-3.1-8B-Instruct: General-purpose but excellent for structured extraction
    - Legal-BERT: Specialized legal understanding

    Can run locally or via HF Inference API.
    """

    # Available models with their characteristics
    MODELS = {
        'saul-7b': {
            'name': 'Equall/Saul-7B-Instruct-v1',
            'type': 'legal',
            'memory_gb': 14,
            'quality': 'excellent',
            'speed': 'medium'
        },
        'llama-3.1-8b': {
            'name': 'meta-llama/Llama-3.1-8B-Instruct',
            'type': 'general',
            'memory_gb': 16,
            'quality': 'excellent',
            'speed': 'fast'
        },
        'mistral-7b': {
            'name': 'mistralai/Mistral-7B-Instruct-v0.3',
            'type': 'general',
            'memory_gb': 14,
            'quality': 'very-good',
            'speed': 'very-fast'
        },
        'gpt-4': {
            'name': 'openai/gpt-4',
            'type': 'proprietary',
            'memory_gb': 0,
            'quality': 'excellent',
            'speed': 'fast'
        }
    }

    def __init__(self, model_id: str = 'saul-7b', use_local: bool = None):
        """
        Initialize extractor with specified model.

        Args:
            model_id: Key from MODELS dict
            use_local: Override settings.HF_USE_LOCAL
        """
        self.model_id = model_id
        # Force API mode if torch not available
        if not TORCH_AVAILABLE:
            self.use_local = False
        else:
            self.use_local = use_local if use_local is not None else getattr(settings, 'HF_USE_LOCAL', False)

        if model_id not in self.MODELS:
            logger.warning(f"Unknown model {model_id}, falling back to saul-7b")
            self.model_id = 'saul-7b'

        self.model_name = self.MODELS[self.model_id]['name']
        self.tokenizer = None
        self.model = None
        self.pipeline = None

        # Track usage stats
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0

        if self.use_local and TORCH_AVAILABLE:
            self._load_local_model()
        else:
            logger.info(f"Using Hugging Face Inference API for {self.model_name}")

    def _load_local_model(self):
        """Load model locally (requires GPU/significant RAM)"""
        logger.info(f"Loading {self.model_name} locally...")

        try:
            # Determine device
            if torch.cuda.is_available():
                device = "cuda"
                logger.info("Using CUDA GPU")
            elif torch.backends.mps.is_available():
                device = "mps"
                logger.info("Using Apple Silicon GPU")
            else:
                device = "cpu"
                logger.warning("Using CPU (will be slow)")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

            # Load model with 8-bit quantization for memory efficiency
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                load_in_8bit=True if device == "cuda" else False,
                device_map="auto" if device == "cuda" else None,
                torch_dtype=torch.float16 if device in ["cuda", "mps"] else torch.float32,
                trust_remote_code=True
            )

            # Create pipeline
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=device if device != "mps" else -1  # MPS doesn't work with device arg
            )

            logger.info(f"Model loaded successfully on {device}")

        except Exception as e:
            logger.error(f"Failed to load model locally: {str(e)}")
            logger.info("Falling back to Inference API")
            self.use_local = False
            self._initialize_inference_api()

    def _initialize_inference_api(self):
        """Initialize HF Inference API client"""
        if settings.HUGGINGFACE_API_KEY:
            from huggingface_hub import InferenceClient
            self.client = InferenceClient(token=settings.HUGGINGFACE_API_KEY)
            logger.info("Initialized Hugging Face Inference API client")
        else:
            logger.warning("No HUGGINGFACE_API_KEY found, using public API (rate limited)")
            from huggingface_hub import InferenceClient
            self.client = InferenceClient()

    def extract_requirement(
        self,
        sentence: str,
        article_num: str,
        law: EULaw
    ) -> Optional[Dict]:
        """
        Extract structured requirement from obligation sentence.

        Args:
            sentence: Obligation sentence from law text
            article_num: Article number
            law: EULaw object for context

        Returns:
            Dict with structured requirement data
        """
        prompt = self._build_extraction_prompt(sentence, article_num, law)

        try:
            # Generate response
            if self.use_local and self.pipeline:
                response = self._generate_local(prompt)
            else:
                response = self._generate_api(prompt)

            # Parse JSON response
            result = self._parse_json_response(response)

            # Track usage
            self.total_requests += 1
            self.total_tokens += len(prompt.split()) + len(response.split())

            return result

        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            # Return fallback
            return self._fallback_extraction(sentence, article_num)

    def _build_extraction_prompt(
        self,
        sentence: str,
        article_num: str,
        law: EULaw
    ) -> str:
        """Build prompt for requirement extraction"""
        return f"""You are an expert EU law analyst. Extract structured compliance requirements.

Law: {law.title}
CELEX: {law.celex}
Article: {article_num}
Text: "{sentence}"

Analyze this legal requirement and provide:
1. Criticality: critical (mandatory with penalties) / important (mandatory) / recommended (best practice)
2. Applicable entity: Who must comply? (e.g., "VLOPs", "all platforms", "data controllers", "member states")
3. Deadline: Any time limit? (extract exact date or relative time like "within 6 months")
4. Clean text: Rewrite the requirement in clear, concise language (max 200 chars)

Respond ONLY with valid JSON:
{{
  "article": "{article_num}",
  "requirement_text": "clean, concise version of the requirement",
  "criticality": "critical|important|recommended",
  "applicable_entity": "who must comply",
  "deadline_text": "deadline if mentioned, else null",
  "confidence": 0.8
}}"""

    def _generate_local(self, prompt: str) -> str:
        """Generate response using local model"""
        if not self.pipeline:
            raise Exception("Local model not loaded")

        result = self.pipeline(
            prompt,
            max_new_tokens=300,
            temperature=0.1,
            do_sample=True,
            top_p=0.95,
            return_full_text=False
        )

        return result[0]['generated_text']

    def _generate_api(self, prompt: str) -> str:
        """Generate response using HF Inference API"""
        if not hasattr(self, 'client'):
            self._initialize_inference_api()

        response = self.client.text_generation(
            prompt,
            model=self.model_name,
            max_new_tokens=300,
            temperature=0.1,
            return_full_text=False
        )

        return response

    def _parse_json_response(self, response: str) -> Dict:
        """Parse JSON from model response"""
        # Find JSON in response (models sometimes add text before/after)
        start = response.find('{')
        end = response.rfind('}') + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        json_str = response[start:end]
        data = json.loads(json_str)

        # Validate required fields
        required = ['article', 'requirement_text', 'criticality']
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Normalize criticality
        crit = data['criticality'].lower()
        if crit not in ['critical', 'important', 'recommended']:
            data['criticality'] = 'important'  # Default

        return data

    def _fallback_extraction(self, sentence: str, article_num: str) -> Dict:
        """Fallback when parsing fails"""
        logger.warning("Using fallback extraction")
        return {
            'article': article_num,
            'requirement_text': sentence[:500],  # Truncate
            'criticality': 'important',
            'applicable_entity': None,
            'deadline_text': None,
            'confidence': 0.5
        }

    def get_stats(self) -> Dict:
        """Get usage statistics"""
        return {
            'model_id': self.model_id,
            'model_name': self.model_name,
            'use_local': self.use_local,
            'total_requests': self.total_requests,
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'avg_tokens_per_request': self.total_tokens / self.total_requests if self.total_requests > 0 else 0
        }

    def estimate_cluster_cost(self, cluster_size: int, avg_reqs_per_law: int = 5) -> Dict:
        """
        Estimate cost/time for processing a cluster.

        Args:
            cluster_size: Number of laws in cluster
            avg_reqs_per_law: Expected requirements per law

        Returns:
            Dict with estimates
        """
        total_reqs = cluster_size * avg_reqs_per_law

        # Token estimates (prompt + response)
        tokens_per_req = 400  # ~300 prompt + ~100 response
        total_tokens = total_reqs * tokens_per_req

        # Cost estimates (if using Inference API)
        # HF Inference API: ~$0.0002 per 1K tokens (much cheaper than GPT-4)
        cost_per_1k_tokens = 0.0002 if not self.use_local else 0
        estimated_cost = (total_tokens / 1000) * cost_per_1k_tokens

        # Time estimates
        if self.use_local:
            seconds_per_req = 2  # With GPU
        else:
            seconds_per_req = 0.5  # API is fast

        estimated_time_seconds = total_reqs * seconds_per_req

        return {
            'cluster_size': cluster_size,
            'estimated_requirements': total_reqs,
            'estimated_tokens': total_tokens,
            'estimated_cost_usd': round(estimated_cost, 2),
            'estimated_time_seconds': estimated_time_seconds,
            'estimated_time_minutes': round(estimated_time_seconds / 60, 1)
        }


def compare_model_costs():
    """
    Compare costs of different models for reference.

    For processing all 21 clusters (~10,500 laws, ~52,500 requirements):
    """
    total_requirements = 52_500
    tokens_per_req = 400
    total_tokens = total_requirements * tokens_per_req  # 21M tokens

    costs = {
        'GPT-4': {
            'cost_per_1k': 0.03,
            'total_cost': (total_tokens / 1000) * 0.03
        },
        'GPT-3.5-Turbo': {
            'cost_per_1k': 0.001,
            'total_cost': (total_tokens / 1000) * 0.001
        },
        'HF Inference API (Saul/Llama)': {
            'cost_per_1k': 0.0002,
            'total_cost': (total_tokens / 1000) * 0.0002
        },
        'Local HF Model': {
            'cost_per_1k': 0,
            'total_cost': 0
        }
    }

    logger.info("Cost comparison for all 21 clusters:")
    for model, data in costs.items():
        logger.info(f"  {model}: ${data['total_cost']:.2f}")

    return costs
