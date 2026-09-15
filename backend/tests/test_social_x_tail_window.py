"""The daily X tail window: dispatched once, oldest-first, same polite pacing.

Added 15 Sep 2026: the 4-hourly verified-first drip never reached the 618 stale
unverified X accounts.
"""
import asyncio
import datetime
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))

import cron_dispatch as d  # noqa: E402


def _social_x_fires(weekday_date=datetime.date(2026, 9, 15)):
    out = []
    for hour in range(24):
        now = datetime.datetime.combine(weekday_date, datetime.time(hour))
        out += [(hour, label, path) for label, path in d.decide_tiers(now)
                if "fetch-social-posts" in path and "mode=x" in path]
    return out


def test_tail_window_fires_once_a_day_oldest_first():
    tail = [f for f in _social_x_fires() if f[1] == "social_x_tail"]
    assert len(tail) == 1 and tail[0][0] == 3
    q = parse_qs(urlparse(tail[0][2]).query)
    assert q["order"] == ["oldest"]
    assert q["limit"] == ["150"] and q["per_account"] == ["5"]
    assert float(q["pace"][0]) >= 3.0 and q["empty_streak_stop"] == ["10"]


def test_existing_drip_unchanged():
    drip = [f for f in _social_x_fires() if f[1] == "social_x_drip"]
    assert [h for h, _, _ in drip] == [1, 5, 9, 13, 17, 21]
    assert all("order=" not in p for _, _, p in drip)


def test_tail_window_not_on_a_drip_hour():
    hours = [h for h, _, _ in _social_x_fires()]
    assert len(hours) == len(set(hours)), "two X runs in one hour double the throttle hit"


def test_endpoint_passes_tail_parameters(monkeypatch):
    pytest.importorskip("fastapi")
    from api import cron
    import services.social.post_fetcher as pf

    seen = {}

    def fake_run(db, **kw):
        seen.update(kw)
        return {"accounts": 0}

    class FakeDB:
        def close(self):
            pass

    monkeypatch.setattr(pf, "run", fake_run)
    monkeypatch.setattr(cron, "SessionLocal", lambda: FakeDB())
    monkeypatch.setattr(cron, "_verify_cron_secret", lambda a: None)

    asyncio.run(cron.cron_fetch_social_posts(
        authorization="Bearer x", mode="x", limit=150, per_account=5, pace=4.0,
        empty_streak_stop=10, order="oldest"))
    assert seen == {"platforms": ("x",), "limit_accounts": 150, "per_account": 5,
                    "pace": 4.0, "empty_streak_stop": 10, "prioritise_verified": False}

    seen.clear()
    asyncio.run(cron.cron_fetch_social_posts(
        authorization="Bearer x", mode="x", limit=40, per_account=None, pace=None,
        empty_streak_stop=None, order="verified_first"))
    assert seen == {"platforms": ("x",), "limit_accounts": 40, "per_account": 10,
                    "pace": 5.0, "empty_streak_stop": 8, "prioritise_verified": True}
