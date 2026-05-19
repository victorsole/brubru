"""
Tests for _resolve_event_location in context_builder.

Pure helper that injects the right city next to each TODAY BLOCK event so
the LLM does not infer co-location from a same-day Strasbourg event.
"""

from services.ai.context_builder import _resolve_event_location


def test_council_always_brussels_even_in_plenary_week():
    assert _resolve_event_location("COUNCIL", "General Affairs Council", "Plenary") == "Brussels"


def test_european_council_always_brussels():
    assert _resolve_event_location("EUROPEAN_COUNCIL", "European Council", "Plenary") == "Brussels"


def test_ep_in_plenary_week_is_strasbourg():
    assert _resolve_event_location("EP", "Plenary session", "Plenary") == "Strasbourg"


def test_ep_in_committee_week_is_brussels():
    assert _resolve_event_location("EP", "AGRI committee meeting", "Committee") == "Brussels"


def test_commission_strasbourg_in_plenary_week():
    title = "College of Commissioners 2026-05-19 (Strasbourg)"
    assert _resolve_event_location("COMMISSION", title, "Plenary") == "Strasbourg"


def test_commission_brussels_off_plenary():
    assert _resolve_event_location("COMMISSION", "College of Commissioners", "Committee") == "Brussels"


def test_explicit_city_in_title_wins_over_default():
    # Council usually Brussels, but if the title says Luxembourg, use Luxembourg.
    assert _resolve_event_location("COUNCIL", "ECOFIN in Luxembourg", "Committee") == "Luxembourg"


def test_explicit_strasbourg_overrides_council_default():
    assert _resolve_event_location("COUNCIL", "Informal Council in Strasbourg", "Plenary") == "Strasbourg"


def test_empty_institution_falls_back_to_brussels():
    assert _resolve_event_location("", "Some event", None) == "Brussels"


def test_none_inputs_safe():
    assert _resolve_event_location(None, None, None) == "Brussels"


def test_case_insensitive_city_match():
    assert _resolve_event_location("COMMISSION", "STRASBOURG visit", "Plenary") == "Strasbourg"
