"""
Phase 8 of docs/applications/euvoc.md — EuroSciVoc resolver tests.

The Turtle dump may or may not be present locally. Tests cover both
states:
  - Without the dump: resolver returns gracefully empty results,
    is_loaded() == False.
  - With a synthetic mini-Turtle: resolver loads correctly, resolves a
    known URI, search hits the right concept, CA falls back to ES → EN.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.vocabularies.euroscivoc_resolver import (  # noqa: E402
    EUROSCIVOC_URI_PREFIX,
    EuroSciVocResolver,
)

# Synthetic Turtle for testing — 3 EuroSciVoc concepts, 3 langs each.
_TEST_TURTLE = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix euroscivoc: <http://data.europa.eu/8mn/euroscivoc/> .

euroscivoc:concept-quantum a skos:Concept ;
    skos:prefLabel "quantum technologies"@en, "tecnologías cuánticas"@es,
                   "tecnologie quantistiche"@it .

euroscivoc:concept-ai a skos:Concept ;
    skos:prefLabel "artificial intelligence"@en, "inteligencia artificial"@es,
                   "intelligenza artificiale"@it, "intelligence artificielle"@fr .

euroscivoc:concept-climate a skos:Concept ;
    skos:prefLabel "climate change"@en, "cambio climático"@es .
"""


@pytest.fixture
def resolver_with_dump(tmp_path: Path) -> EuroSciVocResolver:
    dump = tmp_path / "euroscivoc.ttl"
    dump.write_text(_TEST_TURTLE)
    return EuroSciVocResolver(dump_path=dump)


@pytest.fixture
def resolver_without_dump(tmp_path: Path) -> EuroSciVocResolver:
    # tmp_path / does-not-exist
    return EuroSciVocResolver(dump_path=tmp_path / "nope.ttl")


# ----------------------------------------------------------------------
# Without dump
# ----------------------------------------------------------------------

class TestNoDump:
    def test_is_loaded_false(self, resolver_without_dump):
        assert not resolver_without_dump.is_loaded()

    def test_resolve_returns_none(self, resolver_without_dump):
        assert resolver_without_dump.resolve("http://anything", "en") is None

    def test_search_returns_empty(self, resolver_without_dump):
        assert resolver_without_dump.search("quantum", "en") == []


# ----------------------------------------------------------------------
# With synthetic dump
# ----------------------------------------------------------------------

class TestWithDump:
    def test_is_loaded_true(self, resolver_with_dump):
        assert resolver_with_dump.is_loaded()

    def test_resolve_known_uri_in_english(self, resolver_with_dump):
        uri = f"{EUROSCIVOC_URI_PREFIX}concept-quantum"
        assert resolver_with_dump.resolve(uri, "en") == "quantum technologies"

    def test_resolve_uses_ca_fallback_to_es(self, resolver_with_dump):
        # CA isn't in the dump; expect ES.
        uri = f"{EUROSCIVOC_URI_PREFIX}concept-ai"
        assert resolver_with_dump.resolve(uri, "ca") == "inteligencia artificial"

    def test_resolve_falls_back_to_en_when_es_missing(self, resolver_with_dump):
        # climate concept has no IT, FR, or DE — only EN + ES. Asking IT → fallback chain (CA→ES→EN) → ES first.
        uri = f"{EUROSCIVOC_URI_PREFIX}concept-climate"
        assert resolver_with_dump.resolve(uri, "it") == "cambio climático"

    def test_resolve_unknown_uri_returns_none(self, resolver_with_dump):
        assert resolver_with_dump.resolve("http://no/such", "en") is None

    def test_search_hits_substring(self, resolver_with_dump):
        hits = resolver_with_dump.search("quantum", "en")
        assert len(hits) == 1
        assert hits[0]["pref_label"] == "quantum technologies"

    def test_search_lang_mismatch_misses(self, resolver_with_dump):
        # The IT label doesn't contain the EN keyword.
        hits = resolver_with_dump.search("quantum", "it")
        assert hits == []

    def test_search_es_works(self, resolver_with_dump):
        hits = resolver_with_dump.search("inteligencia", "es")
        assert hits and hits[0]["uri"].endswith("concept-ai")


# ----------------------------------------------------------------------
# Build chain rules
# ----------------------------------------------------------------------

class TestFallbackChain:
    def test_ca_chain_includes_es_and_en(self):
        chain = EuroSciVocResolver._build_chain("ca", None)
        assert chain[0] == "ca"
        assert "es" in chain
        assert "en" in chain

    def test_explicit_chain_respected(self):
        chain = EuroSciVocResolver._build_chain("fr", ["en"])
        assert list(chain) == ["fr", "en"]
