"""
The streaming provider chain retries TRANSIENT failures once, never permanent ones.

Why (audit 8 Oct 2026): on 7 Oct three consecutive answers died with "providers
are temporarily unavailable" within two minutes while Cerebras was already 402.
The chain made one pass, so a single transient refusal from the last working
lane was a total outage, and the reason was not recorded anywhere durable.

These tests use scripted fake providers: no network, no database.
"""

import asyncio
import sys
from pathlib import Path

import httpx
import openai
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ai import multi_provider_service as mps  # noqa: E402
from services.ai.multi_provider_service import (  # noqa: E402
    MultiProviderService,
    _failure_reason,
    _is_transient_failure,
)


class HttpError(Exception):
    """Stand-in for a provider error that carries a status code."""

    def __init__(self, status: int, message: str = ""):
        super().__init__(f"Error code: {status} - {message}")
        self.status_code = status


class ScriptedProvider:
    """Each call to generate_stream consumes the next scripted step.

    A step is an exception instance (raised before any output), a string
    (streamed as one delta), or ("partial", text, exc): yields text then raises.
    """

    def __init__(self, name, steps):
        self.name = name
        self.model = f"{name}-model"
        self.steps = list(steps)
        self.calls = 0
        self.is_available = True

    async def generate_stream(self, system_prompt, messages, max_tokens, temperature):
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        if isinstance(step, Exception):
            raise step
        if isinstance(step, tuple) and step[0] == "partial":
            yield step[1]
            raise step[2]
        yield step


def _service(*providers):
    svc = MultiProviderService.__new__(MultiProviderService)
    svc.providers = list(providers)
    return svc


def _run(svc, telemetry=None):
    async def go():
        out = []
        async for piece in svc.generate_stream("sys", [{"role": "user", "content": "q"}], 100, 0.0, telemetry=telemetry):
            out.append(piece)
        return "".join(out)

    return asyncio.run(go())


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """No real waiting; record every sleep so tests can assert on it."""
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(mps.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(mps, "CHAIN_RETRY_PASSES", 1)
    monkeypatch.setattr(mps, "CHAIN_RETRY_BACKOFF_S", 2.5)
    return sleeps


def test_transient_failure_is_retried_and_answers(_fast_backoff):
    # The 7 Oct shape: the paid lane refuses once, would answer a moment later.
    cerebras = ScriptedProvider("Cerebras", [HttpError(402, "Payment required")])
    scaleway = ScriptedProvider("Scaleway", [HttpError(429, "slow down"), "the answer"])
    tele = {}
    assert _run(_service(cerebras, scaleway), tele) == "the answer"
    assert tele["provider"] == "Scaleway"
    assert tele["attempts"] == ["Cerebras: HTTP 402", "Scaleway: HTTP 429"]
    assert cerebras.calls == 1  # 402 is permanent: never asked again
    assert scaleway.calls == 2
    assert _fast_backoff == [2.5]


def test_permanent_failures_are_not_retried(_fast_backoff):
    a = ScriptedProvider("Cerebras", [HttpError(402, "Payment required")])
    b = ScriptedProvider("Groq", [HttpError(413, "Request too large")])
    c = ScriptedProvider("OpenAI", [HttpError(429, "You have no credits remaining")])
    tele = {}
    with pytest.raises(RuntimeError) as exc:
        _run(_service(a, b, c), tele)
    assert (a.calls, b.calls, c.calls) == (1, 1, 1)
    assert _fast_backoff == []  # nothing to retry, so no wait
    assert "Cerebras: HTTP 402" in str(exc.value)
    assert "Groq: HTTP 413" in str(exc.value)
    # an exhausted-credits 429 reads as permanent, not as "slow down"
    assert "OpenAI: HTTP 429" in str(exc.value)
    assert tele["attempts"] == ["Cerebras: HTTP 402", "Groq: HTTP 413", "OpenAI: HTTP 429"]


def test_only_transient_lanes_are_retried(_fast_backoff):
    dead = ScriptedProvider("Cerebras", [HttpError(402, "Payment required")])
    busy = ScriptedProvider("Gemini", [HttpError(429, "quota"), HttpError(429, "quota")])
    paid = ScriptedProvider("Scaleway", [asyncio.TimeoutError(), "late answer"])
    tele = {}
    assert _run(_service(dead, busy, paid), tele) == "late answer"
    assert dead.calls == 1
    assert busy.calls == 2  # retried first in chain order, still refused
    assert paid.calls == 2
    assert tele["provider"] == "Scaleway"
    assert tele["attempts"] == [
        "Cerebras: HTTP 402",
        "Gemini: HTTP 429",
        "Scaleway: timeout",
        "Gemini: HTTP 429 (retry)",
    ]


def test_still_fails_after_one_retry_and_reports_every_reason(_fast_backoff):
    busy = ScriptedProvider("Scaleway", [HttpError(503, "overloaded")])
    tele = {}
    with pytest.raises(RuntimeError) as exc:
        _run(_service(busy), tele)
    assert busy.calls == 2  # one pass + exactly one retry, never a loop
    assert "Scaleway: HTTP 503; Scaleway: HTTP 503 (retry)" in str(exc.value)
    assert tele["attempts"] == ["Scaleway: HTTP 503", "Scaleway: HTTP 503 (retry)"]


def test_retry_can_be_switched_off(monkeypatch, _fast_backoff):
    monkeypatch.setattr(mps, "CHAIN_RETRY_PASSES", 0)
    busy = ScriptedProvider("Scaleway", [HttpError(429, "slow down"), "never reached"])
    with pytest.raises(RuntimeError):
        _run(_service(busy))
    assert busy.calls == 1
    assert _fast_backoff == []


def test_no_retry_when_the_first_pass_already_took_too_long(monkeypatch, _fast_backoff):
    # A chain of timeouts has already cost the user the worst-case wait: do not double it.
    import types
    clock = iter([0.0, 100.0, 100.0, 100.0])
    # Patch the module's own reference only: patching time.monotonic itself would also
    # replace the clock asyncio's event loop runs on.
    monkeypatch.setattr(mps, "time", types.SimpleNamespace(monotonic=lambda: next(clock)))
    slow = ScriptedProvider("Scaleway", [asyncio.TimeoutError(), "never reached"])
    with pytest.raises(RuntimeError):
        _run(_service(slow))
    assert slow.calls == 1
    assert _fast_backoff == []


def test_mid_stream_failure_is_never_retried(_fast_backoff):
    # Text has already reached the user; a second provider would garble it.
    flaky = ScriptedProvider("Scaleway", [("partial", "Half an ", HttpError(503, "dropped")), "whole answer"])
    other = ScriptedProvider("Mistral", ["other answer"])
    with pytest.raises(HttpError):
        _run(_service(flaky, other))
    assert flaky.calls == 1
    assert other.calls == 0
    assert _fast_backoff == []


def test_first_pass_success_pays_nothing(_fast_backoff):
    ok = ScriptedProvider("Cerebras", ["fine"])
    tele = {}
    assert _run(_service(ok), tele) == "fine"
    assert tele["attempts"] == []
    assert _fast_backoff == []


def test_classifier_on_real_openai_exceptions():
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")

    def status_exc(cls, code, msg):
        return cls(msg, response=httpx.Response(code, request=req), body=None)

    rate = status_exc(openai.RateLimitError, 429, "Rate limit reached")
    gone = status_exc(openai.APIStatusError, 410, "model reached its end of life")
    pay = status_exc(openai.APIStatusError, 402, "Payment required")
    quota = status_exc(openai.RateLimitError, 429, "You exceeded your current quota, insufficient_quota")
    srv = status_exc(openai.InternalServerError, 503, "Service unavailable")
    assert _is_transient_failure(rate) and _failure_reason(rate) == "HTTP 429"
    assert not _is_transient_failure(gone) and _failure_reason(gone) == "HTTP 410"
    assert not _is_transient_failure(pay) and _failure_reason(pay) == "HTTP 402"
    assert not _is_transient_failure(quota)  # a 429 that is really "out of credit"
    assert _is_transient_failure(srv)
    assert _is_transient_failure(openai.APIConnectionError(request=req))
    assert _failure_reason(openai.APIConnectionError(request=req)) == "connection error"
    assert _is_transient_failure(openai.APITimeoutError(request=req))
    assert _failure_reason(openai.APITimeoutError(request=req)) == "timeout"


def test_classifier_on_text_only_errors():
    # Gemini raises RuntimeError("Gemini stream 429: ...") so the status exists only in the text.
    assert _is_transient_failure(RuntimeError("Gemini stream 429: {'error': 'quota'}"))
    assert _failure_reason(RuntimeError("Gemini stream 429: {}")) == "HTTP 429"
    assert not _is_transient_failure(RuntimeError("Gemini stream 403: forbidden"))
    assert _is_transient_failure(RuntimeError("empty output"))
    assert _failure_reason(RuntimeError("empty output")) == "empty output"
    assert not _is_transient_failure(RuntimeError("Mistral provider not configured"))
    assert _failure_reason(RuntimeError("Mistral provider not configured")) == "not configured"
    # an unclassified error is logged once, not repeated
    assert not _is_transient_failure(ValueError("surprise"))
    assert _failure_reason(ValueError("surprise")) == "ValueError"


def test_record_chain_failure_writes_the_reasons(monkeypatch):
    """The all-fail path leaves a durable row carrying the per-provider reasons."""
    from services.ai_service import AIService

    seen = {}

    class Stub:
        async def _log_chat_validation(self, **kw):
            seen.update(kw)

    asyncio.run(
        AIService._record_chain_failure(
            Stub(),
            user_message="What is the AI Act?",
            context_str="ctx" * 10,
            language="en",
            user_id=None,
            attempts=["Cerebras: HTTP 402", "Scaleway: HTTP 429", "Scaleway: HTTP 429 (retry)"],
            error="All AI providers failed (stream)",
        )
    )
    assert seen["outcome"] == "error"
    assert seen["generator"] == "chain_failed"
    assert seen["result"] is None
    assert seen["reason"] == "chain_failed: Cerebras: HTTP 402; Scaleway: HTTP 429; Scaleway: HTTP 429 (retry)"
    assert seen["context_length"] == 30
    assert seen["query"] == "What is the AI Act?"
