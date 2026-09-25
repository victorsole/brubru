"""TRIS stops cleanly on a time budget and when throttled everywhere (25 Sep 2026)."""
import asyncio
import time

from services.scrapers.dg_grow.tris_scraper import TRISScraper, TrisRateLimited


def _scraper(fetch):
    s = TRISScraper.__new__(TRISScraper)
    s.get_notification = fetch
    s.BASE_URL = "https://example.invalid"
    return s


def test_budget_stops_the_walk_and_says_so(monkeypatch):
    monkeypatch.delenv("SCRAPEDO_API_KEY", raising=False)
    calls = []

    async def slow_missing(nid):
        calls.append(nid)
        await asyncio.sleep(0.02)
        return {}
    s = _scraper(slow_missing)
    asyncio.run(s.get_recent_notifications(frontier=100, recheck=0, miss_limit=10_000,
                                           deadline=time.monotonic() + 0.1))
    assert s.budget_hit is True
    assert 0 < len(calls) < 50


def test_throttled_everywhere_stops_instead_of_paying_per_id(monkeypatch):
    monkeypatch.setenv("SCRAPEDO_API_KEY", "x")
    calls = []

    async def throttled(nid):
        calls.append(nid)
        raise TrisRateLimited("HTTP 429")
    s = _scraper(throttled)

    def scrapedo_fails(nid):
        s.uncertain_ids.append(nid)
        return None
    s._via_scrapedo = scrapedo_fails
    asyncio.run(s.get_recent_notifications(frontier=100, recheck=0))
    assert s.throttled is True
    assert len(calls) == 1
