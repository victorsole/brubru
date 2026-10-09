"""What makes the Railway cron job red (23 September 2026).

Since 22 Sep the dispatcher exits non-zero when a job fails, so Railway shows the run red
instead of a green log nobody reads. It then went red on EVERY run and mailed a crash each
hour, because it waited on the tier over its own connection and Railway's edge closes a
request at ~300 seconds while every real tier runs far longer (fast 1,317s, warm 728s,
daily 1,242s, economy 1,778s, measured on 23 Sep). The 502 was counted as a failed tier.

The backend keeps working after the caller goes away, so a cut connection means "still
running". The dispatcher now marks it `detached` and takes its verdict from the ledger the
container writes, which is the only place that says what the scrapers actually did.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import cron_dispatch as cd  # noqa: E402


@pytest.fixture()
def one_tier(monkeypatch):
    """One tier due, a heartbeat that answers, and no real network."""
    monkeypatch.setattr(cd, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(cd, "BACKEND_URL", "https://backend.invalid")
    monkeypatch.setattr(cd, "decide_tiers", lambda now: [("fast", "/api/cron/sync/tier/fast")])
    monkeypatch.setattr(cd, "POLL_SECONDS", 0)
    fired = {}

    def fake_fire(endpoint, timeout=1800):
        fired[endpoint] = timeout
        if endpoint.endswith("/heartbeat"):
            return {"status": "success"}
        return {"status": cd.DETACHED, "http_code": 502}

    monkeypatch.setattr(cd, "_fire", fake_fire)
    # The ledger read at the end of the run: empty unless a test says what the tier did.
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([]))
    return fired


NOW = "2026-10-09T13:52:00+00:00"
MARK = "2026-10-09T12:55:00+00:00"   # the previous run's verdict


def _ledger(rows, *, finished="2026-10-09T13:30:00+00:00", mark=MARK, in_flight_seconds=None):
    """What /runs-since returns: rows stamped as finished after the previous verdict."""
    runs = [{"started_at": "2026-10-09T13:05:00+00:00", "finished_at": finished, **r} for r in rows]
    if mark:
        runs.append({"source_key": cd.JUDGED_KEY, "status": "ok", "started_at": mark, "finished_at": mark})
    return {"runs": runs, "now": NOW, "in_flight": [], "completed": {},
            "in_flight_seconds": in_flight_seconds or {}}


def _tier_ran(monkeypatch, rows, unfinished=()):
    """The tier recorded `rows`: the wait sees them and so does the ledger verdict."""
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started, endpoints=None: (list(rows), list(unfinished)))
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger(rows))


def _exit_code(fn):
    with pytest.raises(SystemExit) as e:
        fn()
    return e.value.code


def test_a_cut_connection_with_a_clean_ledger_is_green(monkeypatch, one_tier):
    _tier_ran(monkeypatch, [
        {"source_key": "news_dg", "status": "success"},
        {"source_key": "oj", "status": "success"},
        {"source_key": "cron_dispatch", "status": "ok"},
        {"source_key": "council_docs", "status": "skipped"},
    ])
    assert _exit_code(cd.main) == 0
    # and it no longer sits on a connection the edge will cut anyway
    assert one_tier["/api/cron/sync/tier/fast"] == cd.EDGE_TIMEOUT


def test_a_cut_connection_with_a_failed_source_is_red(monkeypatch, one_tier):
    _tier_ran(monkeypatch, [
        {"source_key": "news_dg", "status": "success"},
        {"source_key": "oj_acts_ca", "status": "failed"},
    ])
    assert _exit_code(cd.main) == 1


def test_an_audit_source_reporting_gaps_is_not_a_failure(monkeypatch, one_tier):
    """`degraded` is an auditor exiting non-zero to report what it found. Counting it
    would paint every run red for ever, which is how a red build stops meaning anything."""
    _tier_ran(monkeypatch, [
        {"source_key": "news_dg", "status": "success"},
        {"source_key": "scraper_health", "status": "degraded"},
    ])
    assert _exit_code(cd.main) == 0


def test_a_tier_that_recorded_nothing_at_all_is_red(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started, endpoints=None: ([], []))
    assert _exit_code(cd.main) == 1


def test_an_unreadable_ledger_is_red(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started, endpoints=None: (None, []))
    assert _exit_code(cd.main) == 1


def test_a_tier_that_answers_in_time_is_still_judged_on_its_payload(monkeypatch):
    """The short endpoints still return a payload, and a job failing inside a 200 stays
    red: that was the 19-22 Sep outage, where every child died and the run logged ok."""
    monkeypatch.setattr(cd, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(cd, "decide_tiers", lambda now: [("daily", "/api/cron/sync/daily")])
    monkeypatch.setattr(cd, "_fire", lambda endpoint, timeout=1800: (
        {"status": "success"} if endpoint.endswith("/heartbeat")
        else {"tier": "daily", "ran": {"consultations": "success", "tris": "failed"}}))

    def _boom(started, endpoints=None):
        raise AssertionError("nothing was detached; the ledger must not be consulted")

    monkeypatch.setattr(cd, "_wait_for_detached", _boom)
    assert _exit_code(cd.main) == 1


def test_the_wait_ends_on_what_is_in_flight_not_on_a_quiet_ledger(monkeypatch):
    """A quiet ledger is a slow job as often as a finished tier: a row is written when a
    source FINISHES, and votes_ep alone worked for 418s on 23 Sep while writing nothing.
    Waiting on silence declared the tier over mid-run and would have judged it green on
    half its sources. The wait ends when the backend says nothing is in flight."""
    monkeypatch.setattr(cd, "POLL_SECONDS", 0)
    a = {"source_key": "news_dg", "status": "success"}
    b = {"source_key": "votes_ep", "status": "failed"}
    pages = [
        {"in_flight": ["/api/cron/sync/tier/fast"], "runs": [a]},
        {"in_flight": ["/api/cron/sync/tier/fast"], "runs": [a]},   # seven silent minutes
        {"in_flight": ["/api/cron/sync/tier/fast"], "runs": [a]},
        {"in_flight": ["/api/cron/sync/tier/fast"], "runs": [a]},
        {"in_flight": [], "runs": [a, b]},                          # now it has ended
    ]
    calls = {"n": 0}

    def fake_status(minutes):
        calls["n"] += 1
        return pages[min(calls["n"] - 1, len(pages) - 1)]

    monkeypatch.setattr(cd, "_status_since", fake_status)
    import time as _t
    runs, unfinished = cd._wait_for_detached(_t.time())
    assert calls["n"] == 5                       # it did not stop during the silence
    assert [r["source_key"] for r in runs] == ["news_dg", "votes_ep"]
    assert any(r["status"] == "failed" for r in runs)  # the late failure is still seen


def test_an_unreadable_status_does_not_end_the_wait(monkeypatch):
    monkeypatch.setattr(cd, "POLL_SECONDS", 0)
    seq = [None, None, {"in_flight": [], "runs": [{"source_key": "a", "status": "success"}]}]
    calls = {"n": 0}

    def fake_status(minutes):
        calls["n"] += 1
        return seq[min(calls["n"] - 1, len(seq) - 1)]

    monkeypatch.setattr(cd, "_status_since", fake_status)
    import time as _t
    assert [r["source_key"] for r in cd._wait_for_detached(_t.time())[0]] == ["a"]
    assert calls["n"] == 3


# --------------------------------------------------------------------------- the backend side
def _run_dependency(path):
    """Drive the yield dependency the way FastAPI does, and report what it marked."""
    import asyncio

    from api.cron import _IN_FLIGHT, _track_cron_activity

    class _Req:
        def __init__(self, p):
            self.url = type("U", (), {"path": p})()

    async def drive():
        gen = _track_cron_activity(_Req(path))
        await gen.__anext__()
        during = sorted(k.split("#")[0] for k in _IN_FLIGHT)
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
        return during, sorted(k.split("#")[0] for k in _IN_FLIGHT)

    return asyncio.run(drive())


def test_a_cron_call_is_marked_in_flight_while_it_runs():
    during, after = _run_dependency("/api/cron/sync/tier/fast")
    assert during == ["/api/cron/sync/tier/fast"]
    assert after == []  # released even though the caller was long gone


def test_the_two_read_endpoints_are_not_work():
    """The dispatcher's own heartbeat and its status read must not look like a tier
    still running, or the wait would never end."""
    for path in ("/api/cron/heartbeat", "/api/cron/runs-since"):
        during, after = _run_dependency(path)
        assert during == [] and after == []


def test_a_tier_killed_by_a_deploy_is_not_green(monkeypatch, one_tier):
    """A deploy replaces the web container and the tier simply stops: the 15:00 economy
    tier of 23 Sep died after 6 of its 28 sources when another session pushed. Nothing is
    then in flight and every recorded row is a success, so only the backend's own record
    of having REACHED THE END can tell a finished tier from a truncated one. That record
    lives in the process and dies with it."""
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started, endpoints=None: (
        [{"source_key": "economy_eea", "status": "success"},
         {"source_key": "economy_efca", "status": "success"}],
        ["/api/cron/sync/tier/fast"]))
    assert _exit_code(cd.main) == 1


def test_the_end_record_must_be_from_this_run(monkeypatch):
    """A `completed` entry older than the fire is the PREVIOUS run's; it must not pass."""
    monkeypatch.setattr(cd, "POLL_SECONDS", 0)
    import time as _t
    started = _t.time() - 120  # the tier was fired two minutes ago
    monkeypatch.setattr(cd, "_status_since", lambda minutes: {
        "in_flight": [],
        "completed": {"/api/cron/sync/economy": {"seconds_ago": 4000.0, "ok": True}},
        "runs": [{"source_key": "economy_eea", "status": "success"}],
    })
    runs, unfinished = cd._wait_for_detached(started, ["/api/cron/sync/economy?batch=1"])
    assert unfinished == ["/api/cron/sync/economy"]
    monkeypatch.setattr(cd, "_status_since", lambda minutes: {
        "in_flight": [],
        "completed": {"/api/cron/sync/economy": {"seconds_ago": 30.0, "ok": True}},
        "runs": [{"source_key": "economy_eea", "status": "success"}],
    })
    runs, unfinished = cd._wait_for_detached(started, ["/api/cron/sync/economy?batch=1"])
    assert unfinished == []


# --- judged late (9 Oct 2026) -------------------------------------------------------------
# The warm tier needs 60-79 minutes against the 50-minute wait. "Still working at the
# deadline" mailed "Deploy crashed" after every warm run while no source had failed.

def test_a_tier_still_working_at_the_deadline_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(cd, "POLL_SECONDS", 0)
    monkeypatch.setattr(cd, "MAX_WAIT_SECONDS", 0.05)
    import time as _t
    started = _t.time()
    monkeypatch.setattr(cd, "_status_since", lambda minutes: {
        "in_flight": ["/api/cron/sync/tier/warm"], "completed": {},
        "runs": [{"source_key": "texts_adopted", "status": "success"}]})
    runs, unfinished = cd._wait_for_detached(started, ["/api/cron/sync/tier/warm"])
    assert unfinished == []
    assert [r["source_key"] for r in runs] == ["texts_adopted"]


def test_a_tier_neither_in_flight_nor_finished_at_the_deadline_was_cut(monkeypatch):
    """A deploy mid-tier: nothing in flight, no end recorded. Still a failure."""
    monkeypatch.setattr(cd, "POLL_SECONDS", 0)
    monkeypatch.setattr(cd, "MAX_WAIT_SECONDS", 0.05)
    import time as _t
    started = _t.time()
    # warm still working at the deadline; fast neither in flight nor finished: it was cut.
    monkeypatch.setattr(cd, "_status_since", lambda minutes: {
        "in_flight": ["/api/cron/sync/tier/warm"], "completed": {}, "runs": []})
    _, unfinished = cd._wait_for_detached(started, ["/api/cron/sync/tier/fast", "/api/cron/sync/tier/warm"])
    assert unfinished == ["/api/cron/sync/tier/fast"]


def test_the_ledger_judges_only_what_finished_since_the_last_verdict():
    led = _ledger([{"source_key": "old_failure", "status": "failed"}], finished="2026-10-09T12:40:00+00:00")
    assert cd._judge_ledger(led) == ([], NOW)          # judged by the previous run already
    led = _ledger([{"source_key": "tail_failure", "status": "failed"}], finished="2026-10-09T13:10:00+00:00")
    assert cd._judge_ledger(led) == (["tail_failure=failed"], NOW)
    led = _ledger([{"source_key": "after_the_read", "status": "failed"}], finished="2026-10-09T13:53:00+00:00")
    assert cd._judge_ledger(led)[0] == []               # the next run's, not this one's


def test_the_latest_mark_is_the_cursor():
    led = _ledger([{"source_key": "x", "status": "failed"}], finished="2026-10-09T13:00:00+00:00")
    led["runs"].append({"source_key": cd.JUDGED_KEY, "status": "ok",
                        "started_at": "2026-10-09T13:20:00+00:00", "finished_at": "2026-10-09T13:20:00+00:00"})
    assert cd._judge_ledger(led)[0] == []


def test_without_a_mark_the_first_run_looks_back_a_fixed_window():
    led = _ledger([{"source_key": "recent", "status": "failed"}], finished="2026-10-09T13:00:00+00:00", mark=None)
    assert cd._judge_ledger(led)[0] == ["recent=failed"]
    led = _ledger([{"source_key": "ancient", "status": "failed"}], finished="2026-10-09T11:00:00+00:00", mark=None)
    assert cd._judge_ledger(led)[0] == []


def test_a_call_in_flight_for_hours_is_hung():
    led = _ledger([], in_flight_seconds={"/api/cron/sync/tier/warm": 3 * 3600 + 1,
                                         "/api/cron/sync/tier/fast": 1200})
    assert cd._judge_ledger(led)[0] == ["/api/cron/sync/tier/warm=in flight for 3.0h (hung)"]


def test_an_unreadable_ledger_is_a_failure_and_records_no_mark():
    assert cd._judge_ledger(None) == (["runs-since=unreadable"], None)


def test_a_quiet_hour_still_judges_the_tail_of_an_earlier_tier(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "decide_tiers", lambda now: [])
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([{"source_key": "regdel_acts", "status": "failed"}]))
    assert _exit_code(cd.main) == 1
    assert any(e.startswith("/api/cron/heartbeat?judged_at=") for e in one_tier)
    monkeypatch.setattr(cd, "_status_since", lambda minutes: _ledger([{"source_key": "regdel_acts", "status": "success"}]))
    assert _exit_code(cd.main) == 0


def test_every_run_records_its_verdict_at_the_database_clock(monkeypatch, one_tier):
    _tier_ran(monkeypatch, [{"source_key": "news_dg", "status": "success"}])
    assert _exit_code(cd.main) == 0
    marks = [e for e in one_tier if e.startswith("/api/cron/heartbeat?judged_at=")]
    assert marks == ["/api/cron/heartbeat?judged_at=" + cd.urllib.parse.quote(NOW)]


class _FakeDB:
    def __init__(self, now):
        self.now = now

    def execute(self, *a, **k):
        now = self.now

        class _R:
            def mappings(self):
                return self

            def all(self):
                return []

            def scalar(self):
                return now
        return _R()

    def close(self):
        pass


def test_runs_since_gives_the_database_clock_and_how_long_each_call_has_run(monkeypatch):
    import asyncio
    import datetime as dt
    import time as _t
    import api.cron as cron
    now = dt.datetime(2026, 10, 9, 13, 52, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(cron, "SessionLocal", lambda: _FakeDB(now))
    monkeypatch.setattr(cron, "_verify_cron_secret", lambda a: None)
    monkeypatch.setitem(cron._IN_FLIGHT, "/api/cron/sync/tier/warm#1", _t.time() - 3700)
    out = asyncio.run(cron.cron_runs_since(minutes=60, authorization="x"))
    assert out["now"] == now.isoformat()
    assert 3699 < out["in_flight_seconds"]["/api/cron/sync/tier/warm"] < 3800


def test_the_heartbeat_records_the_verdict_mark_at_the_given_instant(monkeypatch):
    import asyncio
    import datetime as dt
    import api.cron as cron
    import services.sync.freshness as fr
    calls = []
    monkeypatch.setattr(cron, "SessionLocal", lambda: _FakeDB(None))
    monkeypatch.setattr(cron, "_verify_cron_secret", lambda a: None)
    monkeypatch.setattr(fr, "record_run", lambda db, **kw: calls.append(kw))
    asyncio.run(cron.cron_heartbeat(authorization="x", judged_at="2026-10-09T13:52:00+00:00"))
    at = dt.datetime(2026, 10, 9, 13, 52, tzinfo=dt.timezone.utc)
    assert calls == [{"source_key": "cron_judged", "tier": "heartbeat", "status": "ok", "items_added": 0,
                      "started_at": at, "finished_at": at}]
    calls.clear()
    asyncio.run(cron.cron_heartbeat(authorization="x"))
    assert calls[0]["source_key"] == "cron_dispatch"
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        asyncio.run(cron.cron_heartbeat(authorization="x", judged_at="yesterday"))
