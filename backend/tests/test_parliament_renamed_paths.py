"""Three European Parliament paths renamed on 8 Oct 2026, by what ONE ROW is:

    /texts-submitted -> /plenary-tabled-texts
    /texts-adopted   -> /plenary-adopted-texts
    /resolutions     -> /resolution-procedures

The old paths answer as deprecated aliases until 8 Oct 2027 (Deprecation, Sunset and
Link headers). Non-live: runs in CI.
"""
import pytest

from main import app
from services.api_keys.scopes import resolve_required_scope

RENAMED = {
    "/api/v2/parliament/texts-submitted": "/api/v2/parliament/plenary-tabled-texts",
    "/api/v2/parliament/texts-adopted": "/api/v2/parliament/plenary-adopted-texts",
    "/api/v2/parliament/resolutions": "/api/v2/parliament/resolution-procedures",
}


@pytest.mark.parametrize("path", list(RENAMED) + list(RENAMED.values()))
def test_every_renamed_and_alias_path_has_a_real_scope(path):
    """An unmapped v2 path falls to read:misc, which no key holds: the new names would
    have refused every API key."""
    for p in (path, path + "/x"):
        assert resolve_required_scope(p) == "read:ep", p


def _routes():
    return {r.path: r for r in app.routes if getattr(r, "path", "").startswith("/api/v2/parliament/")}


@pytest.mark.parametrize("old, new", list(RENAMED.items()))
def test_both_names_are_routed_and_only_the_old_is_deprecated(old, new):
    routes = _routes()
    assert new in routes and old in routes, (old, new)
    assert routes[old].deprecated and not routes[new].deprecated
    assert routes[old].endpoint is routes[new].endpoint, "the alias must be the SAME function"


def test_an_alias_answers_with_the_three_deprecation_headers():
    from fastapi.testclient import TestClient
    from api.v2.parliament.deprecated_aliases import _headers
    from fastapi import FastAPI, Depends

    mini = FastAPI()

    @mini.get("/api/v2/parliament/resolutions/{ref:path}", dependencies=[Depends(_headers("/resolutions", "/resolution-procedures"))])
    async def _probe(ref: str):
        return {"ok": ref}

    r = TestClient(mini).get("/api/v2/parliament/resolutions/2025/2138(INI)")
    assert r.headers["Deprecation"].startswith("@")
    assert "2027" in r.headers["Sunset"]
    assert r.headers["Link"] == '</api/v2/parliament/resolution-procedures/2025/2138(INI)>; rel="successor-version"'
