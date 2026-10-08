"""texts_adopted.celex_number is the text's OWN CELEX, read from Cellar (8 Oct 2026).

97 rows held `5YYYYATNNNN`, a type Cellar never issued (HTTP 404), and others the
number of an act the text CITES (the first CELEX-shaped string in the document).
`/texts-adopted` served both to clients. scripts/backfill_texts_adopted_celex.py
now reads the link Cellar itself holds (work_id_document immc:P10_TA(...)).
"""
import asyncio
import importlib.util
import pathlib

import pytest
from sqlalchemy import text

# Reads production data and Cellar: runs locally, never in CI.
pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


def _job():
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "backfill_texts_adopted_celex.py"
    spec = importlib.util.spec_from_file_location("_celex_job", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_only_parliament_celex_types_are_stored(db):
    """An EP text's own CELEX is sector 5 with a two-letter type (IP, AP, DP, BP...).
    A single letter (R, L, H) is an act the text cites; AT does not exist."""
    bad = db.execute(text("""
        SELECT ta_reference, celex_number FROM texts_adopted
        WHERE celex_number IS NOT NULL
          AND (celex_number !~ '^5[0-9]{4}[A-Z]{2}[0-9]{4}(\\([0-9]{2}\\))?$' OR celex_number ~ '^5[0-9]{4}AT')
    """)).fetchall()
    assert not bad, f"not an EP text's own CELEX: {bad[:5]}"


def test_reports_carry_no_celex(db):
    n = db.execute(text("""
        SELECT count(*) FROM texts_adopted
        WHERE ta_reference !~ '^P[0-9]+_TA' AND celex_number IS NOT NULL
    """)).scalar()
    assert n == 0, f"{n} committee report row(s) carry a CELEX (reports are not in the OJ)"


def test_every_stored_celex_is_the_one_cellar_links_to_the_text(db):
    """A sample checked against Cellar itself, not against our own rules."""
    rows = db.execute(text("""
        SELECT ta_reference, celex_number FROM texts_adopted
        WHERE celex_number IS NOT NULL ORDER BY random() LIMIT 40
    """)).fetchall()
    assert rows, "no CELEX stored at all: the job has not run"
    dates = dict(db.execute(text(
        "SELECT ta_reference, adoption_date::date::text FROM texts_adopted WHERE ta_reference = ANY(:r)"),
        {"r": [r.ta_reference for r in rows]}).fetchall())
    found = asyncio.run(_job()._cellar_celex([r.ta_reference for r in rows], dates))
    wrong = [(r.ta_reference, r.celex_number, sorted(found.get(r.ta_reference, [])))
             for r in rows if r.celex_number not in found.get(r.ta_reference, set())]
    assert not wrong, f"stored CELEX is not Cellar's: {wrong[:5]}"
