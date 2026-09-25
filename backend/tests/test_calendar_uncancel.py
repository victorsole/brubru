"""A row its source produces again is un-cancelled (25 Sep 2026).

Cancellation was one-way: the College Wednesdays of 4 Nov and 9 Dec 2026 were
cancelled while stray plenary rows made those weeks look like Strasbourg weeks,
stayed cancelled once the generator produced them again, and the calendar
showed no College meeting in either week.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from models.eu_calendar import EventStatusEnum
from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService


class _Q:
    def __init__(self, row): self.row = row
    def filter(self, *a, **k): return self
    def first(self): return self.row


class _DB:
    def __init__(self, row): self.row = row
    def query(self, *a, **k): return _Q(self.row)


def _row(start):
    return SimpleNamespace(
        title="College of Commissioners: Weekly Meeting", start_date=start, end_date=None,
        description="d", source_url=None, agenda_url=None, policy_areas=None,
        organiser=None, venue=None, status=EventStatusEnum.CANCELLED, last_updated=None)


def _event(start):
    return {"source": "ec_college", "external_id": "ec_college_x", "institution": "COMMISSION",
            "event_type": "commission_college_meeting", "title": "College of Commissioners: Weekly Meeting",
            "start_date": start, "description": "d", "status": "scheduled"}


def _run(start):
    svc = EUCalendarSyncService.__new__(EUCalendarSyncService)
    row = _row(start)
    result = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    svc._upsert_event(_DB(row), _event(start), result)
    return row, result


def test_future_row_produced_again_is_restored():
    row, result = _run(date.today() + timedelta(days=40))
    assert row.status == EventStatusEnum.SCHEDULED
    assert result["updated"] == 1


def test_past_row_keeps_its_status():
    row, _ = _run(date.today() - timedelta(days=3))
    assert row.status == EventStatusEnum.CANCELLED
