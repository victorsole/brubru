"""Tests for /api/v1/publications and the RSS ingester."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.institutional_publication import InstitutionalPublication
from models.user import User
from services.ingestion.rss_ingestor import FeedConfig, RSSIngestor, list_configs


@pytest.fixture
def auth_headers():
    db = SessionLocal()
    try:
        user = User(
            email=f"test_pub_{uuid.uuid4().hex[:8]}@example.com",
            full_name="pub test",
            subscription_tier="blue",
            is_active=True,
        )
        db.add(user)
        db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="pub")
        db.add(key)
        db.commit()
        yield {"X-API-Key": plaintext}
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


@pytest.fixture
def sample_publication():
    db = SessionLocal()
    pub_id = None
    try:
        pub = InstitutionalPublication(
            source_slug="test_smoke",
            institution_slug="test_institution",
            category="press_release",
            external_id=f"smoke-{uuid.uuid4()}",
            url="https://example.europa.eu/test",
            title="Smoke test publication",
            summary="Testing the publications endpoint",
            language="en",
            published_date=datetime.now(timezone.utc),
            policy_areas=["environment"],
            tags=["test"],
        )
        db.add(pub)
        db.commit()
        pub_id = pub.id
        yield pub
    finally:
        if pub_id:
            db.query(InstitutionalPublication).filter(InstitutionalPublication.id == pub_id).delete()
            db.commit()
        db.close()


# ------------------------------------------------- ingester ---


def test_list_configs_finds_yaml_files():
    configs = list_configs()
    assert len(configs) >= 10
    slugs = [c.slug for c in configs]
    assert "ec_press" in slugs
    assert "ecb_press" in slugs


def test_feed_config_from_file_round_trip(tmp_path: Path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "slug: x\n"
        "institution_slug: x_inst\n"
        "url: https://example.com/rss\n"
        "category: press_release\n"
        "language: en\n"
    )
    cfg = FeedConfig.from_file(p)
    assert cfg.slug == "x"
    assert cfg.institution_slug == "x_inst"
    assert cfg.category == "press_release"


@pytest.mark.asyncio
async def test_ingester_handles_upstream_error_cleanly():
    cfg = FeedConfig(slug="unreach", institution_slug="x", url="https://example.invalid/feed")
    with patch(
        "services.ingestion.rss_ingestor.BaseRSSClient.fetch_feed",
        new=AsyncMock(side_effect=Exception("boom")),
    ):
        stats = await RSSIngestor(cfg).run()
    assert stats["error"] == 1
    assert stats["inserted"] == 0


# ------------------------------------------------- API ---


def test_publications_unauth_401():
    r = TestClient(app).get("/api/v1/publications")
    assert r.status_code == 401


def test_publications_returns_envelope(auth_headers, sample_publication):
    client = TestClient(app)
    r = client.get("/api/v1/publications?limit=5", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for f in ["total", "returned", "data", "meta", "coverage_complete"]:
        assert f in body
    assert body["returned"] == len(body["data"])


def test_publications_filter_by_source(auth_headers, sample_publication):
    client = TestClient(app)
    r = client.get(
        "/api/v1/publications?source_slug=test_smoke",
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(item["source_slug"] == "test_smoke" for item in body["data"])


def test_publications_filter_by_institution(auth_headers, sample_publication):
    client = TestClient(app)
    r = client.get(
        "/api/v1/publications?institution_slug=test_institution",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_publications_full_text_search(auth_headers, sample_publication):
    client = TestClient(app)
    r = client.get("/api/v1/publications?q=Smoke", headers=auth_headers)
    assert r.status_code == 200
    assert any("Smoke" in item["title"] for item in r.json()["data"])


def test_publications_sources_endpoint(auth_headers, sample_publication):
    client = TestClient(app)
    r = client.get("/api/v1/publications/sources", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total_sources" in body
    assert "sources" in body
    assert any(s["source_slug"] == "test_smoke" for s in body["sources"])
