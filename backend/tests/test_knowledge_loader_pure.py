"""
Unit tests for pure-function parts of KnowledgeLoader.

KnowledgeLoader is a 7,000-line class with heavy disk/DB dependencies.
This file covers only the string-parsing helpers that have no I/O,
so they're testable without fixtures or mocks.

Covered:
    _extract_quick_facts  -- parses the QUICK FACTS block out of a guide's markdown
    get_guide_staleness   -- returns a caveat when a guide is older than N days

Out of scope (deferred until a DB fixture exists):
    load_all, search_guides, trigger matching, semantic search.

Quality Framework: partial coverage of F013 "Big 3 zero tests".

Run: cd backend && python3.12 -m pytest tests/test_knowledge_loader_pure.py -v
"""

from datetime import datetime, timedelta

import pytest

from knowledge_base.knowledge_loader import KnowledgeLoader


@pytest.fixture
def loader():
    """
    Bypass __init__ to avoid disk I/O. We only test pure methods.
    """
    return KnowledgeLoader.__new__(KnowledgeLoader)


# ---------------------------------------------------------------------------
# _extract_quick_facts
# ---------------------------------------------------------------------------
class TestExtractQuickFacts:
    """Extracts the QUICK FACTS block from a guide markdown body."""

    def test_extracts_standard_block(self, loader):
        content = (
            "# AI Act\n\n"
            "## QUICK FACTS\n"
            "- CELEX: 32024R1689\n"
            "- Entered into force: 1 August 2024\n\n"
            "## Background\n"
            "Long prose here..."
        )
        result = loader._extract_quick_facts(content)
        assert "CELEX: 32024R1689" in result
        assert "1 August 2024" in result
        # Should stop at the next ## heading
        assert "Long prose" not in result
        assert "Background" not in result

    def test_case_insensitive_heading(self, loader):
        content = "# Guide\n## quick facts\n- Key: value\n\n## Details\nMore."
        result = loader._extract_quick_facts(content)
        assert "Key: value" in result
        assert "More." not in result

    def test_falls_back_when_no_quick_facts_block(self, loader):
        content = "# My Guide\nLine one\nLine two\nLine three."
        result = loader._extract_quick_facts(content)
        # Fallback takes first 500 chars after the title line
        assert "Line one" in result

    def test_handles_guide_with_no_heading(self, loader):
        content = "Plain content without any heading."
        result = loader._extract_quick_facts(content)
        # Fallback to first 500 chars
        assert "Plain content" in result

    def test_fallback_caps_at_500_chars(self, loader):
        long = "# Title\n" + ("x" * 2000)
        result = loader._extract_quick_facts(long)
        # Fallback snippet should be bounded
        assert len(result) <= 500

    def test_trims_whitespace(self, loader):
        content = "# Guide\n## QUICK FACTS\n\n   - Key: value   \n\n\n## Next"
        result = loader._extract_quick_facts(content)
        # Leading and trailing blank lines stripped
        assert result.startswith("- Key:")
        assert not result.endswith("\n\n")


# ---------------------------------------------------------------------------
# get_guide_staleness
# ---------------------------------------------------------------------------
class TestGetGuideStaleness:
    """
    Returns a staleness caveat when a guide's mtime is older than the threshold.
    Depends on loader.guide_freshness, so we set it directly (no init required).
    """

    def test_fresh_guide_returns_none(self, loader):
        loader.guide_freshness = {"my_guide": datetime.now() - timedelta(days=5)}
        assert loader.get_guide_staleness("my_guide", stale_after_days=30) is None

    def test_stale_guide_returns_caveat(self, loader):
        loader.guide_freshness = {"my_guide": datetime.now() - timedelta(days=45)}
        caveat = loader.get_guide_staleness("my_guide", stale_after_days=30)
        assert caveat is not None
        assert "STALENESS NOTE" in caveat
        assert "45 days" in caveat

    def test_unknown_guide_returns_none(self, loader):
        loader.guide_freshness = {}
        assert loader.get_guide_staleness("nonexistent", stale_after_days=30) is None

    def test_exact_threshold_is_fresh(self, loader):
        # Boundary: exactly at threshold = fresh (>= threshold triggers caveat only when > threshold)
        loader.guide_freshness = {"g": datetime.now() - timedelta(days=30)}
        result = loader.get_guide_staleness("g", stale_after_days=30)
        # Implementation uses `age_days > stale_after_days`, so 30 days = fresh
        assert result is None

    def test_one_day_over_triggers_caveat(self, loader):
        loader.guide_freshness = {"g": datetime.now() - timedelta(days=31)}
        assert loader.get_guide_staleness("g", stale_after_days=30) is not None

    def test_caveat_includes_formatted_date(self, loader):
        fixed = datetime(2026, 1, 15)
        loader.guide_freshness = {"g": fixed}
        caveat = loader.get_guide_staleness("g", stale_after_days=30)
        assert caveat is not None
        # Format is "%d %B %Y" -> "15 January 2026"
        assert "15 January 2026" in caveat
