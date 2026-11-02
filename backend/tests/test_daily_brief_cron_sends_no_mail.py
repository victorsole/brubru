"""The daily-brief cron saves the day's headlines and sends no email (2 Nov 2026).

The daily emails stopped in May, when the Brubru Brief replaced them, but the route still
called send_daily_brief_batch every day: 107 people, stopped only because SMTP is closed on
Railway's Hobby plan. Opening SMTP would have mailed them all, unreviewed, every morning.
"""
import smtplib
import subprocess
from types import SimpleNamespace

import api.cron as cron
import services.daily_brief_email as brief


def _run(monkeypatch, returncode=0):
    sends, smtp = [], []
    monkeypatch.setattr(cron, "_verify_cron_secret", lambda authorization: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=returncode, stderr="tail", stdout=""))
    monkeypatch.setattr(brief, "send_daily_brief_batch", lambda *a, **k: sends.append(a) or {"sent": 1})
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: smtp.append(a))
    return cron.cron_daily_brief(authorization="Bearer x"), sends, smtp


def test_the_headlines_are_saved_and_nothing_is_mailed(monkeypatch):
    out, sends, smtp = _run(monkeypatch)
    assert out["results"]["scrape"]["status"] == "success"
    assert sends == [] and smtp == []
    assert set(out["results"]) == {"scrape"}          # the dispatcher reads each key as a job


def test_a_failed_scrape_still_reaches_the_dispatcher_and_mails_nobody(monkeypatch):
    out, sends, smtp = _run(monkeypatch, returncode=1)
    assert out["results"]["scrape"]["status"] == "failed"
    assert sends == [] and smtp == []
