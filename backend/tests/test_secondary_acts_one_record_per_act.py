"""One EU act was two API records with different ids (GovClipping, 25 September 2026).

`/legislative/delegated-acts` and `/legislative/implementing-acts` share the table
`secondary_acts`, which three ingestors write with `ON CONFLICT (reference)`.
`backfill_regulatory_cascade.py` puts the CELEX itself in `reference`, while the regdel
register stores the same act under its Commission document number (32014R0241 against
C(2013)9763). The conflict therefore never fired and the act was inserted a second time as
a stub: no text_body and a 128-character "Derived from ..." description.

GovClipping identifies acts by CELEX, so whichever row they processed last won and the
stub could overwrite the full text of the act. 783 CELEX values held more than one row.

The repair could not simply delete the extra row, and checking first is the point:
  * 729 pairs agreed on parent_celex        -> the stub added nothing
  *  22 had parent_celex ONLY on the stub   -> deleting it would lose the relationship
  *  28 named two DIFFERENT and equally real parents (32017R1569 supplements both
     Regulation (EU) 536/2014 and Directive 2001/20/EC) and the column holds one
  *   4 were two real register rows sharing a CELEX under different C-numbers

So the survivor absorbs the losers into `merged_from`, inherits a parent it lacked, and
every deleted row was written to docs/backups/ first.

Needs the database.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from sqlalchemy import text

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.database import SessionLocal  # noqa: E402


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_no_celex_has_more_than_one_record(db):
    """The claim itself: one act, one record."""
    dupes = db.execute(text(
        "SELECT count(*) FROM (SELECT celex FROM secondary_acts WHERE celex IS NOT NULL "
        "GROUP BY celex HAVING count(*) > 1) z")).scalar()
    assert dupes == 0, f"{dupes} CELEX value(s) still have more than one row"


def test_the_examples_reported_kept_their_full_text(db):
    """The three acts GovClipping named. The stub had ~0 characters; the register row had
    the act. The survivor must be the one with the text."""
    for celex, minimum in (("32014R0241", 90_000), ("32014R0342", 25_000), ("32014R0357", 12_000)):
        row = db.execute(text(
            "SELECT coalesce(length(text_body), 0), reference FROM secondary_acts "
            "WHERE celex = :c"), {"c": celex}).fetchone()
        assert row is not None, f"{celex} is gone entirely"
        assert row[0] >= minimum, f"{celex} kept the stub ({row[0]} chars, ref {row[1]})"


def test_nothing_was_deleted_without_being_recorded(db):
    """Every merge is readable and reversible: the survivor lists what it absorbed."""
    merged = db.execute(text(
        "SELECT count(*) FROM secondary_acts WHERE merged_from IS NOT NULL")).scalar()
    assert merged > 700, f"only {merged} rows record a merge; the history is thinner than the repair"
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts WHERE merged_from IS NOT NULL "
        "AND jsonb_array_length(merged_from) = 0")).scalar()
    assert bad == 0, "a row claims a merge but records nothing absorbed"


def test_a_second_real_parent_survives_the_merge(db):
    """28 acts supplement two different acts. The column holds one; the other has to be
    somewhere, or the merge quietly destroyed a true relationship."""
    kept = db.execute(text(
        "SELECT count(*) FROM secondary_acts s "
        "WHERE s.merged_from IS NOT NULL AND s.parent_celex IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM jsonb_array_elements(s.merged_from) m "
        "            WHERE m->>'parent_celex' IS NOT NULL "
        "              AND m->>'parent_celex' <> s.parent_celex)")).scalar()
    assert kept >= 25, f"only {kept} second parents survive; 28 groups had one"


def test_the_deleted_rows_were_backed_up():
    backups = sorted((BACKEND.parent / "docs" / "backups").glob("secondary_acts_merged_*.json"))
    assert backups, "no backup of the merged-away rows"
    import json
    rows = json.loads(backups[-1].read_text(encoding="utf-8"))
    assert len(rows) > 700, f"backup holds only {len(rows)} rows"
    assert all("celex" in r for r in rows[:20])


def test_the_cascade_script_cannot_recreate_them():
    """The repair is worthless if the job that caused it runs again tonight. It deduped on
    `reference`, which is exactly the field that differs between the two copies."""
    src = (BACKEND / "scripts" / "backfill_regulatory_cascade.py").read_text(encoding="utf-8")
    assert "existing_celex" in src, "the cascade still dedupes on reference alone"
    assert "SELECT reference, celex FROM secondary_acts" in src
    body = src.split("def ")[0] + src
    assert "if ref in existing_celex" in body, "an act stored under its C-number is still 'new'"
