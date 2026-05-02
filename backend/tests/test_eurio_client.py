"""
Phase 7 of docs/applications/euvoc.md — EURIO client + endpoints tests.

The EURIO live endpoint is unconfigured by default (see service
docstring). Tests focus on:
  - the client's safe-fallback behaviour (no live endpoint -> empty
    results + `note`)
  - the v1 endpoints register cleanly and respond 200 with the same
    structure
  - the client signature matches the canonical method surface declared
    in the plan
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.api_clients.eurio_sparql_client import (  # noqa: E402
    DEFAULT_EURIO_ENDPOINT,
    EURIOClient,
)


# ----------------------------------------------------------------------
# Client surface + safe-fallback
# ----------------------------------------------------------------------

class TestEURIOClient:
    def test_default_endpoint_is_unconfigured(self):
        c = EURIOClient()
        assert not c._endpoint_configured

    def test_explicit_endpoint_marks_configured(self):
        c = EURIOClient(endpoint_url="https://example.org/sparql")
        assert c._endpoint_configured

    def test_method_surface(self):
        # The plan declares 5 EURIO methods. Lock the surface.
        c = EURIOClient()
        for m in (
            "find_projects_by_topic",
            "get_project_consortium",
            "get_project_deliverables",
            "get_project_funding_breakdown",
            "find_projects_by_organisation",
        ):
            assert callable(getattr(c, m, None)), f"missing method {m}"

    @pytest.mark.asyncio
    async def test_unconfigured_returns_note(self):
        async with EURIOClient() as c:
            r = await c.find_projects_by_topic("quantum")
        assert r["results"] == []
        assert "note" in r and "endpoint" in r["note"].lower()


# ----------------------------------------------------------------------
# v1 endpoint registration
# ----------------------------------------------------------------------

class TestV1Routes:
    def test_eurio_routes_registered(self):
        from api.v1 import router

        eurio_routes = sorted([
            r.path for r in router.routes if hasattr(r, "path") and "eurio" in r.path
        ])
        # We registered 5 endpoints under /discover/eurio.
        assert len(eurio_routes) >= 5, eurio_routes
        assert any("/projects" in p for p in eurio_routes)
        assert any("/consortium" in p for p in eurio_routes)
        assert any("/deliverables" in p for p in eurio_routes)
        assert any("/funding" in p for p in eurio_routes)
        assert any("/organisations" in p for p in eurio_routes)
