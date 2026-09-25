"""A 2014 regulation looked as if it were published in 2026 (GovClipping, 25 Sep 2026).

/legislative/delegated-acts and /legislative/implementing-acts served only creation_date
and last_updated, and both of those hold OUR import timestamps (2026-04-25, 2026-05-03,
2026-08-10). Measured that day, 4 of 7,521 rows had a publication_date.

It is not only a display problem. The list endpoint SORTS and FILTERS on publication_date,
so `published_from` / `published_to` were answered from those 4 rows and returned almost
nothing, with a 200 and no sign that the filter had nothing to work with.

Cellar holds both dates an act has, and both are now stored:
    publication_date <- cdm:work_date_creation_legacy   the Official Journal date
    adoption_date    <- cdm:work_date_document          the date it was adopted

Verified against the Journal before trusting the predicate: 32014R0241 appeared in OJ L 74
of 14 March 2014 and was adopted on 7 January 2014; 32016R0161 in OJ L 32 of 9 February
2016, adopted 2 October 2015; 32014R0342 in OJ L 100 of 3 April 2014.

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


def test_acts_with_a_celex_carry_a_publication_date(db):
    undated = db.execute(text(
        "SELECT count(*) FROM secondary_acts WHERE celex IS NOT NULL "
        "AND publication_date IS NULL")).scalar()
    assert undated == 0, f"{undated} act(s) with a CELEX still have no publication date"


@pytest.mark.parametrize("celex,adopted,published", [
    ("32014R0241", "2014-01-07", "2014-03-14"),   # OJ L 74, 14.3.2014
    ("32016R0161", "2015-10-02", "2016-02-09"),   # OJ L 32, 9.2.2016
    ("32014R0342", "2014-01-21", "2014-04-03"),   # OJ L 100, 3.4.2014
])
def test_the_dates_are_the_acts_own_dates(db, celex, adopted, published):
    row = db.execute(text(
        "SELECT adoption_date::text, publication_date::text FROM secondary_acts "
        "WHERE celex = :c"), {"c": celex}).fetchone()
    assert row is not None, f"{celex} is missing"
    assert row[0] == adopted, f"{celex} adoption date is {row[0]}, expected {adopted}"
    assert row[1] == published, f"{celex} publication date is {row[1]}, expected {published}"


def test_no_act_is_dated_by_when_we_imported_it(db):
    """The import ran on 25 Apr, 3 May and 10 Aug 2026. An act published on one of those
    exact days is possible but three clusters of them is the bug coming back."""
    for import_day in ("2026-04-25", "2026-05-03", "2026-08-10"):
        n = db.execute(text(
            "SELECT count(*) FROM secondary_acts WHERE publication_date = :d"),
            {"d": import_day}).scalar()
        assert n < 50, f"{n} acts are dated {import_day}, the day we imported them"


def test_an_act_is_not_published_before_it_is_adopted(db):
    """A sanity check on the two predicates: the Journal cannot precede the adoption."""
    impossible = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE adoption_date IS NOT NULL AND publication_date IS NOT NULL "
        "AND publication_date < adoption_date")).scalar()
    assert impossible == 0, f"{impossible} act(s) are published before they were adopted"


def test_the_corpus_spans_real_legislative_history(db):
    """If the dates were import timestamps they would all sit in 2026."""
    lo, hi = db.execute(text(
        "SELECT min(publication_date)::text, max(publication_date)::text "
        "FROM secondary_acts WHERE publication_date IS NOT NULL")).fetchone()
    assert lo < "2015-01-01", f"earliest publication date is {lo}: still import-shaped"
    assert hi >= "2026-01-01", f"latest publication date is {hi}"


def test_a_date_window_now_selects_on_the_acts_date(db):
    """The filter the endpoint exposes has to be answerable."""
    in_2014 = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE publication_date >= '2014-01-01' AND publication_date < '2015-01-01'")).scalar()
    assert in_2014 > 20, f"only {in_2014} acts published in 2014: the window is still empty"


# ------------------------------------------------------------------ what the API serves
@pytest.fixture(scope="module")
def api():
    from fastapi.testclient import TestClient

    from api.v1._deps import api_user_with_rate_limit
    from main import app
    from models.user import User

    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.mark.parametrize("celex,adopted,published", [
    ("32014R0241", "2014-01-07", "2014-03-14"),
    ("32016R0161", "2015-10-02", "2016-02-09"),
])
def test_the_endpoint_serves_both_of_the_acts_dates(api, celex, adopted, published):
    rows = api.get("/api/v2/legislative/delegated-acts", params={"celex": celex}).json()["data"]
    assert len(rows) == 1, f"{celex} returned {len(rows)} rows"
    assert rows[0]["publication_date"] == published
    assert rows[0]["adoption_date"] == adopted
    # document_date is the uniform datapoint and keeps aliasing publication_date, so
    # adding adoption_date did not redefine a field clients already read.
    assert rows[0]["document_date"] == published


def test_filtering_by_celex_returns_that_act(api):
    """`celex` was not a declared parameter, so it was ignored and the caller got an
    unrelated act with a 200. GovClipping identifies acts by CELEX."""
    rows = api.get("/api/v2/legislative/delegated-acts",
                   params={"celex": "32014R0241"}).json()["data"]
    assert [r["celex"] for r in rows] == ["32014R0241"]


def test_a_published_window_is_answered_from_the_acts_own_dates(api):
    """Before the backfill this returned almost nothing, because the column it filters on
    was null for 7,517 of 7,521 rows."""
    body = api.get("/api/v2/legislative/delegated-acts",
                   params={"published_from": "2014-01-01", "published_to": "2014-12-31",
                           "limit": 1}).json()
    assert body["total"] > 20, f"only {body['total']} delegated acts published in 2014"


def test_the_model_knows_about_the_column():
    """The API read it with getattr(..., None), so a column missing from the model read as
    a null date instead of failing. The mapping now uses the attribute directly."""
    from models.w4_entities import SecondaryAct

    assert hasattr(SecondaryAct, "adoption_date")
    src = (BACKEND / "api" / "v1" / "w4_endpoints.py").read_text(encoding="utf-8")
    assert 'getattr(r, "adoption_date"' not in src
