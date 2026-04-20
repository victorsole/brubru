"""Tests for the 7 new v1 endpoints shipped 18 April 2026."""

import uuid
from unittest.mock import AsyncMock, patch

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
            email=f"test_new_{uuid.uuid4().hex[:8]}@example.com",
            full_name="new endpoints test",
            subscription_tier="blue",
            is_active=True,
        )
        db.add(user)
        db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="new")
        db.add(key)
        db.commit()
        yield {"X-API-Key": plaintext}
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


# ---- knowledge-guides ----------------------------------------------------


def test_knowledge_guides_unauth_401():
    r = TestClient(app).get("/api/v1/knowledge-guides")
    assert r.status_code == 401


def test_knowledge_guides_list(auth_headers):
    r = TestClient(app).get("/api/v1/knowledge-guides?limit=5", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 50
    assert len(body["data"]) <= 5


def test_knowledge_guides_search(auth_headers):
    r = TestClient(app).get("/api/v1/knowledge-guides?q=GDPR&limit=3", headers=auth_headers)
    assert r.status_code == 200


# ---- laws/{celex}/text ---------------------------------------------------


def test_law_text_missing_celex_returns_404(auth_headers):
    r = TestClient(app).get("/api/v1/laws/NOT_A_REAL_CELEX/text", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["reason_code"] in ("not_found", "text_unavailable")


# ---- eprs ----------------------------------------------------------------


def test_eprs_envelope(auth_headers):
    r = TestClient(app).get("/api/v1/eprs?limit=5", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for f in ["total", "returned", "data", "meta"]:
        assert f in body


# ---- committees ----------------------------------------------------------


def test_committee_work_items(auth_headers):
    r = TestClient(app).get("/api/v1/committees/LIBE/work-items?limit=3", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 0


def test_committee_minutes(auth_headers):
    r = TestClient(app).get("/api/v1/committees/LIBE/minutes?limit=3", headers=auth_headers)
    assert r.status_code == 200


# ---- calendar/events -----------------------------------------------------


def test_calendar_events(auth_headers):
    r = TestClient(app).get("/api/v1/calendar/events?limit=5", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "data" in body


# ---- meps ----------------------------------------------------------------


def test_meps_list_returns_envelope_or_upstream_error(auth_headers):
    with patch(
        "api.v1.meps._fetch_list",
        new=AsyncMock(return_value=[
            {"identifier": "197668", "label": "Manfred WEBER", "givenName": "Manfred", "familyName": "Weber"},
        ]),
    ):
        r = TestClient(app).get("/api/v1/meps?limit=1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["returned"] == 1
    assert body["data"][0]["full_name"] == "Manfred WEBER"
    assert body["data"][0]["profile_url"] == "https://www.europarl.europa.eu/meps/en/197668"


def test_mep_profile_not_found(auth_headers):
    with patch(
        "api.v1.meps._fetch_profile",
        new=AsyncMock(return_value=None),
    ):
        r = TestClient(app).get("/api/v1/meps/999999999", headers=auth_headers)
    assert r.status_code == 404


# ---- predictions ---------------------------------------------------------


def test_predictions_timeline_unknown_procedure(auth_headers):
    # May return 502 if predictor errors, or 200 with null fields. Accept either.
    r = TestClient(app).get("/api/v1/predictions/9999%2F0000%28COD%29/timeline?use_ml=false", headers=auth_headers)
    assert r.status_code in (200, 404, 502)


# ---- meta/enums updated --------------------------------------------------


def test_meta_enums_includes_new_datasets(auth_headers):
    r = TestClient(app).get("/api/v1/meta/enums", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for ds in ["knowledge-guides", "eprs", "committees", "calendar", "meps", "predictions"]:
        assert ds in body["datasets"], f"{ds} missing from datasets"
    assert "eprs_publication_types" in body
    assert "calendar_institutions" in body
