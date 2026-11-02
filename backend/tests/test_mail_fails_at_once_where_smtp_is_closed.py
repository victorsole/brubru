"""Where SMTP cannot get out, a send fails at once (Victor's decision, 2 Nov 2026).

Railway disables SMTP on the Hobby plan. Each send waited out its 30-second timeout, on the
server's only process for the alert, password reset and sign-up routes, and the weekly
re-engagement job's failure turned the cron red.
"""
import logging
import smtplib
from types import SimpleNamespace

import pytest

import services.daily_brief_email as brief
import services.email_scheduler as es
import services.email_service as mail
import services.sync.freshness as freshness


class _Smtp:
    def __init__(self, *a, **k): self.opened = a
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def ehlo(self): pass
    def starttls(self): pass
    def login(self, *a): pass
    def sendmail(self, *a): pass


@pytest.fixture
def smtp(monkeypatch):
    opened = []
    def make(*a, **k):
        opened.append(a)
        return _Smtp(*a, **k)
    monkeypatch.setattr(smtplib, "SMTP", make)
    monkeypatch.delenv("SMTP_OPEN_ON_RAILWAY", raising=False)
    return opened


def _service():
    svc = mail.EmailService()
    svc.user, svc.password = "from@example.org", "secret"
    return svc


def _runner(monkeypatch, name):
    monkeypatch.setattr(freshness, "current_runner", lambda: name)


def test_on_railway_a_send_fails_without_opening_a_connection(monkeypatch, smtp, caplog):
    _runner(monkeypatch, "railway")
    with caplog.at_level(logging.WARNING):
        assert _service().send(to="to@example.org", subject="Reset your password", html_body="<p>x</p>") is False
    assert smtp == []
    assert "Reset your password" in caplog.text and "to@example.org" not in caplog.text


@pytest.mark.parametrize("runner, flag", [("local", ""), ("railway", "true")])
def test_a_laptop_or_the_flag_still_sends(monkeypatch, smtp, runner, flag):
    _runner(monkeypatch, runner)
    monkeypatch.setenv("SMTP_OPEN_ON_RAILWAY", flag)
    assert _service().send(to="to@example.org", subject="s", html_body="b") is True
    assert len(smtp) == 1


def test_the_reengagement_job_records_skipped_and_how_many_were_not_mailed(monkeypatch, smtp):
    _runner(monkeypatch, "railway")
    recorded = []
    db = SimpleNamespace(rollback=lambda: None, close=lambda: None)
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: recorded.append(kw))
    monkeypatch.setattr(mail, "get_email_service", _service)
    monkeypatch.setattr(es, "reengagement_recipients",
                        lambda db: {"welcome_back": [("a@example.org", "A", 8)], "first_time": []})
    es._send_reengagement_emails()
    assert smtp == []
    assert [r["status"] for r in recorded] == ["skipped"]
    assert "welcome_back=1 first_time=0 not mailed" in recorded[0]["error"]


def test_the_daily_brief_batch_does_not_try_either(monkeypatch, smtp):
    _runner(monkeypatch, "railway")
    monkeypatch.setattr(brief, "_fetch_headlines", lambda db: ([{"headline": "h"}], "2026-11-02"))
    monkeypatch.setattr(brief, "_get_all_recipient_emails", lambda db: ({"a@example.org"}, {"b@example.org"}))
    monkeypatch.setattr(brief, "_get_already_sent", lambda db, d: set())
    monkeypatch.setattr(brief, "_build_brief_email_html", lambda *a, **k: "<p>x</p>")
    out = brief.send_daily_brief_batch(None)
    assert smtp == [] and out["sent"] == 0 and out["failed"] == 2 and "closed" in out["error"]


@pytest.mark.parametrize("ok, word", [(False, "could not be sent"), (True, "email sent")])
def test_the_staleness_log_says_what_happened(monkeypatch, caplog, ok, word):
    import api.cron as cron
    monkeypatch.setattr(mail, "EmailService", lambda: SimpleNamespace(send=lambda **k: ok))
    monkeypatch.setattr(cron.settings, "ALERT_EMAIL", "ops@example.org", raising=False)
    with caplog.at_level(logging.INFO):
        cron._send_staleness_email([{"label": "News", "last_success_at": None}])
    assert word in caplog.text
