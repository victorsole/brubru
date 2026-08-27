"""D3: `/api/v2/parliament/resolutions` had 72 rows with no dates at all.

The defect (measured 27 Aug 2026): `adoption_date` was NULL on every one of the
72 rows, so date filtering could not work and the corpus was undatable.

Working it turned up a refinement worth keeping. "NULL on every row" is not one
fact but two:

  * 34 rows were genuinely MISSING a date. They are recoverable with no new
    fetching at all -- from `texts_adopted.adoption_date`, and from the "Decision
    by Parliament" event on the OEIL page Brubru already stores.
  * ~37 are NULL CORRECTLY. Their procedures are still TABLED or
    CLOSE_TO_ADOPTION, so no adoption date exists yet.

A fix that filled all 72 would have invented dates for resolutions the Parliament
has not adopted. So the endpoint states which is which, and a null now means NOT
YET ADOPTED rather than "unknown".
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 1. Dates exist now
# ---------------------------------------------------------------------------

def test_resolutions_are_no_longer_entirely_undated(db):
    n, dated = db.execute(text(
        "SELECT count(*), count(adoption_date) FROM ep_resolutions")).fetchone()
    assert dated > 0, "every resolution is still undated; date filtering cannot work"
    assert dated >= 30, f"only {dated} of {n} dated; the backfill under-ran"


def test_date_filtering_actually_narrows_the_result(client):
    """The user-visible consequence. With every date NULL this returned nothing
    for any window, which is indistinguishable from an empty corpus."""
    all_ = client.get("/api/v1/resolutions?limit=1").json()["total"]
    filtered = client.get(
        "/api/v1/resolutions?published_from=2026-01-01&limit=1").json()["total"]
    assert filtered > 0, "a date-filtered query still returns nothing"
    assert filtered < all_, "the date filter does not narrow anything"


def test_dates_agree_with_the_other_ep_surface(db):
    """Two EP surfaces must not quietly contradict each other about when the
    Parliament adopted a text."""
    bad = db.execute(text("""
        SELECT count(*) FROM ep_resolutions r
        JOIN texts_adopted t ON t.procedure_ref = r.procedure_ref
        WHERE r.adoption_date IS NOT NULL AND t.adoption_date IS NOT NULL
          AND r.adoption_date <> t.adoption_date::date
    """)).scalar()
    assert bad == 0, f"{bad} resolution(s) disagree with texts_adopted on the date"


# ---------------------------------------------------------------------------
# 2. The refinement: a NULL that is CORRECT
# ---------------------------------------------------------------------------

def test_undated_resolutions_are_genuinely_unadopted(db):
    """No date was invented. Every remaining NULL must belong to a procedure that
    has not been adopted, otherwise the backfill simply missed it."""
    rows = db.execute(text("""
        SELECT c.current_status::text s, count(*) n
        FROM ep_resolutions r
        JOIN legislative_carriages c ON c.oeil_procedure_ref = r.procedure_ref
        WHERE r.adoption_date IS NULL
        GROUP BY 1
    """)).fetchall()
    if not rows:
        pytest.skip("no undated resolutions left")
    adopted_but_undated = [
        r.s for r in rows
        if r.s.upper() not in ("TABLED", "CLOSE_TO_ADOPTION", "IN_COMMITTEE", "PENDING")
    ]
    assert not adopted_but_undated, (
        f"undated resolutions sit on adopted procedures: {adopted_but_undated}"
    )


@pytest.mark.parametrize("path", [
    "/api/v1/resolutions?limit=1",
    "/api/v2/parliament/resolutions?limit=1",
])
def test_the_response_explains_what_a_null_date_means(client, path):
    """Without this, a caller reads a null adoption date as missing data and
    either discards the row or, worse, treats the resolution as never adopted."""
    body = client.get(path).json()
    note = (body.get("coverage_note") or "").lower()
    assert note, f"{path}: no coverage_note"
    assert "not yet adopted" in note or "not been adopted" in note, (
        f"{path}: coverage_note does not explain the null semantics: {note!r}"
    )


@pytest.mark.parametrize("path", [
    "/api/v1/resolutions?limit=1",
    "/api/v2/parliament/resolutions?limit=1",
])
def test_both_ep_resolution_surfaces_declare_coverage(client, path):
    body = client.get(path).json()
    assert body.get("coverage_from"), f"{path}: no coverage_from"
    assert body.get("coverage_to"), f"{path}: no coverage_to"


def test_coverage_counts_are_computed_not_hardcoded(client, db):
    """The note quotes "N of M". Both must come from the table, or they rot as
    the corpus grows."""
    import re
    note = client.get("/api/v1/resolutions?limit=1").json()["coverage_note"]
    m = re.search(r"(\d+) of (\d+)", note)
    assert m, f"coverage_note does not state the counts: {note!r}"
    dated, total = int(m.group(1)), int(m.group(2))
    real = db.execute(text(
        "SELECT count(adoption_date), count(*) FROM ep_resolutions")).fetchone()
    assert (dated, total) == (real[0], real[1]), (
        f"note claims {dated}/{total}, table holds {real[0]}/{real[1]}"
    )


# ---------------------------------------------------------------------------
# 3. Roles reused from D4 rather than left half-empty
# ---------------------------------------------------------------------------

def test_rapporteurs_were_filled_from_the_parsed_carriages(db):
    """D4 recovered rapporteur names for 331 carriages; the resolutions surface
    should not stay blank when the same procedure already has the answer."""
    n = db.execute(text(
        "SELECT count(rapporteur) FROM ep_resolutions")).scalar()
    assert n >= 16, f"only {n} resolutions carry a rapporteur"
