"""
Multi-Provider AI Service with Fallback Chain

Provides resilient AI chat with automatic failover.

Since the 10 June 2026 OSS migration (memory/project_chat_oss_migration.md) the
chat generator runs on a stacked chain of FREE tiers, in this order:

    Cerebras gpt-oss-120b (OPEN, PRIMARY, streams, ~0.8s)
      → Gemini 2.5-flash (free tier, streams, full context)
      → Groq llama-3.3-70b (OPEN; 12K free TPM 413s on Brubru's prompt)
      → NVIDIA llama-3.3-70b (OPEN, full-context backstop, slow)
      → Mistral (free, EU, open-weight; reads only ~30% of injected context)
      → OpenAI (paid last resort)

NO ANTHROPIC. Removed 6 August 2026 by explicit decision: too expensive, and
the open models are what Brubru runs on. The provider class was deleted, not
merely unregistered, so it cannot come back through an env var. Do not re-add
it here or anywhere in the chat path.

The chain order in `self.providers` IS the priority. `prefer_claude` is a
no-op, so `generate()` iterates the chain and returns the first provider that
succeeds; a rate-limit (429) or error on a free tier degrades to the next.

Every SDK client sets max_retries=0. The chain IS the retry: retrying inside
one provider while five alternatives sit idle turned an instant Cerebras 429
into a 122-second wait, which was essentially the whole of Brubru's former
126-second answer latency. See feedback_provider_chain_max_retries_zero.

Each provider implements the same interface, allowing seamless switching.

Cost: €0 at current volume on the open/free tiers. OpenAI is the only paid
link and sits last.
"""

import asyncio
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# Wall-clock ceilings for a SINGLE provider attempt. The chain has seven links;
# no one of them may hold the caller hostage. Two budgets because the callers
# differ: generate() also backs document generation (position papers, tender
# sections, compliance analyses) where a long output is legitimate, whereas a
# chat stream that has produced no token in half a minute is simply stuck.
PROVIDER_TIMEOUT_S = float(os.getenv("PROVIDER_TIMEOUT_S", "90"))
FIRST_TOKEN_TIMEOUT_S = float(os.getenv("FIRST_TOKEN_TIMEOUT_S", "30"))
from datetime import datetime, date
from dataclasses import dataclass, field

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
                 extra_body: Optional[Dict[str, Any]] = None,
                 default_headers: Optional[Dict[str, str]] = None):
        self.api_key = api_key
        self.model = model or self.MODEL
        self.extra_body = extra_body or {}
        # max_retries=0 is the whole point of having a fallback chain.
        #
        # The OpenAI SDK retries 429s internally with exponential backoff. On a
        # rate-limited free tier that turns a refusal into a very long wait:
        # measured 6 Aug 2026, Cerebras took 122.5 SECONDS to surface a 429 that
        # the server returns immediately. Production latency was ~126s and this
        # was essentially all of it -- Gemini then answered the same prompt in
        # 1.7s. Retrying inside one provider while five alternatives sit idle is
        # exactly backwards: fail fast and let the chain do the retrying.
        self.client = (
            AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.BASE_URL,
                max_retries=0,
                timeout=PROVIDER_TIMEOUT_S,
                default_headers=default_headers or None,
            )
            if self.api_key else None
        )

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
        # the answer in a reasoning field, or wrap thinking in <think>...</think>.
        #
        # The field name is NOT consistent across OpenAI-compatible vendors:
        #   - `reasoning_content` — DeepSeek-style (the original case handled here)
        #   - `reasoning`         — Cerebras AND OpenRouter both use this
        # Only `reasoning_content` was checked until 28 July 2026, so a Cerebras
        # or OpenRouter reply with empty content raised "returned empty content"
        # and burned a provider slot. Measured on Kimi K3 via OpenRouter: 4 of 6
        # production-shaped calls returned content=None with the answer in
        # `reasoning`. Check both names.
        if not content:
            for attr in ("reasoning_content", "reasoning"):
                content = (getattr(choice.message, attr, None) or "").strip()
                if content:
                    break
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

        DELIBERATE ASYMMETRY WITH generate(): generate() falls back to the
        `reasoning` / `reasoning_content` fields when `content` is empty, but
        this method must NOT. Streaming those deltas would render the model's
        raw chain-of-thought straight into the user's chat window (measured
        28 July 2026: nemotron-3-super and Kimi K3 both emit "We need to
        answer..." preambles). A model that streams only reasoning therefore
        yields nothing here and correctly falls through to the next provider.
        Do not "fix" this by mirroring the generate() recovery.
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
            # Opportunistic usage capture. Providers that attach a usage block
            # to the final chunk let us record real token counts for a streamed
            # answer; those that do not simply leave it unset. Recorded on the
            # instance and lifted by MultiProviderService into the caller's
            # telemetry dict.
            _usage = getattr(chunk, "usage", None)
            if _usage is not None:
                try:
                    self._last_stream_tokens = (
                        (getattr(_usage, "prompt_tokens", 0) or 0)
                        + (getattr(_usage, "completion_tokens", 0) or 0)
                    )
                except Exception:  # noqa: BLE001
                    pass
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


class OpenRouterProvider(_OpenAICompatibleProvider):
    """OpenRouter — BATCH / EVALUATION provider. NOT part of the chat chain.

    One key fronts ~341 models behind an OpenAI-compatible API, so it costs no
    new dependency. It is constructed only on explicit request (see
    `get_openrouter_provider()`); `MultiProviderService` never appends it to the
    chat fallback list.

    Benchmarked 28 July 2026 against Brubru's real ~17K-token production prompt
    (6-test suite: KB fidelity, anti-hallucination, Catalan, British English,
    strict JSON, amendment drafting):

        nvidia/nemotron-3-super-120b-a12b:free   6/6   9.1s median
        nvidia/nemotron-3-ultra-550b-a55b:free   6/6  22.7s median (best Catalan)
        openai/gpt-oss-20b:free                  5/6  32.1s median
        inclusionai/ling-3.0-flash:free          4/6   4.1s median
        google/gemma-4-31b-it:free               0/6  (100% rate-limited)
        -- for comparison --
        cerebras gpt-oss-120b (chat primary)     6/6   1.5s median

    Why it must stay OUT of Chat:
      - Free tier is 50 requests/DAY (`X-RateLimit-Limit: 50`). A 10-request
        burst at production prompt size returned 0/10. $10 of credits lifts this
        to 1,000/day, still below chat volume.
      - Paid models reject prompts above a credit-derived ceiling: Kimi K3
        returned HTTP 402 "Prompt tokens limit exceeded: 17134 > 13264".
      - Cerebras is both faster (1.5s) and free.

    Where it earns its place: latency-insensitive batch jobs, and grading
    Brubru's own answers with a model family that is NOT already in the chat
    chain (an independent second opinion for /audit-queries and /training).

    Note on reasoning models: OpenRouter returns the answer in `reasoning` with
    `content: null` for some models (measured on Kimi K3, 4 of 6 calls). The
    base class handles both field names since 28 July 2026.
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
    _NAME = "OpenRouter"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(
            api_key=api_key or getattr(settings, 'OPENROUTER_API_KEY', None),
            model=model or getattr(settings, 'OPENROUTER_MODEL', None) or self.MODEL,
            # OpenRouter attributes usage to the referring app via these headers.
            default_headers={
                "HTTP-Referer": getattr(settings, 'OPENROUTER_SITE_URL', '') or '',
                "X-Title": getattr(settings, 'OPENROUTER_APP_NAME', 'Brubru') or 'Brubru',
            },
        )


def get_openrouter_provider(model: Optional[str] = None) -> Optional[OpenRouterProvider]:
    """Explicit opt-in accessor for the batch/eval provider.

    Returns None when no key is configured, so callers can degrade quietly.
    Deliberately a standalone factory rather than a slot in
    `MultiProviderService.providers`: nothing should reach OpenRouter by simply
    falling through the chat chain (50 free requests/day would be exhausted by
    a single burst of user traffic, and paid models bill per call).

    Usage:
        p = get_openrouter_provider()                      # settings default
        p = get_openrouter_provider("moonshotai/kimi-k3")  # explicit override
        if p:
            resp = await p.generate(system_prompt, messages)
    """
    provider = OpenRouterProvider(model=model)
    return provider if provider.is_available else None


class GeminiProvider(AIProvider):
    """Google Gemini provider (fallback 3)"""

    MODEL = "gemini-2.5-flash"  # 11 Jun 2026: gemini-2.0-flash free tier was zeroed by Google (limit:0, persistent, not a daily reset); 2.5-flash has working free quota on the same key. Was 'gemini-1.5-pro' (Apr 2026, dropped from v1beta).

    # A fallback chain is only as fast as the time it wastes on a provider that
    # is not going to answer. This was a hardcoded 120s, so a single
    # unresponsive Gemini cost two minutes before the chain tried the next
    # provider. Now shares the chain-wide ceiling; the stream's first-token
    # bound (FIRST_TOKEN_TIMEOUT_S) catches a stall much earlier than this.
    TIMEOUT_S = PROVIDER_TIMEOUT_S

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

    def _flatten(self, system_prompt: str, messages: List[Dict[str, Any]]) -> str:
        """Flatten the system prompt + messages into Gemini's single-text form."""
        conversation_parts = [f"System Instructions:\n{system_prompt}\n\n---\n\n"]
        for msg in messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            if isinstance(msg.get("content"), list):
                content = "\n".join(
                    block.get("text", "")
                    for block in msg["content"]
                    if block.get("type") == "text"
                )
            else:
                content = msg["content"]
            conversation_parts.append(f"{role_label}: {content}\n\n")
        return "".join(conversation_parts)

    def _gen_cfg(self, max_tokens: int, temperature: float) -> Dict[str, Any]:
        # Call the REST endpoint directly (not the SDK) so we can disable
        # thinking. gemini-2.5-flash is a "thinking" model that burns reasoning
        # tokens before answering (~30-150s on Brubru's large prompt); the
        # installed google-generativeai 0.8.0 SDK has no ThinkingConfig support,
        # so GenerationConfig rejects thinking_budget. The v1beta REST API does
        # accept generationConfig.thinkingConfig.thinkingBudget=0, which turns
        # thinking off entirely for a big latency win with no quality loss on
        # this bounded RAG task. See memory/feedback_mistral_ignores_context.md.
        gen_cfg: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        # thinkingBudget=0 is only valid on 2.5 thinking models (not -lite / 2.0).
        if "2.5-flash" in self.MODEL and "lite" not in self.MODEL:
            gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
        return gen_cfg

    async def generate_stream(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3,
    ):
        """Stream text deltas from Gemini via streamGenerateContent (SSE).

        Added 6 August 2026. Gemini serves about a quarter of Brubru's chat
        traffic but had no generate_stream, so MultiProviderService fell back to
        generate() and yielded the whole answer as ONE chunk. Measured on
        production: time-to-first-token 130.7s against a 130.9s total, i.e. the
        user watched a frozen "Composing response..." for the entire wait and
        then the answer appeared at once. Nothing about the product streamed.
        """
        if not self.is_available:
            raise RuntimeError("Gemini provider not configured")

        # The key goes in a header, never the query string. httpx logs the
        # full request URL at INFO, so `?key=<secret>` put the live Gemini key
        # into every backend log line -- and therefore into Railway's log
        # retention. Google accepts x-goog-api-key as an equivalent.
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.MODEL}:streamGenerateContent?alt=sse"
        )
        payload = {
            "contents": [{"parts": [{"text": self._flatten(system_prompt, messages)}]}],
            "generationConfig": self._gen_cfg(max_tokens, temperature),
        }

        import httpx
        self._last_stream_tokens = 0
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S) as http_client:
            async with http_client.stream(
                "POST", url, json=payload, headers={"x-goog-api-key": self.api_key}
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread())[:200]
                    raise RuntimeError(f"Gemini stream {resp.status_code}: {body!r}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    usage = chunk.get("usageMetadata") or {}
                    if usage.get("totalTokenCount"):
                        self._last_stream_tokens = usage["totalTokenCount"]
                    for cand in chunk.get("candidates") or []:
                        for part in (cand.get("content", {}) or {}).get("parts", []) or []:
                            text = part.get("text")
                            if text:
                                yield text

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> ProviderResponse:
        if not self.is_available:
            raise RuntimeError("Gemini provider not configured")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.MODEL}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": self._flatten(system_prompt, messages)}]}],
            "generationConfig": self._gen_cfg(max_tokens, temperature),
        }

        import httpx
        async with httpx.AsyncClient(timeout=self.TIMEOUT_S) as http_client:
            resp = await http_client.post(
                url, json=payload, headers={"x-goog-api-key": self.api_key}
            )
        if resp.status_code != 200:
            # 429 / quota / other -> raise so the chain falls through to the next provider
            raise RuntimeError(f"Gemini REST {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        candidates = data.get("candidates") or []
        content = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", []) or []
            content = "".join(p.get("text", "") for p in parts)
        tokens = (data.get("usageMetadata") or {}).get("totalTokenCount", 0)

        return ProviderResponse(
            message=content,
            tokens_used=tokens,
            model=self.MODEL,
            provider=self.name
        )



class AnthropicProvider(AIProvider):
    """Anthropic Claude Sonnet — NON-CHAT fallback only.

    Deliberately absent from the chat chain (cost decision, 6 Aug 2026: it was
    serving 12% of chat traffic at ~37,352 tokens an answer). It is reachable
    only through get_extended_provider_service(), which backs the non-chat
    services -- AI summaries, content analysis, proactive notifications -- and
    puts it LAST, after every free tier. Do not add it to get_multi_provider_service().
    """

    # claude-sonnet-4-20250514 was configured here and returns 404 for our key:
    # it is deprecated (retires 15 June 2026) and its documented drop-in
    # replacement is claude-sonnet-5. Because the id was dead, the non-chat
    # services hardwired to Anthropic were failing silently.
    MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = None
        if self.api_key:
            # Imported lazily so the chat path never loads the SDK.
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=self.api_key, max_retries=0,
                                         timeout=PROVIDER_TIMEOUT_S)

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

        # `temperature` is REJECTED on Sonnet 5 and the other current models
        # (400: "`temperature` is deprecated for this model"). The parameter
        # stays in the signature because every provider in the chain shares one
        # interface; it is simply not forwarded. Steer this model by prompt.
        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=max_tokens,
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

        # THREE FAST full-context lanes first (11 June 2026, fix C). Cerebras,
        # Gemini, and Groq all read Brubru's full KB context AND respond fast.
        # Stacking all three near the top triples the concurrent-request ceiling
        # before traffic falls to the slow NVIDIA backstop (measured: the free-
        # tier provider layer, not the backend, is the responsiveness wall — see
        # memory/query_audit.md). Mistral (~30% context, shallow) stays a
        # last-resort; see memory/feedback_mistral_ignores_context.md.

        # 2. Gemini 2.5-flash (free; 1M context, thinking off) — fast full-context
        #    catch when Cerebras 429s.
        gemini = GeminiProvider(gemini_key)
        if gemini.is_available:
            self.providers.append(gemini)
            logger.info("Gemini provider available (full-context fast catch)")

        # 3. Groq llama-3.3-70b (OPEN, fast, full-context) — second fast catch.
        #    Its free TPM 413'd on the old ~19K prompt; the 11 June prompt trim
        #    (-25.7%, ~14K) brought it under the limit (measured: accepts the
        #    trimmed prompt), so it is promoted from last-resort to a fast lane.
        groq = GroqProvider()
        if groq.is_available:
            self.providers.append(groq)
            logger.info(f"Groq provider available (open fast full-context lane, model={groq.model})")

        # 4. NVIDIA NIM (OPEN Llama-3.3-70B, 128K ctx) — full-context backstop,
        #    reached only when the three fast lanes are all saturated. Its free
        #    tier can queue to ~165s, so it sits below them.
        nvidia = NvidiaProvider()
        if nvidia.is_available:
            self.providers.append(nvidia)
            logger.info(f"NVIDIA provider available (open full-context backstop, model={nvidia.model})")

        # 5. Mistral (free, EU) — DEGRADED last-resort: fast but reads only ~30%
        #    of the injected context. Below all full-context readers.
        mistral = MistralProvider(mistral_key)
        if mistral.is_available:
            self.providers.append(mistral)
            logger.info("Mistral provider available (DEGRADED: ~30% context, last-resort)")

        # NO Anthropic. Removed from the chain on 6 August 2026 by explicit
        # decision: it is too expensive, and the open-model chain above is what
        # Brubru runs on. Despite being documented as "opportunistic, only when
        # the free chain is exhausted", it had served 41 of 341 assistant
        # messages over 60 days -- 12% of traffic -- at an average of 37,352
        # tokens each, while the same measurement showed its configured model
        # returning 404. Do not re-add it. The provider class is gone, not just
        # unregistered, so it cannot be revived by setting an env var.

        # 6. OpenAI (paid last resort).
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

                # Same ceiling as generate_stream: no single link in a
                # seven-link chain may hold the caller.
                response = await asyncio.wait_for(
                    provider.generate(
                        system_prompt=system_prompt,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    ),
                    timeout=PROVIDER_TIMEOUT_S,
                )

                elapsed = (datetime.now() - start).total_seconds()
                logger.info(
                    f"{provider.name} succeeded in {elapsed:.2f}s "
                    f"({response.tokens_used} tokens)"
                )

                return response

            # The anthropic.* handlers that used to sit here were removed with
            # the provider. Leaving them would have been worse than untidy:
            # with the import gone, Python evaluating `except anthropic.X`
            # while unwinding ANY provider error raises NameError, so a routine
            # Cerebras 429 would have taken down every request.

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
        telemetry: Optional[Dict[str, Any]] = None,
    ):
        """Stream text from the first provider in the chain that works.

        OpenAI-compatible providers (Groq, Cerebras) stream token deltas
        natively; the others (Gemini, Mistral, Anthropic, OpenAI) fall back to a
        single full-text chunk via generate(). Fallback semantics mirror
        generate(): a connect/429 error BEFORE any output falls through to the
        next provider; a mid-stream error AFTER output has started cannot rewind,
        so it re-raises rather than garble the answer with a second provider.

        telemetry: a CALLER-OWNED dict. On success it receives `provider`,
        `model`, `tokens_used` (0 when the provider sends no usage block) and
        `attempts` (the providers tried and why each failed). It is passed in
        rather than stored on self because production runs a single uvicorn
        worker with many concurrent streams: instance state would let one
        request read another's provider. Until 6 Aug 2026 nothing reported
        this at all, so 22% of assistant rows had model=NULL and the slowest
        defect in the product could not be attributed to a provider.
        """
        errors: List[str] = []
        for provider in self.providers:
            produced = False
            try:
                # Any provider exposing generate_stream streams. Testing for
                # _OpenAICompatibleProvider instead meant Gemini -- about a
                # quarter of traffic -- was forced down the single-blob path
                # even after it grew a working generate_stream.
                if hasattr(provider, "generate_stream"):
                    provider._last_stream_tokens = 0
                    agen = provider.generate_stream(
                        system_prompt, messages, max_tokens, temperature
                    )
                    # Bound the wait for the FIRST delta. Once tokens are
                    # flowing we let the provider finish; before that, a silent
                    # provider must not stall the chain.
                    # StopAsyncIteration must not escape an async generator
                    # (Python turns that into RuntimeError); convert it to the
                    # empty-output signal the loop below already handles.
                    try:
                        first = await asyncio.wait_for(
                            agen.__anext__(), timeout=FIRST_TOKEN_TIMEOUT_S
                        )
                    except StopAsyncIteration:
                        raise RuntimeError("empty output")
                    produced = True
                    yield first
                    async for delta in agen:
                        yield delta
                    _tokens = getattr(provider, "_last_stream_tokens", 0) or 0
                else:
                    resp = await asyncio.wait_for(
                        provider.generate(
                            system_prompt, messages, max_tokens, temperature
                        ),
                        timeout=PROVIDER_TIMEOUT_S,
                    )
                    if resp.message:
                        produced = True
                        yield resp.message
                    _tokens = getattr(resp, "tokens_used", 0) or 0
                if produced:
                    logger.info(f"[stream] {provider.name} produced response")
                    if telemetry is not None:
                        telemetry["provider"] = provider.name
                        # _OpenAICompatibleProvider carries an instance `model`;
                        # Gemini/Mistral/Anthropic/OpenAI carry a class `MODEL`.
                        # Reading only the lowercase one recorded provider=Gemini
                        # with model=NULL on the first production probe.
                        telemetry["model"] = (
                            getattr(provider, "model", "")
                            or getattr(provider, "MODEL", "")
                            or ""
                        )
                        telemetry["tokens_used"] = _tokens
                        telemetry["attempts"] = list(errors)
                    return
                raise RuntimeError("empty output")
            except Exception as e:
                if produced:
                    logger.error(f"[stream] {provider.name} failed mid-stream (cannot fall back): {e}")
                    raise
                errors.append(f"{provider.name}: {type(e).__name__}")
                logger.warning(f"[stream] {provider.name} unavailable, trying next: {e}")
                continue

        if telemetry is not None:
            telemetry["attempts"] = list(errors)
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
    """The CHAT chain: free open models only, no Anthropic.

    Everything a user talks to runs on this. Do not add a paid provider here.
    """
    global _multi_provider_service

    if _multi_provider_service is None:
        _multi_provider_service = MultiProviderService()

    return _multi_provider_service


_extended_provider_service: Optional[MultiProviderService] = None


def get_extended_provider_service() -> MultiProviderService:
    """The NON-CHAT chain: the same free open models, with Anthropic LAST.

    For background work that is not a user conversation -- AI summaries,
    content analysis, proactive notifications. Those services were hardwired
    straight to Anthropic with no fallback at all; this gives them the free
    tiers first and keeps Anthropic as a genuine last resort rather than the
    default.

    Separate instance rather than a flag, so there is no way for a chat request
    to reach the paid provider through shared state.
    """
    global _extended_provider_service

    if _extended_provider_service is None:
        svc = MultiProviderService()
        anthropic_provider = AnthropicProvider()
        if anthropic_provider.is_available:
            svc.providers = list(svc.providers) + [anthropic_provider]
            logger.info(
                "Extended (non-chat) chain: %s",
                ", ".join(p.name for p in svc.providers),
            )
        _extended_provider_service = svc

    return _extended_provider_service
