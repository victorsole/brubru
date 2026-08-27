"""D1: `/api/v1/council-documents` must serve DOCUMENTS, not a calendar.

The defect (measured 27 Aug 2026): the endpoint unions Council-tagged
`institutional_publications` with `eu_calendar_events`. Branch 1 held **0 rows
since it shipped**, so every row it had ever returned was a MEETING -- an events
feed wearing a documents name.

The failure was silent and inverted. `?q=minors` returned HTTP 200 with an empty
list, and a caller reasonably concluded the Council had said nothing about minors
online. It had: 25 EU Member States and 2 EFTA countries signed the Jutland
Declaration on 10 October 2025, recorded in Council document ST 15875/25.

These tests pin three things:
  1. the documents branch is not empty,
  2. the acceptance case -- Council material on minors is reachable,
  3. the corpus declares its own bounds, so a zero can be read honestly.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User

COUNCIL_SLUG = "council_of_the_eu"


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
# 1. The documents branch exists at all
# ---------------------------------------------------------------------------

def test_the_documents_branch_is_not_empty(db):
    """Branch 1 held 0 rows since the endpoint shipped. That is the defect."""
    n = db.execute(text(
        "SELECT count(*) FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%'"
    )).scalar()
    assert n > 0, (
        "Council-tagged institutional_publications is empty, so /council-documents "
        "is serving only calendar meetings again. Run scripts/ingest_council_documents.py"
    )


def test_the_feed_actually_contains_documents_not_only_meetings(client):
    """A documents endpoint whose every row is `calendar_event` is a calendar."""
    body = client.get("/api/v1/council-documents?limit=100").json()
    sources = {i["source"] for i in body["data"]}
    assert "publication" in sources, (
        f"every returned row is a meeting (sources={sources}); the documents "
        "branch is not reaching the response"
    )


# ---------------------------------------------------------------------------
# 2. The acceptance case
# ---------------------------------------------------------------------------

def test_a_query_about_minors_online_returns_council_material(client):
    """The exact query that silently returned nothing.

    The Council has published repeatedly on protecting minors online. A zero here
    is the inverted failure this whole fix exists to remove.
    """
    body = client.get("/api/v1/council-documents?q=minors&limit=50").json()
    assert body["total"] > 0, (
        "?q=minors still returns nothing, so the API still implies the Council "
        "has said nothing about minors online"
    )
    docs = [i for i in body["data"] if i["source"] == "publication"]
    assert docs, "matches exist but none is a document"


def test_document_titles_carry_no_register_codes(db):
    """Register rows arrive as 'WK 9054 2026 INIT - INFORMATION 22/06/2026 <title>'.

    The reference and type are stripped into `external_id`/tags at ingest, because
    Brubru's standing rule keeps institutional codes out of human-facing titles.

    Checked over the WHOLE corpus, not a query. The first version of this test
    sampled `?q=minors`, passed, and missed 35 of 248 titles that still opened
    with their reference -- the prefix stripper required a DATE after the document
    type, so "ST 12436 2026 INIT - LEGISLATIVE ACTS AND OTHER INSTRUMENTS: ..."
    and "'I/A' ITEM NOTE" kept theirs. A sample is not a corpus.
    """
    bad = db.execute(text(
        r"SELECT title FROM institutional_publications "
        r"WHERE institution_slug ILIKE '%council%' "
        r"AND title ~ '^(ST|WK|CM|SN|RE) [0-9]+ [0-9]{4}'"
    )).fetchall()
    assert not bad, (
        f"{len(bad)} title(s) still open with a register code, e.g. "
        f"{[b.title[:60] for b in bad[:3]]}"
    )


def test_every_council_document_has_a_real_body(db):
    """`body_txt`/`body_html` are 2 of the 5 mandatory datapoints.

    The ingest originally stored metadata only, so 218 of 248 rows had no body at
    all -- and because the endpoint composes a fallback body from the structured
    row, a presence check on the API still reported 100%. Assert against the
    STORED text, which is the only place the difference is visible.
    """
    n, with_body = db.execute(text(
        "SELECT count(*), count(html_content) FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%'")).fetchone()
    assert with_body == n, f"only {with_body}/{n} Council documents hold a real body"


def test_stored_bodies_are_distinct_documents(db):
    """All-identical bodies would mean one error page stored N times -- which a
    count of non-null rows cannot distinguish from full coverage."""
    n, distinct = db.execute(text(
        "SELECT count(*), count(DISTINCT md5(html_content)) "
        "FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%' AND html_content IS NOT NULL")).fetchone()
    assert distinct >= n * 0.95, f"only {distinct} distinct bodies across {n} rows"


def test_bodies_do_not_open_with_consent_chrome(db):
    """consilium serves a cookie banner ahead of the article; an early version
    stored bodies opening with "We use cookies to improve you...", which passes
    every length check."""
    bad = db.execute(text(
        "SELECT count(*) FROM institutional_publications "
        "WHERE institution_slug ILIKE '%council%' AND html_content IS NOT NULL "
        "AND left(html_content, 300) ILIKE '%we use cookies%'")).scalar()
    assert bad == 0, f"{bad} body/bodies open with the cookie banner"


def test_documents_carry_a_resolvable_source_url(client):
    """A document a caller cannot open is a citation they cannot verify."""
    body = client.get("/api/v1/council-documents?q=minors&limit=50").json()
    docs = [i for i in body["data"] if i["source"] == "publication"]
    assert docs, "no documents to check"
    missing = [d["title"][:40] for d in docs if not d.get("url")]
    assert not missing, f"{len(missing)} document(s) have no url: {missing[:3]}"
    assert all("europa.eu" in d["url"] for d in docs if d.get("url"))


# ---------------------------------------------------------------------------
# 3. Honest coverage — half the fix
# ---------------------------------------------------------------------------

def test_the_response_declares_its_corpus_bounds(client):
    """A zero must be readable. The corpus is a policy-term slice of a register
    that cannot be enumerated, and the response has to say so."""
    body = client.get("/api/v1/council-documents?limit=1").json()
    assert body.get("coverage_note"), "no coverage_note: an empty result stays ambiguous"
    note = body["coverage_note"].lower()
    assert "slice" in note or "not the complete" in note, (
        "coverage_note does not warn that the corpus is partial"
    )
    assert body.get("coverage_from") and body.get("coverage_to"), (
        "coverage_from/coverage_to are null, so the caller cannot tell what window exists"
    )


def test_coverage_bounds_are_real_dates_not_placeholders(client):
    from datetime import date
    body = client.get("/api/v1/council-documents?limit=1").json()
    lo = date.fromisoformat(body["coverage_from"])
    hi = date.fromisoformat(body["coverage_to"])
    assert lo < hi, f"coverage window is inverted or empty: {lo} .. {hi}"


# ---------------------------------------------------------------------------
# 4. The pagination defect found while fixing D1
# ---------------------------------------------------------------------------

def test_deep_pages_are_not_empty_while_total_claims_more(client):
    """Both branches were fetched with `.limit(limit)` and merged before slicing
    by page, so the merged list held at most 2*limit rows and page 3 onwards came
    back EMPTY while `total` still advertised hundreds.
    """
    first = client.get("/api/v1/council-documents?limit=5&page=1").json()
    if first["total"] <= 20:
        pytest.skip("corpus too small to exercise deep pagination")
    p3 = client.get("/api/v1/council-documents?limit=5&page=3").json()
    assert p3["data"], (
        f"page 3 is empty while total={first['total']}; the page slice cannot see "
        "rows the branch queries never fetched"
    )


def test_pages_do_not_repeat_rows(client):
    p1 = client.get("/api/v1/council-documents?limit=10&page=1").json()["data"]
    p2 = client.get("/api/v1/council-documents?limit=10&page=2").json()["data"]
    if not p2:
        pytest.skip("corpus too small for two pages")
    overlap = {i["id"] for i in p1} & {i["id"] for i in p2}
    assert not overlap, f"{len(overlap)} row(s) appear on both pages"
