"""Regression tests for the two /news tooling defects found on 26 August 2026.

Both defects shared a shape: a failure that degraded silently into plausible
data, so nothing looked broken from the outside.

1. `eli_for_celex` called `asyncio.run()` from inside a running event loop. Its
   only caller (`save_to_daily_briefs`) runs under `asyncio.run(main())`, so the
   call ALWAYS raised, the broad `except` swallowed it, and every Official
   Journal link in the daily brief shipped as a WAF-walled `legal-content` URL.
   The only trace was a RuntimeWarning on stderr about an un-awaited coroutine.

2. The Interoperable Europe / EU GovTech listings fall back to "the first
   date-shaped string anywhere in the card" when there is no `<time datetime>`,
   so an unrelated date could land in `document_date`. "Startups' Corner Digest
   | July 2026" was stored as 2 December 2026 and pinned itself to the top of
   every recency-ordered feed, including /api/v2/news/all, for three months.

Neither test touches the network.
"""
from __future__ import annotations

import asyncio
import importlib.util
import re
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.scrapers.economy_interoperable import _parse_item_date, future_dated_rejects


def _load_scraper_module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "scrape_eu_news.py"
    spec = importlib.util.spec_from_file_location("scrape_eu_news_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# Defect 1: running a coroutine from inside a live event loop
# --------------------------------------------------------------------------

def test_run_coro_blocking_without_a_running_loop():
    mod = _load_scraper_module()

    async def _answer():
        return 42

    assert mod._run_coro_blocking(_answer()) == 42


def test_run_coro_blocking_inside_a_running_loop():
    """The path the scraper actually uses. Before the fix this raised
    RuntimeError and left the coroutine un-awaited."""
    mod = _load_scraper_module()

    async def _answer():
        return "resolved"

    async def _outer():
        return mod._run_coro_blocking(_answer())

    assert asyncio.run(_outer()) == "resolved"


def test_no_unawaited_coroutine_warning_inside_a_loop():
    """An un-awaited coroutine is the fingerprint of the original defect.

    Promote it to an error so a future refactor that reintroduces
    `asyncio.run()` here fails the suite instead of degrading quietly.
    """
    mod = _load_scraper_module()

    async def _answer():
        return 1

    async def _outer():
        return mod._run_coro_blocking(_answer())

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert asyncio.run(_outer()) == 1


def test_clean_brief_url_repairs_the_malformed_oj_path():
    """The feed produced `..././legal-content/...`. Repair is independent of
    ELI resolution, so this must hold with resolve_eli off (no network)."""
    mod = _load_scraper_module()
    out = mod.clean_brief_url(
        "https://eur-lex.europa.eu/./legal-content/AUTO/?uri=CELEX:32026R1961",
        resolve_eli=False,
    )
    assert "/./" not in out
    assert out == ("https://eur-lex.europa.eu/legal-content/EN/TXT/"
                   "?uri=CELEX:32026R1961")


def test_clean_brief_url_prefers_an_eli_the_source_already_gave_us():
    mod = _load_scraper_module()
    src = "http://data.europa.eu/eli/reg_impl/2026/1961/oj"
    assert mod.clean_brief_url(src, resolve_eli=False) == src


# --------------------------------------------------------------------------
# Defect 2: a news item dated in the future
# --------------------------------------------------------------------------

def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


@pytest.mark.parametrize("item_type", ["news", "press_release", "publication"])
def test_future_dated_news_is_rejected(item_type):
    assert _parse_item_date(_iso(98), item_type, title="a digest") is None


def test_events_may_legitimately_be_future_dated():
    """The guard must be type-aware. An event on 2 December is not a defect,
    and blocking it would break My EU Calendar."""
    got = _parse_item_date(_iso(98), "event", title="SEMIC 2026")
    assert got is not None
    assert got.date().isoformat() == _iso(98)


def test_todays_news_survives():
    got = _parse_item_date(_iso(0), "news", title="a genuine item")
    assert got is not None


def test_one_day_of_tolerance_for_timezone_skew():
    """A publisher an hour ahead of UTC must not have its items dropped."""
    assert _parse_item_date(_iso(1), "news", title="tomorrow-ish") is not None


def test_beyond_tolerance_is_dropped():
    assert _parse_item_date(_iso(3), "news", title="three days out") is None


def test_rejections_are_recorded_not_silent():
    """A silent drop is how the original defect stayed invisible for nine days."""
    before = len(future_dated_rejects())
    _parse_item_date(_iso(60), "news", title="Startups' Corner Digest | July 2026")
    after = future_dated_rejects()
    assert len(after) == before + 1
    assert after[-1][0] == "Startups' Corner Digest | July 2026"


def test_unparseable_and_missing_dates_behave_as_before():
    assert _parse_item_date(None, "news") is None
    assert _parse_item_date("not a date", "news") is None


# --------------------------------------------------------------------------
# OJ:C_ / OJ:L_ references have no CELEX, but their ELI is derivable
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("https://eur-lex.europa.eu/./legal-content/AUTO/?uri=OJ:C_202604008",
     "http://data.europa.eu/eli/C/2026/4008/oj"),
    ("https://eur-lex.europa.eu/legal-content/AUTO/?uri=OJ:C_202604615",
     "http://data.europa.eu/eli/C/2026/4615/oj"),
    ("https://eur-lex.europa.eu/legal-content/AUTO/?uri=OJ:L_202601957",
     "http://data.europa.eu/eli/L/2026/1957/oj"),
])
def test_oj_reference_becomes_a_derived_eli(raw, expected):
    """Verified through the WAF browser fetcher on 26 Aug 2026: these three
    resolve to 52026IP0068, 52026M12497 and 22026D1957 respectively."""
    mod = _load_scraper_module()
    assert mod.clean_brief_url(raw, resolve_eli=False) == expected


def test_leading_zeros_are_stripped_from_the_oj_number():
    mod = _load_scraper_module()
    out = mod.clean_brief_url(
        "https://eur-lex.europa.eu/legal-content/AUTO/?uri=OJ:C_202600042",
        resolve_eli=False)
    assert out == "http://data.europa.eu/eli/C/2026/42/oj"


def test_a_non_eurlex_url_is_left_alone():
    mod = _load_scraper_module()
    src = "https://ec.europa.eu/commission/presscorner/detail/en/mex_26_1757"
    assert mod.clean_brief_url(src, resolve_eli=False) == src


def test_oj_reference_outside_the_act_number_space_is_not_derived():
    """Found by the second audit pass, 26 Aug 2026.

    `OJ:L_202690714` would derive eli/L/2026/90714/oj, which resolves to a
    EUR-Lex SEARCH RESULTS page -- a dead link dressed as a permalink. Across
    141 acts published in the 30 days to 26 Aug, real 2026 OJ act numbers ran
    91-1961, so a 9xxxx value is a different series. Above the cap we keep the
    less-stable-but-real legal-content form rather than inventing a permalink.
    """
    mod = _load_scraper_module()
    src = "https://eur-lex.europa.eu/legal-content/AUTO/?uri=OJ:L_202690714"
    assert mod.clean_brief_url(src, resolve_eli=False) == src   # unchanged
    assert "data.europa.eu" not in mod.clean_brief_url(src, resolve_eli=False)


def test_the_act_number_cap_still_admits_every_verified_reference():
    mod = _load_scraper_module()
    for ref, expected in [
        ("OJ:C_202604008", "http://data.europa.eu/eli/C/2026/4008/oj"),
        ("OJ:C_202604615", "http://data.europa.eu/eli/C/2026/4615/oj"),
        ("OJ:L_202601957", "http://data.europa.eu/eli/L/2026/1957/oj"),
    ]:
        got = mod.clean_brief_url(
            f"https://eur-lex.europa.eu/legal-content/AUTO/?uri={ref}", resolve_eli=False)
        assert got == expected, f"{ref} -> {got}"


# --------------------------------------------------------------------------
# Second audit pass: the feed spells the same reference two ways, and the
# CELEX branch was mangling one of them.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("frag,expected", [
    # `CELEX:C_202604108` used to capture just "C" (the char class excluded '_')
    # and emit `?uri=CELEX:C` -- a dead link that was being SAVED to the brief.
    ("?uri=CELEX:C_202604108", "http://data.europa.eu/eli/C/2026/4108/oj"),
    ("?uri=CELEX:L_202601957", "http://data.europa.eu/eli/L/2026/1957/oj"),
    ("?uri=OJ:C_202604008",    "http://data.europa.eu/eli/C/2026/4008/oj"),
])
def test_oj_reference_under_either_uri_key_resolves_the_same(frag, expected):
    mod = _load_scraper_module()
    got = mod.clean_brief_url(
        f"https://eur-lex.europa.eu/legal-content/AUTO/{frag}", resolve_eli=False)
    assert got == expected


@pytest.mark.parametrize("celex", ["52026AP0058", "32026R1961", "22026D1957"])
def test_a_real_celex_is_still_handled_by_the_celex_branch(celex):
    mod = _load_scraper_module()
    got = mod.clean_brief_url(
        f"https://eur-lex.europa.eu/legal-content/AUTO/?uri=CELEX:{celex}",
        resolve_eli=False)
    assert got == f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def test_no_truncated_celex_is_ever_emitted():
    """`?uri=CELEX:C` is not a document. A real CELEX starts with a sector digit."""
    mod = _load_scraper_module()
    for frag in ("?uri=CELEX:C_202604108", "?uri=CELEX:L_202601957"):
        got = mod.clean_brief_url(
            f"https://eur-lex.europa.eu/legal-content/AUTO/{frag}", resolve_eli=False)
        assert not re.search(r"uri=CELEX:[A-Z]$", got), got
        assert "CELEX:C&" not in got and not got.endswith("CELEX:C")
