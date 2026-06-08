"""Smoke tests for the public API docs surface.

v2 is the only public API reference: /api/docs renders the v2 Scalar viewer and
/api/v2/openapi.json is the canonical filtered spec. The v1 raw spec stays live
at /api/v1/openapi.json for existing integrations, but the v1 Scalar viewer
(/api/v1/docs) has been retired.
"""

from fastapi.testclient import TestClient
from main import app


def test_v1_openapi_filtered_to_v1_paths():
    client = TestClient(app)
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "Brubru EU Data API"
    assert spec["info"]["version"] == "v1"
    # All paths must be under /api/v1/
    for path in spec["paths"].keys():
        assert path.startswith("/api/v1/"), f"non-v1 path leaked: {path}"
    # Sanity: at least the core endpoints are present
    assert "/api/v1/ping" in spec["paths"]
    assert "/api/v1/laws" in spec["paths"]
    assert "/api/v1/procedures" in spec["paths"]
    assert "/api/v1/commissioners/{name}/agenda" in spec["paths"]


def test_v2_openapi_filtered_to_v2_paths():
    client = TestClient(app)
    for path in ["/api/v2/openapi.json", "/api/openapi.json"]:
        r = client.get(path)
        assert r.status_code == 200, path
        spec = r.json()
        assert spec["info"]["version"] == "v2", path
        for p in spec["paths"].keys():
            assert p.startswith("/api/v2/"), f"non-v2 path leaked at {path}: {p}"
        # Sanity: the proprietary Brussels Lobbies surface is present
        assert "/api/v2/proprietary/brussels-lobbies" in spec["paths"], path


def test_docs_page_serves_v2_scalar():
    client = TestClient(app)
    # Canonical /api/docs and /api/v2/docs both load Scalar pointed at the v2 spec
    for path in ["/api/docs", "/api/v2/docs"]:
        r = client.get(path)
        assert r.status_code == 200, path
        body = r.text
        assert "scalar" in body.lower(), path
        assert "/api/v2/openapi.json" in body, path
        assert "/api/v1/openapi.json" not in body, path


def test_v1_docs_viewer_retired():
    client = TestClient(app)
    # The old v1 Scalar viewer is gone; the raw v1 spec stays available.
    assert client.get("/api/v1/docs").status_code == 404
