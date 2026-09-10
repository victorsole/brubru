"""U3 (10 Sep 2026): notification delivery had no scheduler for 84 days.

The `notifications` table held 103 rows, all one type, all for ONE recipient,
none read, none created since 18 June 2026. 70 accounts held tracked items; 69
had never received anything.

Neither producer was broken. Neither had a caller in the running application:
CarriageStatusNotifier had a CLI wrapper and a test suite and nothing else, and
saved_search_runner.run_all was reachable only from a manual API endpoint, whose
single invocation is the 18 June date on all 103 rows.
"""
import asyncio
import os
import pathlib
import sys
import threading

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.schedulers import notification_scheduler as ns  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    ns.stop_notification_scheduler()
    os.environ.pop("ENABLE_NOTIFICATION_SCHEDULER", None)
    yield
    ns.stop_notification_scheduler()
    os.environ.pop("ENABLE_NOTIFICATION_SCHEDULER", None)


def _jobs():
    return {j.id: j for j in ns._notification_scheduler.get_jobs()}


def test_both_producers_are_scheduled():
    """The entire defect was that neither ran. Both must be registered."""
    async def go():
        ns.start_notification_scheduler()
        assert ns._notification_scheduler is not None, "scheduler did not start"
        assert set(_jobs()) == {
            "carriage_status_notifications", "saved_search_notifications"
        }
    asyncio.run(go())


def test_jobs_fire_in_utc_not_host_local_time():
    """A bare `hour=` resolves against the HOST timezone while every docstring and
    log line here says UTC. The first run of this scheduler produced
    `06:00:00+02:00`. Production is a python:3.11-slim container with no TZ, so it
    was accidentally correct there and wrong everywhere else."""
    async def go():
        ns.start_notification_scheduler()
        for jid, job in _jobs().items():
            assert job.next_run_time.utcoffset().total_seconds() == 0, (
                f"{jid} is scheduled in {job.next_run_time.tzinfo}, not UTC"
            )
    asyncio.run(go())


def test_jobs_do_not_run_on_the_event_loop():
    """Both producers do synchronous DB work. main.py records that the RSS
    scheduler runs sync work on the loop, blocks the single worker and wedges the
    API -- which is why that one is off by default. This must not repeat it."""
    async def go():
        seen = {}
        original = ns._run_carriage_notifier
        ns._run_carriage_notifier = lambda: seen.setdefault("thread", threading.get_ident())
        try:
            await ns._carriage_job()
        finally:
            ns._run_carriage_notifier = original
        assert seen["thread"] != threading.get_ident(), (
            "the job body ran on the event loop; it would block the API worker"
        )
    asyncio.run(go())


def test_one_failing_producer_does_not_take_down_the_other():
    async def go():
        original = ns._run_carriage_notifier

        def boom():
            raise RuntimeError("provider down")

        ns._run_carriage_notifier = boom
        try:
            await ns._carriage_job()   # must be contained, not raised
        finally:
            ns._run_carriage_notifier = original
    asyncio.run(go())


def test_starting_twice_does_not_double_register():
    async def go():
        ns.start_notification_scheduler()
        ns.start_notification_scheduler()
        assert len(_jobs()) == 2
    asyncio.run(go())


def test_delivery_is_on_by_default_and_opt_out_is_explicit():
    """A delivery system that is OFF by default reproduces the defect with a
    different cause, so the default must be ON."""
    async def go():
        ns.start_notification_scheduler()
        assert ns._notification_scheduler is not None, "must default to ON"
        ns.stop_notification_scheduler()

        os.environ["ENABLE_NOTIFICATION_SCHEDULER"] = "false"
        ns.start_notification_scheduler()
        assert ns._notification_scheduler is None, "opt-out was ignored"
    asyncio.run(go())


def test_app_lifespan_starts_and_stops_it():
    """A scheduler nobody calls is exactly the bug being fixed."""
    text = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "start_notification_scheduler()" in text
    assert "stop_notification_scheduler()" in text


def test_unknown_scope_is_COLLECTED_not_just_logged():
    """Silence is not success.

    A subscribed scope with no handler delivered nothing while the run reported a
    clean result. Measured 10 Sep 2026: 3 of the 7 scopes in use
    (ep_resolutions, mep_amendments, parliamentary_questions) had no entry in
    _SCOPE_QUERIES, so four subscriptions were partly dead and the summary said so
    nowhere.

    This asserts the BEHAVIOUR, not the source text. An earlier version of this
    test grepped `inspect.getsource(run_all)` for the key names, and a mutation
    that deleted them from the summary dict still passed, because one surviving
    assignment line kept the string present.
    """
    from services.alerts.saved_search_runner import _run_one_subscription

    class _RefusingCursor:
        """Any query at all is a failure here: an unhandled scope must not run one."""
        def execute(self, *a, **k):
            raise AssertionError("an unknown scope must not issue a query")
        def fetchall(self):
            raise AssertionError("an unknown scope must not fetch")

    collected = set()
    created = _run_one_subscription(
        _RefusingCursor(),
        {
            "id": "00000000-0000-0000-0000-000000000000",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "label": "test",
            "scopes": ["parliamentary_questions", "mep_amendments"],
            "last_run_at": None,
            "exclude_terms": [],
            "query_phrase": "anything",
            "language_codes": None,
        },
        dry_run=True,
        unknown_scopes=collected,
    )
    assert created == 0
    assert collected == {"parliamentary_questions", "mep_amendments"}, (
        f"unhandled scopes were not collected for the caller: {collected}"
    )


def test_run_all_surfaces_dead_scopes_in_its_summary():
    """The scheduler escalates on `unknown_scopes`, so run_all must actually
    return the key -- checked against the live database."""
    import os
    from dotenv import load_dotenv
    load_dotenv(str(BACKEND / ".env"))
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set in this environment")
    from services.alerts.saved_search_runner import run_all

    summary = run_all(dry_run=True)
    for key in ("unknown_scopes", "subscriptions_failed",
                "subscriptions_run", "notifications_created"):
        assert key in summary, f"run_all summary is missing {key}"
    assert isinstance(summary["unknown_scopes"], list)
