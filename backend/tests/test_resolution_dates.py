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


# ---------------------------------------------------------------------------
# 4. The CORPUS, not just the dates
# ---------------------------------------------------------------------------

def test_the_resolution_corpus_was_backfilled_not_just_dated(db):
    """D3 said "72 rows with NULL dates". Fixing the dates answered half of it.

    The other half: 72 rows was never the corpus. Once `texts_adopted` reached
    703 rows, 157 resolution-typed texts had no row here at all. A surface can be
    perfectly consistent and still be missing most of its subject.
    """
    n = db.execute(text("SELECT count(*) FROM ep_resolutions")).scalar()
    assert n > 100, f"ep_resolutions holds only {n} rows; the corpus backfill has not run"


def test_no_own_initiative_or_topical_resolution_is_missing(db):
    """Every INI / RSP / INL adopted text must have a row here.

    That is this table's declared taxonomy, so a gap in it is a real gap --
    unlike COD/NLE/CNS, which are a different instrument.
    """
    missing = db.execute(text(r"""
        SELECT count(*) FROM texts_adopted t
        WHERE t.text_type::text IN ('resolution','legislative_resolution')
          AND t.procedure_ref IS NOT NULL
          AND substring(t.procedure_ref from '\(([A-Z]+)\)') IN ('INI','RSP','INL')
          AND NOT EXISTS (SELECT 1 FROM ep_resolutions r
                          WHERE r.procedure_ref = t.procedure_ref)
    """)).scalar()
    assert missing == 0, (
        f"{missing} INI/RSP/INL adopted text(s) have no ep_resolutions row -- run "
        "scripts/backfill_ep_resolutions_corpus.py --apply"
    )


def test_the_declared_type_matches_the_procedure_reference(db):
    """`resolution_type` is derived from the procedure suffix, so a mismatch means
    a row was typed by guesswork rather than from its own reference."""
    bad = db.execute(text(r"""
        SELECT count(*) FROM ep_resolutions
        WHERE substring(procedure_ref from '\(([A-Z]+)\)') IS NOT NULL
          AND resolution_type::text <> substring(procedure_ref from '\(([A-Z]+)\)')
    """)).scalar()
    assert bad == 0, f"{bad} row(s) whose resolution_type contradicts their procedure_ref"


def test_vote_tallies_are_internally_consistent(db):
    """A total that is not the sum of its parts is a fabricated tally."""
    bad = db.execute(text(
        "SELECT count(*) FROM ep_resolutions WHERE vote_total IS NOT NULL "
        "AND vote_total <> vote_for + vote_against + vote_abstention")).scalar()
    assert bad == 0, f"{bad} resolution(s) have a vote_total that does not add up"


def test_the_endpoint_declares_what_it_does_not_cover(client):
    """Legislative-procedure texts are absent BY SCOPE. Without saying so, a
    caller reads their absence as the Parliament not having acted."""
    note = client.get("/api/v1/resolutions?limit=1").json()["coverage_note"].lower()
    assert "texts-adopted" in note or "texts_adopted" in note, (
        "coverage_note does not point at where legislative texts actually live"
    )


def test_resolutions_serve_their_own_adopted_text_not_the_procedure_page(client, db):
    """`body_txt` should be the resolution the Parliament adopted.

    This surface used to serve the OEIL PROCEDURE PAGE as the body -- real
    content, but a description of the file rather than its text. Now that
    texts_adopted holds 703/703 bodies, the actual text takes precedence and OEIL
    is the fallback for procedures with no adopted text yet.
    """
    items = []
    for page in (1, 2):
        items += client.get(f"/api/v1/resolutions?limit=100&page={page}").json().get("data") or []
    assert items, "no resolutions returned"
    procedure_page = sum(1 for i in items
                         if (i.get("body_txt") or "").startswith("Basic information"))
    real = len(items) - procedure_page
    assert real > procedure_page, (
        f"only {real} of {len(items)} resolutions serve their own text; "
        f"{procedure_page} still serve the OEIL procedure page"
    )


def test_no_resolution_body_is_navigation_chrome(client):
    """doceo hides a language picker in `.ep_hidden`; 47 stored bodies once OPENED
    with "Choisissez la langue de votre document" -- navigation saved as the text
    of an adopted act, which passes every length and non-null check."""
    items = client.get("/api/v1/resolutions?limit=100").json().get("data") or []
    bad = [i["procedure_ref"] for i in items
           if "Choisissez la langue" in (i.get("body_txt") or "")[:400]]
    assert not bad, f"{len(bad)} resolution body/bodies are the language picker: {bad[:3]}"


def test_every_resolution_has_both_body_datapoints(client):
    items = []
    for page in (1, 2):
        items += client.get(f"/api/v1/resolutions?limit=100&page={page}").json().get("data") or []
    missing_txt = [i["procedure_ref"] for i in items if not (i.get("body_txt") or "").strip()]
    missing_html = [i["procedure_ref"] for i in items if not (i.get("body_html") or "").strip()]
    assert not missing_txt, f"{len(missing_txt)} without body_txt"
    assert not missing_html, f"{len(missing_html)} without body_html"
