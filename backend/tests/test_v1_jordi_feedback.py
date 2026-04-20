"""Regression tests locking every fix from Jordi's 18 April feedback."""

import uuid
import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User


@pytest.fixture
def auth_headers():
    db = SessionLocal()
    try:
        user = User(
            email=f"jordi_{uuid.uuid4().hex[:8]}@example.com",
            full_name="jordi regression",
            subscription_tier="blue",
            is_active=True,
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
    assert items[0].detail_url == "https://commission.europa.eu/commissioners/fitto/meeting-with-stakeholders"


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
    assert body["coverage_complete"] is False
