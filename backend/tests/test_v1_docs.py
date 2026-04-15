"""Smoke tests for the v1 docs page and filtered OpenAPI spec."""

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


def test_v1_docs_page_loads_scalar():
    client = TestClient(app)
    for path in ["/api/v1/docs", "/api/docs"]:
        r = client.get(path)
        assert r.status_code == 200, path
        body = r.text
        assert "scalar" in body.lower()
        assert "/api/v1/openapi.json" in body
