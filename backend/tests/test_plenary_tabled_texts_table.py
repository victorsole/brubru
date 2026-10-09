"""Committee reports tabled for a plenary vote have their own table (migration 285,
9 Oct 2026). They used to sit in texts_adopted with adoption_date NULL, which is how a
draft report was once served as the adopted resolution."""
import pathlib

import pytest
from sqlalchemy import text

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_the_writer_targets_the_tabled_texts_table():
    """Non-live: a scheduled writer is what put the reports back last time."""
    src = (BACKEND / "scripts" / "ingest_texts_submitted.py").read_text()
    assert "INSERT INTO plenary_tabled_texts" in src
    assert "INSERT INTO texts_adopted" not in src


def test_the_bodies_job_reads_both_tables():
    src = (BACKEND / "scripts" / "backfill_texts_adopted_bodies.py").read_text()
    assert "plenary_tabled_texts" in src


@pytest.mark.live
def test_adopted_texts_hold_only_adopted_texts_and_tabled_only_reports():
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        stray = db.execute(text("SELECT count(*) FROM texts_adopted WHERE ta_reference !~ '^P[0-9]+_TA'")).scalar()
        not_report = db.execute(text("SELECT count(*) FROM plenary_tabled_texts WHERE ta_reference !~ '^A[0-9]+/'")).scalar()
        policy = db.execute(text("SELECT count(*) FROM pg_policies WHERE tablename = 'plenary_tabled_texts'")).scalar()
        assert stray == 0, f"{stray} non-adopted row(s) in texts_adopted"
        assert not_report == 0, f"{not_report} row(s) in plenary_tabled_texts are not committee reports"
        assert policy >= 1, "plenary_tabled_texts has RLS but no read policy"
    finally:
        db.close()
