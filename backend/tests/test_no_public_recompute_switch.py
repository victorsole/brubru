"""A public caller must not be able to make the server redo its work (register O201, 5 Nov 2026).

force_recompute was documented "local dev only" yet took any key on /laws/{celex}/recital-article-map and /defined-terms, and no
login at all on /api/legislation/...; refresh took any key on /xref. Each call re-read Cellar or rebuilt and rewrote a stored row.
These call the routes: a test that read the source could not see a value still reaching the store.
"""
import re
import types

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.v1._deps import api_user_with_rate_limit
from core.database import get_db

SWITCHES = re.compile(r"^force|recompute|^refresh$|rebuild|no_?cache|bypass", re.I)


def _user(role="user"):
    return types.SimpleNamespace(id=1, role=role, email="test@example.invalid")


def _client(router, role="user"):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: _user(role)
    app.dependency_overrides[get_db] = lambda: types.SimpleNamespace(rollback=lambda: None)
    return TestClient(app)


def test_no_v2_or_v1_route_lists_a_switch_that_redoes_the_work():
    from api.v1 import router as v1
    from api.v2 import router as v2
    from api import legislative_tracking

    found = []
    for router in (v1, v2, legislative_tracking.router):
        for route in router.routes:
            if isinstance(route, APIRoute):
                found += [f"{route.path} {p.name}" for p in route.dependant.query_params if SWITCHES.search(p.name)]
    assert found == []


def test_a_public_force_recompute_never_reaches_the_recital_store(monkeypatch):
    from api import legislative_tracking
    from services.parsers import recital_article_store as store

    seen = []
    monkeypatch.setattr(store, "get_or_compute_map", lambda db, celex, **kw: seen.append(kw) or {"Article 1": []})
    r = _client(legislative_tracking.router).get("/api/legislation/32016R0679/recital-article-map?force_recompute=true")
    assert r.status_code == 200 and r.json()["available"] is True
    assert seen == [{}]


def test_a_public_force_recompute_never_reaches_the_definitions_store(monkeypatch):
    from api import legislative_tracking
    from services.parsers import definition_store as store

    seen = []
    monkeypatch.setattr(store, "get_or_compute_map", lambda db, celex, **kw: seen.append(kw) or {"risk": {"term": "risk"}})
    r = _client(legislative_tracking.router).get("/api/legislation/32016R0679/defined-terms?force_recompute=true")
    assert r.status_code == 200
    assert seen == [{}]


@pytest.mark.parametrize("role,value,expected", [
    ("user", "true", False),
    ("user", "1", False),
    ("admin", "true", True),
    ("admin", "1", True),
    ("admin", "false", False),
    ("admin", None, False),
    (None, "true", False),
])
def test_only_an_admin_key_can_refresh_xref(role, value, expected):
    from api.v2.legislative.eur_lex import _admin_asks_to_refresh

    request = types.SimpleNamespace(query_params={"refresh": value} if value is not None else {})
    assert _admin_asks_to_refresh(request, _user(role)) is expected


def test_a_standard_key_asking_to_refresh_xref_reads_the_stored_row(monkeypatch):
    """The route itself: with a row stored, a standard key gets it, and nothing goes on to Cellar."""
    from api.v2.legislative import eur_lex

    monkeypatch.setattr(eur_lex, "_law_created_at", lambda db, celex: None)
    monkeypatch.setattr(eur_lex, "_read_law_xref", lambda db, celex: {"relation_total": 7, "relation_counts": {}, "eurovoc": [], "legal_basis": [], "authors": []})

    class _Query:
        def filter(self, *a):
            return self

        def first(self):
            return ("OJ L 119, 4.5.2016, p. 1",)

    app = FastAPI()
    app.include_router(eur_lex.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: _user("user")
    app.dependency_overrides[get_db] = lambda: types.SimpleNamespace(rollback=lambda: None, query=lambda *a: _Query())
    path = next(route.path for route in eur_lex.router.routes if isinstance(route, APIRoute) and route.path.endswith("/laws/{celex}/xref"))
    r = TestClient(app).get(path.replace("{celex}", "32016R0679") + "?refresh=true")
    assert r.status_code == 200, r.text
    assert r.json()["cached"] is True and r.json()["relation_total"] == 7
