"""Brubru's licences: one rule, in the EU list's form, and a credit on every API response (22 Oct 2026).

The catalogue gave CC BY 4.0 to every dataset, the paid API included, as a
creativecommons.org address on the dataset only; the Catalan API said MIT; no
response credited the EU sources. These check the rule (free = CC BY 4.0, keyed =
Brubru's terms), that every distribution carries the licence data.europa.eu
scores, and that a real /api/v1 and /api/v2 response carries the credit.
"""
import pathlib
import sys

from fastapi.testclient import TestClient
from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, DCTERMS, RDF

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.vocabularies.dcat_ap_serializer import serialize  # noqa: E402
from services.vocabularies.licences import (  # noqa: E402
    BRUBRU_DATA_TERMS, CC_BY_4_0, OPEN_DATASETS, SOURCE_CREDIT, licence_for,
)

BASE = "https://brubru.beresol.eu/datasets/"


def test_free_datasets_are_cc_by_and_keyed_ones_carry_our_terms():
    assert licence_for(BASE + "catalan-eu-laws") == CC_BY_4_0
    assert licence_for(BASE + "europa-source-registry") == CC_BY_4_0
    for keyed in ("v2-rest-api", "chat-knowledge-guides", "eu-laws-tsvector", "eu-vocabularies",
                  "textile-circularity-corpus", "eu-digital-product-passport"):
        assert licence_for(BASE + keyed) == BRUBRU_DATA_TERMS, keyed
    # the EU list's address, which the portal's quality check recognises
    assert CC_BY_4_0 == "http://publications.europa.eu/resource/authority/licence/CC_BY_4_0"
    assert all(u.startswith(BASE) for u in OPEN_DATASETS)


def _graph(rows):
    g = Graph()
    g.parse(data=serialize(rows, format="turtle"), format="turtle")
    return g


def _row(uri, dists):
    return {"id": uri, "dcat_uri": uri, "title": "t", "description": {"en": "d"}, "dcat_theme": [],
            "distribution": [{"access_url": a, "media_type": m, "format": "X"} for a, m in dists],
            "license": licence_for(uri), "accrual_periodicity": "P1D"}


def test_every_distribution_carries_the_licence_the_portal_scores():
    rows = [_row(BASE + "catalan-eu-laws", [("https://brubru.beresol.eu/legislacio-ue-catala/", "text/html")]),
            _row(BASE + "v2-rest-api", [("https://x/openapi.json", "application/json"),
                                        ("https://brubru.beresol.eu/api/docs", "text/html")])]
    g = _graph(rows)
    dists = list(g.subjects(RDF.type, DCAT.Distribution))
    assert len(dists) == 3
    licences = {str(next(g.objects(d, DCTERMS.license))) for d in dists}
    assert licences == {CC_BY_4_0, BRUBRU_DATA_TERMS}
    for uri, lic in ((BASE + "catalan-eu-laws", CC_BY_4_0), (BASE + "v2-rest-api", BRUBRU_DATA_TERMS)):
        assert str(next(g.objects(URIRef(uri), DCTERMS.license))) == lic
    # both are licence documents; ours, outside the EU list, has a title
    assert (URIRef(CC_BY_4_0), RDF.type, DCTERMS.LicenseDocument) in g
    assert (URIRef(BRUBRU_DATA_TERMS), RDF.type, DCTERMS.LicenseDocument) in g
    assert list(g.objects(URIRef(BRUBRU_DATA_TERMS), DCTERMS.title))
    assert not list(g.objects(URIRef(CC_BY_4_0), DCTERMS.title))


def test_a_row_without_a_licence_states_none():
    row = _row(BASE + "x", [("https://x/y", "text/html")])
    row["license"] = None
    g = _graph([row])
    assert not list(g.triples((None, DCTERMS.license, None)))


def test_the_credit_names_the_source_the_changes_and_the_terms():
    for words in ("European Union", "2011/833/EU", "CC BY 4.0", "changed", "public_url",
                  "Official Journal", BRUBRU_DATA_TERMS):
        assert words in SOURCE_CREDIT, words
    SOURCE_CREDIT.encode("ascii")   # a header value: ASCII only


def test_real_v1_and_v2_responses_carry_the_credit_and_the_licence_link():
    from main import app
    client = TestClient(app)
    for path in ("/api/v1/laws?limit=1", "/api/v2/dpp/sectors"):
        r = client.get(path)        # no key: refused, and still credited
        assert r.status_code in (401, 403), (path, r.status_code)
        assert r.headers["X-Source-Credit"] == SOURCE_CREDIT, path
        assert f'<{BRUBRU_DATA_TERMS}>; rel="license"' in r.headers.get_list("link"), path
    assert "X-Source-Credit" not in client.get("/openapi.json").headers   # only the data API


def test_a_deprecated_alias_keeps_its_successor_link_beside_the_licence():
    # The real middleware function on a route that sets its own Link, as the
    # deprecated Parliament aliases do: append, not set, so both links survive.
    from fastapi import FastAPI, Response
    import main

    app = FastAPI()

    @app.get("/api/v2/parliament/texts-adopted")
    def old(response: Response):
        response.headers["Link"] = '</api/v2/parliament/plenary-adopted-texts>; rel="successor-version"'
        return {"ok": True}

    app.middleware("http")(main._v1_rate_limit_headers)
    links = TestClient(app).get("/api/v2/parliament/texts-adopted").headers.get_list("link")
    assert '</api/v2/parliament/plenary-adopted-texts>; rel="successor-version"' in links
    assert f'<{BRUBRU_DATA_TERMS}>; rel="license"' in links


def test_the_public_openapi_declares_the_terms():
    from main import app
    spec = TestClient(app).get("/api/openapi.json").json()
    assert spec["info"]["license"]["url"] == BRUBRU_DATA_TERMS
    assert spec["info"]["termsOfService"] == "https://brubru.beresol.eu/terms"
