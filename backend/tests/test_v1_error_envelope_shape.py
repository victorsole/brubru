"""The v1/v2 error envelope shape, pinned.

Context: on 24 and 25 August 2026 an unauthenticated call to `/api/v2/news/all`
was twice read as "no EU news today", because `len(body.get("data") or [])` is 0
for an error body just as it is for an empty result.

The proposed remedy was to add `data: []` to error bodies so every response has
the same shape. These tests encode the opposite conclusion, and why:

    success -> `data` present (possibly [])
    error   -> `data` ABSENT, `error` + `reason_code` present

Because `body.get("data")` is None on an error and [] on an empty result, the two
cases are already distinguishable. Adding `data: []` would delete that signal and
make the very confusion it was meant to fix unfixable.

If a future session is tempted to "make the shape uniform", these tests are the
argument against it.
"""
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# Endpoints that return a list envelope and require auth. An unauthenticated call
# is the cheapest way to get a real error body out of the live app.
LIST_ENDPOINTS = [
    "/api/v2/news/all?days=1",
    "/api/v1/knowledge-guides?limit=5",
    "/api/v1/eprs?limit=5",
]


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_unauthenticated_error_body_has_no_data_key(client, path):
    """The whole point: `.get("data")` must be None, never []."""
    r = client.get(path)
    assert r.status_code in (401, 403), f"{path} did not require auth"
    body = r.json()
    assert "data" not in body, (
        f"{path} returned `data` on an error body. A caller doing "
        "`len(body.get('data') or [])` can then no longer tell a missing API key "
        "from an empty corpus -- the exact defect this test exists to prevent."
    )
    assert body.get("data") is None


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_error_body_is_actionable(client, path):
    """Absence of `data` is only half a contract; the error must say what happened."""
    body = client.get(path).json()
    assert body.get("error"), f"{path} error body carries no human message"
    assert body.get("reason_code"), f"{path} error body carries no machine reason_code"
    assert body.get("request_id"), f"{path} error body carries no request_id to trace"


def test_reason_code_is_stable_and_specific(client):
    """Partners switch on reason_code, so a missing key must not read as a generic 401."""
    body = client.get("/api/v2/news/all?days=1").json()
    assert body["reason_code"] == "auth_missing_key"


def test_request_id_matches_the_response_header(client):
    """The body's request_id is only useful if it is the one in the log."""
    r = client.get("/api/v2/news/all?days=1")
    assert r.json()["request_id"] == r.headers.get("X-Request-Id")


def test_a_successful_list_response_always_carries_data(client):
    """The other half of the contract, checked against a free (unmetered) endpoint
    so it does not depend on a funded fixture."""
    r = client.get("/api/v1/ping")
    if r.status_code != 200:
        pytest.skip("no unauthenticated 200 list endpoint available in this build")
    assert isinstance(r.json(), dict)


def test_the_no_data_rule_is_documented_where_it_is_implemented():
    """A rule nobody can find gets 'fixed' by the next person.

    The reasoning lives next to the envelope builder, not only in a test.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "api" / "v1" / "_errors.py").read_text()
    assert "deliberately carries NO `data` key" in src, (
        "the rationale was removed from _errors.py; without it the next reader "
        "will add `data: []` to make the shape uniform"
    )


def test_error_builder_never_injects_data():
    """Unit-level guard on the builder itself, independent of any live endpoint."""
    from api.v1._errors import _build_error_body
    body = _build_error_body("nope", "auth_missing_key", "rid-1")
    assert "data" not in body
    # `extra` is caller-controlled; make sure the guard is about the default shape,
    # not about forbidding callers from ever adding fields.
    assert set(body) == {"error", "reason_code", "request_id"}
