"""The body-source registry must describe the database that actually exists.

`core/body_sources.py` is the single place naming the column that holds each
table's text. Its whole value is that handlers stop hardcoding physical column
names, so the eventual rename to `body_txt` / `body_html` everywhere becomes a
one-line edit per table.

That only holds if the registry cannot drift from the database. A declared
column that no longer exists would make every SELECT through `body_select()`
fail -- or worse, if someone "fixed" it by falling back to NULL, serve empty
bodies over a full corpus, which is exactly the failure the registry exists to
end. So these tests check the claim against the live schema rather than trusting
the file.
"""
import pytest
from sqlalchemy import text

from core.body_sources import (BODY_SOURCES, UnknownBodyTable, body_select,
                                  declared_tables, get_source)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module")
def schema(db):
    rows = db.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public'")).fetchall()
    out: dict[str, set] = {}
    for t, c in rows:
        out.setdefault(t, set()).add(c)
    return out


@pytest.mark.parametrize("table", declared_tables())
def test_the_table_exists(schema, table):
    assert table in schema, f"BODY_SOURCES declares {table}, which is not in the database"


@pytest.mark.parametrize("table", declared_tables())
def test_the_declared_columns_exist(schema, table):
    """A rename that lands in the database and not here must fail HERE, loudly,
    rather than downstream as an empty body."""
    src = BODY_SOURCES[table]
    for col in (src.txt, src.html):
        if col:
            assert col in schema[table], (
                f"{table}.{col} is declared as a body column and does not exist. "
                f"If it was renamed, update BODY_SOURCES -- do not drop it to NULL."
            )


@pytest.mark.parametrize("table", declared_tables())
def test_every_entry_records_its_measurement(table):
    """The note is what separates 'this endpoint is broken' from 'this corpus is
    thin'. An entry without one invites the next person to guess."""
    assert BODY_SOURCES[table].note.strip(), f"{table} has no measured note"


def test_body_select_always_yields_both_contract_names():
    """The row shape must not change with the flag: a mapper that reads
    row.body_html cannot be made to trip over a column that exists in one branch
    and not the other."""
    for table in declared_tables():
        for flag in (True, False):
            sql = body_select(table, flag)
            assert "AS body_txt" in sql and "AS body_html" in sql, (table, flag, sql)


def test_a_table_with_no_html_column_yields_a_typed_null():
    """texts_adopted holds text extracted from a PDF and never saw HTML.
    Fabricating an HTML rendering would misrepresent the source."""
    sql = body_select("texts_adopted", True)
    assert "full_text AS body_txt" in sql
    assert "NULL::text AS body_html" in sql


def test_an_undeclared_table_raises_rather_than_defaulting():
    """A silent default is how a new table ships serving nulls."""
    with pytest.raises(UnknownBodyTable):
        get_source("some_table_nobody_declared")


def test_the_alias_is_applied_to_both_columns():
    sql = body_select("commission_documents", True, alias="d")
    assert "d.text_body AS body_txt" in sql and "d.body_html AS body_html" in sql


@pytest.mark.parametrize("table", declared_tables())
def test_the_select_actually_runs(db, table):
    """Proof by execution, not by inspection: build the real SELECT and run it.
    A quoting or aliasing mistake shows up here rather than in production."""
    sql = body_select(table, True)
    db.execute(text(f"SELECT {sql} FROM {table} LIMIT 1")).fetchall()
