"""
Phase 2 of docs/applications/euvoc.md — DCAT-AP serializer tests.

Static (no DB):
  - serialize() round-trips through rdflib for all 3 formats
  - mandatory DCAT-AP fields are populated
  - dcat:DataService classification rule (v1 API rows)

Live (gated on DATABASE_URL_TEST):
  - end-to-end: load brubru_dataset_catalog rows + serialize
  - HTTP-level smoke for the 3 public endpoints
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

# Add backend/ to sys.path so `from services...` works under pytest.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.vocabularies.dcat_ap_serializer import serialize, catalog_uri  # noqa: E402

DCAT_NS = "http://www.w3.org/ns/dcat#"
DCT_NS = "http://purl.org/dc/terms/"


def _fixture_rows():
    """Two illustrative rows — one Dataset, one DataService."""
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "dcat_uri": "https://brubru.beresol.eu/datasets/test-dataset",
            "title": "Test dataset",
            "description": {"en": "A test dataset", "ca": "Un conjunt de dades de prova"},
            "dcat_theme": ["http://eurovoc.europa.eu/2462"],
            "distribution": [
                {
                    "title": "HTML view",
                    "access_url": "https://brubru.beresol.eu/test/",
                    "media_type": "text/html",
                    "format": "HTML",
                }
            ],
            "license": "http://creativecommons.org/licenses/by/4.0/",
            "accrual_periodicity": "P1D",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "dcat_uri": "https://brubru.beresol.eu/datasets/test-api",
            "title": "Test v1 API",
            "description": {"en": "v1 API surface"},
            "dcat_theme": [],
            "distribution": [
                {
                    "access_url": "https://brubru.beresol.eu/api/v1/test",
                    "media_type": "application/json",
                    "format": "JSON",
                }
            ],
            "license": None,
            "accrual_periodicity": None,
        },
    ]


# ----------------------------------------------------------------------
# Static checks
# ----------------------------------------------------------------------

class TestSerializerStatic:
    def test_turtle_parses(self):
        ttl = serialize(_fixture_rows(), format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        assert len(g) > 0

    def test_rdfxml_parses(self):
        rdf = serialize(_fixture_rows(), format="xml")
        g = Graph()
        g.parse(data=rdf, format="xml")
        assert len(g) > 0

    def test_jsonld_parses(self):
        jl = serialize(_fixture_rows(), format="json-ld")
        g = Graph()
        g.parse(data=jl, format="json-ld")
        assert len(g) > 0

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError):
            serialize(_fixture_rows(), format="csv")

    def test_catalog_iri_stable(self):
        assert catalog_uri().startswith("https://brubru.beresol.eu/")

    def test_catalog_present(self):
        ttl = serialize(_fixture_rows(), format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        catalogs = list(g.subjects(RDF.type, URIRef(f"{DCAT_NS}Catalog")))
        assert len(catalogs) == 1

    def test_data_service_for_v1_api(self):
        ttl = serialize(_fixture_rows(), format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        services = list(g.subjects(RDF.type, URIRef(f"{DCAT_NS}DataService")))
        # The fixture's second row has v1+JSON distribution — should be DataService.
        assert any("test-api" in str(s) for s in services), (
            "v1 API row not classified as dcat:DataService"
        )

    def test_mandatory_dcat_ap_fields(self):
        ttl = serialize(_fixture_rows(), format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        ds_subjects = list(g.subjects(RDF.type, URIRef(f"{DCAT_NS}Dataset"))) + list(
            g.subjects(RDF.type, URIRef(f"{DCAT_NS}DataService"))
        )
        assert ds_subjects, "no datasets serialised"
        for ds in ds_subjects:
            for prop, label in [
                (URIRef(f"{DCT_NS}title"), "title"),
                (URIRef(f"{DCT_NS}description"), "description"),
                (URIRef(f"{DCT_NS}publisher"), "publisher"),
                (URIRef(f"{DCAT_NS}contactPoint"), "contactPoint"),
            ]:
                assert list(g.objects(ds, prop)), f"{ds}: missing {label}"

    def test_multilang_descriptions_preserved(self):
        ttl = serialize(_fixture_rows(), format="turtle")
        # Both EN + CA descriptions of the test-dataset must end up as
        # language-tagged literals in the Turtle.
        ttl_str = ttl.decode("utf-8")
        assert "@en" in ttl_str
        assert "@ca" in ttl_str

    def test_eurovoc_theme_preserved(self):
        ttl = serialize(_fixture_rows(), format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        themes = list(g.objects(predicate=URIRef(f"{DCAT_NS}theme")))
        assert any("eurovoc.europa.eu/2462" in str(t) for t in themes)

    def test_empty_rows_still_renders_catalog(self):
        ttl = serialize([], format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        catalogs = list(g.subjects(RDF.type, URIRef(f"{DCAT_NS}Catalog")))
        assert len(catalogs) == 1


# ----------------------------------------------------------------------
# Live HTTP smoke (gated on DATABASE_URL_TEST)
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

    from api.datasets_dcat import router
    from core.database import get_db

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
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.mark.live
class TestEndpoints:
    def test_ttl_endpoint(self, http_client):
        r = http_client.get("/api/datasets.ttl")
        assert r.status_code == 200
        assert "text/turtle" in r.headers["content-type"]
        # Round-trip parse
        g = Graph()
        g.parse(data=r.content, format="turtle")
        assert len(g) > 0

    def test_rdf_endpoint(self, http_client):
        r = http_client.get("/api/datasets.rdf")
        assert r.status_code == 200
        assert "application/rdf+xml" in r.headers["content-type"]
        g = Graph()
        g.parse(data=r.content, format="xml")
        assert len(g) > 0

    def test_jsonld_endpoint(self, http_client):
        r = http_client.get("/api/datasets.json")
        assert r.status_code == 200
        assert "application/ld+json" in r.headers["content-type"]
        g = Graph()
        g.parse(data=r.content, format="json-ld")
        assert len(g) > 0

    def test_v1_vocabularies_referenced_in_feed(self, http_client):
        """Phase 1 cumulative re-iterate: the 4 vocabulary endpoints
        must appear as dcat:DataService access URLs in the feed."""
        r = http_client.get("/api/datasets.ttl")
        ttl = r.text
        for slug in ("corporate-bodies", "procedures", "directories", "modification-types"):
            assert f"/api/v1/vocabularies/{slug}" in ttl, (
                f"v1 endpoint /api/v1/vocabularies/{slug} not advertised in DCAT-AP feed"
            )
