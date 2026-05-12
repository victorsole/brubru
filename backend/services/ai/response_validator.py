"""
Response validator -- second-LLM anti-hallucination pass.

Workstream 1 of the Chat AI architecture evolution
(memory/project_chat_ai_architecture_evolution.md).

After the generator produces a response, the validator receives:
  - the user query
  - the retrieved Brubru context blocks (the same context_str the generator saw)
  - the proposed response

and asks a strict question: "Does every factual claim in the response appear
in the context? Are list answers complete? Is the response refusing data that
is actually present?"

Validator model: Claude Haiku 4.5 (cheap, fast, sufficient for the bounded
fact-checking task). Configurable via VALIDATOR_MODEL env var.

Failure mode: fail-soft. If the validator errors (network, JSON parse, timeout)
the result returns passed=True with an error field set, and the caller logs
but ships the original response unchanged.

Created: 12 May 2026.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from anthropic import AsyncAnthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover -- defensive
    AsyncAnthropic = None  # type: ignore
    _ANTHROPIC_AVAILABLE = False

from services.ai.validator_settings import (
    VALIDATOR_CONTEXT_CHAR_CAP,
    VALIDATOR_MODEL,
    VALIDATOR_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass
class Violation:
    """One violation observation from the validator."""

    type: str
    evidence: str
    explanation: str

    def to_dict(self) -> dict:
        return {"type": self.type, "evidence": self.evidence, "explanation": self.explanation}


@dataclass
class ValidationResult:
    """Outcome of one validator pass."""

    passed: bool
    severity: str
    violations: List[Violation] = field(default_factory=list)
    validator_model: str = ""
    latency_ms: int = 0
    error: Optional[str] = None

    @property
    def has_critical(self) -> bool:
        return self.severity == "critical"


_VALIDATOR_SYSTEM = (
    "You are a strict fact-checker for an EU policy assistant. Your only job is to "
    "detect hallucinations and incomplete answers by comparing the assistant's "
    "RESPONSE against the CONTEXT that was retrieved for this query.\n\n"
    "You will receive three inputs: CONTEXT (the data retrieved from Brubru's "
    "database), QUERY (what the user asked), and RESPONSE (what the assistant "
    "said).\n\n"
    "Check the RESPONSE against the CONTEXT for these violation types:\n\n"
    "1. HALLUCINATION -- any named entity, number, date, CELEX number, MEP name, "
    "regulation number, organisation name, or specific institutional fact in the "
    "RESPONSE that does NOT appear in the CONTEXT. Generic background knowledge "
    "(e.g. \"the EU has 27 member states\", \"the Commission proposes legislation\") "
    "is acceptable. Specific factual claims with concrete identifiers MUST be "
    "grounded in CONTEXT.\n\n"
    "2. COMPLETENESS -- if the CONTEXT clearly lists N items (e.g. 27 commissioners, "
    "all member states, all rapporteurs) and the RESPONSE names only k where k < N "
    "WITHOUT saying \"showing k of N\" or \"for the full list see X\", that is a "
    "completeness violation.\n\n"
    "3. NEGATION -- if the CONTEXT contains data that answers the QUERY but the "
    "RESPONSE says \"I don't have that information\" or equivalent, that is a "
    "negation violation. The RESPONSE must use the data when CONTEXT provides it.\n\n"
    "Severity rules:\n"
    "  - critical -- fabricated names / numbers / dates / CELEX refs presented as "
    "fact, OR claiming \"no data\" when CONTEXT provides clear data.\n"
    "  - warning  -- completeness gap of more than 50% with no \"k of N\" disclaimer.\n"
    "  - info     -- minor issues with no factual harm; default when nothing is wrong.\n\n"
    "Return STRICT JSON only, no prose, no markdown fences. Schema:\n"
    "{\"passed\": bool, \"severity\": \"critical\"|\"warning\"|\"info\", "
    "\"violations\": [{\"type\": \"hallucination\"|\"completeness\"|\"negation\", "
    "\"evidence\": str, \"explanation\": str}]}\n\n"
    "If everything is fine, return {\"passed\": true, \"severity\": \"info\", "
    "\"violations\": []}."
)


def _build_user_message(query: str, context_blocks: str, response: str) -> str:
    return (
        "CONTEXT:\n"
        f"{context_blocks}\n\n"
        "---\n\n"
        "QUERY:\n"
        f"{query}\n\n"
        "---\n\n"
        "RESPONSE:\n"
        f"{response}\n\n"
        "---\n\n"
        "Now return the JSON verdict."
    )


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of a possibly-wrapped LLM string."""

    stripped = raw.strip()
    # Strip ```json fences if the model ignored the instruction.
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"```\s*$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("validator did not return JSON")


class ResponseValidator:
    """Fact-check a generated response against the retrieved context."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = VALIDATOR_MODEL,
        timeout: int = VALIDATOR_TIMEOUT_SECONDS,
        context_cap: int = VALIDATOR_CONTEXT_CHAR_CAP,
    ):
        self.model = model
        self.timeout = timeout
        self.context_cap = context_cap
        self._client: Optional[AsyncAnthropic] = None

        if not _ANTHROPIC_AVAILABLE:
            logger.warning("anthropic SDK not importable -- validator disabled")
            return

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            logger.warning("ANTHROPIC_API_KEY not set -- validator disabled")
            return

        self._client = AsyncAnthropic(api_key=key)

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def _truncate_context(self, context_blocks: str) -> str:
        if len(context_blocks) <= self.context_cap:
            return context_blocks
        head = context_blocks[: self.context_cap]
        return head + f"\n\n[CONTEXT TRUNCATED FOR VALIDATOR -- {len(context_blocks) - self.context_cap} chars elided]"

    async def validate(
        self,
        query: str,
        context_blocks: str,
        response: str,
    ) -> ValidationResult:
        """Run a single validation pass. Fail-soft on any error."""

        if not self.is_available:
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=self.model,
                error="validator unavailable",
            )

        if not response or not response.strip():
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=self.model,
            )

        bounded_context = self._truncate_context(context_blocks or "(no context retrieved)")
        user_msg = _build_user_message(query, bounded_context, response)

        start = time.monotonic()
        try:
            api_response = await asyncio.wait_for(
                self._client.messages.create(
                    model=self.model,
                    max_tokens=1200,
                    temperature=0.0,
                    system=_VALIDATOR_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                ),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=self.model,
                latency_ms=int((time.monotonic() - start) * 1000),
                error="timeout",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("validator API call failed: %s", exc)
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=self.model,
                latency_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            raw = api_response.content[0].text if api_response.content else ""
            parsed = _extract_json(raw)
        except (ValueError, json.JSONDecodeError, IndexError, AttributeError) as exc:
            logger.warning("validator returned unparseable output: %s", exc)
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=self.model,
                latency_ms=latency_ms,
                error=f"parse_error: {exc}",
            )

        violations_payload = parsed.get("violations", []) or []
        violations: List[Violation] = []
        for v in violations_payload:
            if not isinstance(v, dict):
                continue
            violations.append(
                Violation(
                    type=str(v.get("type", "unknown"))[:32],
                    evidence=str(v.get("evidence", ""))[:1000],
                    explanation=str(v.get("explanation", ""))[:1000],
                )
            )

        severity = str(parsed.get("severity", "info")).lower()
        if severity not in ("critical", "warning", "info"):
            severity = "info"

        passed = bool(parsed.get("passed", True))

        return ValidationResult(
            passed=passed,
            severity=severity,
            violations=violations,
            validator_model=self.model,
            latency_ms=latency_ms,
        )


_singleton: Optional[ResponseValidator] = None


def get_response_validator() -> ResponseValidator:
    """Process-wide singleton."""

    global _singleton
    if _singleton is None:
        _singleton = ResponseValidator()
    return _singleton
