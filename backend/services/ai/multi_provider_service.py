"""
Multi-Provider AI Service with Fallback Chain

Provides resilient AI chat with automatic failover:
  Anthropic Claude (primary) → OpenAI GPT-4 (fallback) → Google Gemini (second fallback)

Each provider implements the same interface, allowing seamless switching.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from anthropic import AsyncAnthropic
import anthropic
from openai import AsyncOpenAI
import openai

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProviderResponse:
    """Standardised response from any AI provider"""
    message: str
    tokens_used: int
    model: str
    provider: str


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging"""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available"""
        pass

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """Generate a response from the AI model"""
        pass


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider (primary)"""

    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None

    @property
    def name(self) -> str:
        return "Anthropic"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError("Anthropic provider not configured")

        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages
        )

        content = response.content[0].text if response.content else ""
        tokens = response.usage.input_tokens + response.usage.output_tokens

        return ProviderResponse(
            message=content,
            tokens_used=tokens,
            model=self.MODEL,
            provider=self.name
        )


class OpenAIProvider(AIProvider):
    """OpenAI GPT-4 provider (first fallback)"""

    MODEL = "gpt-4-turbo-preview"

    def __init__(self, api_key: Optional[str] = None, org_id: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.org_id = org_id or settings.OPENAI_ORG_ID
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            organization=self.org_id
        ) if self.api_key else None

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError("OpenAI provider not configured")

        # Convert messages to OpenAI format (add system message)
        openai_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            # Handle multi-modal content (documents)
            if isinstance(msg.get("content"), list):
                # Simplify for OpenAI - extract text content only
                text_parts = []
                for block in msg["content"]:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                openai_messages.append({
                    "role": msg["role"],
                    "content": "\n".join(text_parts)
                })
            else:
                openai_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        response = await self.client.chat.completions.create(
            model=self.MODEL,
            messages=openai_messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        return ProviderResponse(
            message=content,
            tokens_used=tokens,
            model=self.MODEL,
            provider=self.name
        )


class GeminiProvider(AIProvider):
    """Google Gemini provider (second fallback)"""

    MODEL = "gemini-1.5-pro"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_GEMINI_API_KEY
        self.client = None

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(self.MODEL)
            except ImportError:
                logger.warning("google-generativeai package not installed")
            except Exception as e:
                logger.warning(f"Failed to initialise Gemini: {e}")

    @property
    def name(self) -> str:
        return "Gemini"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError("Gemini provider not configured")

        import google.generativeai as genai

        # Build conversation for Gemini
        # Gemini uses a different format - combine system prompt with first message
        conversation_parts = []

        # Add system instruction as context
        conversation_parts.append(f"System Instructions:\n{system_prompt}\n\n---\n\n")

        # Add message history
        for msg in messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"

            if isinstance(msg.get("content"), list):
                # Handle multi-modal - extract text
                text_parts = []
                for block in msg["content"]:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                content = "\n".join(text_parts)
            else:
                content = msg["content"]

            conversation_parts.append(f"{role_label}: {content}\n\n")

        full_prompt = "".join(conversation_parts)

        # Configure generation
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature
        )

        # Generate response (Gemini SDK is sync, wrap for async context)
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
        )

        content = response.text if response.text else ""

        # Gemini doesn't always provide token counts
        tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tokens = getattr(response.usage_metadata, 'total_token_count', 0)

        return ProviderResponse(
            message=content,
            tokens_used=tokens,
            model=self.MODEL,
            provider=self.name
        )


class MultiProviderService:
    """
    Orchestrates AI providers with automatic fallback.

    Order: Anthropic → OpenAI → Gemini

    Usage:
        service = MultiProviderService()
        response = await service.generate(system_prompt, messages)
    """

    def __init__(
        self,
        anthropic_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        gemini_key: Optional[str] = None
    ):
        self.providers: List[AIProvider] = []

        # Initialise providers in priority order
        anthropic = AnthropicProvider(anthropic_key)
        if anthropic.is_available:
            self.providers.append(anthropic)
            logger.info("Anthropic provider available (primary)")

        openai_provider = OpenAIProvider(openai_key)
        if openai_provider.is_available:
            self.providers.append(openai_provider)
            logger.info("OpenAI provider available (fallback 1)")

        gemini = GeminiProvider(gemini_key)
        if gemini.is_available:
            self.providers.append(gemini)
            logger.info("Gemini provider available (fallback 2)")

        if not self.providers:
            raise RuntimeError("No AI providers configured. Set at least one API key.")

        logger.info(f"Multi-provider service initialised with {len(self.providers)} providers")

    @property
    def available_providers(self) -> List[str]:
        """List of available provider names"""
        return [p.name for p in self.providers]

    @property
    def primary_provider(self) -> str:
        """Name of the primary (first) provider"""
        return self.providers[0].name if self.providers else "None"

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """
        Generate a response, falling back through providers on failure.

        Args:
            system_prompt: System prompt for the AI
            messages: Conversation messages
            max_tokens: Maximum response tokens
            temperature: Response temperature

        Returns:
            ProviderResponse with message and metadata

        Raises:
            RuntimeError: If all providers fail
        """
        errors = []

        for provider in self.providers:
            try:
                logger.info(f"Attempting generation with {provider.name}")
                start = datetime.now()

                response = await provider.generate(
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                elapsed = (datetime.now() - start).total_seconds()
                logger.info(
                    f"{provider.name} succeeded in {elapsed:.2f}s "
                    f"({response.tokens_used} tokens)"
                )

                return response

            except anthropic.APIConnectionError as e:
                logger.warning(f"{provider.name} connection error: {e}")
                errors.append(f"{provider.name}: Connection error")

            except anthropic.RateLimitError as e:
                logger.warning(f"{provider.name} rate limited: {e}")
                errors.append(f"{provider.name}: Rate limited")

            except anthropic.APIStatusError as e:
                logger.warning(f"{provider.name} API error {e.status_code}: {e.message}")
                errors.append(f"{provider.name}: API error {e.status_code}")

            except openai.APIConnectionError as e:
                logger.warning(f"{provider.name} connection error: {e}")
                errors.append(f"{provider.name}: Connection error")

            except openai.RateLimitError as e:
                logger.warning(f"{provider.name} rate limited: {e}")
                errors.append(f"{provider.name}: Rate limited")

            except openai.APIStatusError as e:
                logger.warning(f"{provider.name} API error {e.status_code}: {e.message}")
                errors.append(f"{provider.name}: API error {e.status_code}")

            except Exception as e:
                logger.warning(f"{provider.name} unexpected error: {type(e).__name__}: {e}")
                errors.append(f"{provider.name}: {type(e).__name__}")

        # All providers failed
        error_summary = "; ".join(errors)
        logger.error(f"All AI providers failed: {error_summary}")
        raise RuntimeError(f"All AI providers failed: {error_summary}")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        return {
            "providers": [
                {
                    "name": p.name,
                    "available": p.is_available,
                    "priority": i + 1
                }
                for i, p in enumerate(self.providers)
            ],
            "primary": self.primary_provider,
            "total_available": len(self.providers)
        }


# Global singleton
_multi_provider_service: Optional[MultiProviderService] = None


def get_multi_provider_service() -> MultiProviderService:
    """Get global multi-provider service instance"""
    global _multi_provider_service

    if _multi_provider_service is None:
        _multi_provider_service = MultiProviderService()

    return _multi_provider_service
