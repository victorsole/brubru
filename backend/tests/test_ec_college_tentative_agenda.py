"""The College generator writes tentative-agenda items into meeting descriptions.

Guards the 16 September 2026 fix: the calendar sync overwrites a differing
description on every run, so agenda items only survive if the generator itself
emits them.
"""
import json
from datetime import date

from services.scrapers import ec_college_scraper as g


AGENDA = {
    "source_label": "Commission tentative agenda of 14 September 2026",
    "responsible_heading": "President or Executive Vice-President responsible",
    "meetings": {"2026-10-20": [{"item": "Climate resilience framework", "responsible": "Ribera"},
                                {"item": "Enlargement package", "responsible": "President"}]},
}


def test_listed_date_carries_items_source_and_hedge():
    d = g.describe_meeting(date(2026, 10, 20), AGENDA)
    assert "Climate resilience framework (Ribera)" in d
    assert "Enlargement package (President)" in d
    assert "tentative" in d and "may change" in d
    assert "14 September 2026" in d
    assert d.endswith(g.GENERIC_DESCRIPTION)


def test_unlisted_date_keeps_generic_description():
    assert g.describe_meeting(date(2026, 11, 4), AGENDA) == g.GENERIC_DESCRIPTION


def test_missing_file_does_not_break_generation(tmp_path):
    assert g.load_tentative_agenda(tmp_path / "absent.json") == {}
    assert g.describe_meeting(date(2026, 10, 20), {}) == g.GENERIC_DESCRIPTION


def test_malformed_file_is_ignored(tmp_path):
    f = tmp_path / "bad.json"; f.write_text("{not json")
    assert g.load_tentative_agenda(f) == {}


def test_repository_file_is_valid_and_has_no_dashes():
    data = g.load_tentative_agenda()
    assert data.get("meetings"), "college_tentative_agenda.json missing or empty"
    text = json.dumps(data, ensure_ascii=False)
    assert "—" not in text and "–" not in text


def test_generator_uses_the_file_for_the_strasbourg_tuesday():
    events = g.generate_college_meetings(months_ahead=3,
                                         strasbourg_plenary_dates=[date(2026, 10, 19)])
    ev = next((e for e in events if e["start_date"] == date(2026, 10, 20)), None)
    assert ev is not None
    assert "Climate resilience framework (Ribera)" in ev["description"]


def test_held_meeting_keeps_the_description_the_oj_sync_wrote():
    """The generator must not revert a held meeting's OJ-built description."""
    from types import SimpleNamespace
    from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService

    existing = SimpleNamespace(title="College of Commissioners: Weekly Meeting (Strasbourg)",
                               start_date=date(2026, 9, 15), end_date=None,
                               description="Ordre du jour de la 2578eme reunion: fair labour mobility package",
                               source_url="u", agenda_url=None, policy_areas=[], organiser=None,
                               venue=None, last_updated=None)

    class Q:
        def filter(self, *a, **k): return self
        def first(self): return existing

    db = SimpleNamespace(query=lambda *a, **k: Q())
    svc = EUCalendarSyncService.__new__(EUCalendarSyncService)
    data = {"institution": "COMMISSION", "event_type": "commission_college_meeting",
            "title": existing.title, "start_date": existing.start_date,
            "description": g.GENERIC_DESCRIPTION, "source": "ec_college",
            "external_id": "ec_college_2026-09-15", "source_url": "u",
            "keep_existing_description": True}
    svc._upsert_event(db, data, {"added": 0, "updated": 0, "skipped": 0, "errors": 0})
    assert existing.description.startswith("Ordre du jour")

    data.pop("keep_existing_description")
    svc._upsert_event(db, data, {"added": 0, "updated": 0, "skipped": 0, "errors": 0})
    assert existing.description == g.GENERIC_DESCRIPTION  # without the flag it would be reverted
