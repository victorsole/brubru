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
is actually present? Is the response validating a user-asserted role that
the context does not confirm?"

Validator engine: the shared free open-model chain (Cerebras gpt-oss-120b ->
NVIDIA Llama-3.3-70B -> Mistral -> Gemini -> Groq -> Anthropic -> OpenAI), the
SAME MultiProviderService the generator uses. Migrated off the direct
Anthropic-Haiku client on 11 June 2026: the old client failed every call when
Anthropic ran out of funds, and because the validator fails OPEN that silently
disabled the anti-hallucination net at the exact moment a weaker open generator
needs it most (a fabricated DSA CELEX shipped to production unvalidated). Going
through the chain means the validator is funded-independent.

Failure mode: fail-soft. If the validator errors (network, JSON parse, timeout)
the result returns passed=True with an error field set, and the caller logs
but ships the original response unchanged.

History:
- 12 May 2026: validator scaffolded on Claude Haiku 4.5.
- 28 May 2026 (am): briefly migrated to Mistral -- INCORRECT, reverted same day.
  Chat = Anthropic, full stop.
- 28 May 2026 (pm): expanded violation taxonomy after EFPIA-demo
  Biotech Act / Andriukaitis fabrication incident.
- 11 June 2026: migrated to the shared open-model chain (Anthropic-independent)
  after the chat OSS migration left the Haiku validator dead while unfunded.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from services.ai.multi_provider_service import (
    MultiProviderService,
    get_multi_provider_service,
)
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

    @property
    def should_override(self) -> bool:
        """
        Whether this result warrants swapping the answer for a safe refusal.

        Only genuinely dangerous, demo-killing FABRICATION types trigger an
        override. A 'negation' (over-cautious refusal) or 'completeness' gap
        rated critical by the model must NOT override -- replacing an answer
        with a refusal template there is nonsensical, and over-cautious
        escalation was silently refusing legitimate, guide-grounded answers
        (29 May 2026). See memory feedback_validator_override_hard_types.
        """
        return self.severity == "critical" and any(
            v.type in _OVERRIDE_VIOLATION_TYPES for v in self.violations
        )


# Violation types that justify swapping the answer for a safe refusal. The
# soft types (negation, completeness) are logged but never override.
_OVERRIDE_VIOLATION_TYPES = frozenset({
    "hallucination",            # a fabricated named role / citation / quote / hard figure
    "user_claim_capitulation",
    "name_splitting",
    "fabricated_meeting",
    "fabricated_future_date",
})


_VALIDATOR_SYSTEM = (
    "You are a strict fact-checker for an EU policy assistant. Your only job is to "
    "detect hallucinations, incomplete answers, and user-claim capitulations by comparing "
    "the assistant's RESPONSE against the CONTEXT that was retrieved for this query.\n\n"
    "You will receive three inputs: CONTEXT (the data retrieved from Brubru's "
    "database), QUERY (what the user asked), and RESPONSE (what the assistant "
    "said).\n\n"
    "Guiding principle: you are catching FABRICATIONS that would mislead a specialist "
    "reader, not policing every sentence. General EU legal and procedural background, "
    "explanations of how a mechanism works, and reasonable inferences that are consistent "
    "with the CONTEXT are ACCEPTABLE and must NOT be flagged. Only flag a claim when it "
    "asserts a SPECIFIC, checkable fact that the CONTEXT contradicts or does not support.\n\n"
    "Check the RESPONSE against the CONTEXT for these violation types:\n\n"
    "1. HALLUCINATION -- a SPECIFIC, checkable fabricated fact presented as true that the "
    "CONTEXT does not support: a named person (MEP / rapporteur / shadow / official) given a "
    "role or position; a CELEX / procedure / regulation number presented as a citation; a "
    "specific statistic or vote tally presented as a hard figure; a direct quote attributed "
    "to a named person or outlet (Euractiv, Politico, Reuters, Bloomberg, FT, Contexte, "
    "Bruegel). These MUST be grounded in CONTEXT. "
    "NOT a hallucination: generic background ('the EU has 27 member states', 'the Commission "
    "proposes legislation'), explaining how a procedure or mechanism works, defining a term, "
    "a reasonable inference about legislative history or context, or rephrasing CONTEXT. Do "
    "NOT flag these. When unsure whether a statement is harmful fabrication or harmless "
    "background, treat it as background (info), not a hallucination.\n\n"
    "2. COMPLETENESS -- if the CONTEXT clearly lists N items (e.g. 27 commissioners, "
    "all member states, all rapporteurs) and the RESPONSE names only k where k < N "
    "WITHOUT saying 'showing k of N' or 'for the full list see X', that is a "
    "completeness violation (warning, never critical).\n\n"
    "3. NEGATION -- if the CONTEXT contains data that answers the QUERY but the "
    "RESPONSE says 'I don't have that information' or equivalent, that is a "
    "negation violation (warning, never critical -- the answer is over-cautious, not wrong).\n\n"
    "4. USER_CLAIM_CAPITULATION -- if the QUERY asserts a fact about a named person's role "
    "on a procedure (rapporteur, shadow, coordinator, lead negotiator) and the RESPONSE "
    "accepts that assertion without the CONTEXT confirming it, that is a critical violation. "
    "The RESPONSE must refuse to validate the user's claim and state what the CONTEXT does "
    "and does not contain.\n\n"
    "5. NAME_SPLITTING -- if the RESPONSE treats one named individual as two different people "
    "based on name variants, middle names, or career stages (e.g. 'X is not an MEP; however "
    "X Y is an MEP'), that is a critical violation. A person with multiple given names is "
    "ONE person.\n\n"
    "6. FABRICATED_MEETING -- if the RESPONSE asserts that a named person met with a specific "
    "institution / DG / committee on a specific date, that meeting MUST appear in the CONTEXT "
    "(calendar event, Transparency Register row, press release). Otherwise it is a critical "
    "violation.\n\n"
    "7. FABRICATED_FUTURE_DATE -- if the RESPONSE asserts a specific future committee vote, "
    "plenary vote, or trilogue date and that date does NOT appear in the CONTEXT, that is a "
    "critical violation.\n\n"
    "Severity rules. Be conservative -- reserve 'critical' for fabrications that would "
    "mislead a specialist, NOT for harmless background or inference:\n"
    "  - critical -- ONLY one of: a fabricated NAMED person given a role the CONTEXT does not "
    "confirm (includes user_claim_capitulation); name_splitting; a fabricated_meeting; a "
    "fabricated_future_date; a fabricated direct QUOTE; or a fabricated CELEX / procedure / "
    "regulation NUMBER presented as a citation. These are the only override-worthy violations.\n"
    "  - warning  -- a claim that is plausible and consistent with the CONTEXT but not stated "
    "verbatim there (general background, mechanism explanation, reasonable inference about "
    "legislative history); a completeness gap over 50% with no 'k of N' disclaimer; or a "
    "negation. Warnings are logged, NOT overridden. Do NOT escalate these to critical.\n"
    "  - info     -- minor issues with no factual harm; default when nothing is wrong.\n\n"
    "Return STRICT JSON only, no prose, no markdown fences. Schema:\n"
    "{\"passed\": bool, \"severity\": \"critical\"|\"warning\"|\"info\", "
    "\"violations\": [{\"type\": \"hallucination\"|\"completeness\"|\"negation\""
    "|\"user_claim_capitulation\"|\"name_splitting\"|\"fabricated_meeting\""
    "|\"fabricated_future_date\", \"evidence\": str, \"explanation\": str}]}\n\n"
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
        api_key: Optional[str] = None,  # retained for signature compatibility; unused
        model: str = VALIDATOR_MODEL,
        timeout: int = VALIDATOR_TIMEOUT_SECONDS,
        context_cap: int = VALIDATOR_CONTEXT_CHAR_CAP,
        service: Optional[MultiProviderService] = None,
    ):
        self.model = model  # label only; the real engine is the chain's first working provider
        self.timeout = timeout
        self.context_cap = context_cap
        self._service: Optional[MultiProviderService] = None

        try:
            self._service = service or get_multi_provider_service()
        except Exception as exc:  # noqa: BLE001 -- no providers configured at all
            logger.warning("validator disabled -- no AI providers available: %s", exc)
            self._service = None

    @property
    def is_available(self) -> bool:
        return self._service is not None and bool(self._service.providers)

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
        engine = self.model
        try:
            # prefer_claude=False keeps the validator on the open chain's first
            # working provider (Cerebras gpt-oss-120b) rather than routing to
            # Sonnet; max_tokens bumped to 2000 so a reasoning model's JSON is
            # not truncated. temperature 0.0 for a deterministic verdict.
            provider_response = await asyncio.wait_for(
                self._service.generate(
                    system_prompt=_VALIDATOR_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                    max_tokens=2000,
                    temperature=0.0,
                    prefer_claude=False,
                ),
                timeout=self.timeout,
            )
            engine = provider_response.model or provider_response.provider or self.model
        except asyncio.TimeoutError:
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=engine,
                latency_ms=int((time.monotonic() - start) * 1000),
                error="timeout",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("validator API call failed: %s", exc)
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=engine,
                latency_ms=int((time.monotonic() - start) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            raw = provider_response.message or ""
            parsed = _extract_json(raw)
        except (ValueError, json.JSONDecodeError, IndexError, AttributeError) as exc:
            logger.warning("validator returned unparseable output: %s", exc)
            return ValidationResult(
                passed=True,
                severity="info",
                validator_model=engine,
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
            validator_model=engine,
            latency_ms=latency_ms,
        )


_singleton: Optional[ResponseValidator] = None


def get_response_validator() -> ResponseValidator:
    """Process-wide singleton."""

    global _singleton
    if _singleton is None:
        _singleton = ResponseValidator()
    return _singleton
