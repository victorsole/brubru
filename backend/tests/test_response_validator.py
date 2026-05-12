"""
Unit tests for the response validator (Workstream 1).

Covers:
  - JSON extraction from validator output (clean, fenced, prose-wrapped)
  - Truncation of oversized context
  - Validator unavailable path (no API key, no SDK)
  - Successful validation (mocked Anthropic)
  - Timeout and exception paths (fail-soft)
  - Empty response short-circuit

Run: cd backend && python3.12 -m pytest tests/test_response_validator.py -v
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.ai.response_validator import (
    ResponseValidator,
    ValidationResult,
    Violation,
    _extract_json,
)


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
    def test_unavailable_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        v = ResponseValidator()
        assert v.is_available is False

    def test_validate_unavailable_returns_fail_soft(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        v = ResponseValidator()
        result = asyncio.run(v.validate("q", "ctx", "resp"))
        assert result.passed is True
        assert result.error == "validator unavailable"


class TestEmptyResponse:
    def test_empty_response_short_circuits(self):
        v = ResponseValidator(api_key="fake-key-for-test")
        # The SDK is imported lazily; with a fake key the client exists but
        # validate() shorts on empty response before touching the network.
        result = asyncio.run(v.validate("q", "ctx", ""))
        assert result.passed is True
        assert result.violations == []


class TestContextTruncation:
    def test_short_context_unchanged(self):
        v = ResponseValidator(api_key="fake", context_cap=100)
        assert v._truncate_context("short") == "short"

    def test_long_context_truncated_with_marker(self):
        v = ResponseValidator(api_key="fake", context_cap=10)
        out = v._truncate_context("x" * 50)
        assert out.startswith("x" * 10)
        assert "TRUNCATED" in out


def _mock_anthropic_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


class TestSuccessfulValidation:
    def test_clean_pass(self):
        v = ResponseValidator(api_key="fake")
        fake_resp = _mock_anthropic_response(
            '{"passed": true, "severity": "info", "violations": []}'
        )
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(return_value=fake_resp)

        result = asyncio.run(v.validate("query", "ctx", "response"))
        assert result.passed is True
        assert result.severity == "info"
        assert result.violations == []
        assert result.error is None

    def test_hallucination_detected(self):
        v = ResponseValidator(api_key="fake")
        fake_resp = _mock_anthropic_response(
            '{"passed": false, "severity": "critical", "violations": [{"type": "hallucination", "evidence": "20th package", "explanation": "not in context"}]}'
        )
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(return_value=fake_resp)

        result = asyncio.run(v.validate("q", "ctx", "the 20th package was adopted"))
        assert result.passed is False
        assert result.severity == "critical"
        assert result.has_critical is True
        assert len(result.violations) == 1
        assert result.violations[0].type == "hallucination"

    def test_unknown_severity_normalised_to_info(self):
        v = ResponseValidator(api_key="fake")
        fake_resp = _mock_anthropic_response(
            '{"passed": true, "severity": "weird", "violations": []}'
        )
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(return_value=fake_resp)

        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.severity == "info"


class TestFailSoft:
    def test_timeout_is_fail_soft(self):
        v = ResponseValidator(api_key="fake", timeout=1)
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())

        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.passed is True
        assert result.error == "timeout"

    def test_api_error_is_fail_soft(self):
        v = ResponseValidator(api_key="fake")
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert result.passed is True
        assert "RuntimeError" in (result.error or "")

    def test_parse_error_is_fail_soft(self):
        v = ResponseValidator(api_key="fake")
        fake_resp = _mock_anthropic_response("not json at all")
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(return_value=fake_resp)

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
        v = ResponseValidator(api_key="fake")
        long_text = "x" * 5000
        fake_resp = _mock_anthropic_response(
            '{"passed": false, "severity": "critical", "violations": [{"type": "hallucination", "evidence": "'
            + long_text
            + '", "explanation": "long"}]}'
        )
        v._client = MagicMock()
        v._client.messages.create = AsyncMock(return_value=fake_resp)

        result = asyncio.run(v.validate("q", "ctx", "r"))
        assert len(result.violations) == 1
        assert len(result.violations[0].evidence) <= 1000
