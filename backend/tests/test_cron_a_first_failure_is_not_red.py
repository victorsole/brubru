"""A source's first failure does not make the cron run red (14 October 2026).

In the 7 days to 14 Oct the hourly run went red, and Railway mailed "Deploy crashed", in
35 hours; 16 of them were one failure the same source's next run did not repeat: a page
that hung once (EIT, EEAS, EU GovTech) or an EU site briefly down (EP Open Data, eMeeting,
the RegDel and COM registers). Red now means the same source failed twice in a row, or
failed with no good run for a day and a half. The economy bodies, killed at 600 s with no
word on what they were doing, now stop themselves at a time budget, keep what they stored
and say where they stopped; two such stops in a row are red as well.
"""
import asyncio
import pathlib
import sys
import time

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import cron_dispatch as cd  # noqa: E402

NOW = "2026-10-14T13:52:00+00:00"
MARK = "2026-10-14T12:55:00+00:00"


def _row(key, status, *, previous_problem=False, last_good_at="2026-10-14T05:00:00+00:00", problem=None):
    """A ledger row as the backend now returns it, with the source's history."""
    if problem is None:
        problem = status not in cd.OK_STATUSES
    return {"source_key": key, "status": status, "started_at": "2026-10-14T13:05:00+00:00",
            "finished_at": "2026-10-14T13:30:00+00:00", "problem": problem,
            "previous_problem": previous_problem, "last_good_at": last_good_at}


def _ledger(rows):
    runs = list(rows) + [{"source_key": cd.JUDGED_KEY, "status": "ok", "started_at": MARK, "finished_at": MARK}]
    return {"runs": runs, "now": NOW, "in_flight": [], "completed": {}, "in_flight_seconds": {}}


def _verdict(rows):
    first = []
    failures, _ = cd._judge_ledger(_ledger(rows), first)
    return failures, first


def test_a_first_failure_is_reported_but_not_red():
    failures, first = _verdict([_row("economy_eugovtech", "failed")])
    assert failures == [] and first == ["economy_eugovtech=failed"]


def test_the_same_source_failing_twice_in_a_row_is_red():
    failures, first = _verdict([_row("ep_amendments", "failed", previous_problem=True)])
    assert failures == ["ep_amendments=failed (twice in a row)"] and first == []


def test_a_failure_with_no_good_run_for_a_day_and_a_half_is_red():
    # A weekly source: its previous run was fine, but a week ago.
    failures, _ = _verdict([_row("weekly_source", "failed", last_good_at="2026-10-07T05:00:00+00:00")])
    assert failures == ["weekly_source=failed (no good run for 177h)"]
    failures, _ = _verdict([_row("brand_new", "failed", previous_problem=None, last_good_at=None)])
    assert failures == ["brand_new=failed (no good run on record)"]
    # 30 hours is inside the limit: a daily source gets its retry first.
    failures, first = _verdict([_row("daily_source", "failed", last_good_at="2026-10-13T07:52:00+00:00")])
    assert failures == [] and first == ["daily_source=failed"]


def test_a_stop_at_the_time_budget_is_red_only_the_second_time():
    once = _row("economy_eit", "degraded", problem=True)
    assert _verdict([once]) == ([], ["economy_eit=degraded"])
    twice = _row("economy_eit", "degraded", problem=True, previous_problem=True)
    assert _verdict([twice])[0] == ["economy_eit=degraded (twice in a row)"]


def test_an_auditor_reporting_gaps_is_still_fine_however_often():
    # previous_problem is about failures and budget stops; an auditor's degraded is neither.
    assert _verdict([_row("scraper_health", "degraded", problem=False, previous_problem=False)]) == ([], [])


def test_a_row_without_the_history_is_judged_the_old_way():
    """Backend and dispatcher deploy separately: an older backend's rows carry no history,
    and their failures stay red rather than pass unseen."""
    old = {"source_key": "oj", "status": "failed", "started_at": "2026-10-14T13:05:00+00:00",
           "finished_at": "2026-10-14T13:30:00+00:00"}
    assert _verdict([old]) == (["oj=failed"], [])


@pytest.fixture()
def one_tier(monkeypatch):
    monkeypatch.setattr(cd, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(cd, "decide_tiers", lambda now: [("daily", "/api/cron/sync/daily")])
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started, endpoints=None: ([], []))


def _exit(fn):
    with pytest.raises(SystemExit) as e:
        fn()
    return e.value.code


def test_a_job_failing_in_a_payload_is_left_to_its_ledger_row(monkeypatch, one_tier, capsys):
    monkeypatch.setattr(cd, "_fire", lambda endpoint, timeout=1800: (
        {"status": "success"} if "/heartbeat" in endpoint
        else {"tier": "daily", "ran": {"consultations": "success", "tris": "failed"}}))
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([_row("tris", "failed")]))
    assert _exit(cd.main) == 0
    assert "FIRST FAILURES (recorded, not red" in capsys.readouterr().out
    # The same failure a second time is red, from the ledger.
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([_row("tris", "failed", previous_problem=True)]))
    assert _exit(cd.main) == 1
    # A payload failure with no ledger row to judge it by stays red.
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([]))
    assert _exit(cd.main) == 1


def test_a_quiet_hour_reports_a_first_failure_without_going_red(monkeypatch, capsys):
    monkeypatch.setattr(cd, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(cd, "decide_tiers", lambda now: [])
    monkeypatch.setattr(cd, "_fire", lambda endpoint, timeout=1800: {"status": "success"})
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([_row("com_register", "failed")]))
    assert _exit(cd.main) == 0
    assert "com_register=failed" in capsys.readouterr().out


# --------------------------------------------------------------------------- the backend
class _Rows:
    def __init__(self, rows, now):
        self.rows, self.now, self.params = rows, now, None

    def execute(self, sql, params=None):
        if params is not None:
            self.params = params
        rows, now = self.rows, self.now

        class _R:
            def mappings(self):
                return self

            def all(self):
                return rows

            def scalar(self):
                return now
        return _R()

    def close(self):
        pass


def test_runs_since_gives_each_row_its_sources_history(monkeypatch):
    import datetime as dt

    import api.cron as cron
    from services.sync.freshness import BUDGET_STOP
    t = dt.datetime(2026, 10, 14, 11, 58, tzinfo=dt.timezone.utc)
    db = _Rows([{"source_key": "economy_eugovtech", "tier": "economy_b2", "status": "failed",
                 "started_at": t, "finished_at": t, "problem": True, "previous_problem": False,
                 "last_good_at": t - dt.timedelta(hours=6)}], t)
    monkeypatch.setattr(cron, "SessionLocal", lambda: db)
    monkeypatch.setattr(cron, "_verify_cron_secret", lambda a: None)
    out = asyncio.run(cron.cron_runs_since(minutes=60, authorization="x"))
    row = out["runs"][0]
    assert row["problem"] is True and row["previous_problem"] is False
    assert row["last_good_at"] == "2026-10-14T05:58:00+00:00"
    assert db.params == {"m": 60, "budget": BUDGET_STOP}
    # ...and the dispatcher reads that row as a first failure.
    assert cd._judge_row(row, t) == ("first", "economy_eugovtech=failed")


def test_an_economy_body_stopped_at_its_budget_is_recorded_degraded(monkeypatch):
    import api.cron as cron
    import services.sync.freshness as fr
    recorded, calls = [], []

    async def fake_script(name, script, args=None, timeout=600):
        calls.append((name, list(args or []), timeout))
        if name == "economy_eit":
            return {"status": "degraded", "stderr_tail": "time budget reached (590s) during eit/news"}
        return {"status": "success"}

    monkeypatch.setattr(cron, "_run_script_async", fake_script)
    monkeypatch.setattr(cron, "SessionLocal", lambda: _Rows([], None))
    monkeypatch.setattr(fr, "record_run", lambda db, **kw: recorded.append(kw))
    asyncio.run(cron._run_economy_batch_bg(1, ["eba", "eit"]))
    body = {r["source_key"]: r for r in recorded}
    assert body["economy_eba"]["status"] == "success"
    assert body["economy_eit"]["status"] == "degraded"
    assert body["economy_eit"]["error"].startswith(fr.BUDGET_STOP)
    assert body["cron_dispatch"]["status"] == "degraded"
    name, args, timeout = calls[0]
    assert args[-2:] == ["--max-seconds", str(cron.ECONOMY_BODY_SECONDS)] and timeout > cron.ECONOMY_BODY_SECONDS


# --------------------------------------------------------------------------- sync_economy
def test_the_budget_cuts_a_page_that_hangs_even_inside_a_broad_except():
    from scripts import sync_economy as se

    def hung_page():
        try:
            time.sleep(30)
        except Exception:  # what scrapers do around a page
            pass
        return "carried on"

    t0 = time.monotonic()
    with pytest.raises(se._OutOfTime):
        with se._deadline(0.5):
            hung_page()
    assert time.monotonic() - t0 < 5


def test_the_run_keeps_what_it_stored_and_names_where_it_stopped(monkeypatch):
    from scripts import sync_economy as se
    monkeypatch.setattr(se, "_MIN_START_SECONDS", 0)

    class _Db:
        rollbacks = 0

        def rollback(self):
            self.rollbacks += 1

    def run_one(body, itype):
        if itype == "slow":
            time.sleep(30)
        if itype == "broken":
            raise RuntimeError("listing changed")
        return 3

    db = _Db()
    targets = [("eit", "news"), ("eit", "broken"), ("eit", "slow"), ("eit", "event")]
    total, stopped, not_started = se._run_targets(db, targets, run_one, 1.5)
    assert (total, stopped, not_started) == (3, "eit/slow", ["eit/event"])
    assert db.rollbacks == 2
    assert se._run_targets(db, [("eit", "news")], run_one, None) == (3, None, [])


def test_a_stopped_run_through_the_real_runner_is_degraded_and_leaves_no_child(tmp_path):
    """End to end through api.cron._run_script: the script starts a child that holds its
    stdout (as Chromium does), hangs, stops at its budget, ends the child and reports
    degraded. Without the child's end the runner waits for the pipe until its kill."""
    from api.cron import _run_script
    script = tmp_path / "hang.py"
    script.write_text(
        "import subprocess, sys, time\n"
        f"sys.path.insert(0, {str(BACKEND)!r})\n"
        "from scripts import sync_economy as se\n"
        "se._MIN_START_SECONDS = 0\n"
        "child = subprocess.Popen(['sleep', '300'])\n"
        "class Db:\n"
        "    def rollback(self): pass\n"
        "total, stopped, rest = se._run_targets(Db(), [('eit', 'news'), ('eit', 'event')],\n"
        "                                       lambda b, t: time.sleep(300), 1.0)\n"
        "se._end_children()\n"
        "print(f'[SYNC_STATUS] degraded: time budget reached during {stopped}; not started: {rest}')\n")
    t0 = time.monotonic()
    res = _run_script("hang", str(script), timeout=40)
    assert time.monotonic() - t0 < 30, "the runner waited on an orphan's pipe"
    assert res["status"] == "degraded", res
    assert "eit/news" in res["stderr_tail"] and "eit/event" in res["stderr_tail"]


def test_a_refused_undated_item_is_never_red():
    # 19 Oct 2026: EDPS's new undatable item was judged "twice in a row" against a refusal row
    # of other items; and a refusal after a quiet spell had "no good run" for days.
    for row in (_row("economy_edps_undated_refused", "failed", previous_problem=True),
                _row("economy_satcen_undated_refused", "failed", last_good_at="2026-10-10T03:00:00+00:00"),
                _row("news_dg_undated_refused", "failed", last_good_at=None)):
        assert cd._judge_row(row, None) == ("first", f"{row['source_key']}=failed")
    # The same history on a real job is still red.
    assert cd._judge_row(_row("economy_edps", "failed", previous_problem=True), None)[0] == "red"
