"""
Tests for Day-6 items shipped into /api/v1/*:
    1. structured error envelope (error / reason_code / request_id)
    2. X-Request-Id response header
    3. `returned` + `coverage_complete` in the envelope
    4. `published_end` and `updated_end` param aliases
    5. Dual auth: both Authorization: Bearer and X-API-Key work
    6. GET /api/v1/meta/enums
"""

import re
import uuid
import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

from tests.conftest import TEST_API_BALANCE_MICRO


@pytest.fixture
def blue_user_key():
    db = SessionLocal()
    try:
        user = User(
            email=f"test_day6_{uuid.uuid4().hex[:8]}@example.com",
            full_name="day6 test",
            subscription_tier="blue",
            is_active=True,
            # Metered v1 endpoints debit before the handler runs; an unfunded
            # user 402s and the test reports a billing gate as a broken endpoint.
            api_balance_eur_micro=TEST_API_BALANCE_MICRO,
        )
        db.add(user)
        db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="day6")
        db.add(key)
        db.commit()
        yield plaintext
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


# ------------------------- 1. structured error envelope ---------------------


def test_error_envelope_has_error_reason_code_request_id_for_401():
    client = TestClient(app)
    r = client.get("/api/v1/whoami")
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert "reason_code" in body
    assert "request_id" in body
    assert body["reason_code"] == "auth_missing_key"
    # request_id looks like a uuid
    assert re.fullmatch(r"[0-9a-f-]{36}", body["request_id"])


def test_error_envelope_for_unknown_endpoint_404():
    client = TestClient(app)
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body.get("reason_code") == "not_found"
    assert "request_id" in body


def test_error_envelope_for_bad_query_422(blue_user_key):
    client = TestClient(app)
    r = client.get("/api/v1/laws?limit=9999", headers={"X-API-Key": blue_user_key})
    assert r.status_code == 422
    body = r.json()
    assert body.get("reason_code") == "invalid_query"
    assert "request_id" in body


# ------------------------- 2. X-Request-Id header ---------------------------


def test_x_request_id_on_success(blue_user_key):
    client = TestClient(app)
    r = client.get("/api/v1/whoami", headers={"X-API-Key": blue_user_key})
    assert r.status_code == 200
    assert "X-Request-Id" in r.headers
    assert re.fullmatch(r"[0-9a-f-]{36}", r.headers["X-Request-Id"])


def test_x_request_id_on_error():
    client = TestClient(app)
    r = client.get("/api/v1/whoami")
    assert r.status_code == 401
    header = r.headers.get("X-Request-Id")
    body = r.json()
    assert header and header == body["request_id"]


def test_x_request_id_echoes_inbound(blue_user_key):
    inbound = "00000000-1111-2222-3333-444444444444"
    client = TestClient(app)
    r = client.get(
        "/api/v1/whoami",
        headers={"X-API-Key": blue_user_key, "X-Request-Id": inbound},
    )
    assert r.headers["X-Request-Id"] == inbound


# ------------------------- 3. returned + coverage_complete ------------------


def test_envelope_has_returned_and_coverage_complete(blue_user_key):
    client = TestClient(app)
    r = client.get("/api/v1/laws?limit=3", headers={"X-API-Key": blue_user_key})
    assert r.status_code == 200
    body = r.json()
    assert "returned" in body
    assert "coverage_complete" in body
    assert body["returned"] == len(body["data"])
    assert isinstance(body["coverage_complete"], bool)


# ------------------------- 4. alias params ---------------------------------


def test_published_end_alias_is_accepted(blue_user_key):
    client = TestClient(app)
    r = client.get(
        "/api/v1/laws?published_from=2026-01-01&published_end=2026-01-31&limit=2",
        headers={"X-API-Key": blue_user_key},
    )
    assert r.status_code == 200
    body = r.json()
    # Envelope echoes both (published_end mirrors published_to)
    assert body["published_from"] == "2026-01-01"
    assert body["published_to"] == "2026-01-31"
    assert body["published_end"] == "2026-01-31"


# ------------------------- 5. dual auth ------------------------------------


def test_authorization_bearer_works(blue_user_key):
    client = TestClient(app)
    r = client.get(
        "/api/v1/whoami",
        headers={"Authorization": f"Bearer {blue_user_key}"},
    )
    assert r.status_code == 200
    assert r.json()["tier"] == "blue"


def test_x_api_key_still_works(blue_user_key):
    client = TestClient(app)
    r = client.get("/api/v1/whoami", headers={"X-API-Key": blue_user_key})
    assert r.status_code == 200


def test_bearer_wrong_scheme_rejected():
    client = TestClient(app)
    r = client.get("/api/v1/whoami", headers={"Authorization": "Basic zzz"})
    assert r.status_code == 401


# ------------------------- 6. /meta/enums ----------------------------------


def test_meta_enums_unauth_returns_401():
    client = TestClient(app)
    r = client.get("/api/v1/meta/enums")
    assert r.status_code == 401


def test_meta_enums_returns_expected_keys(blue_user_key):
    client = TestClient(app)
    r = client.get("/api/v1/meta/enums", headers={"X-API-Key": blue_user_key})
    assert r.status_code == 200
    body = r.json()
    for k in [
        "datasets", "methods_by_dataset", "doc_types", "policy_areas",
        "ep_committees", "procedure_statuses", "stakeholder_user_types",
        "detail_levels", "generated_at",
    ]:
        assert k in body, f"missing {k}"
    assert "laws" in body["datasets"]
    assert "LIBE" in body["ep_committees"]
    assert body["detail_levels"] == ["Minimal", "Summary", "Full"]
    assert isinstance(body["policy_areas"], list)
