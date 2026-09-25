"""Only an EP committee-meeting event counts as calendar coverage (25 Sep 2026).

The gap query matched a committee's four-letter code anywhere in ANY event that
day ("AGRI" in the Agriculture and Fisheries Council, "BUDG" in the Committee Week
banner), so 9 of 13 committees meeting on 28 Sep 2026 were never added.
"""
import pathlib
import re
import sys

_B = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_B / "scripts"))

from sync_calendar_from_emeeting_agendas import _MISSING_SQL  # noqa: E402

_SQL = " ".join(_MISSING_SQL.split())


def test_coverage_is_restricted_to_ep_committee_meetings():
    assert "e.institution = 'EP'" in _SQL
    assert "e.event_type = 'committee_meeting'" in _SQL


def test_no_substring_match_on_free_text():
    assert "description" not in _SQL
    assert not re.search(r"ILIKE\s+'%'\s*\|\|\s*a\.committee_code", _SQL, re.I)


def test_title_fallback_is_a_whole_word():
    assert "\\y' || a.committee_code || '\\y" in _SQL


def test_one_row_per_committee_and_day():
    assert "DISTINCT ON (a.committee_code, a.meeting_date)" in _SQL
