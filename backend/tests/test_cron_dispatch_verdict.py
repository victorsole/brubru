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
    return fired


def _exit_code(fn):
    with pytest.raises(SystemExit) as e:
        fn()
    return e.value.code


def test_a_cut_connection_with_a_clean_ledger_is_green(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started: [
        {"source_key": "news_dg", "status": "success"},
        {"source_key": "oj", "status": "success"},
        {"source_key": "cron_dispatch", "status": "ok"},
        {"source_key": "council_docs", "status": "skipped"},
    ])
    assert _exit_code(cd.main) == 0
    # and it no longer sits on a connection the edge will cut anyway
    assert one_tier["/api/cron/sync/tier/fast"] == cd.EDGE_TIMEOUT


def test_a_cut_connection_with_a_failed_source_is_red(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started: [
        {"source_key": "news_dg", "status": "success"},
        {"source_key": "oj_acts_ca", "status": "failed"},
    ])
    assert _exit_code(cd.main) == 1


def test_an_audit_source_reporting_gaps_is_not_a_failure(monkeypatch, one_tier):
    """`degraded` is an auditor exiting non-zero to report what it found. Counting it
    would paint every run red for ever, which is how a red build stops meaning anything."""
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started: [
        {"source_key": "news_dg", "status": "success"},
        {"source_key": "scraper_health", "status": "degraded"},
    ])
    assert _exit_code(cd.main) == 0


def test_a_tier_that_recorded_nothing_at_all_is_red(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started: [])
    assert _exit_code(cd.main) == 1


def test_an_unreadable_ledger_is_red(monkeypatch, one_tier):
    monkeypatch.setattr(cd, "_wait_for_detached", lambda started: None)
    assert _exit_code(cd.main) == 1


def test_a_tier_that_answers_in_time_is_still_judged_on_its_payload(monkeypatch):
    """The short endpoints still return a payload, and a job failing inside a 200 stays
    red: that was the 19-22 Sep outage, where every child died and the run logged ok."""
    monkeypatch.setattr(cd, "CRON_SECRET", "test-secret")
    monkeypatch.setattr(cd, "decide_tiers", lambda now: [("daily", "/api/cron/sync/daily")])
    monkeypatch.setattr(cd, "_fire", lambda endpoint, timeout=1800: (
        {"status": "success"} if endpoint.endswith("/heartbeat")
        else {"tier": "daily", "ran": {"consultations": "success", "tris": "failed"}}))

    def _boom(started):
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
    runs = cd._wait_for_detached(_t.time())
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
    assert [r["source_key"] for r in cd._wait_for_detached(_t.time())] == ["a"]
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
