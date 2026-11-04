"""What the walk through the API Console found on 4 Nov 2026: each test calls the route, because a test that reads the
source cannot see a crash."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql


class _Query:
    """Stands in for a Session's query and compiles every filter it is given, as the database would be asked to."""
    def __init__(self):
        self.sql = []

    def filter(self, *clauses):
        self.sql += [str(c.compile(dialect=postgresql.dialect())) for c in clauses]
        return self

    def __getattr__(self, name):
        if name in ("count", "scalar"):
            return lambda *a, **k: 0
        if name in ("all",):
            return lambda *a, **k: []
        return lambda *a, **k: self


def _request():
    return SimpleNamespace(url=SimpleNamespace(path="/api/v2/legislative/oeil/procedures"), query_params={}, state=SimpleNamespace(), headers={},
                           base_url="https://x/")


def test_the_procedure_status_filter_compiles_to_sql_postgres_can_run():
    from api.v1 import procedures
    query = _Query()
    db = SimpleNamespace(query=lambda *a, **k: query)
    try:
        asyncio.run(procedures.list_procedures(
            _request(), q=None, reference=None, committee=None, rapporteur_mep_id=None, status="tabled", updated_from=None,
            updated_to=None, updated_end=None, include_other_sources=False, limit=1, page=1, user=SimpleNamespace(id=1), db=db,
        ))
    except Exception:  # the response builder is not under test: only what reached the query is
        pass
    status_sql = [s for s in query.sql if "current_status" in s and "lower" in s]
    assert status_sql, f"the status filter never reached the query: {query.sql}"
    assert "AS TEXT" in status_sql[0] and "Function" not in status_sql[0], status_sql[0]


def test_no_route_casts_through_a_function_generator_any_more():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "api"
    assert not [str(p) for p in root.rglob("*.py") if "func.TEXT.type" in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("family,unknown", [
    ("climate", ["climate"]),
    ("nonsense-xyz,finance-economy", ["nonsense-xyz"]),
    ("finance-economy", []),
    ("finance-economy, digital-tech", []),
    ("", []),
    (None, []),
])
def test_unknown_families_are_named(family, unknown):
    from services.economy.body_families import unknown_families
    assert unknown_families(family) == unknown


@pytest.mark.parametrize("module,path", [
    ("api.v2.news", "/all"),
    ("api.v2.events", "/all"),
])
def test_an_unknown_family_is_refused_not_answered_with_the_whole_feed(module, path):
    import importlib
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    mod = importlib.import_module(module)
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: None
    prefix = mod.router.prefix
    response = TestClient(app).get(f"{prefix}{path}", params={"family": "climate"})
    assert response.status_code == 400, response.text
    assert "climate-energy-environment" in response.text


def test_an_unknown_family_is_refused_on_consultations():
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.consultations import consultations_all
    from core.database import get_db
    app = FastAPI()
    app.include_router(consultations_all.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: None
    route = next(r for r in consultations_all.router.routes if r.path.endswith("/all"))
    response = TestClient(app).get(route.path, params={"family": "climate"})
    assert response.status_code == 400, response.text


def test_the_pick_lists_answer_with_no_key_and_give_a_name_for_every_code():
    from api.v2 import pick_lists
    from core.database import get_db
    pick_lists._cache.update(at=0.0, bodies=[])
    rows = [SimpleNamespace(code="commission", name="European Commission"), SimpleNamespace(code="ecb", name=None)]
    db = SimpleNamespace(execute=lambda *a, **k: SimpleNamespace(fetchall=lambda: rows))
    app = FastAPI()
    app.include_router(pick_lists.router)
    app.dependency_overrides[get_db] = lambda: db
    response = TestClient(app).get("/pick-lists")
    assert response.status_code == 200
    body = response.json()
    assert {"code": "commission", "name": "European Commission"} in body["bodies"]
    assert {"code": "ecb", "name": "ecb"} in body["bodies"]
    assert all(b["code"] and b["name"] for b in body["bodies"])
    assert {"slug": "climate-energy-environment", "label": "Climate, Energy & Environment"} in body["families"]
    assert any(c["code"] == "ENVI" and c["name"] for c in body["committees"])
    assert "max-age" in response.headers["Cache-Control"]
