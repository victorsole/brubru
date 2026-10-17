"""/api/sync/health judges each nightly job by name (17 Oct 2026).

The tier line averaged its jobs: `tris_titles` failed on its first run while `daily` read
healthy (1 failure in 51 runs), and a job dropped from the schedule writes no row, so
nothing could turn red for it. `jobs.daily` lists each job with `failing` and `stale`.

The audit of the same day: a stopped job dropped off a 30-day window, a 6-hourly job was
judged at 36 hours, degraded could last for ever, `failures_7d` counted 'failed' only, `tbt`
was recorded twice per run, and nothing mailed anyone. Each has a test below.
"""
import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api import cron, sync_status
from api.sync_status import judge_jobs

BACKEND = Path(__file__).resolve().parents[1]

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


def row(key, status="success", hours_ago=7, error=None, runs=7, fails=0, success_days_ago=None, first_days_ago=60):
    t = NOW - timedelta(hours=hours_ago)
    if success_days_ago is not None:
        ok = NOW - timedelta(days=success_days_ago)
    else:
        ok = t if status in ("success", "ok") else None
    return {"source_key": key, "last_status": status, "last_error": error, "last_run": t,
            "first_run": NOW - timedelta(days=first_days_ago),
            "last_success": ok, "runs_7d": runs, "failures_7d": fails}


def test_a_failed_job_turns_the_tier_red_whatever_the_others_do():
    j = judge_jobs([row(f"ok_{i}") for i in range(50)] + [row("tris_titles", "failed", error="rc=1: boom")], NOW, 36)
    assert j["healthy"] is False and j["failing"] == ["tris_titles"] and j["count"] == 51
    assert j["detail"][0]["job"] == "tris_titles" and j["detail"][0]["error"] == "rc=1: boom"


def test_a_job_that_stopped_running_is_stale():
    j = judge_jobs([row("eu_laws_in_force", hours_ago=40), row("consultations")], NOW, 36)
    assert j["stale"] == ["eu_laws_in_force"] and j["failing"] == [] and j["healthy"] is False


def test_degraded_is_listed_and_red_only_once_it_lasts():
    fresh = judge_jobs([row("jrc", "degraded", error="walk not finished", success_days_ago=3), row("cor")], NOW, 36)
    assert fresh["degraded"] == ["jrc"] and fresh["degraded_too_long"] == [] and fresh["healthy"] is True
    assert fresh["detail"][0]["error"] == "walk not finished"
    old = judge_jobs([row("jrc", "degraded", error="walk not finished", success_days_ago=8), row("cor")], NOW, 36)
    assert old["degraded_too_long"] == ["jrc"] and old["healthy"] is False
    assert old["detail"][0]["degraded_too_long"] == "no success in 7 days"


def test_a_job_degraded_since_its_first_run_counts_from_that_run():
    never = row("sanctions_oj_delta", "degraded", error="gap", first_days_ago=15)
    assert judge_jobs([never], NOW, 36)["degraded_too_long"] == ["sanctions_oj_delta"]
    new = row("sanctions_oj_delta", "degraded", error="gap", first_days_ago=2)
    assert judge_jobs([new], NOW, 36)["degraded_too_long"] == []


def test_a_job_may_have_its_own_degraded_limit():
    walk = row("comitology", "degraded", error="stopped at page 674", success_days_ago=8)
    assert judge_jobs([walk], NOW, 36, degraded_days_by_job={"comitology": 21})["healthy"] is True
    walk = row("comitology", "degraded", error="stopped at page 674", success_days_ago=22)
    assert judge_jobs([walk], NOW, 36, degraded_days_by_job={"comitology": 21})["healthy"] is False


def test_an_accepted_reason_is_listed_and_another_reason_is_judged():
    accepted = {"tenderator_translations_ted": ("no translation engine", "credits spent")}
    j = judge_jobs([row("tenderator_translations_ted", "degraded", error="1583 rows: no translation engine here",
                        success_days_ago=None, first_days_ago=30)], NOW, 36, accepted=accepted)
    assert j["accepted"] == ["tenderator_translations_ted"] and j["healthy"] is True
    assert j["detail"][0]["accepted"] == "credits spent"
    other = judge_jobs([row("tenderator_translations_ted", "degraded", error="database locked",
                            first_days_ago=30)], NOW, 36, accepted=accepted)
    assert other["accepted"] == [] and other["degraded_too_long"] == ["tenderator_translations_ted"]


def test_the_sanctions_marker_accepts_no_fetch_failure_only():
    marker = sync_status._ACCEPTED_DEGRADED["sanctions_oj_delta"][0]
    msg = "Commission consolidated list newest act 2026-07-23; OJ newest {0}; 32 regulations, 32 fetched, {1} fetch failures, 3 with"
    assert marker in msg.format("2026-10-15", 0)
    assert marker not in msg.format("2026-10-15", 10) and marker not in msg.format("2026-10-15", 2)


def test_a_job_that_runs_more_often_has_its_own_stale_limit():
    j = judge_jobs([row("eu_laws_cellar", hours_ago=14), row("cor", hours_ago=14)], NOW, 36,
                   stale_by_job={"eu_laws_cellar": 13})
    assert j["stale"] == ["eu_laws_cellar"]
    assert {d["job"]: d["stale_after_hours"] for d in j["detail"]} == {"eu_laws_cellar": 13, "cor": 36}


def test_the_configured_limits_name_the_jobs_that_need_them():
    assert sync_status._JOB_STALE_AFTER_HOURS_BY_JOB["eu_laws_cellar"] < 24
    assert sync_status._JOB_DEGRADED_DAYS_BY_JOB["comitology"] > sync_status._JOB_DEGRADED_DAYS
    assert "tbt" in sync_status._RETIRED_JOBS


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


class _CaptureDb(_FakeDb):
    def __init__(self):
        self.calls = []

    def execute(self, stmt, params=None, *a, **k):
        self.calls.append((str(stmt), params))
        return _Result()


def test_the_query_reads_every_run_not_a_recent_window():
    db = _CaptureDb()
    sync_status._jobs(db, "daily", 36)
    sql, params = db.calls[0]
    assert params == {"tier": "daily"} and "make_interval" not in sql and "days" not in params
    # a failure is any status but success/ok/degraded, as in `failing`
    assert "NOT IN ('success', 'ok', 'degraded')" in sql and "min(started_at)" in sql


def _daily_scripts():
    tree = ast.parse((BACKEND / "api" / "cron.py").read_text())
    fn = next(n for n in tree.body if getattr(n, "name", "") == "cron_sync_daily")
    out = {}
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_run_script_async"
                and len(n.args) >= 2 and all(isinstance(a, ast.Constant) for a in n.args[:2])):
            out[n.args[0].value] = n.args[1].value
    return out


def test_no_job_the_tier_records_also_records_itself():
    """A job here whose script writes its own row gets two rows per run (tbt and wto_tbt until 17 Oct 2026)."""
    scripts = _daily_scripts()
    for key in cron._DAILY_TIER_RECORDED:
        if key not in scripts:
            continue
        body = (BACKEND / scripts[key]).read_text()
        assert not re.search(r"\b(record_run|_record_simple)\(", body), f"{key}: {scripts[key]} records itself"
    assert "tbt" not in cron._DAILY_TIER_RECORDED and "tbt" in scripts


def _verdict(**lists):
    detail = [{"job": j, "last_status": "failed", "error": "<boom>", "last_run": "2026-10-15T02:00:00+00:00",
               "stale_after_hours": 36, "degraded_too_long": "no success in 7 days", "last_success": None}
              for v in lists.values() for j in v]
    return {"healthy": not any(lists.values()), "failing": [], "stale": [], "degraded_too_long": [], **lists,
            "detail": detail}


def test_a_healthy_verdict_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr("services.email_service.EmailService.send", lambda self, **k: sent.append(k) or True)
    cron._send_jobs_alert(_verdict())
    cron._send_jobs_alert({"healthy": None, "detail": []})
    assert sent == []


def test_a_job_that_needs_a_look_is_mailed_with_its_reason(monkeypatch):
    sent = []
    monkeypatch.setattr("services.email_service.EmailService.send", lambda self, **k: sent.append(k) or True)
    monkeypatch.setattr(cron.settings, "ALERT_EMAIL", "ops@example.org", raising=False)
    cron._send_jobs_alert(_verdict(failing=["tris_titles"], stale=["eu_laws_cellar"], degraded_too_long=["jrc"]))
    assert len(sent) == 1 and sent[0]["to"] == "ops@example.org"
    assert sent[0]["subject"] == "[Brubru] 3 nightly job(s) need a look"
    body = sent[0]["html_body"]
    assert "tris_titles" in body and "eu_laws_cellar" in body and "jrc" in body
    assert "&lt;boom&gt;" in body and "<boom>" not in body


def test_a_failed_job_that_is_also_stale_is_listed_once():
    subject, body = cron._jobs_alert(_verdict(failing=["tris_titles"], stale=["tris_titles"]))
    assert subject == "[Brubru] 1 nightly job(s) need a look" and body.count("tris_titles") == 1


def test_the_daily_tier_mails_after_it_records():
    src = (BACKEND / "api" / "cron.py").read_text()
    fn = src[src.index("async def cron_sync_daily("):src.index("# Economy folders (economy_items)")]
    assert fn.index("record_run(_db, source_key=_key") < fn.index("_send_jobs_alert(daily_jobs_verdict(_db))")


@pytest.mark.live
def test_the_query_runs_on_the_real_ledger():
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        j = sync_status._jobs(db, "daily", 36)
    finally:
        db.rollback()
        db.close()
    assert j["count"] > 0 and {"failing", "stale", "degraded", "degraded_too_long", "accepted", "retired",
                                "detail"} <= set(j)
    assert all(d["last_status"] for d in j["detail"])


@pytest.mark.live
def test_failures_7d_matches_a_count_made_another_way():
    from sqlalchemy import text
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        j = sync_status._jobs(db, "daily", 36)
        rows = db.execute(text("SELECT source_key, status FROM sync_runs WHERE tier = 'daily' "
                               "AND runner IS DISTINCT FROM 'local' AND started_at > now() - interval '7 days'")).all()
    finally:
        db.rollback()
        db.close()
    counted = {}
    for key, status in rows:
        counted[key] = counted.get(key, 0) + (status not in ("success", "ok", "degraded"))
    assert {d["job"]: d["failures_7d"] for d in j["detail"] if d["runs_7d"]} == counted
