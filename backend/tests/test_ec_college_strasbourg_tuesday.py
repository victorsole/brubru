"""The College meets on Tuesday in Strasbourg plenary weeks (15 Sep 2026 fix)."""
from datetime import date

import pytest

import services.scrapers.ec_college_scraper as college
from services.scrapers.ec_college_scraper import generate_college_meetings


class _FrozenDate(date):
    """`date` whose today() is the day the fix was made."""

    @classmethod
    def today(cls):
        return cls(2026, 9, 15)


@pytest.fixture(autouse=True)
def today_is_15_september_2026(monkeypatch):
    """The generator starts from date.today(), and these tests name October 2026 dates:
    they passed until 6 October passed, then failed for every push (12 Oct 2026: main went
    red on a calendar date, with no code change). Freeze the day the tests were written for."""
    monkeypatch.setattr(college, "date", _FrozenDate)

PLENARY = [
    date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8),    # Strasbourg
    date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22),  # Strasbourg
    date(2026, 11, 11), date(2026, 11, 12),                                          # Brussels mini-session
]


def _dates(events):
    return {e["start_date"] for e in events}


def test_strasbourg_weeks_move_to_tuesday():
    got = _dates(generate_college_meetings(6, PLENARY))
    assert date(2026, 10, 6) in got and date(2026, 10, 7) not in got
    assert date(2026, 10, 20) in got and date(2026, 10, 21) not in got


def test_mini_session_week_keeps_wednesday():
    got = _dates(generate_college_meetings(6, PLENARY))
    assert date(2026, 11, 11) in got


def test_without_plenary_dates_everything_is_wednesday():
    assert all(d.weekday() == 2 for d in _dates(generate_college_meetings(3)))


def test_external_id_follows_the_meeting_day():
    ev = [e for e in generate_college_meetings(6, PLENARY) if e["start_date"] == date(2026, 10, 6)][0]
    assert ev["external_id"] == "ec_college_2026-10-06"
    assert "Strasbourg" in ev["title"]
