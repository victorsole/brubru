"""The weekly re-engagement job has a switch, a run record and a bounded audience (16 Oct 2026).

Before: no switch, no sync_runs row, no log, and every Monday it mailed every active
non-admin account (127 on 16 Oct 2026), prospects never contacted included.
"""
from types import SimpleNamespace

import pytest

import services.email_scheduler as es
import services.sync.freshness as freshness


class _DB:
    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def runs(monkeypatch):
    recorded = []
    monkeypatch.setattr(es, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: recorded.append(kw))
    return recorded


def _email_service(configured=True, ok=True):
    sent = []

    def send(to, **kw):
        sent.append(to)
        return ok

    return SimpleNamespace(is_configured=configured, send=send, sent=sent)


def _patch_email(monkeypatch, svc):
    import services.email_service as mail
    monkeypatch.setattr(mail, "get_email_service", lambda: svc)
    monkeypatch.setattr(mail, "build_welcome_back_email", lambda **kw: {"subject": "s", "html_body": "b"})
    monkeypatch.setattr(mail, "build_first_time_welcome_email", lambda **kw: {"subject": "s", "html_body": "b"})


def test_switch_off_records_a_skipped_run_and_sends_nothing(monkeypatch, runs):
    svc = _email_service()
    _patch_email(monkeypatch, svc)
    monkeypatch.setenv("REENGAGEMENT_EMAILS_ENABLED", "false")
    es._send_reengagement_emails()
    assert svc.sent == []
    assert runs and runs[-1]["status"] == "skipped" and runs[-1]["source_key"] == "reengagement_emails"


def test_smtp_missing_records_a_skipped_run(monkeypatch, runs):
    _patch_email(monkeypatch, _email_service(configured=False))
    monkeypatch.delenv("REENGAGEMENT_EMAILS_ENABLED", raising=False)
    es._send_reengagement_emails()
    assert runs[-1]["status"] == "skipped" and "SMTP" in runs[-1]["error"]


def test_sends_to_the_computed_lists_and_counts_persisted_sends(monkeypatch, runs):
    svc = _email_service()
    _patch_email(monkeypatch, svc)
    monkeypatch.delenv("REENGAGEMENT_EMAILS_ENABLED", raising=False)
    monkeypatch.setattr(es, "reengagement_recipients", lambda db: {
        "welcome_back": [("a@x.eu", "A", 9)], "first_time": [("b@y.eu", "B")]})
    es._send_reengagement_emails()
    assert svc.sent == ["a@x.eu", "b@y.eu"]
    assert runs[-1]["status"] == "success" and runs[-1]["items_added"] == 2


def test_failed_sends_are_not_reported_as_success(monkeypatch, runs):
    _patch_email(monkeypatch, _email_service(ok=False))
    monkeypatch.delenv("REENGAGEMENT_EMAILS_ENABLED", raising=False)
    monkeypatch.setattr(es, "reengagement_recipients", lambda db: {"welcome_back": [("a@x.eu", "A", 9)], "first_time": []})
    es._send_reengagement_emails()
    assert runs[-1]["status"] == "failed" and runs[-1]["items_added"] == 0


def test_the_audience_query_excludes_internal_accounts_and_is_windowed():
    import inspect
    src = inspect.getsource(es.reengagement_recipients)
    assert "INTERNAL_USER_SQL" in src          # admins, trainers, shells, test/beresol/hellobo accounts
    assert ">= :a AND" in src and "< :b" in src  # one lapse window, not "everyone older than 7 days"
    assert "created_at >= :a" in src            # first-time welcome only in the account's first week
