"""Audit defect D5, 25 Aug 2026 -- the EU Calendar relevance gate.

Every filter in `_fetch_eu_calendar_events` is optional. When none matched,
what survived was "any non-recess event in the date window", and the LIMIT 8
then returned eight arbitrary events straight into the context and the
citation list. On 24 August every payments answer carried the same eight, of
which seven were unrelated: an International Youth Day beach cleanup, a
freestyle award presentation, a CHMP plenary. Across all answers since 1 July
this block produced 906 citations, second only to web search.

These tests pin the gate WITHOUT touching the database: they exercise the
decision, not the query.

Run: cd backend && python3.12 -m pytest tests/test_calendar_relevance_gate.py -v
"""

import pytest

from services.ai.context_builder import ContextBuilder


def gate_opens(query: str, *, institutions=False, areas=False,
               committee=False, procedures=False) -> bool:
    """Re-derivation of the gate, kept in the test so a silent change to the
    condition shows up here as a failure rather than as noise in production."""
    has_topical_hook = bool(institutions or areas or committee or procedures)
    asks_about_calendar = any(
        kw in query.lower() for kw in ContextBuilder._CALENDAR_INTENT_KEYWORDS
    )
    return has_topical_hook or asks_about_calendar


class TestCalendarRelevanceGate:

    @pytest.mark.parametrize("query", [
        "what is the verification of payee obligation under EU law",
        "when does the GDPR apply?",
        "who is the rapporteur for the AI Act?",
        "what are the penalties under the Digital Services Act?",
    ])
    def test_a_pure_legal_question_gets_no_calendar(self, query):
        assert not gate_opens(query), (
            f"{query!r} has no calendar dimension; a beach cleanup is not a "
            f"weak match to it, it is a non-match"
        )

    @pytest.mark.parametrize("query", [
        "what is on the agenda next week?",
        "show me the calendar",
        "what meetings are coming up",
        "which events are scheduled this month",
    ])
    def test_an_explicit_calendar_question_opens_the_gate(self, query):
        assert gate_opens(query)

    @pytest.mark.parametrize("query,lang", [
        ("quel est le calendrier du Parlement", "FR"),
        ("quelles sont les prochaines reunions", "FR"),
        ("quin es el calendari del Parlament", "CA"),
        ("cual es el calendario del Parlamento", "ES"),
        ("quali sono le prossime riunioni", "IT"),
        ("wat is de kalender van het Parlement", "NL"),
    ])
    def test_calendar_intent_is_recognised_in_all_six_languages(self, query, lang):
        assert gate_opens(query), f"{lang} calendar request not recognised"

    def test_a_topical_hook_opens_the_gate_without_calendar_words(self):
        assert gate_opens("energy policy", areas=True)
        assert gate_opens("Council decisions", institutions=True)
        assert gate_opens("2023/0209(COD)", procedures=True)
        assert gate_opens("ITRE work", committee=True)

    def test_the_gate_is_not_opened_by_a_bare_temporal_word(self):
        """look_past / look_future fire on words like "when does", which is why
        they are deliberately NOT part of the gate."""
        assert not gate_opens("when does the Data Act start to apply")
        assert not gate_opens("what happened to the Nature Restoration Law")
