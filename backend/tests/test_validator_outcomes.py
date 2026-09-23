"""Every chat answer leaves a validator outcome row (audit 23 Sep 2026).

Two defects made an unjudged answer look judged, or look like nothing:
  - a skip, a caller timeout or a crash wrote NO row, so the audit could not
    tell "skipped by design" from "the validator broke" (5 of 10 answers);
  - the validator fails soft with passed=True and `error` set, and that was
    stored as a pass (80 of 428 rows).
"""
import asyncio

import pytest

import services.ai.validator_settings as vs
import services.ai.response_validator as rv
import services.ai_service as ai_mod
from services.ai.response_validator import ValidationResult, Violation
from services.ai_service import AIService

CHECKABLE = "The rapporteur report A10-0201/2026 passed with 412 votes in favour."
PLAIN = "The AI Act is a regulation on artificial intelligence."


class _Validator:
    def __init__(self, result=None, delay=0.0, raises=None, available=True):
        self.result, self.delay, self.raises, self.is_available = result, delay, raises, available

    async def validate(self, **_):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises:
            raise self.raises
        return self.result


@pytest.fixture()
def run(monkeypatch):
    svc = AIService.__new__(AIService)
    svc.validator_timeout_s = 0.2
    calls = []

    async def fake_log(**kw):
        calls.append(kw)

    monkeypatch.setattr(svc, "_log_chat_validation", fake_log)
    monkeypatch.setattr(vs, "VALIDATOR_ENABLED", True)
    monkeypatch.setattr(vs, "VALIDATOR_SHADOW_MODE", True)

    def go(message, validator=None, use_context=True):
        if validator is not None:
            monkeypatch.setattr(rv, "get_response_validator", lambda: validator)

        async def main():
            out = await svc._validate_and_maybe_override(
                message=message, user_message="q", context_str="ctx",
                provider_used="Gemini", user_id=None, use_context=use_context,
                query_lang="EN")
            await asyncio.sleep(0)  # let the create_task'd logger run
            return out

        return asyncio.run(main()), calls

    return go


def test_skipped_answer_leaves_a_skipped_row(run):
    out, calls = run(PLAIN)
    assert out == PLAIN
    assert [(c["outcome"], c["reason"]) for c in calls] == [("skipped", "no_checkable_surface")]


def test_no_context_is_recorded(run):
    _, calls = run(CHECKABLE, use_context=False)
    assert [(c["outcome"], c["reason"]) for c in calls] == [("skipped", "no_context")]


def test_judged_answer(run):
    _, calls = run(CHECKABLE, _Validator(ValidationResult(passed=True, severity="info")))
    assert [c["outcome"] for c in calls] == ["judged"]


def test_soft_failure_is_not_a_pass(run):
    soft = ValidationResult(passed=True, severity="info", error="timeout")
    _, calls = run(CHECKABLE, _Validator(soft))
    assert [(c["outcome"], c["reason"]) for c in calls] == [("timeout", "timeout")]


def test_caller_budget_timeout_is_recorded(run):
    out, calls = run(CHECKABLE, _Validator(ValidationResult(True, "info"), delay=1.0))
    assert out == CHECKABLE
    assert calls[0]["outcome"] == "timeout" and "budget" in calls[0]["reason"]


def test_crash_is_recorded(run):
    out, calls = run(CHECKABLE, _Validator(raises=ValueError("bad json")))
    assert out == CHECKABLE
    assert calls[0]["outcome"] == "error" and "ValueError" in calls[0]["reason"]


def test_unavailable_validator_is_recorded(run):
    _, calls = run(CHECKABLE, _Validator(available=False))
    assert [(c["outcome"], c["reason"]) for c in calls] == [("error", "validator_unavailable")]


def test_paragraph_article_citation_is_checkable():
    assert ai_mod._response_needs_validation("Under Art 4(6) of the Chips Act the Fund...")
    assert ai_mod._response_needs_validation("Segons l'article 17(2) del Reglament...")
    assert not ai_mod._response_needs_validation("Article 5 bans social scoring.")


# --- the row itself -------------------------------------------------------

@pytest.fixture()
def rows(monkeypatch):
    saved = []

    class _DB:
        def add(self, row):
            saved.append(row)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(ai_mod, "SessionLocal", lambda: _DB())
    svc = AIService.__new__(AIService)

    def log(**kw):
        base = dict(query="q", response="r", context_length=3, generator="Gemini",
                    language="EN", shadow_mode=True, user_id=None)
        asyncio.run(svc._log_chat_validation(**{**base, **kw}))
        return saved[-1]

    return log


def test_skipped_row_has_null_passed(rows):
    row = rows(result=None, outcome="skipped", reason="no_checkable_surface")
    assert row.passed is None and row.outcome == "skipped" and row.severity == "skipped"
    assert row.error == "no_checkable_surface" and row.validator_model == "none"


def test_soft_failure_row_has_null_passed(rows):
    row = rows(result=ValidationResult(True, "info", error="timeout", validator_model="gemini"),
               outcome="timeout", reason="timeout")
    assert row.passed is None and row.outcome == "timeout"


def test_judged_row_keeps_verdict(rows):
    v = ValidationResult(False, "critical", violations=[Violation("fabricated_ref", "A10", "x")],
                         validator_model="gemini", latency_ms=900)
    row = rows(result=v, outcome="judged")
    assert row.passed is False and row.severity == "critical" and row.violation_count == 1
