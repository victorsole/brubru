"""The COM-register radar (scripts/sync_com_register.py): pure logic, no network, no database."""
import datetime as dt
import importlib.util
import logging
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def radar():
    spec = importlib.util.spec_from_file_location("com_radar_under_test", BACKEND / "scripts" / "sync_com_register.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        logging.disable(logging.NOTSET)       # the script silences logging at import; do not leak that
    return mod


TODAY = dt.date(2026, 10, 9)


def _raw(ref="COM(2026)546", date="2026-10-07T00:00:00.000+0000", typ="REPORT", dept="REFOR", latest=True,
         title="REPORT FROM THE COMMISSION on the implementation of the Recovery and Resilience Facility", celex=None):
    return {"reference": ref, "date": date, "type": typ, "responsibleDepartment": dept, "version": "final",
            "isLatestVersion": latest, "celex": celex, "url": f"https://x.example/{ref}",
            "attachments": [{"main": True, "original": "en", "linguisticVersions": {"en": {"title": title}}}]}


def _entry(radar, n, date, **kw):
    e = radar.parse_doc(_raw(ref=f"COM(2026){n}", date=f"{date}T00:00:00.000+0000", **kw))
    assert e is not None
    return e


# -- parsing ---------------------------------------------------------------------------------------

def test_reference_and_url(radar):
    assert radar.ref_parts("COM(2026)546") == (2026, 546)
    assert radar.ref_parts("COM(2026) 546 final") == (2026, 546)
    assert radar.ref_parts("SWD(2026) 546") is None
    assert radar.eurlex_url(2026, 546) == "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:2026:546:FIN"


def test_the_title_comes_from_the_main_attachment_in_english(radar):
    assert radar.english_title(_raw()).startswith("REPORT FROM THE COMMISSION")
    assert radar.english_title({"attachments": []}) is None
    assert radar.english_title({}) is None


def test_parse_doc_keeps_the_register_celex_and_never_invents_one(radar):
    assert radar.parse_doc(_raw())["celex"] is None
    assert radar.parse_doc(_raw(celex="52026DC0546"))["celex"] == "52026DC0546"


def test_parse_doc_rejects_entries_without_a_reference_or_date(radar):
    assert radar.parse_doc(_raw(date="not a date")) is None
    assert radar.parse_doc(_raw(ref="SWD(2026)705")) is None


# -- what we already hold ---------------------------------------------------------------------------

def test_held_numbers_reads_celex_and_com_style_references(radar):
    held = radar.held_numbers(["52026PC0537", "52026DC0553", "COM(2026) 546", "COM(2025)12"])
    assert {(2026, 537), (2026, 553), (2026, 546), (2025, 12)} <= held


def test_a_staff_working_document_number_never_counts_as_holding_the_com_document(radar):
    """SWD(2026) 705 and COM(2026) 705 are different documents: the same number in two series."""
    held = radar.held_numbers(["SWD(2026) 705", "52026SC0705", "JOIN(2026) 705", "52026JC0705"])
    assert (2026, 705) not in held


def test_a_cellar_style_reference_of_another_kind_is_ignored(radar):
    assert radar.held_numbers(["32026R2269", "52026XC04817", "52026AS120994", ""]) == set()


# -- what is missing ---------------------------------------------------------------------------------

def test_missing_lists_unheld_entries_in_the_window_newest_first(radar):
    entries = [_entry(radar, 546, "2026-10-07"), _entry(radar, 950, "2026-10-09"), _entry(radar, 300, "2026-08-01"),
               _entry(radar, 535, "2026-10-08")]
    out = radar.missing(entries, {(2026, 535)}, TODAY, days=10)
    assert [e["number"] for e in out] == [950, 546]          # 535 is held, 300 is outside the window


def test_a_superseded_version_is_not_reported(radar):
    entries = [_entry(radar, 546, "2026-10-07", latest=False)]
    assert radar.missing(entries, set(), TODAY, days=10) == []


def test_state_separates_cellar_lag_from_an_ingestion_gap(radar):
    e = _entry(radar, 546, "2026-10-07")
    assert radar.state_of(e, {(2026, 546)}) == "in Cellar, never ingested"
    assert radar.state_of(e, {(2026, 1)}) == "NOT IN CELLAR YET"
    assert radar.state_of(e, None) == "cellar state unknown"           # never guessed when Cellar cannot be read


# -- paging -------------------------------------------------------------------------------------------

def _pager(radar, pages):
    calls = []

    def post(n):
        calls.append(n)
        return {"documents": pages[n - 1] if n <= len(pages) else []}
    return post, calls


def _page(radar, start, count, day0):
    """`count` raw entries, one per day going back from day0."""
    return [_raw(ref=f"COM(2026){start - i}", date=f"{(day0 - dt.timedelta(days=i)).isoformat()}T00:00:00.000+0000")
            for i in range(count)]


def test_paging_stops_once_the_oldest_date_is_past_the_window(radar):
    post, calls = _pager(radar, [_page(radar, 900, 50, TODAY)])        # 50 days back: past the 10-day window
    entries, meta = radar.fetch_pages(post, TODAY, days=10)
    assert calls == [1] and len(entries) == 50 and meta["covers_window"] is True


def test_paging_continues_until_the_window_is_covered_and_says_when_it_is_not(radar):
    full = [_page(radar, 900 - 50 * k, 50, TODAY - dt.timedelta(days=k)) for k in range(3)]
    post, calls = _pager(radar, [p[:50] for p in full])
    entries, meta = radar.fetch_pages(post, TODAY, days=120, max_pages=2)
    assert calls == [1, 2] and meta["covers_window"] is False          # asked for 120 days, only reached ~50: said so


def test_an_empty_first_page_is_an_error_not_a_quiet_day(radar):
    post, _ = _pager(radar, [[]])
    with pytest.raises(RuntimeError):
        radar.fetch_pages(post, TODAY, days=10)


def test_the_same_document_listed_twice_keeps_the_latest_version(radar):
    old = _raw(ref="COM(2026)546", latest=False, title="old")
    new = _raw(ref="COM(2026)546", latest=True, title="new")
    post, _ = _pager(radar, [[old, new]])
    entries, _ = radar.fetch_pages(post, TODAY, days=10)
    assert len(entries) == 1 and entries[0]["title"] == "new"


def test_unparseable_entries_are_counted_not_hidden(radar):
    post, _ = _pager(radar, [[_raw(), _raw(ref="SWD(2026)1"), _raw(date="garbage")]])
    entries, meta = radar.fetch_pages(post, TODAY, days=10)
    assert len(entries) == 1 and meta["unparsed"] == 2
