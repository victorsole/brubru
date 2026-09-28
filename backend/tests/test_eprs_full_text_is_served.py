"""Filling a column is not delivering it.

`eprs_publications.full_text` held 3 rows of text out of 921 until 28 September 2026. Once the
studies were backfilled, three readers still could not see them:

  * `/api/v1/eprs` served `body_txt = summary`, and its own field description said so
    ("currently the publication summary -- EPRS full-text lives in the source HTML behind
    html_url"). That is the "a summary is not a body" defect, documented as intentional
    because the text was not stored. It is now.
  * the same list loaded `full_text` on every row and discarded it, which after the backfill
    means megabytes per call (one study is 437,919 characters).
  * the MCP `search_eprs` tool matched on title and summary only, answering "which studies are
    CALLED this" rather than "which studies SAY this".
"""
import pathlib
import sys

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def headers():
    key = next((l.split("=", 1)[1].strip() for l in pathlib.Path(_BACKEND, ".env").read_text().splitlines()
                if l.startswith("BRUBRU_API_KEY=")), None)
    if not key:
        pytest.skip("no BRUBRU_API_KEY")
    return {"X-API-Key": key, "X-Brubru-Probe": "eprs-tests"}


def _first_with_text(client, headers):
    r = client.get("/api/v1/eprs?limit=25", headers=headers)
    assert r.status_code == 200, r.text[:200]
    for item in r.json().get("data") or []:
        if item.get("has_full_text"):
            return item
    pytest.skip("no row with full text yet (backfill still running)")


def test_the_item_route_serves_the_study_not_its_summary(client, headers):
    listed = _first_with_text(client, headers)
    r = client.get(f"/api/v1/eprs/{listed['publication_id']}", headers=headers)
    assert r.status_code == 200
    body = r.json().get("body_txt") or ""
    assert len(body) > 5_000, f"item route served {len(body)} characters"
    assert len(body) > len(listed.get("body_txt") or ""), "the item must carry more than the list"


def test_the_list_does_not_ship_whole_studies(client, headers):
    """One study is 437,919 characters. A page of 25 of those is not a list response."""
    r = client.get("/api/v1/eprs?limit=25", headers=headers)
    assert r.status_code == 200
    longest = max((len(i.get("body_txt") or "") for i in r.json().get("data") or []), default=0)
    assert longest < 20_000, f"the list served a {longest}-character body"


def test_q_finds_a_study_by_words_inside_it(client, headers):
    """A study's subject is frequently named in neither its title nor its summary."""
    r = client.get("/api/v1/eprs?limit=5&q=economic+coercion", headers=headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("total", 0) > 0, "no study matched a phrase that appears in the corpus"


def test_the_mcp_tool_searches_the_text_and_says_where(client, headers):
    from services.mcp.tools import _handle_search_eprs

    result = _handle_search_eprs("economic coercion", 5)
    assert result["total_results"] > 0
    pubs = result["publications"]
    assert any(p.get("has_full_text") for p in pubs), "no result carried full text"
    assert all("excerpt" in p for p in pubs), "the excerpt field must always be present"
    located = [p for p in pubs if p.get("excerpt")]
    assert located, "nothing matched inside a study's text"
    assert all(len(p["excerpt"]) <= 800 for p in located), "an excerpt is a window, not the study"
