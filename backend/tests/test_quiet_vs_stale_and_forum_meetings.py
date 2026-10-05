"""Publisher silence is not scraper failure; Forum meetings are read live (5 Oct 2026)."""
import datetime as dt
import importlib.util
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")
sys.path.insert(0, _REPO_ROOT + "/backend/scripts")

import pytest  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, f"{_REPO_ROOT}/backend/scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Res:
    def __init__(self, v):
        self.v = v

    def scalar(self):
        return self.v


class _DB:
    """First scalar() is the freshness query, the second the sync_runs lookup."""
    def __init__(self, newest, ran):
        self.vals = [newest, ran]

    def execute(self, *a, **k):
        return _Res(self.vals.pop(0))

    def rollback(self):
        pass


SRC = {"key": "eea", "name": "x", "ingested": True, "sql": "select 1", "stale_after_days": 5}
OLD = dt.date.today() - dt.timedelta(days=13)


def test_stale_source_whose_scraper_ran_is_quiet():
    led = _load("client_source_ledger")
    assert led.check(_DB(OLD, dt.datetime.now()), SRC | {"scraper_key": "economy_eea"})["state"] == "QUIET"


def test_stale_source_whose_scraper_did_not_run_stays_stale():
    led = _load("client_source_ledger")
    assert led.check(_DB(OLD, None), SRC | {"scraper_key": "economy_eea"})["state"] == "STALE"


def test_stale_source_without_scraper_key_stays_stale():
    led = _load("client_source_ledger")
    assert led.check(_DB(OLD, dt.datetime.now()), SRC)["state"] == "STALE"


class _Resp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"content": self.content}


def test_forum_meetings_upcoming_is_urgent_and_past_is_not(monkeypatch):
    watch = _load("dpp_watch")
    import requests
    today = dt.date.today()
    rows = [{"meetingId": 1, "title": "Ecodesign Forum - textiles", "refGroup": "E03969 - Forum",
             "startDate": (today + dt.timedelta(days=9)).isoformat()},
            {"meetingId": 2, "title": "Ecodesign Forum - DPP", "refGroup": "E03969 - Forum",
             "startDate": (today - dt.timedelta(days=3)).isoformat()}]
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(rows))
    hits, row = watch.forum_meetings(35)
    by_id = {h["url"].rsplit("=", 1)[1]: h for h in hits}
    assert by_id["1"]["urgent"] is True and by_id["2"]["urgent"] is False
    assert row["state"] == "OK" and row["age_days"] == 3


def test_forum_meetings_failure_is_failed_not_empty(monkeypatch):
    watch = _load("dpp_watch")
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(requests, "post", boom)
    hits, row = watch.forum_meetings(35)
    assert hits == [] and row["state"] == "FAILED"
