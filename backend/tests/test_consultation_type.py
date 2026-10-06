"""consultation_type describes the SAME feedback period as the status and the dates.

The third field of the same defect. On 29 Sep 2026 status, start and end were made to
come from one chosen period; the type was left reading `frontEndStage` off whichever
entry happened to be first. Initiative 19293 ("Minimum performance standards for data
centres") carries two periods OPEN at once with the same 14 Dec window --
PLANNING_WORKFLOW and OPC_LAUNCHED -- so it was served as a call for evidence while a
public consultation was open on it.

Measured across all 4,108 initiatives: 18 carry more than one frontEndStage, and
exactly 5 have two OPEN at once, every one of them that same pair.
"""
import pytest
from datetime import date

from scripts.sync_have_your_say import _pick_period, _period_type


TODAY = date(2026, 9, 29)


def _p(stage, status, start=None, end=None, current=False):
    return {"frontEndStage": stage, "receivingFeedbackStatus": status,
            "feedbackStartDate": start, "feedbackEndDate": end, "isCurrent": current}


class TestTheTypeDescribesTheChosenPeriod:
    def test_an_open_public_consultation_outranks_a_call_for_evidence(self):
        """19293 exactly as the portal serves it: both open, same window."""
        periods = [_p("PLANNING_WORKFLOW", "OPEN", "2026/09/21 12:14:46", "2026/12/14 23:59:59", True),
                   _p("OPC_LAUNCHED", "OPEN", "2026/09/21 12:14:46", "2026/12/14 23:59:59", True)]
        status, start, end = _pick_period(periods, TODAY)
        assert status == "open"
        assert _period_type(periods, status, TODAY) == "public_consultation"

    def test_a_lone_call_for_evidence_is_still_one(self):
        periods = [_p("PLANNING_WORKFLOW", "OPEN", None, "2026/12/14 23:59:59", True)]
        assert _period_type(periods, "open", TODAY) == "call_for_evidence"

    def test_the_type_follows_the_open_period_not_the_first_one(self):
        """A closed call for evidence beside an open public consultation."""
        periods = [_p("PLANNING_WORKFLOW", "CLOSED", None, "2026/01/31 23:59:59", True),
                   _p("OPC_LAUNCHED", "OPEN", None, "2026/12/14 23:59:59", False)]
        assert _period_type(periods, "open", TODAY) == "public_consultation"

    def test_an_initiative_with_no_feedback_exercise_stays_an_initiative(self):
        periods = [_p("ADOPTION_WORKFLOW", "DISABLED")]
        assert _period_type(periods, "closed", TODAY) == "initiative"

    def test_no_periods_at_all(self):
        assert _period_type([], "closed", TODAY) == "initiative"


class TestItAgreesWithTheStoredData:
    @pytest.fixture(scope="class")
    def db(self):
        from core.database import SessionLocal
        s = SessionLocal()
        yield s
        s.close()

    @pytest.mark.live
    def test_19293_is_a_public_consultation(self, db):
        from sqlalchemy import text
        got = db.execute(text(
            "SELECT consultation_type FROM public_consultations "
            "WHERE initiative_id = '19293'")).scalar()
        assert got == "public_consultation", (
            "a public consultation is open on it until 14 December")

    @pytest.mark.live
    def test_the_five_coherence_checks_stay_at_zero(self, db):
        from sqlalchemy import text
        checks = {
            "open past its deadline": "status='open' AND end_date < CURRENT_DATE",
            "open with no deadline": "status='open' AND end_date IS NULL",
            "closed with a future deadline": "status='closed' AND end_date > CURRENT_DATE",
            "upcoming already ended": "status='upcoming' AND end_date < CURRENT_DATE",
            "start after its own end": "start_date > end_date",
        }
        for label, pred in checks.items():
            n = db.execute(text(
                f"SELECT count(*) FROM public_consultations WHERE {pred}")).scalar()
            assert n == 0, f"{label}: {n}"
