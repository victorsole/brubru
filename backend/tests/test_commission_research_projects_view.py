"""/commission/research-projects reads the funded projects, the one table of the funding standard's §4 (Phase 3e,
2 Nov 2026, register O50), and an old id still opens its project."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_funding_standard_phase2 import COMPILED, _OrmDb


def _client(db):
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.commission import router
    from core.database import get_db
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def _get(params=None):
    COMPILED.clear()
    r = _client(_OrmDb()).get("/api/v2/commission/research-projects", params=params or {})
    return r, list(COMPILED)


def test_the_list_reads_the_funded_projects_of_the_dump_with_its_old_defaults():
    r, sql = _get({"q": "fungus", "since": "2026-01-01", "created_from": "2026-10-01"})
    assert r.status_code == 200, r.text
    count_sql, page_sql = sql
    assert "FROM ft_funded_projects" in count_sql and "economy_items" not in count_sql
    assert "ft_funded_projects.framework_programme IN " in count_sql
    assert "ft_funded_projects.first_seen >= " in count_sql
    assert r.json()["limit"] == 20                                       # the route's old page size
    assert "ORDER BY CASE WHEN (CURRENT_DATE >= date(ft_funded_projects.published_at))" in page_sql   # recent


def test_its_orders_and_a_bad_one():
    _, sql = _get({"order": "title"})
    assert "ORDER BY ft_funded_projects.title ASC" in sql[1]
    _, sql = _get({"order": "updated_asc"})
    assert "ORDER BY ft_funded_projects.last_updated ASC" in sql[1]
    assert _get({"order": "amount"})[0].status_code == 400


def test_an_old_numeric_id_opens_its_project_and_a_grant_number_goes_straight_there(monkeypatch):
    from api.v2.commission import research_projects as rp
    seen = []

    async def get_funded_project(project_id, **kw):
        seen.append(project_id)
        return {"id": project_id}
    monkeypatch.setattr(rp._v1, "get_funded_project", get_funded_project)

    class Db:
        def __init__(self, guid): self.guid = guid
        def execute(self, stmt, params=None):
            assert "item_type = 'research_project'" in str(stmt)
            return SimpleNamespace(scalar=lambda: self.guid)

    async def run(item_id, db):
        return await rp.get_research_project(item_id=item_id, body_threshold=0, user=None, db=db)

    import asyncio
    asyncio.run(run("5992123", Db("101300652")))
    asyncio.run(run("101300652", None))                                  # never asks the old rows
    asyncio.run(run("eeb0808e-3bfa-48a0-81ed-58bd108cea15", None))
    assert seen == ["101300652", "101300652", "eeb0808e-3bfa-48a0-81ed-58bd108cea15"]
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        asyncio.run(run("5", Db(None)))
    assert e.value.status_code == 404


def test_no_writer_keeps_the_old_copy():
    from scripts import sync_economy
    assert ("commission", "research_project") not in sync_economy.INGESTORS
