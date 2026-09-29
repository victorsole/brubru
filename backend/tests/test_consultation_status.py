"""Consultation status must never contradict the deadline beside it (29 Sep 2026).

Two independent bugs served closed consultations as open:
  * the agency listing walker read the PRECEDING card's deadline, so AMLA's
    "inherent and residual risk profile" carried 6 Oct when it closed 27 Sep;
  * Have Your Say status came from "any period is OPEN" while the dates came from
    the first period that had them, so a row could be open beside the end date of a
    period that closed weeks earlier.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sync_have_your_say import _pick_period  # noqa: E402
from scripts.sync_agency_consultations import _status  # noqa: E402
from models.public_consultation import ConsultationStatusEnum as S  # noqa: E402
from services.scrapers.agency_consultations import parse_body_facts  # noqa: E402

TODAY = date(2026, 9, 29)


def _p(status, start=None, end=None, current=False):
    return {"receivingFeedbackStatus": status, "feedbackStartDate": start,
            "feedbackEndDate": end, "isCurrent": current, "frontEndStage": "X"}


class TestPickPeriod:
    def test_status_and_both_dates_come_from_the_same_period(self):
        # The exact shape of initiative 18892: a closed call for evidence beside an
        # upcoming consultation. The old logic paired neither status nor dates.
        st, start, end = _pick_period(
            [_p("DISABLED"),
             _p("CLOSED", None, "2026/09/23 23:59:59", current=True),
             _p("UPCOMING", "2026/10/01 00:00:00", "2026/12/31 00:00:00")], TODAY)
        assert st == "upcoming"
        assert (start, end) == (date(2026, 10, 1), date(2026, 12, 31))

    def test_open_period_wins_and_keeps_its_own_dates(self):
        st, start, end = _pick_period(
            [_p("CLOSED", "2026/01/01 00:00:00", "2026/02/01 00:00:00"),
             _p("OPEN", "2026/09/01 00:00:00", "2026/10/26 23:59:59")], TODAY)
        assert (st, start, end) == ("open", date(2026, 9, 1), date(2026, 10, 26))

    def test_an_open_period_past_its_deadline_is_not_open(self):
        st, _, end = _pick_period([_p("OPEN", None, "2026/09/23 23:59:59")], TODAY)
        assert st == "closed" and end == date(2026, 9, 23)

    def test_most_recently_closed_period_is_the_one_described(self):
        st, _, end = _pick_period(
            [_p("CLOSED", None, "2025/01/01 00:00:00"),
             _p("CLOSED", None, "2026/08/12 00:00:00")], TODAY)
        assert st == "closed" and end == date(2026, 8, 12)

    def test_a_planned_window_that_has_passed_is_not_upcoming(self):
        # Initiative 12131 is still UPCOMING at the portal with a window of Jan-Mar
        # 2020. Serving that as forthcoming six years on is the same defect as
        # serving a closed consultation as open.
        st, _, end = _pick_period(
            [_p("DISABLED", current=True),
             _p("UPCOMING", "2020/01/01 00:00:00", "2020/03/31 00:00:00"),
             _p("UPCOMING"),
             _p("DISABLED", "2020/07/01 00:00:00", "2020/09/30 00:00:00")], TODAY)
        assert st == "closed" and end == date(2020, 3, 31)

    def test_a_dated_window_is_preferred_over_an_undated_one(self):
        st, _, end = _pick_period(
            [_p("UPCOMING"),
             _p("UPCOMING", "2026/10/01 00:00:00", "2026/12/31 00:00:00")], TODAY)
        assert st == "upcoming" and end == date(2026, 12, 31)

    def test_planned_with_no_window_stays_upcoming_and_carries_no_dates(self):
        assert _pick_period([_p("UPCOMING")], TODAY) == ("upcoming", None, None)

    def test_a_start_after_its_own_end_is_dropped(self):
        # Have Your Say publishes initiative 14641 with a period starting 18 Dec 2025
        # and ending 2 Apr 2025. The impossible value is not stored.
        st, start, end = _pick_period(
            [_p("CLOSED", "2025/12/18 00:00:00", "2025/04/02 00:00:00")], TODAY)
        assert (st, start, end) == ("closed", None, date(2025, 4, 2))

    def test_no_usable_period_says_so_rather_than_guessing(self):
        assert _pick_period([_p("DISABLED")], TODAY) == (None, None, None)


class _D:
    """A closing date shaped like the datetime the mirror receives."""
    def __init__(self, d): self._d = d
    def date(self): return self._d


class TestAgencyStatus:
    def test_source_closed_is_believed(self):
        assert _status(_D(date(2026, 12, 1)), "Closed") is S.CLOSED

    def test_stated_open_past_its_deadline_is_closed(self):
        assert _status(_D(date(2026, 9, 27)), "Open") is S.CLOSED

    def test_stated_open_without_any_deadline_is_not_served_as_open(self):
        # The ACER regression: a stale "Open" and no date could never be contradicted.
        assert _status(None, "Open") is S.CLOSED

    def test_open_with_a_future_deadline(self):
        assert _status(_D(date(2026, 10, 20)), "Open") is S.OPEN

    def test_no_stated_status_falls_back_to_the_deadline(self):
        assert _status(_D(date(2026, 10, 20)), None) is S.OPEN
        assert _status(_D(date(2026, 1, 1)), None) is S.CLOSED
        assert _status(None, None) is S.CLOSED

    def test_upcoming_is_preserved(self):
        assert _status(_D(date(2026, 12, 1)), "Upcoming") is S.UPCOMING


class TestBodyFacts:
    def test_round_trip_of_the_three_facts(self):
        body = "A title\nStatus: Closed\nStart date: 2026-07-13\nClosing date: 2026-09-27"
        assert parse_body_facts(body) == {"status": "Closed", "start": "2026-07-13",
                                          "end": "2026-09-27"}

    def test_absent_facts_are_none_never_borrowed(self):
        assert parse_body_facts("Just a title") == {"status": None, "start": None, "end": None}
