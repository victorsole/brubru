"""/api/v2/news/all says where its history ends (15 Oct 2026).

GovClipping's backfill asks for press releases since 15 July 2024. The newsrooms are read
from RSS feeds, held in full only from late May 2026, while the envelope claimed
coverage_complete: true and gave no note: a thin 2025 read as institutional silence."""
import asyncio
import inspect
from datetime import date


class _R:
    def scalar(self):
        return 0

    def fetchall(self):
        return []


class _DB:
    def execute(self, *a, **k):
        return _R()


def _call(**given):
    from api.v2.news import list_news
    kwargs = {n: given.get(n) for n in inspect.signature(list_news).parameters}
    kwargs.update(db=_DB(), kind="press_release", order="recent", page=1, limit=10, include_body=True, **given)
    return asyncio.run(list_news(**kwargs))


def test_a_window_before_the_newsrooms_history_is_not_complete():
    env = _call(from_=date(2024, 7, 15))
    assert env.coverage_complete is False and "15 July 2024" in env.coverage_note
    assert _call().coverage_complete is False


def test_a_recent_window_is_complete():
    env = _call(from_=date(2026, 9, 27), to=date(2026, 9, 28))
    assert env.coverage_complete is True and env.coverage_note is None
