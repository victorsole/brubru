"""
Tests for greeting policy hook composition.

These cover the pure helpers in services.personalization.greeting_service
that turn ProactiveBriefing objects and DailyBrief rows into the chip
payloads the chat empty state renders under the salutation.
"""

from dataclasses import dataclass

from services.personalization.greeting_service import (
    GreetingResult,
    MAX_GREETING_HOOKS,
    compose_hooks_from_brief_headlines,
    compose_hooks_from_briefings,
    generate_personalized_greeting,
)


# ---------------------------------------------------------------------------
# Stand-in dataclasses (don't import the real ones to avoid pulling SQLAlchemy
# into a pure-function test).
# ---------------------------------------------------------------------------


@dataclass
class FakeBriefing:
    trigger_source: str
    title: str
    summary: str
    suggested_query: str


@dataclass
class FakeBriefRow:
    headline: str
    suggested_query: str | None = None


# ---------------------------------------------------------------------------
# compose_hooks_from_briefings
# ---------------------------------------------------------------------------


def test_compose_hooks_from_briefings_caps_at_two_by_default():
    briefings = [
        FakeBriefing("tracked_file_movement", f"Title {i}", "summary", f"query {i}")
        for i in range(5)
    ]
    hooks = compose_hooks_from_briefings(briefings)
    assert len(hooks) == MAX_GREETING_HOOKS == 2
    assert hooks[0]["suggested_query"] == "query 0"
    assert hooks[1]["suggested_query"] == "query 1"


def test_compose_hooks_preserves_priority_order():
    briefings = [
        FakeBriefing("amendment_surge", "5 amendments tabled", "", "summarise amendments"),
        FakeBriefing("tracked_file_movement", "AI Act moved", "", "summarise status"),
    ]
    hooks = compose_hooks_from_briefings(briefings)
    assert hooks[0]["source"] == "amendment_surge"
    assert hooks[1]["source"] == "tracked_file_movement"


def test_compose_hooks_skips_missing_fields():
    briefings = [
        FakeBriefing("morning_brief", "", "", "query"),
        FakeBriefing("morning_brief", "Real title", "", ""),
        FakeBriefing("morning_brief", "Other title", "", "other query"),
    ]
    hooks = compose_hooks_from_briefings(briefings)
    assert len(hooks) == 1
    assert hooks[0]["label"] == "Other title"


def test_compose_hooks_accepts_dicts():
    briefings = [
        {
            "trigger_source": "morning_brief",
            "title": "Hello world",
            "summary": "Something happened that you should know.",
            "suggested_query": "do the thing",
        }
    ]
    hooks = compose_hooks_from_briefings(briefings)
    assert hooks == [
        {
            "label": "Hello world",
            "spoken": "Something happened that you should know.",
            "suggested_query": "do the thing",
            "source": "morning_brief",
        }
    ]


def test_compose_hooks_falls_back_to_title_when_no_summary():
    briefings = [
        {
            "trigger_source": "morning_brief",
            "title": "Title only",
            "suggested_query": "q",
        }
    ]
    hooks = compose_hooks_from_briefings(briefings)
    assert hooks[0]["spoken"] == "Title only"


def test_compose_hooks_truncates_long_titles():
    long_title = "x" * 200
    briefings = [FakeBriefing("morning_brief", long_title, "", "q")]
    hooks = compose_hooks_from_briefings(briefings)
    assert len(hooks[0]["label"]) <= 91  # 90 + ellipsis char
    assert hooks[0]["label"].endswith("…")


# ---------------------------------------------------------------------------
# compose_hooks_from_brief_headlines
# ---------------------------------------------------------------------------


def test_compose_hooks_from_brief_headlines_uses_suggested_query_if_present():
    items = [FakeBriefRow(headline="AI Act vote today", suggested_query="What is on the AI Act vote agenda?")]
    hooks = compose_hooks_from_brief_headlines(items)
    assert hooks[0]["suggested_query"] == "What is on the AI Act vote agenda?"
    assert hooks[0]["source"] == "daily_brief"


def test_compose_hooks_from_brief_headlines_falls_back_to_tell_me_about():
    items = [FakeBriefRow(headline="Pharma Package on College agenda")]
    hooks = compose_hooks_from_brief_headlines(items)
    assert hooks[0]["suggested_query"].startswith("Tell me about:")


def test_compose_hooks_from_brief_headlines_caps_at_max():
    items = [FakeBriefRow(headline=f"Headline {i}") for i in range(10)]
    hooks = compose_hooks_from_brief_headlines(items)
    assert len(hooks) == MAX_GREETING_HOOKS


# ---------------------------------------------------------------------------
# generate_personalized_greeting still returns a GreetingResult with an
# empty hooks list by default (the API layer fills it).
# ---------------------------------------------------------------------------


def test_generate_personalized_greeting_returns_empty_hooks_by_default():
    result = generate_personalized_greeting(
        first_name="Victor",
        preferred_name=None,
        timezone="Europe/Brussels",
        language="en",
        full_name="Victor Solé",
        previous_last_login=None,
    )
    assert isinstance(result, GreetingResult)
    assert result.policy_hooks == []
    assert "Victor" in result.message
