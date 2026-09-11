"""Behavioural tests for the tender match scheduler and the matcher speedups.

These target the three things that were actually wrong on 11 September 2026, not
the shape of the code: the scheduler did not exist, the trigger timezone is easy
to get wrong, and stop() can strand the singleton.

Every body that calls start() runs inside `asyncio.run`, matching
test_notification_scheduler.py. AsyncIOScheduler.start() calls
asyncio.get_event_loop(), which raises when no loop is current -- these tests
passed alone and failed in the full suite until that was fixed, because an
earlier async test had closed the loop. Production is unaffected: start() is
called from the app lifespan, where a loop is always running.
"""
import asyncio
import os

import pytest

import services.schedulers.tender_match_scheduler as sched


@pytest.fixture(autouse=True)
def _clean():
    sched.stop_tender_match_scheduler()
    os.environ.pop("ENABLE_TENDER_MATCH_SCHEDULER", None)
    yield
    sched.stop_tender_match_scheduler()
    os.environ.pop("ENABLE_TENDER_MATCH_SCHEDULER", None)


def test_the_job_is_registered():
    """The entire defect was that nothing called the matcher."""
    async def go():
        sched.start_tender_match_scheduler()
        assert sched._tender_match_scheduler is not None, "scheduler did not start"
        assert [j.id for j in sched._tender_match_scheduler.get_jobs()] == ["tender_matching"]
    asyncio.run(go())


def test_the_trigger_is_utc_not_the_host_timezone():
    """A bare `hour=` resolves against the host zone. Three schedulers in this
    repo carried that bug until 10 September; asserting the offset is the only
    way to catch it on a non-UTC machine."""
    async def go():
        sched.start_tender_match_scheduler()
        job = sched._tender_match_scheduler.get_jobs()[0]
        assert job.next_run_time.utcoffset().total_seconds() == 0
        assert job.next_run_time.hour == sched._MATCH_HOUR
    asyncio.run(go())


def test_it_never_overlaps_itself():
    """A run takes minutes. Two concurrent matchers would double-write."""
    async def go():
        sched.start_tender_match_scheduler()
        job = sched._tender_match_scheduler.get_jobs()[0]
        assert job.max_instances == 1
        assert job.coalesce is True
    asyncio.run(go())


def test_opting_out_leaves_no_scheduler():
    async def go():
        os.environ["ENABLE_TENDER_MATCH_SCHEDULER"] = "false"
        sched.start_tender_match_scheduler()
        assert sched._tender_match_scheduler is None
    asyncio.run(go())


def test_it_is_on_by_default():
    """A matcher that is off by default reproduces the defect being fixed."""
    async def go():
        assert "ENABLE_TENDER_MATCH_SCHEDULER" not in os.environ
        sched.start_tender_match_scheduler()
        assert sched._tender_match_scheduler is not None
    asyncio.run(go())


def test_a_raising_shutdown_still_clears_the_singleton():
    """If the singleton survived a failed shutdown, the next start() would
    decline as 'already running' and leave a dead scheduler matching nothing:
    the exact bug this module exists to fix."""
    async def go():
        sched.start_tender_match_scheduler()

        def _boom(*a, **k):
            raise RuntimeError("event loop is closed")

        sched._tender_match_scheduler.shutdown = _boom
        sched.stop_tender_match_scheduler()
        assert sched._tender_match_scheduler is None
        sched.start_tender_match_scheduler()
        assert sched._tender_match_scheduler is not None, "restart after a failed stop"
    asyncio.run(go())


def test_a_failing_matcher_does_not_escape_the_job(monkeypatch):
    """The scheduler must survive a bad run; an escaping exception would kill
    the job and silently stop all future matching."""
    monkeypatch.setattr(
        sched, "_run_matcher", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    asyncio.run(sched._match_job())  # must not raise


def test_the_matcher_has_a_risk_cache():
    """The per-pair regulatory-risk lookup was the real cost of a run: 247,138
    calls computing 72 distinct answers."""
    from services.tenders.matcher import TenderMatcher
    m = TenderMatcher.__new__(TenderMatcher)
    TenderMatcher.__init__(m, db=None)
    assert m._risk_cache == {}
