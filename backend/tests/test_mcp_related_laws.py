"""Relevance guard for ask_brubru's related_laws (competitor scan, 25 Aug 2026).

Found while checking whether Brubru could survive the head-to-head demo a
competitor published that morning: ask the same question of an assistant with
and without the connector, and show the difference.

Asking Brubru's MCP "which article of the Cyber Resilience Act imposes the
24-hour reporting duty" returned, as its top related law:

    32008R1010  Council Regulation (EC) No 1010/2008 ... imposing a definitive
                countervailing duty on imports of sulphanilic acid from India

The precise plainto_tsquery path finds nothing for conversational phrasing, and
the OR fallback then matched "duty" against "countervailing duty" and "imposes"
against "imposing a definitive countervailing duty". EU law is full of acts
whose TITLE is built from generic legal English, so those words are noise, not
signal. Confidently irrelevant, on the surface being marketed next week.

These tests hit the real database, because the defect was in what the corpus
returns and a mocked one would have proved nothing.
"""

import re

import pytest

from services.mcp.tools import _STOP, _related_laws


class TestRelatedLawsRelevance:

    def test_the_cyber_resilience_act_leads_its_own_question(self):
        laws = _related_laws(
            "Which article of the Cyber Resilience Act imposes the 24-hour reporting duty?",
            limit=5,
        )
        assert laws, "a question naming an act by name must find that act"
        assert laws[0]["celex"] == "32024R2847", (
            f"expected the Cyber Resilience Act first, got {laws[0]['celex']}: "
            f"{laws[0]['title'][:80]}"
        )

    def test_a_cybersecurity_question_returns_no_trade_defence_act(self):
        """The exact failure: 'duty' and 'imposes' dragging in countervailing duties."""
        laws = _related_laws(
            "Which article of the Cyber Resilience Act imposes the 24-hour reporting duty?",
            limit=5,
        )
        for law in laws:
            title = law["title"].lower()
            assert "countervailing duty" not in title, f"trade-defence act surfaced: {law['celex']}"
            assert "anti-dumping" not in title, f"trade-defence act surfaced: {law['celex']}"

    @pytest.mark.parametrize("word", [
        "duty", "imposes", "reporting", "article", "obligation", "regulation", "directive",
    ])
    def test_generic_legal_english_is_stopped(self, word):
        assert word in _STOP, f"{word!r} appears in thousands of act titles and is noise"

    def test_a_named_acronym_still_survives_the_stoplist(self):
        """Over-stopping would be the opposite failure: nothing found at all."""
        q = "Which article of the Cyber Resilience Act imposes the 24-hour reporting duty?"
        surviving = [w for w in re.findall(r"[A-Za-z]{4,}", q) if w.lower() not in _STOP]
        assert "Cyber" in surviving and "Resilience" in surviving

    def test_the_act_outranks_its_own_corrigenda(self):
        """A corrigendum shares the act's words, ties on rank, and used to win on
        row order alone. The act is what a reader wants named."""
        laws = _related_laws("Cyber Resilience Act", limit=5)
        titles = [l["title"].lower() for l in laws]
        if any(t.startswith("corrigendum") for t in titles):
            first_corr = next(i for i, t in enumerate(titles) if t.startswith("corrigendum"))
            first_act = next((i for i, t in enumerate(titles) if not t.startswith("corrigendum")), None)
            assert first_act is not None and first_act < first_corr

    def test_topical_questions_still_return_something(self):
        """Guard against over-correction: a rank threshold tried here dropped
        genuine CBAM and payments results and was removed."""
        assert _related_laws("How does CBAM affect steel?", limit=3), "CBAM query went empty"
        assert _related_laws("verification of payee obligation", limit=3), "payments query went empty"
