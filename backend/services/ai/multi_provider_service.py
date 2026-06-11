"""
Multi-Provider AI Service with Fallback Chain

Provides resilient AI chat with automatic failover.

Since the 10 June 2026 OSS migration (memory/project_chat_oss_migration.md) the
chat generator runs on a stacked chain of FREE open-model tiers, in this order:

    Cerebras gpt-oss-120b (OPEN, PRIMARY — 60K TPM fits Brubru's ~19K-token
    prompt) → Mistral (free, EU, open-weight, reliable catch) → Gemini (free,
    daily quota) → Groq (open but 12K free TPM 413s on Brubru's prompt; idle
    unless the prompt is trimmed) → Anthropic Sonnet (OPPORTUNISTIC — only when
    the free chain is exhausted AND funded) → OpenAI (paid last resort)

The chain order in `self.providers` IS the priority. `prefer_claude` is now a
no-op (the legacy `sonnet_primary_provider` slot is left None), so `generate()`
simply iterates the chain and returns the first provider that succeeds; a
rate-limit (429) or error on a free tier degrades to the next provider, never
to paid usage unless the whole free chain is down.

Each provider implements the same interface, allowing seamless switching.

Cost: €0 at current volume — Groq/Cerebras free tiers (open models) + Gemini/
Mistral free tiers. Anthropic/OpenAI are reached only as a last resort.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic
import anthropic
from openai import AsyncOpenAI
import openai

from core.config import settings

# Optional Mistral import
try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

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
        temperature: float = 0.3
    ) -> ProviderResponse:
        """Generate a response from the AI model"""
        pass


class MistralProvider(AIProvider):
    """Mistral AI provider. Cap-day primary + base-chain head for non-knowledge
    queries; fallback 1 when prefer_claude=True. Most cost-effective option."""

    MODEL = "mistral-small-latest"  # $0.20/1M input, $0.60/1M output

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'MISTRAL_API_KEY', None)
        self.client = None

        if self.api_key and MISTRAL_AVAILABLE:
            try:
                self.client = Mistral(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialise Mistral client: {e}")

    @property
    def name(self) -> str:
        return "Mistral"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.client and MISTRAL_AVAILABLE)

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError("Mistral provider not configured")

        # Convert messages to Mistral format
        mistral_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            # Handle multi-modal content (documents)
            if isinstance(msg.get("content"), list):
                # Simplify - extract text content only
                text_parts = []
                for block in msg["content"]:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                mistral_messages.append({
                    "role": msg["role"],
                    "content": "\n".join(text_parts)
                })
            else:
                mistral_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Use async chat completion
        response = await self.client.chat.complete_async(
            model=self.MODEL,
            messages=mistral_messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        content = response.choices[0].message.content if response.choices else ""
        tokens = response.usage.total_tokens if response.usage else 0

        return ProviderResponse(
            message=content,
            tokens_used=tokens,
            model=self.MODEL,
            provider=self.name
        )


class AnthropicSonnetPrimaryProvider(AIProvider):
    """Anthropic Claude Sonnet provider — runtime PRIMARY for knowledge-heavy
    queries (those that matched a Brubru knowledge guide). Routed FIRST when
    `prefer_claude=True` is passed to `MultiProviderService.generate()`.

    Subject to a $10/day soft cap (see `_sonnet_daily_cap_usd` on the service);
    when the cap is reached for the day, traffic falls back to Mistral as the
    cap-day primary.

    Distinct from `AnthropicProvider` (fallback 1 in the base chain) only in
    routing role; both call the same Sonnet model. The legacy class name
    `AnthropicHaikuProvider` was renamed on 5 May 2026 because the actual
    model has been Sonnet since 23 March 2026 — keeping the old "Haiku" name
    was misleading future readers."""

    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None

    @property
    def name(self) -> str:
        # Public identifier flowing into ChatMessage.provider + telemetry.
        # Renamed from "Anthropic-Haiku" on 5 May 2026 to reflect actual model.
        return "Anthropic-Sonnet-Primary"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError("Anthropic Sonnet (primary) provider not configured")

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


class AnthropicProvider(AIProvider):
    """Anthropic Claude Sonnet provider (fallback 1)"""

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
        temperature: float = 0.3
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
    """OpenAI GPT-4 provider (fallback 2)"""

    MODEL = "gpt-4o"  # 20 Apr 2026: was 'gpt-4-turbo-preview' which returns 404 model_not_found

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
        temperature: float = 0.3
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


class _OpenAICompatibleProvider(AIProvider):
    """Base for OpenAI-compatible FREE open-model endpoints (Groq, Cerebras).

    Reuses the OpenAI async SDK with a custom ``base_url`` — no extra dependency.
    Handles reasoning models (gpt-oss, GLM-4.7, Qwen3) that may (a) leave
    ``content`` empty and put the answer in ``reasoning_content`` or (b) wrap
    thinking in ``<think>...</think>`` tags. NO Anthropic — this is the
    sanctioned free open-model generation path (10 June 2026 migration, see
    memory/project_chat_oss_migration.md).
    """

    BASE_URL: str = ""
    MODEL: str = ""
    _NAME: str = ""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 extra_body: Optional[Dict[str, Any]] = None):
        self.api_key = api_key
        self.model = model or self.MODEL
        self.extra_body = extra_body or {}
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.BASE_URL) if self.api_key else None

    @property
    def name(self) -> str:
        return self._NAME

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError(f"{self._NAME} provider not configured")

        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            if isinstance(msg.get("content"), list):
                text_parts = [b.get("text", "") for b in msg["content"] if b.get("type") == "text"]
                oai_messages.append({"role": msg["role"], "content": "\n".join(text_parts)})
            else:
                oai_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs: Dict[str, Any] = dict(
            model=self.model,
            messages=oai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if self.extra_body:
            kwargs["extra_body"] = dict(self.extra_body)

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        # Reasoning-model recovery: some open models leave content empty and put
        # the answer in reasoning_content, or wrap thinking in <think>...</think>.
        if not content:
            content = (getattr(choice.message, "reasoning_content", None) or "").strip()
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
        tokens = response.usage.total_tokens if response.usage else 0

        if not content:
            raise RuntimeError(f"{self._NAME} returned empty content (finish={choice.finish_reason})")

        return ProviderResponse(
            message=content,
            tokens_used=tokens,
            model=self.model,
            provider=self.name
        )

    async def generate_stream(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ):
        """Yield assistant `content` deltas via OpenAI-compatible SSE streaming.

        Reasoning deltas are skipped. The default Groq model
        (llama-3.3-70b-versatile) is non-thinking, so the stream is clean;
        thinking models (qwen3-32b, gpt-oss) interleave reasoning we drop, with
        a cheap inline <think>...</think> suppressor as a safety net.
        """
        if not self.is_available:
            raise RuntimeError(f"{self._NAME} provider not configured")

        oai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            if isinstance(msg.get("content"), list):
                text_parts = [b.get("text", "") for b in msg["content"] if b.get("type") == "text"]
                oai_messages.append({"role": msg["role"], "content": "\n".join(text_parts)})
            else:
                oai_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs: Dict[str, Any] = dict(
            model=self.model,
            messages=oai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        if self.extra_body:
            kwargs["extra_body"] = dict(self.extra_body)

        stream = await self.client.chat.completions.create(**kwargs)
        in_think = False
        async for chunk in stream:
            if not chunk.choices:
                continue
            piece = getattr(chunk.choices[0].delta, "content", None)
            if not piece:
                continue
            # Inline <think> suppression (the default model never emits it).
            if in_think:
                if "</think>" in piece:
                    in_think = False
                    piece = piece.split("</think>", 1)[1]
                else:
                    continue
            if "<think>" in piece:
                before, _, after = piece.partition("<think>")
                if "</think>" in after:
                    piece = before + after.split("</think>", 1)[1]
                else:
                    in_think = True
                    piece = before
            if piece:
                yield piece


class GroqProvider(_OpenAICompatibleProvider):
    """Groq free tier — chat PRIMARY. Open models (default Llama 3.3 70B; swap
    to qwen/qwen3-32b via GROQ_MODEL for stronger Catalan). Fast, clean,
    multilingual. Free TPM is tight (~12K) so very large contexts 429 and fall
    through to Gemini — intended (Gemini is the big-context catcher)."""

    BASE_URL = "https://api.groq.com/openai/v1"
    MODEL = "llama-3.3-70b-versatile"
    _NAME = "Groq"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            api_key=api_key or getattr(settings, 'GROQ_API_KEY', None),
            model=model or getattr(settings, 'GROQ_MODEL', None) or self.MODEL,
        )


class CerebrasProvider(_OpenAICompatibleProvider):
    """Cerebras free tier — deep OPEN fallback (high TPD, ~60K TPM). Default
    gpt-oss-120b (reasoning model -> reasoning_effort=low, only sent for
    gpt-oss; GLM/Qwen variants handled via reasoning_content recovery)."""

    BASE_URL = "https://api.cerebras.ai/v1"
    MODEL = "gpt-oss-120b"
    _NAME = "Cerebras"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        resolved = model or getattr(settings, 'CEREBRAS_MODEL', None) or self.MODEL
        # reasoning_effort is a gpt-oss parameter; don't send it to GLM/Qwen.
        extra = {"reasoning_effort": "low"} if str(resolved).startswith("gpt-oss") else None
        super().__init__(
            api_key=api_key or getattr(settings, 'CEREBRAS_API_KEY', None),
            model=resolved,
            extra_body=extra,
        )


class NvidiaProvider(_OpenAICompatibleProvider):
    """NVIDIA NIM free tier — strong OPEN fallback (Llama-3.3-70B-Instruct,
    128K context so it comfortably fits Brubru's ~19K-token prompt; permanent
    free tier, no card). OpenAI-compatible at integrate.api.nvidia.com. Sits
    right below Cerebras as the second big-context open model — if Cerebras
    queues/rate-limits, NVIDIA catches before any non-open provider."""

    BASE_URL = "https://integrate.api.nvidia.com/v1"
    MODEL = "meta/llama-3.3-70b-instruct"
    _NAME = "NVIDIA"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            api_key=api_key or getattr(settings, 'NVIDIA_API_KEY', None),
            model=model or getattr(settings, 'NVIDIA_MODEL', None) or self.MODEL,
        )


class GeminiProvider(AIProvider):
    """Google Gemini provider (fallback 3)"""

    MODEL = "gemini-2.0-flash"  # 20 Apr 2026: was 'gemini-1.5-pro' which is no longer supported for generateContent on v1beta

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
        temperature: float = 0.3
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

    Runtime routing (see `feedback_claude_is_runtime_primary.md`):
      - prefer_claude=True (knowledge-bearing queries, the default for Brubru):
        Claude Sonnet primary ($10/day cap) → Mistral → Claude Sonnet fallback
        → OpenAI → Gemini
      - prefer_claude=False OR Sonnet daily cap reached:
        Base chain only: Mistral → Claude Sonnet fallback → OpenAI → Gemini

    Base chain ordering (cost-effectiveness):
      - Mistral Small 3: $0.20/$0.60 per 1M tokens
      - Claude Sonnet 4: $3.00/$15.00 per 1M tokens
      - GPT-4 Turbo: $10.00/$30.00 per 1M tokens
      - Gemini 1.5 Pro: $1.25/$5.00 per 1M tokens

    Sonnet-primary slot (consulted FIRST when prefer_claude=True):
      - Same Claude Sonnet model, separate $10/day soft cap.

    Usage:
        service = MultiProviderService()
        response = await service.generate(system_prompt, messages, prefer_claude=True)
    """

    def __init__(
        self,
        mistral_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        gemini_key: Optional[str] = None
    ):
        self.providers: List[AIProvider] = []
        # Sonnet-primary slot: consulted FIRST when prefer_claude=True (most
        # Brubru queries). Distinct from the base-chain Sonnet entry below
        # which is fallback 1. Was named `haiku_provider` until 5 May 2026.
        self.sonnet_primary_provider: Optional[AIProvider] = None

        # Daily spend cap for the Sonnet-primary slot ($10/day soft cap).
        # When exceeded, prefer_claude=True traffic falls back to the base chain
        # (Mistral first). Was named `_haiku_daily_*` until 5 May 2026.
        self._sonnet_daily_cap_usd = 10.00
        self._sonnet_daily_tokens = 0
        self._sonnet_daily_date = date.today()

        # Free open-model chain (10 June 2026 migration, see
        # memory/project_chat_oss_migration.md). List order = fallback priority.
        # NOTE: sonnet_primary_provider is intentionally left None so generate()
        # iterates this chain in order instead of routing to Claude first.

        # 1. Cerebras (OPEN-SOURCE PRIMARY — gpt-oss-120b, ~60K TPM fits Brubru's
        #    large (~19K-token) prompt; 1M tokens/day free; ~0.8s. Groq was the
        #    original primary but its 12K free TPM 413s on every Brubru request
        #    (the prompt alone exceeds it), so it is demoted below.)
        cerebras = CerebrasProvider()
        if cerebras.is_available:
            self.providers.append(cerebras)
            logger.info(f"Cerebras provider available (OPEN primary, model={cerebras.model})")

        # 2. NVIDIA NIM (OPEN — Llama-3.3-70B, 128K ctx fits the ~19K prompt;
        #    permanent free tier). Second big-context open model, catches when
        #    Cerebras queues/rate-limits before any non-open provider is reached.
        nvidia = NvidiaProvider()
        if nvidia.is_available:
            self.providers.append(nvidia)
            logger.info(f"NVIDIA provider available (open, 128K ctx, model={nvidia.model})")

        # 3. Mistral (free tier, EU, open-weight) — reliable catch for Cerebras's
        #    occasional queue_exceeded congestion.
        mistral = MistralProvider(mistral_key)
        if mistral.is_available:
            self.providers.append(mistral)
            logger.info("Mistral provider available (free EU catch)")

        # 4. Gemini (free; 1M context) — when its daily quota is available.
        gemini = GeminiProvider(gemini_key)
        if gemini.is_available:
            self.providers.append(gemini)
            logger.info("Gemini provider available (free, daily quota)")

        # 5. Groq (OPEN, but 12K free TPM < Brubru's prompt -> 413s on real
        #    queries; kept only for the rare small prompt / if the system prompt
        #    is later trimmed).
        groq = GroqProvider()
        if groq.is_available:
            self.providers.append(groq)
            logger.info(f"Groq provider available (open, TPM-limited, model={groq.model})")

        # 6. Anthropic Sonnet (OPPORTUNISTIC — only reached when the free chain
        #    is exhausted; fails fast when unfunded, then the chain continues).
        anthropic = AnthropicProvider(anthropic_key)
        if anthropic.is_available:
            self.providers.append(anthropic)
            logger.info("Anthropic Sonnet provider available (opportunistic, when funded)")

        # 7. OpenAI (paid last resort).
        openai_provider = OpenAIProvider(openai_key)
        if openai_provider.is_available:
            self.providers.append(openai_provider)
            logger.info("OpenAI provider available (paid last resort)")

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
        temperature: float = 0.3,
        prefer_claude: bool = False
    ) -> ProviderResponse:
        """
        Generate a response, falling back through providers on failure.

        Args:
            system_prompt: System prompt for the AI
            messages: Conversation messages
            max_tokens: Maximum response tokens
            temperature: Response temperature
            prefer_claude: If True, route to Claude Sonnet (primary slot) first
                for knowledge-heavy queries; falls through to the base chain on
                Sonnet daily-cap or failure.

        Returns:
            ProviderResponse with message and metadata

        Raises:
            RuntimeError: If all providers fail
        """
        # Route knowledge-heavy queries to Claude Sonnet (primary slot) for
        # better extraction quality on injected guide content.
        if prefer_claude and self.sonnet_primary_provider:
            # Reset daily counter if new day
            today = date.today()
            if today != self._sonnet_daily_date:
                self._sonnet_daily_tokens = 0
                self._sonnet_daily_date = today

            # Estimate cost: Sonnet = $3.00/1M input + $15.00/1M output
            # Average query ~5K tokens. $10/day cap = ~50-100 queries/day
            estimated_daily_cost = (self._sonnet_daily_tokens / 1_000_000) * 15.00
            if estimated_daily_cost >= self._sonnet_daily_cap_usd:
                logger.warning(
                    f"Claude Sonnet daily cap reached (${estimated_daily_cost:.2f}/"
                    f"${self._sonnet_daily_cap_usd:.2f}). Falling back to Mistral."
                )
            else:
                try:
                    logger.info("Routing to Claude Sonnet (knowledge guide matched)")
                    start = datetime.now()
                    response = await self.sonnet_primary_provider.generate(
                        system_prompt=system_prompt,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    elapsed = (datetime.now() - start).total_seconds()
                    self._sonnet_daily_tokens += response.tokens_used
                    logger.info(
                        f"Claude Sonnet succeeded in {elapsed:.2f}s "
                        f"({response.tokens_used} tokens, "
                        f"daily: {self._sonnet_daily_tokens} tokens)"
                    )
                    return response
                except Exception as e:
                    logger.warning(f"Claude Sonnet primary failed, falling back to chain: {e}")

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

    async def generate_stream(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3,
    ):
        """Stream text from the first provider in the chain that works.

        OpenAI-compatible providers (Groq, Cerebras) stream token deltas
        natively; the others (Gemini, Mistral, Anthropic, OpenAI) fall back to a
        single full-text chunk via generate(). Fallback semantics mirror
        generate(): a connect/429 error BEFORE any output falls through to the
        next provider; a mid-stream error AFTER output has started cannot rewind,
        so it re-raises rather than garble the answer with a second provider.
        """
        errors: List[str] = []
        for provider in self.providers:
            produced = False
            try:
                if isinstance(provider, _OpenAICompatibleProvider):
                    async for delta in provider.generate_stream(
                        system_prompt, messages, max_tokens, temperature
                    ):
                        produced = True
                        yield delta
                else:
                    resp = await provider.generate(
                        system_prompt, messages, max_tokens, temperature
                    )
                    if resp.message:
                        produced = True
                        yield resp.message
                if produced:
                    logger.info(f"[stream] {provider.name} produced response")
                    return
                raise RuntimeError("empty output")
            except Exception as e:
                if produced:
                    logger.error(f"[stream] {provider.name} failed mid-stream (cannot fall back): {e}")
                    raise
                errors.append(f"{provider.name}: {type(e).__name__}")
                logger.warning(f"[stream] {provider.name} unavailable, trying next: {e}")
                continue

        raise RuntimeError(f"All AI providers failed (stream): {'; '.join(errors)}")

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
