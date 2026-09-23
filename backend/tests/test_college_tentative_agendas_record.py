"""college_tentative_agendas must leave one sync_runs row per run (23 Sep 2026).

It ran from the hot-6h tier through a bare subprocess that records nothing, so
a quiet register and a job that never ran looked identical.
"""
import importlib.util
import pathlib
import sys

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sync_college_tentative_agendas.py"


@pytest.fixture()
def job(monkeypatch):
    spec = importlib.util.spec_from_file_location("sync_cta", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import core.database
    import services.sync.freshness as freshness

    recorded, state = [], {"persisted": 0}

    class _DB:
        def execute(self, *a, **k):
            class _R:
                def scalar(self_inner):
                    return state["persisted"]
            return _R()

        def close(self):
            pass

    monkeypatch.setattr(core.database, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: recorded.append(kw))
    return mod, recorded, state


def _started():
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc)


def test_quiet_run_is_success_with_zero(job):
    mod, recorded, _ = job
    mod._record({"new": [], "changed": 0, "unchanged": 20, "failed": []}, 0, _started())
    assert recorded == [{"source_key": "college_tentative_agendas", "tier": "hot_6h",
                         "status": "success", "items_added": 0, "error": None,
                         "started_at": recorded[0]["started_at"]}]


def test_new_documents_are_counted_once_persisted(job):
    mod, recorded, state = job
    state["persisted"] = 2
    mod._record({"new": ["SEC(2026)2600", "SEC(2026)2601"], "failed": []}, 0, _started())
    assert recorded[0]["status"] == "success" and recorded[0]["items_added"] == 2


def test_new_documents_that_did_not_land_are_a_failure(job):
    mod, recorded, state = job
    state["persisted"] = 1
    mod._record({"new": ["SEC(2026)2600", "SEC(2026)2601"], "failed": []}, 0, _started())
    assert recorded[0]["status"] == "failed" and "persisted 1 of 2" in recorded[0]["error"]


def test_unfetchable_pdf_or_unparsed_agenda_is_degraded(job):
    mod, recorded, _ = job
    mod._record({"new": [], "failed": [("SEC(2026)2599", "not a PDF")],
                 "warn": "no items parsed from SEC(2026)2578"}, 0, _started())
    assert recorded[0]["status"] == "degraded"
    assert "SEC(2026)2599: not a PDF" in recorded[0]["error"]
    assert "no items parsed" in recorded[0]["error"]


def test_empty_register_is_a_failure_not_a_quiet_day(job):
    mod, recorded, _ = job
    mod._record({"error": "the register returned no documents"}, 1, _started())
    assert recorded[0]["status"] == "failed"
    assert "no documents" in recorded[0]["error"]


def test_dry_run_records_nothing(job, monkeypatch):
    mod, recorded, _ = job
    monkeypatch.setattr(mod, "_run", lambda a, outcome: 0)
    monkeypatch.setattr(sys, "argv", ["x", "--dry-run"])
    assert mod.main() == 0
    assert recorded == []


def test_a_crash_is_recorded_then_raised(job, monkeypatch):
    mod, recorded, _ = job

    def boom(a, outcome):
        raise ConnectionError("register unreachable")

    monkeypatch.setattr(mod, "_run", boom)
    monkeypatch.setattr(sys, "argv", ["x"])
    with pytest.raises(ConnectionError):
        mod.main()
    assert recorded[0]["status"] == "failed" and "ConnectionError" in recorded[0]["error"]
