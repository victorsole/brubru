"""The TRIS title refresh survives a throttled TRIS (20 Oct 2026).

refresh_tris_titles.py calls `TRISScraper._safe_notification` directly. The run state that
method and `_via_scrapedo` use (`uncertain_ids`, `paid_fetches`) was created only by the
new-notification sweep, so the first throttled id raised AttributeError, and the daily tier
recorded tris_titles failed on 17, 19 and 20 Oct (cron red: "twice in a row"). The existing
tests build the scraper with `__new__` and set the state by hand, so they could not see it:
these build it the way production does.
"""
import asyncio
import importlib
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.scrapers.dg_grow.tris_scraper import TRISScraper, TrisRateLimited  # noqa: E402


def _throttled_scraper(monkeypatch, scrapedo):
    monkeypatch.setenv("SCRAPEDO_API_KEY", "x")
    s = TRISScraper()

    async def throttled(nid):
        raise TrisRateLimited("HTTP 429")
    s.get_notification = throttled
    s._fetch_scrapedo = scrapedo
    return s


def test_a_fresh_scraper_reads_a_throttled_id_through_scrapedo(monkeypatch):
    s = _throttled_scraper(monkeypatch, lambda url, retries=1: "<html></html>")
    monkeypatch.setattr(s, "_parse_notification_detail",
                        lambda soup, nid: {"reference": f"2026/{nid}/DE", "title": "Airworthiness Notice"})
    detail = asyncio.run(s._safe_notification(27990))
    assert detail["reference"] == "2026/27990/DE"
    assert s.paid_fetches == 1


def test_a_fresh_scraper_stops_when_scrapedo_fails_too(monkeypatch):
    def scrapedo_502(url, retries=1):
        raise RuntimeError("502 rotation failure")
    s = _throttled_scraper(monkeypatch, scrapedo_502)
    try:
        asyncio.run(s._safe_notification(27990))
    except TrisRateLimited:
        pass
    else:
        raise AssertionError("expected TrisRateLimited")
    assert s.uncertain_ids == [27990]


def test_the_refresh_records_a_throttled_run_as_degraded_not_failed(monkeypatch, capsys):
    mod = importlib.import_module("scripts.refresh_tris_titles")
    rows = [SimpleNamespace(notification_number=n, title="Lufttüchtigkeitshinweis Nr. 40B der Behörde",
                            source_url=f"https://technical-regulation-information-system.ec.europa.eu/en/notification/{n}")
            for n in (27990, 27991)]

    class _Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, q): return rows

    class _Session:
        def __init__(self, engine): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def commit(self): raise AssertionError("nothing to write")

    def scrapedo_502(url, retries=1):
        raise RuntimeError("502 rotation failure")
    tris = _throttled_scraper(monkeypatch, scrapedo_502)
    sync = importlib.import_module("services.scrapers.dg_grow.dg_grow_sync_service")
    monkeypatch.setattr(sync, "DGGrowSyncService", lambda db: SimpleNamespace(tris=tris))
    monkeypatch.setattr(mod, "create_engine", lambda url, **kw: SimpleNamespace(connect=_Conn))
    monkeypatch.setattr(mod, "Session", _Session)
    monkeypatch.setattr(mod, "_db_url", lambda: "postgresql://unused")

    assert asyncio.run(mod.run(apply=True, limit=30, max_seconds=240)) == 0
    out = capsys.readouterr().out
    degraded = [ln for ln in out.splitlines() if ln.startswith("[SYNC_STATUS] degraded:")]
    assert degraded and "throttled at notification 27990" in degraded[-1]
    # Not a time-budget stop: two of those in a row are red, a throttled TRIS is not.
    from services.sync.freshness import BUDGET_STOP
    assert BUDGET_STOP not in degraded[-1]
