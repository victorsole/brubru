"""Paging served some records twice and never served others (GovClipping, 25 Sep 2026).

A full backfill of the EU feeds returned the right NUMBER of records with the wrong
records in them: 4,835 consultations served over 49 pages but only 3,543 distinct ids, so
about 1,290 consultations (27%) never arrived; 19,081 laws served for 17,882 distinct
CELEX numbers. Nothing failed. `total`, `has_more` and `coverage_complete` were all
correct, and each duplicate quietly took the place of a record that was never sent.

LIMIT/OFFSET returns each row exactly once only when the ORDER BY is a TOTAL order. SQL
leaves tied rows in an undefined order and PostgreSQL may resolve the tie differently for
each OFFSET, so a row can appear on page 2 and again on page 5 while another is skipped.
Our sort columns were nowhere near unique. Measured across the database the same day,
103 of 120 sortable timestamp columns had tie groups and 84 had more than half their rows
inside one:

    eu_comitology_documents.updated_at   95,461 rows /   221 distinct (biggest tie 77,566)
    catalan_law_eurovoc.created_at       73,971 rows /     1 distinct
    eu_laws.updated_at                   30,474 rows /    91 distinct (biggest tie  4,965)
    public_consultations.last_updated     4,835 rows /   471 distinct (biggest tie    500)

`stable()` appends the primary key, making the sort a total order. It is applied to every
paginated query in `api/`, and the first test here is what keeps it that way: the fix is
one call that is easy to omit when a new endpoint is written, and omitting it produces no
error, just a quietly incomplete corpus.
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._pagination import stable  # noqa: E402


# ------------------------------------------------------------------ the rule, everywhere
def _offset_receivers():
    """Every expression that has .offset(...) called on it, with its location."""
    for path in sorted((BACKEND / "api").rglob("*.py")):
        if "__pycache__" in str(path) or path.name == "_pagination.py":
            continue
        src = path.read_text(encoding="utf-8")
        if ".offset(" not in src:
            continue
        for node in ast.walk(ast.parse(src)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "offset"):
                seg = ast.get_source_segment(src, node.func.value) or ""
                yield path.relative_to(BACKEND), node.lineno, seg


def test_every_paginated_query_has_a_unique_tiebreaker():
    unstable = [f"{p}:{ln}" for p, ln, seg in _offset_receivers()
                if not seg.lstrip().startswith("stable(")]
    assert not unstable, (
        "paginated without a total order, so these endpoints can serve a row twice and "
        f"skip another: {unstable}")


def test_there_are_paginated_queries_to_check():
    """Guards the test above against silently passing on an empty list."""
    assert sum(1 for _ in _offset_receivers()) > 50


# ------------------------------------------------------------------ what stable() does
def test_stable_appends_the_primary_key():
    from core.database import SessionLocal
    from models.eu_law import EULaw

    db = SessionLocal()
    try:
        sql = str(stable(db.query(EULaw).order_by(EULaw.date.desc().nullslast())))
        order = sql.split("ORDER BY")[1]
        assert "eu_laws.date DESC" in order
        assert order.rstrip().endswith("eu_laws.id ASC"), order
    finally:
        db.close()


def test_stable_keeps_the_callers_own_ordering_first():
    """It decides ties; it must not reorder the result."""
    from core.database import SessionLocal
    from models.eu_law import EULaw

    db = SessionLocal()
    try:
        order = str(stable(db.query(EULaw).order_by(EULaw.date.desc()))).split("ORDER BY")[1]
        assert order.index("eu_laws.date") < order.index("eu_laws.id")
    finally:
        db.close()


def test_stable_refuses_rather_than_quietly_doing_nothing():
    """A no-op fallback would reintroduce the bug invisibly, which is how it survived."""
    class NotAQuery:
        column_descriptions = []

    with pytest.raises(ValueError, match="could not derive a primary key"):
        stable(NotAQuery())


def test_an_explicit_tiebreaker_is_honoured():
    from core.database import SessionLocal
    from models.eu_law import EULaw

    db = SessionLocal()
    try:
        sql = str(stable(db.query(EULaw).order_by(EULaw.date.desc()), EULaw.celex.asc()))
        assert sql.split("ORDER BY")[1].rstrip().endswith("eu_laws.celex ASC")
    finally:
        db.close()


# ------------------------------------------------------------------ the corpus, walked
@pytest.mark.parametrize("table,column", [
    ("public_consultations", "last_updated"),
    ("eu_laws", "updated_at"),
])
def test_the_sort_columns_really_are_tied(table, column):
    """Documents WHY the tiebreaker is needed: if these ever became unique the fix would
    look unnecessary, and this test says plainly that they are not."""
    from sqlalchemy import text

    from core.database import SessionLocal

    db = SessionLocal()
    try:
        total, distinct = db.execute(text(
            f'SELECT count(*), count(DISTINCT "{column}") FROM "{table}"')).fetchone()
        assert distinct < total, (
            f"{table}.{column} is unique after all; re-check whether paging still needs help")
    finally:
        db.close()


# ------------------------------------------------------------------ raw SQL
def _raw_sql_paginated_order_bys():
    """Every raw-SQL ORDER BY that is followed by LIMIT/OFFSET."""
    import re

    pattern = re.compile(r"ORDER BY\s+(.{0,160}?)\s*LIMIT\s+:\w+\s+OFFSET\s+:", re.I | re.S)
    for path in sorted((BACKEND / "api").rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        src = path.read_text(encoding="utf-8")
        if "OFFSET :" not in src:
            continue
        for m in pattern.finditer(src):
            clause = " ".join(m.group(1).split())
            yield path.relative_to(BACKEND), src[:m.start()].count("\n") + 1, clause


# Columns that are unique in their table, so an ORDER BY ending in one is already a total
# order. Verified against the database on 25 September 2026 (rows == distinct):
#   eu_trade_defence_measures.celex 1,528   eu_trade_agreements.celex     1,652
#   eu_comitology_documents.document_reference 95,461                     
#   eu_geographical_indications.gi_identifier  6,147
# catalan_translations.celex is NOT unique (41,740 rows, 41,370 distinct) and is only a
# valid tiebreaker where the query GROUPs BY it.
_UNIQUE_TAILS = ("id", "celex", "concept_uri", "uri", "document_reference", "gi_identifier",
                 "mep_id", "code", "item_type", "ind_code")


def test_every_raw_sql_page_query_ends_on_a_unique_column():
    """The ORM fix cannot reach raw SQL: these ORDER BYs must end in a unique column
    themselves, or the same rows repeat and others are never served."""
    offenders = []
    for path, line, clause in _raw_sql_paginated_order_bys():
        if "{" in clause:          # built from a vetted map; those carry their own id
            continue
        tail = clause.split(",")[-1].strip().split()[0].lower()
        tail = tail.rsplit(".", 1)[-1]
        if tail not in _UNIQUE_TAILS:
            offenders.append(f"{path}:{line} -> {clause}")
    assert not offenders, "raw-SQL paging without a unique final sort column:\n  " + "\n  ".join(offenders)


def test_there_are_raw_sql_page_queries_to_check():
    assert sum(1 for _ in _raw_sql_paginated_order_bys()) > 20


# ------------------------------------------------------------------ the walk itself
@pytest.fixture(scope="module")
def api():
    from api.v1._deps import api_user_with_rate_limit
    from main import app
    from models.user import User

    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin")
    from fastapi.testclient import TestClient
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.mark.parametrize("route,key", [
    ("/api/v2/commission/consultations", "id"),
    ("/api/v2/legislative/eur-lex/laws", "celex"),
])
def test_walking_every_page_yields_every_record_exactly_once(api, route, key):
    """GovClipping's own measurement, as a test: walk the whole envelope and compare the
    number of records SERVED with the number of DISTINCT records. Before the fix these
    differed by 27% on consultations, with no error anywhere in the response."""
    first = api.get(route, params={"page": 1, "limit": 100})
    assert first.status_code == 200, first.text[:200]
    pages = first.json()["pages"]
    assert pages > 3, f"{route} has only {pages} page(s): too few to detect the bug"

    seen, served = [], 0
    for page in range(1, min(pages, 25) + 1):     # bounded: the defect shows in the first few
        body = api.get(route, params={"page": page, "limit": 100}).json()
        rows = body.get("data") or []
        served += len(rows)
        seen.extend(r[key] for r in rows)

    duplicates = served - len(set(seen))
    assert duplicates == 0, (
        f"{route}: {served} records served but only {len(set(seen))} distinct "
        f"({duplicates} repeats, each one standing in for a record never served)")
