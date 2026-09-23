"""council_calendar records every run (23 Sep 2026).

A blocked consilium fetch returned an empty list, which read as "no new
meetings", so the Council calendar froze on 24 July with nothing recorded.
"""
import pytest

import services.scrapers.council_calendar_scraper as ccs
import services.sync.freshness as freshness
from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService


class _DB:
    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture()
def run(monkeypatch):
    rec = []
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: rec.append(kw))
    svc = EUCalendarSyncService.__new__(EUCalendarSyncService)
    monkeypatch.setattr(svc, "_get_db", lambda: _DB(), raising=False)
    monkeypatch.setattr(svc, "_should_close_db", lambda: True, raising=False)

    def go(events, upsert_raises=False):
        monkeypatch.setattr(ccs.CouncilCalendarScraper, "scrape_meetings", lambda self, m: events)

        def up(db, ev, result):
            if upsert_raises:
                raise ValueError("bad row")
            result["added"] += 1

        monkeypatch.setattr(svc, "_upsert_event", up, raising=False)
        out = svc.sync_council_meetings(months_ahead=1)
        return out, rec

    return go


def test_zero_meetings_is_a_failure(run):
    out, rec = run([])
    assert rec[0]["source_key"] == "council_calendar" and rec[0]["status"] == "failed"


def test_meetings_written_is_success(run):
    out, rec = run([{"external_id": "a"}, {"external_id": "b"}])
    assert rec[0]["status"] == "success" and rec[0]["items_added"] == 2


def test_write_errors_are_degraded(run):
    out, rec = run([{"external_id": "a"}], upsert_raises=True)
    assert rec[0]["status"] == "degraded"
