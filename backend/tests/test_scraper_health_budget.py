"""The scraper-health detector had itself stopped working (24 September 2026).

`confirm` mode runs the REAL scraper for every source that looks stale. A healthy night is
about 2.5 minutes, but the run grows with the number of stale sources, and on 21, 22 and
23 September it passed the caller's 20-minute deadline. The caller writes its results only
after that await, so each of those nights recorded `TIMEOUT: exceeded 1200s` and stored
NOTHING: the thing that exists to notice broken scrapers was the broken one.

`run()` now takes a live-check budget, spends it on the stalest sources first, and leaves
the rest for tomorrow. A source it did not reach is absent from the results: never
reported as healthy, never as broken. Measured the same day: 6 live checks took 138s
(~23s each), so the configured 30 is about 11.5 minutes inside the deadline.

No network: the ingestors are stubbed.
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import scripts.scraper_health as sh  # noqa: E402


@pytest.fixture()
def fake_sources(monkeypatch):
    """Six ingestors: three long stale, three fresh. Records who was actually run."""
    called: list[str] = []
    now = datetime.now(timezone.utc)

    def make(name):
        def fn(fetch_bodies=False):
            called.append(name)
            return [{"x": 1}]
        return fn

    ingestors = {(f"body{i}", "news"): make(f"body{i}") for i in range(6)}
    monkeypatch.setattr(sh.se, "INGESTORS", ingestors, raising=False)

    state = {
        ("body0", "news"): (10, now - timedelta(days=400)),   # stalest
        ("body1", "news"): (10, now - timedelta(days=300)),
        ("body2", "news"): (10, now - timedelta(days=200)),
        ("body3", "news"): (10, now),                          # fresh, no live check
        ("body4", "news"): (10, now),
        ("body5", "news"): (10, now),
    }
    monkeypatch.setattr(sh, "_db_state", lambda db: state)
    monkeypatch.setattr(sh, "SessionLocal", lambda: type("S", (), {"close": lambda self: None})())
    return called


def test_the_budget_caps_the_live_checks(fake_sources):
    sh.run("confirm", None, 2)
    assert len(fake_sources) == 2, f"ran {len(fake_sources)} live checks against a budget of 2"


def test_the_stalest_sources_are_checked_first(fake_sources):
    sh.run("confirm", None, 2)
    assert fake_sources == ["body0", "body1"], fake_sources


def test_a_source_not_reached_is_not_reported_at_all(fake_sources):
    """Silence about a source is honest; calling it healthy because nobody looked is not."""
    results = sh.run("confirm", None, 1)
    reported = {r["body"] for r in results}
    assert "body0" in reported                      # the one that was checked
    assert "body1" not in reported and "body2" not in reported   # out of budget


def test_without_a_budget_nothing_changes(fake_sources):
    """The CLI and any full run keep their old behaviour."""
    sh.run("confirm", None, None)
    assert sorted(fake_sources) == ["body0", "body1", "body2"]   # every stale one, no cap


def test_the_caller_passes_a_budget_that_fits_its_deadline():
    cron = (pathlib.Path(__file__).resolve().parents[1] / "api" / "cron.py").read_text(encoding="utf-8")
    assert "_SCRAPER_HEALTH_LIVE_BUDGET" in cron
    budget = int(cron.split("_SCRAPER_HEALTH_LIVE_BUDGET = ")[1].split("\n")[0])
    deadline = eval(cron.split("_SCRAPER_HEALTH_DEADLINE_S = ")[1].split("#")[0].strip())
    # 23s per live check, measured. Leave at least a third of the deadline spare.
    assert budget * 23 < deadline * 0.75, f"budget {budget} x 23s does not fit {deadline}s"
