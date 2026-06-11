"""
Unit tests for AI response post-processing functions.

Covers the four functions in ai_service.py that directly transform
every AI response before it reaches the user:

    _strip_context_markers    -- removes leaked internal prompt markers
    _strip_orphan_citations   -- removes [N] references that don't map to sources
    _linkify_mep_names        -- converts MEP names into clickable EP profile links
    _linkify_legislation      -- converts legislation acronyms into EUR-Lex links

Quality Framework: Week 1 playbook item C. Great Audit: F013 addresses the
"Big 3 zero tests" finding.

Run: cd backend && python3.12 -m pytest tests/test_ai_post_processing.py -v
"""

import pytest
from unittest.mock import MagicMock

from services.ai_service import AIService


@pytest.fixture
def service():
    """
    Create an AIService instance without running __init__.

    The four post-processing methods under test are effectively pure:
    they don't touch self.client, self.model, or any other init state.
    Using __new__ bypasses the Anthropic client setup and keeps these
    as true unit tests (no API key, no network, no mocks of internals).
    """
    return AIService.__new__(AIService)


# ---------------------------------------------------------------------------
# _strip_context_markers
# ---------------------------------------------------------------------------
class TestStripContextMarkers:
    """Removes leaked internal prompt structure markers from the response."""

    def test_strips_single_marker(self, service):
        text = "The AI Act is EU CONTEXT Regulation 2024/1689."
        result = service._strip_context_markers(text)
        assert "EU CONTEXT" not in result
        assert "The AI Act is" in result
        assert "Regulation 2024/1689" in result

    def test_strips_all_known_markers(self, service):
        markers = [
            "EU LAW SNAPSHOT",
            "EU INSTITUTIONAL CALENDAR",
            "LEGISLATIVE FILES",
            "COMMISSION DOCUMENTS",
            "COMMITTEE WORK IN PROGRESS",
            "EPRS PUBLICATIONS",
            "EU CONTEXT",
        ]
        for marker in markers:
            text = f"Before {marker} after."
            result = service._strip_context_markers(text)
            assert marker not in result, f"Failed to strip: {marker}"

    def test_leaves_clean_text_untouched(self, service):
        text = "The GDPR (Regulation 2016/679) governs personal data."
        result = service._strip_context_markers(text)
        assert result == text

    def test_strips_multiple_markers_in_one_response(self, service):
        text = "EU LAW SNAPSHOT info here LEGISLATIVE FILES more info EU CONTEXT end."
        result = service._strip_context_markers(text)
        assert "EU LAW SNAPSHOT" not in result
        assert "LEGISLATIVE FILES" not in result
        assert "EU CONTEXT" not in result
        assert "info here" in result
        assert "more info" in result

    def test_handles_empty_string(self, service):
        assert service._strip_context_markers("") == ""

    def test_handles_only_whitespace(self, service):
        assert service._strip_context_markers("   \n\t  ") == ""

    def test_preserves_similar_but_distinct_text(self, service):
        # "EU context" lowercase should NOT be stripped (only exact marker)
        text = "The EU context of this regulation is important."
        result = service._strip_context_markers(text)
        assert "EU context of this regulation" in result


# ---------------------------------------------------------------------------
# _strip_orphan_citations
# ---------------------------------------------------------------------------
class TestStripOrphanCitations:
    """Removes [N] markers that reference non-existent citations (prevents hallucinations)."""

    def test_strips_orphan_when_no_citations(self, service):
        text = "The AI Act [1] is a landmark regulation [2]."
        result = service._strip_orphan_citations(text, citations=[])
        assert "[1]" not in result
        assert "[2]" not in result
        assert "The AI Act" in result
        assert "is a landmark regulation" in result

    def test_keeps_valid_citations(self, service):
        citations = [{"title": "A"}, {"title": "B"}]
        text = "The AI Act [1] is landmark [2]."
        result = service._strip_orphan_citations(text, citations=citations)
        assert "[1]" in result
        assert "[2]" in result

    def test_strips_only_out_of_range_markers(self, service):
        citations = [{"title": "A"}, {"title": "B"}]  # max_valid = 2
        text = "Valid [1] valid [2] orphan [3] orphan [5]."
        result = service._strip_orphan_citations(text, citations=citations)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" not in result
        assert "[5]" not in result

    def test_handles_zero_and_negative(self, service):
        # [0] should be stripped (citations are 1-indexed)
        citations = [{"title": "A"}]
        text = "The AI Act [0] and [1] are referenced."
        result = service._strip_orphan_citations(text, citations=citations)
        assert "[0]" not in result
        assert "[1]" in result

    def test_collapses_double_spaces(self, service):
        text = "Text [5] with orphan [7] markers."
        result = service._strip_orphan_citations(text, citations=[])
        # No double spaces should remain
        assert "  " not in result

    def test_leaves_non_citation_brackets_alone(self, service):
        # [note] should not be matched (not numeric)
        text = "Some text [note] with [1] a [marker]."
        result = service._strip_orphan_citations(text, citations=[])
        assert "[note]" in result
        assert "[marker]" in result
        assert "[1]" not in result

    def test_handles_empty_text(self, service):
        assert service._strip_orphan_citations("", citations=[]) == ""

    def test_regression_preserves_markdown_links(self, service):
        # Markdown links like [text](url) should not be broken
        text = "See [EUR-Lex](https://eur-lex.europa.eu) for [1] references."
        result = service._strip_orphan_citations(text, citations=[])
        assert "[EUR-Lex](https://eur-lex.europa.eu)" in result
        assert "[1]" not in result


# ---------------------------------------------------------------------------
# _linkify_mep_names
# ---------------------------------------------------------------------------
class TestLinkifyMepNames:
    """Converts MEP names in the response to clickable EP profile links."""

    def test_linkifies_full_name(self, service):
        mep_data = {
            "antonio_decaro": {
                "name": "Antonio DECARO",
                "url": "https://www.europarl.europa.eu/meps/en/204568",
            }
        }
        text = "The rapporteur is Antonio DECARO."
        result = service._linkify_mep_names(text, mep_data)
        assert "[Antonio DECARO](https://www.europarl.europa.eu/meps/en/204568)" in result

    def test_strips_markdown_bold_when_linking(self, service):
        mep_data = {
            "maria_salinas": {
                "name": "Maria SALINAS",
                "url": "https://www.europarl.europa.eu/meps/en/999",
            }
        }
        text = "Co-rapporteur **Maria SALINAS** proposed."
        result = service._linkify_mep_names(text, mep_data)
        # The ** should be removed, link should be present
        assert "**Maria SALINAS**" not in result
        assert "[Maria SALINAS](https://www.europarl.europa.eu/meps/en/999)" in result

    def test_empty_mep_data_returns_unchanged(self, service):
        text = "Antonio DECARO is the rapporteur."
        result = service._linkify_mep_names(text, {})
        assert result == text

    def test_does_not_double_link(self, service):
        mep_data = {
            "benifei": {
                "name": "Brando BENIFEI",
                "url": "https://example.com/benifei",
            }
        }
        # Already-linked name should not be re-linked
        text = "Already linked: [Brando BENIFEI](https://other.example.com)."
        result = service._linkify_mep_names(text, mep_data)
        # Should still only have one link
        assert result.count("[Brando BENIFEI]") == 1

    def test_case_insensitive_matching(self, service):
        mep_data = {
            "decaro": {
                "name": "Antonio Decaro",
                "url": "https://example.com/decaro",
            }
        }
        text = "The rapporteur ANTONIO DECARO and antonio decaro both appear."
        result = service._linkify_mep_names(text, mep_data)
        # At least one should be linked
        assert "example.com/decaro" in result

    def test_handles_empty_text(self, service):
        mep_data = {"x": {"name": "Test MEP", "url": "https://ex.com"}}
        assert service._linkify_mep_names("", mep_data) == ""


# ---------------------------------------------------------------------------
# _linkify_legislation
# ---------------------------------------------------------------------------
class TestLinkifyLegislation:
    """
    Converts legislation acronyms (GDPR, AI Act, CBAM) to EUR-Lex links.

    These tests exercise the live acronyms database
    (backend/knowledge_base/institutions/legislation_acronyms.json).
    They verify behaviour, not specific CELEX numbers, to stay robust
    as the database evolves.
    """

    def test_adds_eurlex_link_for_known_acronym(self, service):
        text = "The GDPR regulates personal data."
        result = service._linkify_legislation(text)
        # Should produce a markdown link to EUR-Lex containing CELEX
        assert "eur-lex.europa.eu" in result
        assert "CELEX:" in result
        # The acronym should now appear inside a markdown link
        assert "[GDPR](" in result

    def test_does_not_double_link_already_linked_acronym(self, service):
        text = "See [GDPR](https://example.com/other) for details."
        result = service._linkify_legislation(text)
        # The pre-existing link should not be broken
        assert "[GDPR](https://example.com/other)" in result

    def test_removes_incorrect_committee_link_for_legislation_acronym(self, service):
        # Claude sometimes wrongly treats legislation acronyms as committee codes.
        # The post-processor should remove the wrong committee link and replace
        # with the correct EUR-Lex link (or leave the bare acronym).
        text = "The [CBAM](https://www.europarl.europa.eu/committees/en/CBAM/home) applies."
        result = service._linkify_legislation(text)
        # Should NOT contain the wrong committee link
        assert "committees/en/CBAM" not in result

    def test_leaves_unknown_acronym_alone(self, service):
        text = "The XYZZZ-ACT is fictional."
        result = service._linkify_legislation(text)
        # Unknown acronym: no link added
        assert "[XYZZZ-ACT]" not in result

    def test_preserves_surrounding_text(self, service):
        text = "Before GDPR content after."
        result = service._linkify_legislation(text)
        assert "Before" in result
        assert "content after" in result

    def test_handles_empty_text(self, service):
        assert service._linkify_legislation("") == ""

    def test_strips_fake_committee_codes(self, service):
        # NZIA is not a real EP committee code.
        # If Claude writes [NZIA](...committees/en/NZIA/home), strip the link.
        text = "The [NZIA](https://www.europarl.europa.eu/committees/en/NZIA/home) targets net-zero."
        result = service._linkify_legislation(text)
        assert "committees/en/NZIA" not in result
        # The acronym text should still be present (link was stripped, text kept)
        assert "NZIA" in result

    def test_preserves_real_committee_links(self, service):
        # ENVI is a real EP committee code - its committee link should survive.
        text = "The [ENVI](https://www.europarl.europa.eu/committees/en/ENVI/home) committee voted."
        result = service._linkify_legislation(text)
        # ENVI committee link should be preserved (it's a real committee)
        assert "committees/en/ENVI" in result


# ---------------------------------------------------------------------------
# _linkify_legislation STEP 0 -- correct a WRONG CELEX the generator emitted
# inline. Regression guard for the 11 June 2026 production bug where a weaker
# open model wrote [Digital Services Act](...CELEX:32023R1201) (an implementing
# regulation) instead of the real DSA (32022R2065). DSA is asserted by exact
# CELEX because it is a marquee law whose number is fixed by CLAUDE.md.
# ---------------------------------------------------------------------------
class TestLinkifyLegislationCelexOverride:
    DSA = "32022R2065"
    WRONG = "32023R1201"

    def _eurlex(self, celex):
        return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

    def test_corrects_wrong_inline_celex_for_full_name(self, service):
        text = f"[Digital Services Act]({self._eurlex(self.WRONG)}) governs platforms."
        result = service._linkify_legislation(text)
        assert self.WRONG not in result
        assert self.DSA in result

    def test_corrects_wrong_inline_celex_for_acronym(self, service):
        text = f"The [DSA]({self._eurlex(self.WRONG)}) governs platforms."
        result = service._linkify_legislation(text)
        assert self.WRONG not in result
        assert self.DSA in result

    def test_leaves_correct_inline_celex_untouched(self, service):
        text = f"[Digital Services Act]({self._eurlex(self.DSA)}) governs platforms."
        result = service._linkify_legislation(text)
        assert self.DSA in result
        assert result.count(self.DSA) == 1  # not duplicated

    def test_bare_full_name_links_to_correct_celex(self, service):
        # The DB key "Digital Services Act" must map to the real DSA, not the
        # implementing regulation (the poisoned entry that caused the prod bug).
        result = service._linkify_legislation("The Digital Services Act governs platforms.")
        assert self.WRONG not in result
        assert self.DSA in result

    def test_does_not_touch_unknown_link_text(self, service):
        # An unmapped link text must be left exactly as-is (conservative).
        text = f"[some niche measure]({self._eurlex(self.WRONG)})."
        result = service._linkify_legislation(text)
        assert result == text

    def test_does_not_touch_non_eurlex_domain(self, service):
        text = f"[Digital Services Act](https://example.com/CELEX:{self.WRONG})."
        result = service._linkify_legislation(text)
        assert result == text

    def test_db_has_no_name_celex_conflicts(self):
        # The conflict that caused the prod bug (DSA -> two CELEX) must stay gone.
        import json
        from pathlib import Path
        from collections import defaultdict

        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge_base" / "institutions" / "legislation_acronyms.json"
        )
        db = json.loads(path.read_text(encoding="utf-8"))["acronyms"]
        names = defaultdict(set)
        for key, info in db.items():
            celex = info.get("celex")
            if not celex:
                continue
            names[key.strip().lower()].add(celex)
            full = (info.get("full_name") or "").strip().lower()
            if full:
                names[full].add(celex)
        conflicts = {k: s for k, s in names.items() if len(s) > 1}
        assert conflicts == {}, f"name->CELEX conflicts present: {conflicts}"
