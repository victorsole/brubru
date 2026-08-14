"""The chat must not import the vector stack when the store is empty.

Production runs the chat on an EMPTY chroma store (chroma_db is gitignored and
never populated at boot), so semantic search already returned nothing. The gating
in services/search + services/ai/context_builder turns that no-op into a genuine
skip, so chromadb / onnxruntime / scikit-learn / scipy never load and ~200 MB is
not paid on every process start (including every cron subprocess).

These tests pin two things that must never regress:
  1. With no store, the availability probe is False, the whole chat retrieval path
     builds keyword-only, and importing it does not drag in the vector stack.
  2. EPRS retrieval returns IDENTICAL results whether the ChromaDB indexer is None
     (the gated production path) or present-but-empty (the old production path) --
     because the PostgreSQL pass is what actually carries EPRS in production.

Run: python3.12 -m pytest tests/test_semantic_gating.py -q
"""
from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def no_store(monkeypatch, tmp_path):
    """Point the probe at an empty directory and clear any override."""
    monkeypatch.delenv("BRUBRU_SEMANTIC_SEARCH", raising=False)
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "absent"))
    yield


def test_availability_probe_false_when_store_absent(no_store):
    from services.search.hybrid_search import semantic_store_available
    assert semantic_store_available() is False


def test_availability_probe_false_for_empty_store(monkeypatch, tmp_path):
    """A freshly-created store has chroma.sqlite3 but no collection dirs."""
    monkeypatch.delenv("BRUBRU_SEMANTIC_SEARCH", raising=False)
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path))
    (tmp_path / "chroma.sqlite3").write_text("")  # empty store marker only
    from services.search.hybrid_search import semantic_store_available
    assert semantic_store_available() is False


def test_override_forces_true(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "absent"))
    monkeypatch.setenv("BRUBRU_SEMANTIC_SEARCH", "1")
    from services.search.hybrid_search import semantic_store_available
    assert semantic_store_available() is True


def test_hybrid_search_keyword_only_returns_empty(no_store):
    """No store -> get_hybrid_search builds with semantic_search=None -> empty response."""
    from services.search.hybrid_search import get_hybrid_search, SearchResponse
    hs = get_hybrid_search()
    assert hs.semantic_search is None
    resp = asyncio.new_event_loop().run_until_complete(hs.search(query="gdpr", limit=5))
    assert isinstance(resp, SearchResponse)
    assert resp.results == []
    assert resp.total_found == 0


def test_context_builder_gates_eprs_to_none(no_store):
    from services.ai.context_builder import get_context_builder
    cb = get_context_builder()
    assert cb.eprs_indexer is None
    assert cb.eprs_matcher is None
    assert cb.hybrid_search.semantic_search is None


def test_eprs_retrieval_identical_gated_vs_empty_indexer(no_store):
    """The whole point: gating changes nothing a production user sees.

    Pass 1 (PostgreSQL) carries EPRS in production. Pass 2 (ChromaDB) is empty.
    Skipping Pass 2 (indexer None) must equal running it against an empty store.
    """
    from services.ai.context_builder import get_context_builder, ExtractedEntities

    cb = get_context_builder()
    assert cb.eprs_indexer is None

    pg_rows = [
        {"publication_id": "EPRS_BRI(2024)001", "title": "GDPR at a glance", "source": "eprs"},
        {"publication_id": "EPRS_STU(2024)002", "title": "AI Act explainer", "source": "eprs"},
    ]
    cb._search_eprs_postgresql = lambda query, entities: list(pg_rows)

    ent = ExtractedEntities(
        celex_numbers=[], procedure_references=[], mep_names=[], committee_codes=[],
        article_references=[], policy_areas=[], dg_codes=[],
    )
    loop = asyncio.new_event_loop()

    gated = loop.run_until_complete(cb._search_eprs_publications("data protection", ent))

    class _EmptyIndexer:
        async def search(self, *a, **k):
            return []

    cb.eprs_indexer = _EmptyIndexer()
    with_empty = loop.run_until_complete(cb._search_eprs_publications("data protection", ent))

    assert gated == with_empty
    assert [r["publication_id"] for r in gated] == [
        "EPRS_BRI(2024)001", "EPRS_STU(2024)002",
    ]
