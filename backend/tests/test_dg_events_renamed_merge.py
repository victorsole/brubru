"""A renamed DG event page is merged into its new row, on proof only (29 Sep 2026).

GROW renamed one webinar page twice; each slug became its own calendar row, so
the DPP battery webinar of 30 September showed three times. A stale row is merged
only when its OWN URL now redirects to a URL in this run's listing.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import requests

from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService

DAY = date.today() + timedelta(days=5)
NEW = "https://example.eu/events/webinar-third_en"
OLD = "https://example.eu/events/webinar-old-title_en"


class _Q:
    def __init__(self, stale, survivor):
        self.stale, self.survivor = stale, survivor
    def filter(self, *a, **k): return self
    def all(self): return self.stale
    def first(self): return self.survivor


class _DB:
    def __init__(self, stale, survivor):
        self.q = _Q(stale, survivor)
        self.executed, self.deleted = [], []
    def query(self, *a, **k): return self.q
    def execute(self, stmt, params=None): self.executed.append(params)
    def delete(self, row): self.deleted.append(row)


def _run(monkeypatch, final_url, status=200):
    stale = SimpleNamespace(id="old-id", external_id="webinar-old-title_en", source_url=OLD, start_date=DAY)
    survivor = SimpleNamespace(id="new-id", external_id="webinar-third_en", source_url=NEW, start_date=DAY)
    db = _DB([stale], survivor)
    monkeypatch.setattr(requests, "get", lambda url, **k: SimpleNamespace(url=final_url, status_code=status))
    listed = [{"source": "dg_events:GROW", "external_id": "webinar-third_en", "source_url": NEW, "start_date": DAY}]
    result = {"merged_renamed": 0}
    EUCalendarSyncService.__new__(EUCalendarSyncService)._merge_renamed_dg_events(db, "dg_events:GROW", listed, result)
    return db, result


def test_redirect_to_a_listed_event_merges_and_moves_user_rows_first(monkeypatch):
    db, result = _run(monkeypatch, NEW)
    assert result["merged_renamed"] == 1
    assert [r.id for r in db.deleted] == ["old-id"]
    # subscriptions and archives repointed before the delete (both CASCADE on delete)
    assert db.executed == [{"old": "old-id", "new": "new-id"}, {"old": "old-id", "new": "new-id"}]


def test_a_page_that_still_answers_itself_is_not_merged(monkeypatch):
    db, result = _run(monkeypatch, OLD)
    assert result["merged_renamed"] == 0 and db.deleted == [] and db.executed == []


def test_a_redirect_elsewhere_or_an_error_is_not_merged(monkeypatch):
    db, result = _run(monkeypatch, "https://example.eu/events_en")
    assert result["merged_renamed"] == 0 and db.deleted == []
    db, result = _run(monkeypatch, NEW, status=404)
    assert result["merged_renamed"] == 0 and db.deleted == []
