"""A failed SPARQL call must retry, say what failed, and flag itself (5 Oct 2026)."""
import asyncio
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")

import httpx  # noqa: E402
import pytest  # noqa: E402
from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

Q = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"


class _Fake:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    async def get(self, *a, **k):
        self.calls += 1
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def _ok():
    return httpx.Response(200, json={"results": {"bindings": []}},
                          request=httpx.Request("GET", "http://x"))


def _run(client, fake, monkeypatch):
    async def nosleep(_):
        return None
    monkeypatch.setattr("asyncio.sleep", nosleep)
    client.client = fake
    return asyncio.run(client.query(Q))


def test_timeout_then_success_retries(monkeypatch):
    c = CellarSPARQLClient()
    fake = _Fake([httpx.ReadTimeout(""), _ok()])
    _run(c, fake, monkeypatch)
    assert fake.calls == 2 and getattr(c, "failure_count", 0) == 0


def test_persistent_timeout_is_flagged_with_a_reason(monkeypatch):
    c = CellarSPARQLClient()
    fake = _Fake([httpx.ReadTimeout("")] * 3)
    with pytest.raises(httpx.ReadTimeout):
        _run(c, fake, monkeypatch)
    assert fake.calls == 3 and c.failure_count == 1 and "ReadTimeout" in c.last_error
