"""
A funding template's "next deadline" is the next cut-off still open, never a past one.

Why (8 Oct 2026): three places showed `cut_offs_2026_cet[0]`, so in October the
EIC Accelerator templates offered 7 January / 4 March 2026 and STEP 11 February
2026 as the "next cut-off", and a new draft was pre-filled with a date already
past. The short proposal also carried the FULL-proposal batches, although short
proposals are batched the first Tuesday of every month at 17:00 Brussels time.

No network, no database: templates are read from the repository.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.funding_template_loader import TEMPLATES_DIR, next_deadline  # noqa: E402

BXL = ZoneInfo("Europe/Brussels")


def at(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=BXL)


def tpl(name):
    return json.loads((TEMPLATES_DIR / f"{name}.json").read_text())


SHORT = {"cutoff_rule": "first_tuesday_monthly", "cutoff_time_brussels": "17:00", "submission_end_date": "2026-12-17"}


def test_short_proposal_batches_on_the_first_tuesday():
    # 8 Oct 2026: October's first Tuesday (6 Oct) has passed, so the next batch is 3 Nov.
    assert next_deadline(SHORT, at(2026, 10, 8)) == "2026-11-03T17:00:00+01:00"


def test_first_tuesday_itself_before_and_after_five_pm():
    assert next_deadline(SHORT, at(2026, 10, 6, 16, 59)) == "2026-10-06T17:00:00+02:00"  # still summer time
    assert next_deadline(SHORT, at(2026, 10, 6, 17, 1)) == "2026-11-03T17:00:00+01:00"


def test_short_proposal_window_ends_with_the_portal_topic():
    # December's batch (1 Dec) is still inside the topic; January's would not be.
    assert next_deadline(SHORT, at(2026, 11, 20)) == "2026-12-01T17:00:00+01:00"
    assert next_deadline(SHORT, at(2026, 12, 5)) == "2026-12-17"


def test_list_gives_the_next_future_cut_off_not_the_first():
    full = tpl("eic-accelerator-stage-2")
    assert next_deadline(full, at(2026, 10, 8)) == "2026-11-04T17:00:00+01:00"
    step = tpl("eic-step-scale-up")
    assert next_deadline(step, at(2026, 10, 8)) == "2026-11-25T17:00:00+01:00"


def test_all_past_returns_the_last_known_date():
    full = tpl("eic-accelerator-stage-2")
    assert next_deadline(full, at(2026, 12, 1)) == "2026-11-04T17:00:00+01:00"


def test_single_deadline_and_indicative_future_deadline():
    assert next_deadline({"deadline_2026_cet": "2026-10-28T17:00:00+01:00"}, at(2026, 10, 8)) == "2026-10-28T17:00:00+01:00"
    both = {"deadline_2026_cet": "2026-02-26T17:00:00+01:00", "deadline_2027_indicative_cet": "2027-06-18T17:00:00+02:00"}
    assert next_deadline(both, at(2026, 10, 8)) == "2027-06-18T17:00:00+02:00"


def test_no_template_shows_a_past_date_while_a_future_one_exists():
    """Every real template: if any stated date is in the future, the answer is in the future."""
    now = at(2026, 10, 8)
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        if "." in path.stem:
            continue
        t = json.loads(path.read_text())
        dates = list(t.get("cut_offs_2026_cet") or []) + [
            t[k] for k in ("deadline_2026_cet", "deadline_2027_cet", "deadline_2027_indicative_cet") if t.get(k)
        ]
        has_future = t.get("cutoff_rule") == "first_tuesday_monthly" or any(
            datetime.fromisoformat(s) > now for s in dates if len(s) > 10
        )
        got = next_deadline(t, now)
        if has_future:
            assert got, path.name
            parsed = datetime.fromisoformat(got) if len(got) > 10 else datetime.fromisoformat(got + "T17:00:00+01:00")
            assert parsed > now, f"{path.name} shows past date {got}"


def test_stage_1_no_longer_carries_the_full_proposal_batches():
    short = tpl("eic-accelerator-stage-1")
    assert "cut_offs_2026_cet" not in short
    assert short["cutoff_rule"] == "first_tuesday_monthly"
