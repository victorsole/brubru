"""/api/sync/health judges each nightly job by name (17 Oct 2026).

The tier line averaged its jobs: `tris_titles` failed on its first run while `daily` read
healthy (1 failure in 51 runs), and a job dropped from the schedule writes no row, so
nothing could turn red for it. `jobs.daily` lists each job with `failing` and `stale`.
"""
from datetime import datetime, timedelta, timezone

import pytest

from api import sync_status
from api.sync_status import judge_jobs

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


def row(key, status="success", hours_ago=7, error=None, runs=7, fails=0):
    t = NOW - timedelta(hours=hours_ago)
    return {"source_key": key, "last_status": status, "last_error": error, "last_run": t,
            "last_success": t if status in ("success", "ok") else None, "runs_7d": runs, "failures_7d": fails}


def test_a_failed_job_turns_the_tier_red_whatever_the_others_do():
    j = judge_jobs([row(f"ok_{i}") for i in range(50)] + [row("tris_titles", "failed", error="rc=1: boom")], NOW, 36)
    assert j["healthy"] is False and j["failing"] == ["tris_titles"] and j["count"] == 51
    assert j["detail"][0]["job"] == "tris_titles" and j["detail"][0]["error"] == "rc=1: boom"


def test_a_job_that_stopped_running_is_stale():
    j = judge_jobs([row("eu_laws_in_force", hours_ago=40), row("consultations")], NOW, 36)
    assert j["stale"] == ["eu_laws_in_force"] and j["failing"] == [] and j["healthy"] is False


def test_degraded_is_listed_never_red():
    j = judge_jobs([row("tenderator_translations_ted", "degraded", error="no translation engine"), row("cor")], NOW, 36)
    assert j["degraded"] == ["tenderator_translations_ted"] and j["healthy"] is True
    assert j["detail"][0]["error"] == "no translation engine"


@pytest.mark.parametrize("status", ["skipped", "running", "partial", None])
def test_a_status_nobody_thought_about_is_not_counted_as_fine(status):
    assert judge_jobs([row("x", status)], NOW, 36)["failing"] == ["x"]


def test_a_retired_job_is_listed_not_stale_until_it_runs_again():
    retired = {"dpp_watch": "13 Oct 2026"}
    j = judge_jobs([row("dpp_watch", hours_ago=100), row("cor")], NOW, 36, retired)
    assert j["retired"] == ["dpp_watch"] and j["stale"] == [] and j["healthy"] is True
    back = judge_jobs([row("dpp_watch", "failed", hours_ago=2)], NOW, 36, retired)
    assert back["failing"] == ["dpp_watch"] and back["retired"] == []


def test_nothing_to_judge_is_unknown_not_healthy():
    assert judge_jobs([], NOW, 36)["healthy"] is None
    only_retired = judge_jobs([row("dpp_watch", hours_ago=100)], NOW, 36, {"dpp_watch": "x"})
    assert only_retired["healthy"] is None


def test_a_naive_timestamp_is_read_as_utc():
    r = row("cor", hours_ago=1)
    r["last_run"] = r["last_run"].replace(tzinfo=None)
    assert judge_jobs([r], NOW, 36)["detail"][0]["stale"] is False


class _Result:
    def scalar(self):
        return None

    def mappings(self):
        return self

    def all(self):
        return []

    def first(self):
        return None


class _FakeDb:
    rolled_back = 0

    def execute(self, *a, **k):
        return _Result()

    def connection(self):
        raise RuntimeError("no connection in this test")

    def rollback(self):
        self.rolled_back += 1


def test_an_unreadable_job_list_says_so_and_the_page_still_answers(monkeypatch):
    def broken(db, tier, hours):
        raise RuntimeError("relation sync_runs does not exist")

    monkeypatch.setattr(sync_status, "_jobs", broken)
    db = _FakeDb()
    h = sync_status.get_sync_health(db)
    assert h["jobs"]["daily"]["healthy"] is None and "RuntimeError" in h["jobs"]["daily"]["error"]
    assert db.rolled_back == 1 and "tiers" in h


def test_the_route_reports_every_judged_tier(monkeypatch):
    monkeypatch.setattr(sync_status, "_jobs", lambda db, tier, hours: judge_jobs([row("cor")], NOW, hours))
    h = sync_status.get_sync_health(_FakeDb())
    assert set(h["jobs"]) == set(sync_status._JOB_STALE_AFTER_HOURS) and h["jobs"]["daily"]["stale_after_hours"] == 36


@pytest.mark.live
def test_the_query_runs_on_the_real_ledger():
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        j = sync_status._jobs(db, "daily", 36)
    finally:
        db.rollback()
        db.close()
    assert j["count"] > 0 and {"failing", "stale", "degraded", "retired", "detail"} <= set(j)
    assert all(d["last_status"] for d in j["detail"])
