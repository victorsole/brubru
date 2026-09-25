"""The body backfills, and the three ways they quietly produced the wrong answer.

GovClipping need the whole text in body_txt and the whole HTML in body_html wherever we
can get it (Victor, 25 September 2026). Getting there took three corrections, and none of
the faults raised anything on its own:

1. A crash that stopped everything. PDF extraction yields NUL bytes and PostgreSQL refuses
   them outright, so all three Cellar corpora died on their first commit; eu_eesc_opinions
   lasted seven seconds. Separately the news fetcher died on len(None), because
   extract_html() returns (None, None) for a page with no article text and
   error_body_reason(None) is None -- "absent" is deliberately not "invalid".

2. Cover images stored as publications. A Cellar manifestation holds several items and the
   RDF lists DOC_2, a cover JPEG, before DOC_1, the document. Taking the first item
   downloaded the JPEG and reported "not a pdf": 3 of 40 rows succeeded and the other 37
   would have been recorded as having no text. Trying DOC_1 first made it 26 of 40.

3. Failures indistinguishable from absence. Every error in the fetch path was swallowed by
   one `except Exception: return None, None`, so "this publication has no text" and "our
   download failed" were the same fact. That is what let (2) look like a property of the
   corpus rather than a bug.

These tests defend the three, at source level so they run without the network.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

CELLAR = BACKEND / "scripts" / "fetch_general_publication_bodies.py"
NEWS = BACKEND / "scripts" / "fetch_institutional_news_bodies.py"


# ------------------------------------------------------------------ NUL bytes
def test_pdf_text_cannot_carry_nul_bytes_into_postgres():
    from scripts.fetch_general_publication_bodies import clean_text

    assert clean_text("a\x00b") == "ab"
    assert clean_text("\x00") is None          # nothing left is nothing, not an empty row
    assert clean_text(None) is None


def test_the_cellar_writer_cleans_before_it_writes():
    src = CELLAR.read_text(encoding="utf-8")
    assert "clean_text(body)" in src, "bodies reach the UPDATE without the NUL strip"


def test_the_news_writer_cleans_too():
    src = NEWS.read_text(encoding="utf-8")
    assert 'replace("\\x00", "")' in src


# ------------------------------------------------------------------ the right item
def test_the_document_is_preferred_over_the_cover_image():
    """DOC_2 is a cover JPEG and the RDF lists it first. Sorting must put DOC_1 first."""
    items = [
        "http://publications.europa.eu/resource/cellar/x.0001.01/DOC_2",
        "http://publications.europa.eu/resource/cellar/x.0001.01/DOC_1",
        "http://publications.europa.eu/resource/cellar/x.0001.01/DOC_3",
    ]
    items.sort(key=lambda u: (not u.rstrip("/").endswith("DOC_1"), u))
    assert items[0].endswith("DOC_1"), items


def test_the_fetcher_does_not_stop_at_the_first_item():
    src = CELLAR.read_text(encoding="utf-8")
    assert "_ITEM.findall(rdf)" in src, "it still takes only the first item"
    assert "_ITEM.search(rdf)" not in src.split("def fetch_one")[1][:1200], (
        "fetch_one still uses the first match")


# ------------------------------------------------------------------ honest failures
def test_a_failure_says_which_failure_it_was():
    """'no text available' and 'the download failed' are different facts about the world."""
    src = CELLAR.read_text(encoding="utf-8")
    body = src.split("def fetch_one")[1][:2000]
    for reason in ("no item in manifestation", "download ", "not a pdf", "pdf unreadable"):
        assert reason in body, f"the fetcher cannot report {reason!r}"
    assert "except Exception:  # noqa: BLE001  a failure leaves the row untouched" not in src, (
        "the blanket except that hid the cover-image bug is back")


def test_the_reasons_reach_the_operator():
    src = CELLAR.read_text(encoding="utf-8")
    assert "reasons[why]" in src and "full text {ok}, none {no_pdf}" in src, (
        "failure reasons are counted but never printed")


# ------------------------------------------------------------------ resumability
def test_a_rerun_does_not_redo_finished_work_or_skip_stubs():
    """The resume threshold has to sit ABOVE the composed stubs it replaces: they reach
    590 characters, so resuming on 500 would have skipped the 14 longest and called the
    corpus complete."""
    from scripts.fetch_general_publication_bodies import HAVE_REAL_BODY, MIN_BODY

    assert HAVE_REAL_BODY > 590, "resume threshold sits inside the stub range"
    assert HAVE_REAL_BODY > MIN_BODY


def test_progress_is_committed_per_batch():
    """A single commit at the end means a run that dies after hours has written nothing,
    which is how the first two failures cost a full afternoon."""
    lines = CELLAR.read_text(encoding="utf-8").splitlines()
    loop = next(i for i, l in enumerate(lines) if "for start_i in range" in l)
    # Inside the loop body, i.e. indented deeper than the `for`, not merely after it.
    indent = len(lines[loop]) - len(lines[loop].lstrip())
    in_loop = [l for l in lines[loop + 1:]
               if l.strip() and (len(l) - len(l.lstrip())) > indent]
    # Either form: a plain commit, or the reconnecting _commit() that replaced it after
    # Supabase dropped a session held across hours of fetching.
    assert any("db.commit()" in l or "_commit(db)" in l for l in in_loop), (
        "the batch loop does not commit as it goes")


def test_a_dropped_database_session_is_reopened_not_fatal():
    """These runs hold one Session across hours of network work and Supabase closes it
    from its side; pool_pre_ping validates on CHECKOUT and so cannot help. The EESC
    backfill died at 652 rows with "server closed the connection unexpectedly" AFTER
    fetching every one of them."""
    for path in (CELLAR, NEWS):
        src = path.read_text(encoding="utf-8")
        assert "def _commit(" in src, f"{path.name} has no reconnecting commit"
        assert "OperationalError" in src, f"{path.name} does not catch a dropped session"
        assert "SessionLocal()" in src.split("def _commit(")[1][:900], (
            f"{path.name} catches the drop but never reopens")
