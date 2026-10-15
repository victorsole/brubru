"""A work item without a committee vote or carriage referral is dated from its OEIL file (15 Oct 2026).

123 committee work items (immunity cases, objections) served document_date null on
/api/v2/parliament/ep-documents: their carriage held no referral. oeil_procedures holds
the OEIL file's key events; 45 of them list one."""
from __future__ import annotations

from datetime import date

from api.v1.ep_entities import _oeil_procedure_dates


class _Session:
    def __init__(self, rows):
        self.rows, self.asked = rows, None

    def execute(self, stmt, params):
        self.asked = params
        return type("R", (), {"fetchall": lambda _s: self.rows})()


def test_referral_first_else_first_event_else_nothing():
    db = _Session([
        ("2026/2001(IMM)", [{"date": "2026-03-02", "event": "Vote in committee"},
                            {"date": "2026-02-10", "event": "Committee referral announced in Parliament"}]),
        ("2026/2010(IMM)", [{"date": "2026-07-07", "event": "Decision by Parliament"},
                            {"date": "2026-06-23", "event": "Vote in committee"}]),
        ("2026/2016(IMM)", []),
    ])
    got = _oeil_procedure_dates(db, ["2026/2001(IMM)", "2026/2010(IMM)", "2026/2016(IMM)", None])
    assert got == {"2026/2001(IMM)": date(2026, 2, 10), "2026/2010(IMM)": date(2026, 6, 23)}
    assert db.asked == {"refs": ["2026/2001(IMM)", "2026/2010(IMM)", "2026/2016(IMM)"]}


def test_no_reference_asks_nothing():
    db = _Session([])
    assert _oeil_procedure_dates(db, [None, ""]) == {} and db.asked is None
