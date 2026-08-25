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


# ---------------------------------------------------------------------------
# Safe-by-default rule (11 June 2026): never auto-link an acronym whose DB entry
# is an Implementing/Delegated act. The acronyms DB was bulk auto-ingested and
# mis-keyed popular acronyms onto such instruments (DSA->implementing-reg class,
# plus WEEE, UCITS, FLEGT, ELTIF, ...). _is_linkify_safe_act neutralises the
# whole poisoned long tail deterministically.
# ---------------------------------------------------------------------------
class TestLinkifySafeByDefault:
    def test_helper_rejects_implementing_and_delegated(self):
        from services.ai_service import _is_linkify_safe_act
        assert _is_linkify_safe_act("Regulation (EU) 2022/2065 ... (Digital Services Act)") is True
        assert _is_linkify_safe_act("Commission Implementing Regulation (EU) 2017/699 ...") is False
        assert _is_linkify_safe_act("Commission Delegated Regulation (EU) 2024/911 ...") is False
        assert _is_linkify_safe_act("Council Implementing Decision (EU) 2018/748 ...") is False
        assert _is_linkify_safe_act(None) is True  # absence of marker = treat as base

    def test_poison_acronyms_do_not_linkify(self, service):
        # WEEE/UCITS/FLEGT/ELTIF entries point at implementing/delegated acts.
        for acr in ("WEEE", "UCITS", "FLEGT", "ELTIF"):
            out = service._linkify_legislation(f"The {acr} framework applies.")
            assert f"[{acr}](" not in out, f"{acr} should not auto-link (non-base act)"

    def test_base_marquee_laws_still_linkify(self, service):
        for acr in ("DSA", "GDPR", "CBAM", "DMA"):
            out = service._linkify_legislation(f"The {acr} framework applies.")
            assert f"[{acr}](" in out and "eur-lex" in out, f"{acr} must still link (base act)"

    def test_removed_non_eu_keys_are_gone(self):
        import json
        from pathlib import Path
        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge_base" / "institutions" / "legislation_acronyms.json"
        )
        db = json.loads(path.read_text(encoding="utf-8"))["acronyms"]
        assert "Personal Information Protection Act" not in db
        assert "Renewable Energy Sources Act" not in db
        # IPA II repointed to its base regulation, not the implementing reg.
        assert db["IPA II"]["celex"] == "32014R0231"


class TestSanitiseCelexLinks:
    """_sanitise_celex_links must never delete answer text.

    Regression guard for defect D1 (audit, 25 Aug 2026). The CELEX capture
    group admitted parentheses, so it swallowed a link's own closing bracket
    and ran to the next ")" in the paragraph. Two links in one paragraph
    collapsed into a single match and everything between them was deleted --
    silently, with the second sentence's citation markers grafted onto the
    first, so the output still parsed as valid Markdown. Measured against the
    production corpus: 98 of 589 stored answers would have lost text, 35,060
    characters in total, worst single answer 1,348 characters.

    The first test below is the one that matters: it fails loudly on any
    future regex change that starts eating prose.
    """

    EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"

    def _link(self, label, celex):
        return f"[{label}]({self.EURLEX}{celex})"

    def test_two_links_in_one_paragraph_keep_the_text_between_them(self, service):
        """The D1 case, with a second label that is NOT denylisted.

        The production sentence used [PSP], but that is now stripped by the
        echoed-denylist guard, which would mask what this test is actually
        about: prose between two links surviving. Keep the two concerns apart.
        """
        between = " [2], [3]. Refund duty is owed under "
        text = (
            "Article 5c of "
            + self._link("Regulation (EC) 260/2012", "32024R0886")
            + between
            + self._link("Regulation (EU) 2024/886", "32024R0886")
            + " [1], [3]."
        )
        out = service._sanitise_celex_links(text)
        assert "Refund duty is owed under" in out, "prose between two links was deleted"
        assert out.count("](https://eur-lex") == 2, "two links in, two links out"
        assert out.count("[2], [3]") == 1 and out.count("[1], [3]") == 1

    def test_many_links_in_one_paragraph_lose_nothing(self, service):
        parts = [f"clause {i} " + self._link(f"Act {i}", c) + " ends. "
                 for i, c in enumerate(("32016R0679", "32024R1689", "32017R1980",
                                        "32022R2065", "32023R1542"))]
        text = "".join(parts)
        out = service._sanitise_celex_links(text)
        for i in range(5):
            assert f"clause {i}" in out
        assert out.count("](https://eur-lex") == 5

    def test_link_text_still_overrides_a_contradicting_celex(self, service):
        """The function's actual job must keep working."""
        text = "Article 5c of " + self._link("Regulation (EC) 260/2012", "32024R0886") + "."
        out = service._sanitise_celex_links(text)
        assert "CELEX:32012R0260" in out, "text names 260/2012, so the URL must say so"

    def test_impossible_year_drops_the_link_but_keeps_the_words(self, service):
        text = "The " + self._link("OLAF Regulation", "31073R1999") + " applies."
        out = service._sanitise_celex_links(text)
        assert "OLAF Regulation" in out and "applies" in out
        assert "eur-lex" not in out

    def test_corrigendum_celex_is_still_matched_whole(self, service):
        text = "See " + self._link("GDPR corrigendum", "32016R0679(01)") + " today."
        out = service._sanitise_celex_links(text)
        assert "today" in out
        assert "32016R0679(01)" in out

    def test_url_with_trailing_query_params_survives(self, service):
        text = "[AI Act](" + self.EURLEX + "32024R1689&from=EN) is in force."
        out = service._sanitise_celex_links(text)
        assert "is in force" in out
        assert out.count("](https://eur-lex") == 1

    def test_output_is_never_shorter_unless_a_link_was_dropped(self, service):
        """Blanket guard: the only sanctioned way to lose characters is rule 1."""
        text = (
            "First " + self._link("Regulation (EU) 2024/1689", "32024R1689")
            + " and second " + self._link("Regulation (EU) 2016/679", "32016R0679")
            + " and third " + self._link("Directive (EU) 2015/2366", "32015L2366") + "."
        )
        out = service._sanitise_celex_links(text)
        assert len(out) == len(text), "no link should be dropped here, so length must hold"


class TestAcronymCollisionGuards:
    """Audit defects D2/D3, 25 Aug 2026.

    PSP was confirmed firing in production on 24 Aug in all three payments
    answers, on three different providers, linking "payment service provider"
    to a paralytic-shellfish-poison regulation. It survived the 24 Aug cleanup
    because it genuinely appears inside a real act's title, and it passed both
    existing guards. These tests pin the two remedies: a code denylist for
    acronyms whose entry is accurate but whose common meaning is something
    else, and outright removal for organisation acronyms and State-aid case
    numbers, which per CLAUDE.md must never be in the file at all.
    """

    COLLIDING = ("PSP", "BIT", "CIT", "PES", "PAC", "EEE", "MIT", "SGEI")
    ORGS_AND_JUNK = ("IOC", "WCO", "GRECO", "ICAC", "IPEEC", "IRSG", "GFCM",
                     "WCPFC", "ECSA", "ETSC", "ERAC", "CFSP",
                     "C29/08", "CNU", "EMEF", "SZP", "ZFM")

    def test_colliding_acronyms_never_linkify(self, service):
        for acr in self.COLLIDING:
            out = service._linkify_legislation(f"The {acr} framework applies here.")
            assert f"[{acr}](" not in out, f"{acr} must not auto-link"

    def test_the_production_psp_sentence_stays_clean(self, service):
        """The exact shape that shipped to production on 24 August."""
        out = service._linkify_legislation(
            "Article 5c(8) creates a refund duty on the payer's PSP."
        )
        assert "32017R1980" not in out, "shellfish regulation linked into a payments answer"
        assert "eur-lex" not in out

    def test_organisation_and_junk_keys_are_gone_from_the_file(self):
        import json
        from pathlib import Path
        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge_base" / "institutions" / "legislation_acronyms.json"
        )
        db = json.loads(path.read_text(encoding="utf-8"))["acronyms"]
        for key in self.ORGS_AND_JUNK:
            assert key not in db, f"{key} is an organisation or a case number, not legislation"

    def test_grandfathered_entries_are_untouched(self):
        """CLAUDE.md names IMO explicitly. Do not let a future sweep take it."""
        import json
        from pathlib import Path
        path = (
            Path(__file__).resolve().parent.parent
            / "knowledge_base" / "institutions" / "legislation_acronyms.json"
        )
        db = json.loads(path.read_text(encoding="utf-8"))["acronyms"]
        assert db["IMO"]["celex"] == "32016D0807"

    def test_marquee_acts_still_linkify(self, service):
        for acr in ("GDPR", "DSA", "CBAM", "DMA"):
            out = service._linkify_legislation(f"The {acr} framework applies.")
            assert f"[{acr}](" in out, f"{acr} must still link"

    def test_an_echoed_denylisted_link_is_stripped(self, service):
        """The denylist guards our linkifier; this guards the generator.

        Three answers carrying [PSP](...32017R1980) are already stored in
        chat_messages, and history is replayed into context, so the model can
        echo one back past a guard that only runs when WE build the link.
        """
        text = ("Article 5c(8) creates a refund duty on the payer's "
                "[PSP](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32017R1980)"
                " within the deadline.")
        out = service._sanitise_celex_links(text)
        assert "32017R1980" not in out, "echoed shellfish link survived"
        assert "PSP" in out, "the word itself must be kept"
        assert "within the deadline" in out, "surrounding prose must be kept"

    def test_a_legitimate_acronym_link_is_not_stripped(self, service):
        text = ("The [GDPR](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679)"
                " applies.")
        out = service._sanitise_celex_links(text)
        assert "32016R0679" in out and "](https://eur-lex" in out
