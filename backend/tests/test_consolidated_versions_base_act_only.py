"""`/api/v2/legislative/eur-lex/laws/{celex}/consolidated` returned foreign acts.

The defect (15 Sep 2026): for the AI Act (32024R1689) the endpoint answered
`latest = 02016L0797-20260802` (the rail interoperability directive) with 25
versions, 16 of them `celex: None`.

Root cause: the Cellar query used `cdm:act_consolidated_consolidates_resource_legal`,
which links a consolidation to its base act AND to every amending act folded
into it. The AI Act amends the rail directive, the type-approval regulations,
the EASA regulation..., so their consolidations came back too, sorted first
because they are the newest. The CELEX-less rows are intermediate layer works
(`do_not_index`) that carry no CELEX at all.

Fix: query `cdm:act_consolidated_based_on_resource_legal` with a REQUIRED CELEX,
and filter again on the consolidated CELEX shape `0` + base number + `-YYYYMMDD`.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api_clients.cellar_sparql_client import (
    CellarSPARQLClient,
    filter_consolidated_versions,
)

CELLAR = "http://publications.europa.eu/resource/cellar/"

# Shape of the SPARQL response the OLD query returned for 32024R1689 (trimmed).
SPARQL_FIXTURE = [
    {"consolidated": CELLAR + "4e94b669", "consolidatedCelex": "02016L0797-20260802", "date": "2026-08-02"},
    {"consolidated": CELLAR + "278bbb76", "consolidatedCelex": "02018R1139-20260802", "date": "2026-08-02"},
    {"consolidated": CELLAR + "4bf46908", "date": "2026-08-02"},  # layer work, no CELEX
    {"consolidated": CELLAR + "b1730fb2", "consolidatedCelex": "02024R1689-20260727", "date": "2026-07-27"},
    {"consolidated": CELLAR + "ae4cf081", "date": "2026-07-27"},
    {"consolidated": CELLAR + "b93c5306", "consolidatedCelex": "02024R1689-20240712", "date": "2024-07-12"},
    # Same version returned twice, and a lookalike with a malformed suffix.
    {"consolidated": CELLAR + "b93c5306", "consolidatedCelex": "02024R1689-20240712", "date": "2024-07-12"},
    {"consolidated": CELLAR + "zzz", "consolidatedCelex": "02024R16890-20240712", "date": "2025-01-01"},
    # Base act itself (sector 3) must never count as a consolidation.
    {"consolidated": CELLAR + "dc8116a1", "consolidatedCelex": "32024R1689", "date": "2024-07-12"},
]


def test_filter_keeps_only_versions_of_the_base_act_newest_first():
    out = filter_consolidated_versions("32024R1689", SPARQL_FIXTURE)
    assert [r["consolidatedCelex"] for r in out] == [
        "02024R1689-20260727",
        "02024R1689-20240712",
    ]
    assert all(r["date"] for r in out)


def test_filter_takes_the_date_from_the_celex_when_missing():
    out = filter_consolidated_versions(
        "32016r0679", [{"consolidatedCelex": "02016R0679-20160504", "consolidated": "x"}]
    )
    assert out == [{"consolidated": "x", "consolidatedCelex": "02016R0679-20160504", "date": "2016-05-04"}]


def test_filter_on_empty_input():
    assert filter_consolidated_versions("32024R1689", []) == []
    assert filter_consolidated_versions("", SPARQL_FIXTURE) == []


def test_client_queries_based_on_not_consolidates():
    client = CellarSPARQLClient(enable_cache=False)
    captured = {}

    async def fake_select(query):
        captured["q"] = query
        return SPARQL_FIXTURE

    with patch.object(client, "select", side_effect=fake_select):
        rows = asyncio.run(client.get_consolidated_versions("32024R1689"))
    assert "act_consolidated_based_on_resource_legal" in captured["q"]
    assert "act_consolidated_consolidates_resource_legal" not in captured["q"]
    assert rows[0]["consolidatedCelex"] == "02024R1689-20260727"


@pytest.fixture(scope="module")
def api():
    from api.v1._deps import api_user_with_rate_limit
    from main import app
    from models.user import User

    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


def test_endpoint_latest_is_the_base_acts_newest_consolidation(api):
    with patch.object(CellarSPARQLClient, "select", new=AsyncMock(return_value=SPARQL_FIXTURE)):
        r = api.get("/api/v2/legislative/eur-lex/laws/32024R1689/consolidated")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 2
    assert d["latest"]["celex"] == "02024R1689-20260727"
    assert d["latest"]["date"] == "2026-07-27"
    assert all(v["celex"] and v["celex"].startswith("02024R1689-") for v in d["versions"])
