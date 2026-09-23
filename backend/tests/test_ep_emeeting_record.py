"""ep_emeeting leaves one sync_runs row per run (23 Sep 2026).

The daily cron refreshed the store without ever recording a run, so its health
was invisible to /api/sync/health.
"""
import datetime as dt
import importlib.util
import pathlib
import sys

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sync_ep_emeeting.py"


@pytest.fixture()
def job(monkeypatch):
    spec = importlib.util.spec_from_file_location("sync_eme", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import services.sync.freshness as freshness
    recorded = []

    class _DB:
        def close(self):
            pass

    monkeypatch.setattr(mod, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: recorded.append(kw))
    return mod, recorded


def _o(**kw):
    base = {"committees": 3, "empty": [], "skipped": 0, "docs_new": 0}
    return {**base, **kw}


def _now():
    return dt.datetime.now(dt.timezone.utc)


def test_quiet_success_counts_persisted_docs(job):
    mod, rec = job
    mod._record(_o(docs_new=7), _now())
    assert rec[0]["status"] == "success" and rec[0]["items_added"] == 7
    assert rec[0]["source_key"] == "ep_emeeting" and rec[0]["error"] is None


def test_an_empty_committee_is_degraded(job):
    mod, rec = job
    mod._record(_o(empty=["LIBE"]), _now())
    assert rec[0]["status"] == "degraded" and "LIBE" in rec[0]["error"]


def test_every_committee_empty_is_a_failure(job):
    mod, rec = job
    mod._record(_o(empty=["AFCO", "IMCO", "ITRE"]), _now())
    assert rec[0]["status"] == "failed"


def test_write_failures_are_degraded(job):
    mod, rec = job
    mod._record(_o(skipped=2, docs_new=5), _now())
    assert rec[0]["status"] == "degraded" and "2 agenda" in rec[0]["error"]


def test_crash_is_recorded_then_raised(job, monkeypatch):
    mod, rec = job

    def boom(outcome):
        outcome["committees"] = 26
        raise ConnectionError("eMeeting API down")

    monkeypatch.setattr(mod, "_main", boom)
    with pytest.raises(ConnectionError):
        mod.main()
    assert rec[0]["status"] == "failed" and "ConnectionError" in rec[0]["error"]


def test_dry_run_records_nothing(job, monkeypatch):
    mod, rec = job

    def dry(outcome):
        outcome["dry_run"] = True

    monkeypatch.setattr(mod, "_main", dry)
    mod.main()
    assert rec == []
