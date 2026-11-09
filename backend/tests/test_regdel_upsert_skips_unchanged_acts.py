"""O236 (6 Nov 2026): the RegDel feed rewrote every delegated and implementing act on every run.

`ON CONFLICT ... DO UPDATE` had no WHERE, so each of ~8,500 records got a new row version in all 12
indexes, and the touch trigger rebuilt the row with its text bodies: ~150 KB of write log per act.
6,638 upserts in two hours made 1.02 GB of the database's 1.19 GB of WAL, for ONE row that changed.

`only_if_changed` builds the WHERE from the SET list itself, so the row is written only when some
column would actually change. Proven on a copy of the production table (scratch Postgres, the same
Commission export fed to both versions): with ~290 planted stale values the old and the new script
left identical tables (every column, the same 221 rows touched, the same 8 inserts) while the new one
rewrote 241 rows instead of 7,860; on a quiet run it rewrote none (10 MB of WAL instead of 3.6 GB on
that copy). These tests hold the shape that proof depends on; Postgres is not available in CI.
"""
import re

import pytest

from scripts import ingest_regdel_acts as job

SETS = {"celex": job._CELEX_SET, "reference": job._REFERENCE_SET, "keep_celex": job._KEEP_CELEX_SET}
STATEMENTS = {"celex": job.SQL_BY_CELEX, "reference": job.SQL_BY_REFERENCE,
              "keep_celex": job.SQL_BY_REFERENCE_KEEP_CELEX}


def _targets(set_sql: str) -> list:
    """The SET targets, read independently of only_if_changed: a column name at the start of a line,
    then '='. Every item in these SET lists starts on its own line."""
    no_comments = re.sub(r"--[^\n]*", "", set_sql)
    return re.findall(r"^\s*([a-z_]+)\s*=(?!=)", no_comments, re.M)


@pytest.mark.parametrize("path", SETS)
def test_the_guard_compares_every_column_the_update_writes_except_last_updated(path):
    guard = job.only_if_changed(SETS[path], "secondary_acts")
    cols = re.search(r"WHERE \((.*?)\)\s+IS DISTINCT FROM", guard, re.S).group(1)
    compared = [c.strip().removeprefix("secondary_acts.") for c in cols.split(",")]
    expected = [c for c in _targets(SETS[path]) if c != "last_updated"]
    assert compared == expected, "the guard must compare exactly the columns the SET writes, in order"
    assert "last_updated" not in compared, "last_updated always differs (NOW()); the trigger owns it"
    assert len(compared) == {"celex": 14, "reference": 13, "keep_celex": 13}[path]


@pytest.mark.parametrize("path", SETS)
def test_each_compared_expression_is_the_set_expression_verbatim(path):
    set_sql = SETS[path]
    guard = job.only_if_changed(set_sql, "secondary_acts")
    for col in ("title", "status", "parent_celex", "regdel_updated_at"):
        # the SET's own CASE/COALESCE text appears in the guard unchanged (no copy that could drift)
        expr = re.search(rf"^\s*{col}\s*=\s*(.*?)(?=,\s*\n\s*(?:--|[a-z_]+\s*=)|\Z)", set_sql, re.M | re.S).group(1).strip()
        assert expr in guard, col


@pytest.mark.parametrize("path", STATEMENTS)
def test_every_upsert_carries_its_guard_between_set_and_returning(path):
    sql = STATEMENTS[path]
    guard = job.only_if_changed(SETS[path], "secondary_acts")
    assert guard in sql
    assert sql.index("DO UPDATE SET") < sql.index(guard) < sql.index("RETURNING (xmax = 0) AS was_inserted")


def test_the_reference_paths_differ_only_in_whose_celex_wins():
    assert "celex = COALESCE(EXCLUDED.celex, secondary_acts.celex)" in job._REFERENCE_SET
    assert "celex = COALESCE(secondary_acts.celex, EXCLUDED.celex)" in job._KEEP_CELEX_SET
    assert "ON CONFLICT (reference)" not in job.SQL_BY_CELEX


def test_the_splitter_respects_quotes_parentheses_and_comments():
    guard = job.only_if_changed("""
        -- a comment, with a comma (and a parenthesis
        a = CASE WHEN x ~ '(a|b), c' THEN f(x, y) ELSE 'it''s, (fine' END,
        b = COALESCE(EXCLUDED.b, t.b),
        last_updated = NOW()""", table="t")
    assert "(t.a, t.b)" in guard
    assert "CASE WHEN x ~ '(a|b), c' THEN f(x, y) ELSE 'it''s, (fine' END, COALESCE(EXCLUDED.b, t.b))" in guard
    with pytest.raises(ValueError):
        job.only_if_changed("a = f(x", "t")
    with pytest.raises(ValueError):
        job.only_if_changed("NOT A COLUMN = 1", "t")


def test_a_skipped_record_is_counted_as_unchanged_not_as_updated():
    src = (job.ROOT / "backend" / "scripts" / "ingest_regdel_acts.py").read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", src)
    assert "if row is None: unchanged += 1" in flat
    assert "elif row[0]: inserted += 1 else: updated += 1" in flat
    assert "unchanged={unchanged}" in src and "inserted + updated + unchanged == 0" in src
