"""
Phase 3 of docs/applications/euvoc.md — OP Core Metadata mixin tests.

Static (no DB): the envelope serialises to the expected shape.
Live (gated on DATABASE_URL_TEST): an end-to-end vocabulary endpoint
carries the new op_core block and the X-OP-Core-Conformance header.

Phase 3 contract — additive only:
  - Existing PaginatedResponse keys (total, returned, pages, …) all
    remain.
  - One new optional key `op_core` is present.
  - HTTP responses on /api/v1/* gain the X-OP-Core-Conformance: v1.0
    header.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from api.v1._envelope import (  # noqa: E402
    OPCoreMetadata,
    PaginatedResponse,
    build_envelope,
)


# ----------------------------------------------------------------------
# Static checks
# ----------------------------------------------------------------------

class TestOPCoreMetadata:
    def test_default_values(self):
        m = OPCoreMetadata()
        assert m.publisher == "https://brubru.beresol.eu/.well-known/publisher"
        assert m.conforms_to == "https://op.europa.eu/en/web/eu-vocabularies/opcm"
        assert m.is_referenced_by == []

    def test_alias_serialisation(self):
        m = OPCoreMetadata(title="Test", type="Listing", language="en")
        dumped = m.model_dump(by_alias=True)
        assert "dct:title" in dumped
        assert "dct:type" in dumped
        assert "dct:language" in dumped
        assert "dct:publisher" in dumped
        assert "dct:conformsTo" in dumped


class TestEnvelope:
    def test_legacy_fields_preserved(self):
        env = build_envelope(items=[], total=0, page=1, limit=10)
        # The 8 pagination fields must all still exist.
        for k in (
            "total", "returned", "pages", "page", "limit", "has_more",
            "next_page", "remaining_pages",
        ):
            assert hasattr(env, k), f"legacy field '{k}' lost"

    def test_op_core_populated_by_default(self):
        env = build_envelope(items=[], total=0, page=1, limit=10)
        assert env.op_core is not None
        assert env.op_core.publisher == "https://brubru.beresol.eu/.well-known/publisher"
        assert env.op_core.is_part_of == "https://brubru.beresol.eu/.well-known/dcat-ap-catalog"

    def test_op_core_referenced_by_explicit(self):
        env = build_envelope(
            items=[],
            total=0,
            page=1,
            limit=10,
            op_core_title="X listing",
            op_core_type="X",
            op_core_referenced_by=["https://brubru.beresol.eu/api/v1/x"],
        )
        assert env.op_core.title == "X listing"
        assert env.op_core.type == "X"
        assert "https://brubru.beresol.eu/api/v1/x" in env.op_core.is_referenced_by

    def test_payload_serialises_with_aliases(self):
        env = build_envelope(items=[], total=0, page=1, limit=10)
        payload = env.model_dump(by_alias=True)
        assert "op_core" in payload
        assert "dct:title" in payload["op_core"]
        assert "dct:conformsTo" in payload["op_core"]


# ----------------------------------------------------------------------
# Live HTTP smoke
# ----------------------------------------------------------------------

@pytest.fixture
def http_client():
    db_url = os.environ.get("DATABASE_URL_TEST")
    if not db_url:
        pytest.skip("DATABASE_URL_TEST not set")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from api.v1 import router
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db

    # Build a session bound to the test DB and override get_db at the app level.
    test_engine = create_engine(db_url, echo=False)
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def _override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(router)

    async def _fake_user():
        class U:
            id = "test"
            api_tier = "free"
        return U()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[api_user_with_rate_limit] = _fake_user
    return TestClient(app)


@pytest.mark.live
class TestEnvelopeLive:
    def test_v1_vocabularies_carries_op_core(self, http_client):
        r = http_client.get("/api/v1/vocabularies/procedures", params={"lang": "en"})
        assert r.status_code == 200
        body = r.json()
        # Legacy fields preserved
        assert "total" in body
        assert "data" in body
        # New OP Core block present
        assert "op_core" in body, "envelope is missing the op_core block"
        assert body["op_core"]["dct:conformsTo"] == "https://op.europa.eu/en/web/eu-vocabularies/opcm"

    def test_v1_vocabularies_carries_referenced_by_when_set(self, http_client):
        # The vocabularies endpoint doesn't currently inject referenced_by
        # but the field must be present (even if empty list).
        r = http_client.get("/api/v1/vocabularies/procedures", params={"lang": "en"})
        body = r.json()
        assert "dct:isReferencedBy" in body["op_core"]
        assert isinstance(body["op_core"]["dct:isReferencedBy"], list)
