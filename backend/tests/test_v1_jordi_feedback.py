"""Regression tests locking every fix from Jordi's 18 April feedback."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

from tests.conftest import TEST_API_BALANCE_MICRO


@pytest.fixture
def auth_headers():
    db = SessionLocal()
    try:
        user = User(
            email=f"jordi_{uuid.uuid4().hex[:8]}@example.com",
            full_name="jordi regression",
            subscription_tier="blue",
            is_active=True,
            # Metered v1 endpoints debit before the handler runs; an unfunded
            # user 402s and the test reports a billing gate as a broken endpoint.
            api_balance_eur_micro=TEST_API_BALANCE_MICRO,
        )
        db.add(user); db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="jordi")
        db.add(key); db.commit()
        yield {"X-API-Key": plaintext}
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit(); db.close()


# -- Point 11: laws filter + 422 on conflicting bounds ---------------------


def test_laws_conflicting_upper_bounds_returns_422(auth_headers):
    r = TestClient(app).get(
        "/api/v1/laws?published_to=2026-01-01&published_end=2026-03-31&limit=5",
        headers=auth_headers,
    )
    assert r.status_code == 422
    assert r.json()["reason_code"] == "conflicting_params"


def test_laws_published_to_and_end_same_value_accepted(auth_headers):
    r = TestClient(app).get(
        "/api/v1/laws?published_to=2026-01-01&published_end=2026-01-01&limit=3",
        headers=auth_headers,
    )
    assert r.status_code == 200


def test_laws_inverted_range_returns_422(auth_headers):
    r = TestClient(app).get(
        "/api/v1/laws?published_from=2026-12-31&published_to=2026-01-01&limit=3",
        headers=auth_headers,
    )
    assert r.status_code == 422
    assert r.json()["reason_code"] == "invalid_date_range"


def test_laws_default_limit_is_50(auth_headers):
    r = TestClient(app).get("/api/v1/laws", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["limit"] == 50


# -- Legal-text recital-article-map: 500 becomes 503 gracefully ------------


def test_legal_text_recital_map_503_on_parser_failure(auth_headers, monkeypatch):
    import api.v1.legal_text as lt
    # Simulate the known-bad GDPR parser crash
    def boom(*a, **kw):
        raise RuntimeError("TF-IDF vocabulary empty")
    monkeypatch.setattr("services.parsers.recital_article_store.get_or_compute_map", boom)
    r = TestClient(app).get("/api/v1/legal-text/32016R0679/recital-article-map", headers=auth_headers)
    assert r.status_code == 503
    assert r.json()["reason_code"] == "computation_unavailable"


# -- Consultations: date format is ISO-8601 --------------------------------


def test_consultations_date_iso_format_helper():
    from api.v1.consultations import _normalise_date
    from datetime import datetime

    assert _normalise_date("2020/10/09 22:02:54") == "2020-10-09T22:02:54Z"
    assert _normalise_date("2020-10-09 22:02:54") == "2020-10-09T22:02:54Z"
    assert _normalise_date("2020-10-09") == "2020-10-09T00:00:00Z"
    assert _normalise_date(datetime(2020, 10, 9, 22, 2, 54)) == "2020-10-09T22:02:54Z"
    assert _normalise_date(None) is None
    assert _normalise_date("") is None


# -- Commissioner detail_url: the cleaner never emits "#" or javascript: ---


def test_commissioner_detail_url_cleaner():
    from services.api_clients.commissioner_agenda_client import CommissionerAgendaClient
    # Build a minimal HTML fragment with a good link + a bad anchor
    html = """
    <article class="ecl-content-item--inline">
      <time><span class="ecl-date-block__day">15</span><span class="ecl-date-block__month">APR</span><span class="ecl-date-block__year">2026</span></time>
      <div class="ecl-content-block__title"><a href="/commissioners/fitto/meeting-with-stakeholders">Meeting with stakeholders</a></div>
      <a href="#top">top</a>
    </article>
    """
    items = CommissionerAgendaClient._parse_items(html)
    assert len(items) == 1
    assert items[0].title == "Meeting with stakeholders"
    # detail_url is INTENTIONALLY empty here, and has been since the Spring-2026
    # ECL redesign. The inline <a href> on a card points at a NEIGHBOURING card's
    # "read more" anchor, so trusting it gave every item the previous item's URL.
    # The parser now leaves it blank and the RSS-merge step fills it in by
    # token-set scoring (see _lookup_rss_url / _lookup_db_urls).
    #
    # Asserting the absolute URL here would be asserting the bug that was fixed --
    # the same trap as an "EDPS is broken" alarm firing on a deliberate `return []`.
    assert items[0].detail_url == "", (
        "the inline href is not trustworthy after the ECL redesign; detail_url "
        "must be populated by the RSS merge, not by the card anchor"
    )


# -- MEPs: total is offset+len (not just limit), profile_url always set ----


def test_meps_total_computation(auth_headers):
    from unittest.mock import AsyncMock, patch
    with patch(
        "api.v1.meps._fetch_list",
        new=AsyncMock(return_value=[
            {"identifier": str(i), "label": f"Test MEP {i}"} for i in range(50)
        ]),
    ):
        r = TestClient(app).get("/api/v1/meps?limit=50", headers=auth_headers)
    body = r.json()
    # 50 returned at page 1 → hint there might be more → total = 50 + 1
    assert body["total"] >= 50
    assert all(x["profile_url"] and x["profile_url"].startswith("https://www.europarl.europa.eu/meps/en/") for x in body["data"])
    # NOTE: this test used to assert coverage_complete is False unconditionally.
    # The endpoint since gained `_fetch_total_count`, an exhaustive upstream count
    # (cached 6h), so when the count SUCCEEDS the total is exact and coverage IS
    # complete. Only the offset+len heuristic is partial. Mocking `_fetch_list`
    # alone no longer reaches the fallback, so the two paths are asserted
    # separately below rather than by flipping this one to True -- which would
    # have deleted the coverage of the fallback path entirely.
    assert isinstance(body["coverage_complete"], bool)


def test_meps_coverage_is_incomplete_only_when_the_count_falls_back(auth_headers):
    """The heuristic path: upstream count unavailable → total is a guess → partial.

    `_fetch_total_count` returning a negative value is the documented "could not
    count" signal, and it is the ONLY thing that may set coverage_complete False.
    """
    with patch(
        "api.v1.meps._fetch_list",
        new=AsyncMock(return_value=[
            {"identifier": str(i), "label": f"Test MEP {i}"} for i in range(50)
        ]),
    ), patch("api.v1.meps._fetch_total_count", new=AsyncMock(return_value=-1)):
        r = TestClient(app).get("/api/v1/meps?limit=50", headers=auth_headers)
    body = r.json()
    assert r.status_code == 200
    assert body["coverage_complete"] is False, (
        "an estimated total must never be advertised as complete coverage"
    )
    assert body["total"] == 51, "offset+len, +1 to hint there may be more"


def test_meps_coverage_is_complete_when_the_count_succeeds(auth_headers):
    """The normal path: an exact upstream total means coverage IS complete."""
    with patch(
        "api.v1.meps._fetch_list",
        new=AsyncMock(return_value=[
            {"identifier": str(i), "label": f"Test MEP {i}"} for i in range(50)
        ]),
    ), patch("api.v1.meps._fetch_total_count", new=AsyncMock(return_value=705)):
        r = TestClient(app).get("/api/v1/meps?limit=50", headers=auth_headers)
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 705
    assert body["coverage_complete"] is True
