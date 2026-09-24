"""Brubru served four Council research papers that do not exist (24 September 2026).

`scripts/ingest_research_publications.py` seeds "verified URLs" by hand. Checked at the
source, they are not verified at all:

  * ART's `.../council-research-papers/2026/01/12/enlargement-fatigue/` answers **404,
    "Page not found"**, and none of the four seeded ART titles appear on the Council's
    listing, which carries "Weaponised suspicion", "Prospects for 2026", "Forward Look
    2026" and "Bridging Water Extremes";
  * a seeded ECA row points at a REAL report, `SR-2026-09`, under an invented title: that
    report is "European innovation partnership in the common agricultural policy", not
    "Recovery and Resilience Facility — Member State...".

All 19 seeded rows (art 4, jrc 6, stoa 4, eca 5) were backed up to
`docs/backups/seeded_research_rows_2026-09-24.json` and deleted, and ART is now read from
the Council's own listing by `scripts/sync_council_art.py`.

These tests are about the RULE, not about ART: a research corpus may not be filled by
hand, because a plausible title next to a plausible URL is indistinguishable from a real
publication once it is in the database and on the API.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from sqlalchemy import text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.database import SessionLocal  # noqa: E402

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SEEDER = BACKEND / "scripts" / "ingest_research_publications.py"
ART_SYNC = BACKEND / "scripts" / "sync_council_art.py"


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_no_research_row_carries_a_hand_written_art_url(db):
    """The seeded ART URLs are the ones that 404. None may come back."""
    n = db.execute(text(
        "SELECT count(*) FROM eprs_publications "
        "WHERE html_url ~ 'council-research-papers/20[0-9][0-9]/[0-9]{2}/[0-9]{2}/'")).scalar()
    assert n == 0, f"{n} row(s) point at a per-paper ART URL, a shape the Council does not serve"


def test_art_rows_come_from_the_listing(db):
    rows = db.execute(text(
        "SELECT publication_id, html_url, pdf_url FROM eprs_publications WHERE source = 'art'")).fetchall()
    assert rows, "no ART papers at all: the sync has not run"
    for pid, html_url, pdf_url in rows:
        assert pid.startswith("ART-"), pid
        assert html_url and html_url.rstrip("/").endswith("council-research-papers"), html_url
        assert pdf_url and pdf_url.lower().endswith(".pdf"), pdf_url


def test_a_paper_without_a_known_day_is_not_given_one(db):
    """The listing carries no date and the PDF name carries only a year. A year read as
    the 1st of January is how 57 FRA rows landed on 1 January (15 Sep 2026)."""
    bad = db.execute(text(
        "SELECT count(*) FROM eprs_publications WHERE source = 'art' "
        "AND publication_date IS NOT NULL "
        "AND (EXTRACT(month FROM publication_date) = 1 AND EXTRACT(day FROM publication_date) = 1)")).scalar()
    assert bad == 0, "an ART paper carries a 1 January placeholder date"


def test_the_sync_refuses_to_read_a_challenge_page_as_an_empty_council():
    src = ART_SYNC.read_text(encoding="utf-8")
    assert "FETCH BLOCK" in src and "never 'no papers'" in src
    assert "parsed to 0 papers" in src, "a zero-paper parse must raise, not write nothing quietly"


def test_the_seeder_is_not_what_fills_art_any_more():
    """It may still exist for other sources, but nothing should point ART at it."""
    assert ART_SYNC.is_file()
    if SEEDER.is_file():
        cron = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
        assert "ingest_research_publications.py" not in cron, (
            "the hand-written seeder is on a schedule: it would re-insert invented rows"
        )
        assert "scripts/sync_council_art.py" in cron, "the real ART sync is not scheduled"
