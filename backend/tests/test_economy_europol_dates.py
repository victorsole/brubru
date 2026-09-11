"""Date parsing for the Europol newsroom fetcher.

The bug these exist for (11 September 2026): Europol's cards render the month as
"11 Sept 2026", and the month index was built as `full` plus `full[:3]`.
September is the ONLY month whose natural abbreviation is four letters, so that
rule covered eleven months and dropped the twelfth. `_DMY` accepts
[A-Za-z]{3,9}, so "Sept" matched the regex and then missed the lookup, and
`_text_date` returned None instead of raising.

It was masked: the detail-page fallback reads the long form "9 September 2026",
so only items whose body fetch did not run lost their date. A bug that hides
eleven months of the year and only in one direction is worth a test.
"""
import pytest

from services.scrapers.economy_europol import _text_date


@pytest.mark.parametrize("text,expect", [
    ("11 Sept 2026", (2026, 9, 11)),
    ("Date 11 Sept 2026", (2026, 9, 11)),   # the card's own wording
    ("1 Sept 2026", (2026, 9, 1)),
    ("11 Sep 2026", (2026, 9, 11)),
    ("11 September 2026", (2026, 9, 11)),
])
def test_every_september_spelling_parses(text, expect):
    d = _text_date(text)
    assert d is not None, f"{text!r} lost its date"
    assert (d.year, d.month, d.day) == expect


@pytest.mark.parametrize("month,idx", [
    ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4), ("May", 5), ("Jun", 6),
    ("Jul", 7), ("Aug", 8), ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12),
])
def test_all_twelve_short_months_still_parse(month, idx):
    """The fix adds a key; it must not disturb the other eleven."""
    d = _text_date(f"7 {month} 2026")
    assert d is not None and d.month == idx


@pytest.mark.parametrize("month,idx", [
    ("January", 1), ("February", 2), ("March", 3), ("April", 4), ("May", 5),
    ("June", 6), ("July", 7), ("August", 8), ("September", 9), ("October", 10),
    ("November", 11), ("December", 12),
])
def test_all_twelve_long_months_still_parse(month, idx):
    d = _text_date(f"7 {month} 2026")
    assert d is not None and d.month == idx


@pytest.mark.parametrize("text", ["not a date", "", "Sept 2026", "11 Smarch 2026", "2026-09-11"])
def test_non_dates_return_none_rather_than_guessing(text):
    """Returning None is the contract. A wrong date is worse than no date:
    an undated row is visibly undated, a mis-dated one silently sorts wrong."""
    assert _text_date(text) is None
