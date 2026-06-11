"""
Unit tests for the response validator (Workstream 1).

Covers:
  - JSON extraction from validator output (clean, fenced, prose-wrapped)
  - Truncation of oversized context
  - Validator unavailable path (no providers at all)
  - Successful validation (mocked open-model chain)
  - Timeout and exception paths (fail-soft)
  - Empty response short-circuit

Engine note (11 June 2026): the validator runs on the shared MultiProviderService
open-model chain, not a direct Anthropic client. Tests mock `_service.generate`
returning a ProviderResponse-shaped object.

Run: cd backend && python3.12 -m pytest tests/test_response_validator.py -v
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.ai.response_validator import (
    ResponseValidator,
    ValidationResult,
    Violation,
    _extract_json,
)


def _fake_service(providers=("Cerebras",)):
    """A MultiProviderService stand-in whose .providers is non-empty so
    is_available is True. .generate is replaced per-test."""
    svc = MagicMock()
    svc.providers = list(providers)
    return svc


def _provider_response(text: str):
    """ProviderResponse-shaped object returned by MultiProviderService.generate."""
    return SimpleNamespace(
        message=text, tokens_used=10, model="gpt-oss-120b", provider="Cerebras"
    )


def _validator_with(generate_mock):
    """Build a validator wired to a fake service with the given generate mock."""
    svc = _fake_service()
    svc.generate = generate_mock
    return ResponseValidator(service=svc)


class TestExtractJson:
    def test_clean_json(self):
        assert _extract_json('{"passed": true}') == {"passed": True}

    def test_fenced_json(self):
        raw = '```json\n{"passed": false, "severity": "critical"}\n```'
        assert _extract_json(raw) == {"passed": False, "severity": "critical"}

    def test_prose_wrapped_json(self):
        raw = 'Here is the verdict:\n\n{"passed": true, "severity": "info"}\n\nThanks.'
        assert _extract_json(raw)["passed"] is True

    def test_invalid_returns_value_error(self):
        with pytest.raises(ValueError):
            _extract_json("no JSON anywhere")


class TestUnavailableValidator:
    def test_unavailable_with_no_providers(self):
        # A service with an empty provider list -> validator disabled.
        svc = _fake_service(providers=())
        v = ResponseValidator(service=svc)
        assert v.is_available is False

    def test_validate_unavailable_returns_fail_soft(self):
        svc = _fake_service(providers=())
        v = ResponseValidator(service=svc)
        result = asyncio.run(v.validate("q", "ctx", "resp"))
        assert result.passed is True
        assert result.error == "validator unavailable"


class TestEmptyResponse:
    def test_empty_response_short_circuits(self):
        # Available service, but empty response shorts before any generate call.
        v = _validator_with(AsyncMock())
        result = asyncio.run(v.validate("q", "ctx", ""))
        assert result.passed is True
        assert result.violations == []


class TestContextTruncation:
    def test_short_context_unchanged(self):
        v = ResponseValidator(service=_fake_service(), context_cap=100)
        assert v._truncate_context("short") == "short"

    def test_long_context_truncated_with_marker(self):
        v = ResponseValidator(service=_fake_service(), context_cap=10)
        out = v._truncate_context("x" * 50)
        assert out.startswith("x" * 10)
        assert "TRUNCATED" in out


class TestSuccessfulValidation:
    def test_clean_pass(self):
        v = _validator_with(AsyncMock(return_value=_provider_response(
            '{"passed": true, "severity": "info", "violations": []}'
        )))
        result = asyncio.run(v.validate("query", "ctx", "response"))
        assert result.passed is True
        assert result.severity == "info"
        assert result.violations == []
        assert result.error is None
        assert result.validator_model == "gpt-oss-120b"

    def test_hallucination_detected(self):
        v = _validator_with(AsyncMock(return_value=_provider_response(
            '{"passed": false, "severity": "critical", "violations": [{"type": "hallucination", "evidence": "20th package", "explanation": "not in context"}]}'
        )))
        result = asyncio.run(v.validate("q", "ctx", "the 20th package was adopted"))
        assert result.passed is False
        assert result.severity == "critical"
        assert result.has_critical is True
        assert result.should_override is True
        assert len(result.violations) == 1
        assert result.violations[0].type == "hallucination"

    def test_unknown_severity_normalised_to_info(self):
        v = _validator_with(AsyncMock(return_value=_provider_response(
            '{"passed": true, "severity": "weird", "violations": []}'
        )))
        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.severity == "info"


class TestFailSoft:
    def test_timeout_is_fail_soft(self):
        v = _validator_with(AsyncMock(side_effect=asyncio.TimeoutError()))
        v.timeout = 1
        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.passed is True
        assert result.error == "timeout"

    def test_api_error_is_fail_soft(self):
        v = _validator_with(AsyncMock(side_effect=RuntimeError("boom")))
        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.passed is True
        assert "RuntimeError" in (result.error or "")

    def test_parse_error_is_fail_soft(self):
        v = _validator_with(AsyncMock(return_value=_provider_response("not json at all")))
        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.passed is True
        assert "parse_error" in (result.error or "")


class TestViolationSerialization:
    def test_violation_to_dict_roundtrip(self):
        v = Violation(type="hallucination", evidence="ev", explanation="ex")
        assert v.to_dict() == {
            "type": "hallucination",
            "evidence": "ev",
            "explanation": "ex",
        }

    def test_violations_truncated_to_1000_chars(self):
        long_text = "x" * 5000
        v = _validator_with(AsyncMock(return_value=_provider_response(
            '{"passed": false, "severity": "critical", "violations": [{"type": "hallucination", "evidence": "'
            + long_text
            + '", "explanation": "long"}]}'
        )))
        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert len(result.violations) == 1
        assert len(result.violations[0].evidence) <= 1000
