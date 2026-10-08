"""
The curated EIC calendar gives the next batch the portal cannot, and stays in step with the Work Programme.

Why (8 Oct 2026): the portal gives the EIC Accelerator topic one end date and a
budget of 0, so the Tenderator feed counted down to 17 December 2026 while short
proposals batch on the first Tuesday of every month and full proposals on six
dates. The calendar (data/eic_call_calendar.json) carries the Work Programme's
dates and budgets; the next date uses the Tender Docs helper so both agree.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.eic_call_calendar import conflict_note, next_batches, wp_budget  # noqa: E402

BXL = ZoneInfo("Europe/Brussels")


def test_accelerator_next_short_and_full_batches():
    got = next_batches("HORIZON-EIC-2026-ACCELERATOR-01", datetime(2026, 10, 8, 12, tzinfo=BXL))
    assert got == {"short": "2026-11-03T17:00:00+01:00", "full": "2026-11-04T17:00:00+01:00"}


def test_a_kind_with_only_past_dates_is_omitted_not_shown_as_next():
    got = next_batches("HORIZON-EIC-2026-ACCELERATOR-01", datetime(2026, 11, 10, tzinfo=BXL))
    assert got == {"short": "2026-12-01T17:00:00+01:00"}


def test_step_and_defence():
    now = datetime(2026, 10, 8, 12, tzinfo=BXL)
    assert next_batches("HORIZON-EIC-2026-STEP", now) == {"batch": "2026-11-25T17:00:00+01:00"}
    assert next_batches("HORIZON-EIC-2026-DEFENCE-01", now) == {"batch": "2026-10-28T17:00:00+01:00"}
    assert conflict_note("HORIZON-EIC-2026-STEP")  # the portal end date disagrees with the WP batch


def test_work_programme_budgets():
    assert wp_budget("HORIZON-EIC-2026-ACCELERATOR-01") == 634_000_000
    assert wp_budget("HORIZON-EIC-2026-STEP") == 300_000_000
    assert wp_budget("HORIZON-EIC-2026-DEFENCE-01") == 100_000_000


def test_other_calls_are_untouched():
    assert next_batches("LIFE-2026-SAP-ENV", datetime(2026, 10, 8, tzinfo=BXL)) is None
    assert wp_budget("LIFE-2026-SAP-ENV") is None
