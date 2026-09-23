"""TRIS feed: frontier enumeration, detail parsing and run recording (23 Sep 2026).

The feed counted down from a hard-coded id and re-read the same 46
notifications for six and a half months, recording nothing. A client found a
Spanish textile decree (page 27983) that we never saw. The parser also read
every comment and detailed opinion as absent.
"""
from __future__ import annotations

import asyncio
import importlib.util
import pathlib

import pytest

from services.scrapers.dg_grow.tris_scraper import TRISScraper, TrisRateLimited

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "tris_notification_27983.html"


@pytest.fixture(scope="module")
def parsed():
    s = TRISScraper()
    return s._parse_notification_detail(s._parse_html(FIXTURE.read_text(encoding="utf-8")), 27983)


def test_reference_country_and_title(parsed):
    assert parsed["reference"] == "2026/0266/ES"
    assert parsed["country"] == "ES"
    assert parsed["title"].startswith("Draft Royal Decree regulating textile and footwear products")


def test_extended_standstill_is_the_effective_end(parsed):
    assert parsed["standstill_end_date"].startswith("2026-09-28")
    assert parsed["standstill_original_end_date"].startswith("2026-08-28")
    assert parsed["standstill_extended"] is True


def test_comments_and_detailed_opinion_are_read(parsed):
    assert parsed["comments_by"] == ["European Commission"] and parsed["has_comments"] is True
    assert parsed["detailed_opinions"] == ["European Commission"] and parsed["has_detailed_opinion"] is True


def test_message_sections_are_captured(parsed):
    assert "Directive (EU) 2025/1892" in parsed["main_content"]
    assert parsed["product_description"].startswith("It applies to textile")
    assert "Law 7/2022" in parsed["grounds"]


def test_a_passed_standstill_is_never_called_adopted():
    s = TRISScraper()
    html = FIXTURE.read_text(encoding="utf-8").replace("28/08/2026 (28/09/2026)", "28/08/2020")
    d = s._parse_notification_detail(s._parse_html(html), 27983)
    assert d["status"] == "standstill_ended"


# --- enumeration -----------------------------------------------------------

def _scraper_with(existing_ids, throttled_ids=()):
    s = TRISScraper()
    calls = []

    async def fake(nid):
        calls.append(nid)
        if nid in throttled_ids:
            raise TrisRateLimited("HTTP 429")
        return {"reference": f"2026/{nid}/XX", "notification_number": nid} if nid in existing_ids else None

    s._safe_notification = fake
    return s, calls


def test_counts_up_from_the_frontier_past_gaps():
    s, _ = _scraper_with({101, 102, 105, 130})
    out = asyncio.run(s.get_recent_notifications(frontier=100, recheck=0, miss_limit=25))
    refs = sorted(int(r["reference"].split("/")[1]) for r in out)
    assert refs == [101, 102, 105, 130]      # a 24-id gap does not stop it
    assert s.last_frontier == 130


def test_stops_after_miss_limit_and_keeps_frontier_when_nothing_new():
    s, calls = _scraper_with(set())
    asyncio.run(s.get_recent_notifications(frontier=500, recheck=0, miss_limit=5))
    assert calls == [501, 502, 503, 504, 505]
    assert s.last_frontier == 500


def test_rechecks_below_the_frontier():
    s, calls = _scraper_with({98, 99, 100})
    out = asyncio.run(s.get_recent_notifications(frontier=100, recheck=3, miss_limit=2))
    assert [c for c in calls if c <= 100] == [100, 99, 98]
    assert len(out) == 3


def test_max_new_caps_one_run():
    s, _ = _scraper_with(set(range(1, 1000)))
    out = asyncio.run(s.get_recent_notifications(frontier=0, recheck=0, max_new=10))
    assert len(out) == 10


def test_throttling_stops_the_run_without_counting_misses():
    s, calls = _scraper_with({101, 102, 103}, throttled_ids={102})
    out = asyncio.run(s.get_recent_notifications(frontier=100, recheck=5))
    assert s.throttled is True
    assert [r["notification_number"] for r in out] == [101]    # no recheck after a throttle
    assert s.last_frontier == 101                              # resumes from 101 next run
    assert 103 not in calls


def test_backoff_retries_then_succeeds(monkeypatch):
    import asyncio as _a
    s = TRISScraper()
    s.RATE_LIMIT_BACKOFF = (0, 0)
    n = {"calls": 0}

    async def flaky(nid):
        n["calls"] += 1
        if n["calls"] < 3:
            raise TrisRateLimited("HTTP 429")
        return {"reference": "2026/0001/ES", "notification_number": nid}

    s.get_notification = flaky
    assert _a.run(s._safe_notification(5))["reference"] == "2026/0001/ES"
    assert n["calls"] == 3


def test_a_429_from_the_site_is_raised_not_swallowed(monkeypatch):
    from services.scrapers.base_scraper import ScraperError
    s = TRISScraper()

    async def boom(url, **k):
        raise ScraperError("HTTP 429: Too Many Requests")

    s._fetch = boom
    with pytest.raises(TrisRateLimited):
        asyncio.run(s.get_notification(1))


# --- run recording -----------------------------------------------------------

@pytest.fixture()
def record(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "sync_dg_grow", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sync_dg_grow.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import services.sync.freshness as freshness
    rec, age = [], {"days": 1}
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: rec.append(kw))

    class _DB:
        def rollback(self):
            pass

        def execute(self, *a, **k):
            class R:
                def scalar(self_inner):
                    return age["days"]
            return R()

    def go(stats, newest_age=1):
        age["days"] = newest_age
        mod._record_tris(_DB(), stats, None)
        return rec[-1]

    return go


def test_fresh_run_is_success(record):
    r = record({"synced": 60, "new": 12, "errors": 0, "frontier_before": 27740, "frontier_after": 27990})
    assert r["status"] == "success" and r["items_added"] == 12 and r["source_key"] == "tris"


def test_nothing_fetched_is_failed(record):
    assert record({"synced": 0, "new": 0, "errors": 0})["status"] == "failed"


def test_stale_newest_notification_is_degraded(record):
    r = record({"synced": 40, "new": 0, "errors": 0, "frontier_before": 5, "frontier_after": 5}, newest_age=12)
    assert r["status"] == "degraded" and "12 days old" in r["error"]


def test_throttled_run_is_degraded(record):
    r = record({"synced": 30, "new": 30, "errors": 0, "throttled": True, "frontier_after": 27843})
    assert r["status"] == "degraded" and "rate limited" in r["error"]


def test_crash_is_failed(record):
    assert record({"error": "ConnectionError: TRIS down"})["status"] == "failed"


# --- the paid fallback on a 429 ----------------------------------------------

def test_429_with_a_scrapedo_key_fetches_through_scrapedo(monkeypatch):
    monkeypatch.setenv("SCRAPEDO_API_KEY", "test")
    s = TRISScraper()
    s.uncertain_ids, s.paid_fetches = [], 0

    async def throttled(nid):
        raise TrisRateLimited("HTTP 429")

    s.get_notification = throttled
    s._fetch_scrapedo = lambda url, retries=1: FIXTURE.read_text(encoding="utf-8")
    d = asyncio.run(s._safe_notification(27983))
    assert d["reference"] == "2026/0266/ES" and s.paid_fetches == 1


def test_scrapedo_failure_is_a_miss_recorded_as_uncertain(monkeypatch):
    monkeypatch.setenv("SCRAPEDO_API_KEY", "test")
    s = TRISScraper()
    s.uncertain_ids, s.paid_fetches = [], 0

    async def throttled(nid):
        raise TrisRateLimited("HTTP 429")

    def fails(url, retries=1):
        raise RuntimeError("ROTATION_FAILED")

    s.get_notification = throttled
    s._fetch_scrapedo = fails
    assert asyncio.run(s._safe_notification(99999)) is None
    assert s.uncertain_ids == [99999]
