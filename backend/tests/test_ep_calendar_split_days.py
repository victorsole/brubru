"""A split EP calendar day carries both activities (25 Sep 2026).

The EP's PDF colours Thursday 1 Oct 2026 half committee pink, half group blue.
The derivation took the majority colour and the calendar called it a group day
while six committees met. Ten Thursdays in 2026 are split.
"""
from datetime import date

from services.scrapers.ep_calendar_loader import load_ep_calendar


def _on(events, d):
    return sorted(e["event_type"] for e in events if e["start_date"] == d and e["source"] == "ep_calendar_json")


def test_split_thursday_has_committee_and_group():
    ev = load_ep_calendar(2026)
    assert _on(ev, date(2026, 10, 1)) == ["committee_week", "group_week"]
    assert _on(ev, date(2026, 10, 15)) == ["committee_week", "group_week"]


def test_plain_days_are_unchanged():
    ev = load_ep_calendar(2026)
    assert _on(ev, date(2026, 9, 28)) == ["committee_week"]
    assert _on(ev, date(2026, 9, 29)) == ["group_week"]


def test_no_unknown_event_type_reaches_the_enum():
    ev = load_ep_calendar(2026)
    assert "committee_and_group" not in {e["event_type"] for e in ev}
