"""Regression guard for the PI semantic fallback (added 27 Jun 2026).

The fallback only fires when the keyword/body pass returns nothing, and maps meaning-only
titles to the canonical 34-label set. These pins lock the headline behaviours so the rules
can't silently regress, and assert the fallback never invents a non-canonical label.
"""
import pytest

from services.tracking.policy_area_classifier import classify, _FALLBACK_TOPICAL

_CANON = {
    "Agriculture", "Business and Industry", "Climate Action",
    "Communication Networks, Content and Technology", "Competition", "Consumer Protection",
    "Culture", "Customs", "Defence and Security", "Development and Cooperation",
    "Digital Policy and Digital Economy", "Economic and Financial Affairs",
    "Education, Training and Youth", "Employment and Social Affairs", "Energy", "Environment",
    "Food Safety", "Foreign and Security Policy", "Health", "Human Rights and Democracy",
    "Humanitarian Aid and Civil Protection", "Justice and Fundamental Rights",
    "Maritime Affairs and Fisheries", "Migration and Home Affairs",
    "Neighbourhood and Enlargement", "Regional Policy", "Research and Innovation",
    "Single Market", "Space Policy", "Statistics", "Taxation", "Trade and Economic Security",
    "Transport", "Women's Rights and Gender Equality",
}


@pytest.mark.parametrize("title,expected", [
    ("Situation in Cuba", "Foreign and Security Policy"),
    ("Recent proposals to fight poverty in the EU", "Employment and Social Affairs"),
    ("AI continent action plan", "Digital Policy and Digital Economy"),
    ("Revision of the Frontex regulation", "Migration and Home Affairs"),
    ("Approval of the assessment of the recovery and resilience plan for Spain",
     "Economic and Financial Affairs"),
    ("Council Implementing Regulation concerning restrictive measures against Iran",
     "Foreign and Security Policy"),
    ("LANDFILL DIRECTIVE", "Environment"),
])
def test_fallback_classifies_meaning_only_titles(title, expected):
    assert classify(title) == [expected]


def test_fallback_silent_on_pure_institutional():
    # genuinely horizontal -> stays empty, never forced
    assert classify("Amendments to Parliament's Rules of Procedure concerning appointments") == []
    assert classify("CELEX:31985R1578R(03)") == []
    assert classify("") == []


def test_fallback_only_canonical_labels():
    for leaf, _ in _FALLBACK_TOPICAL:
        assert leaf in _CANON, f"fallback rule emits non-canonical label {leaf!r}"
