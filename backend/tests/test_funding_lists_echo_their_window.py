"""Every funding list that takes a change window says back the window it applied (23 Oct 2026).

Read on production: the TED list and the factory lists echoed `updated_from` / `updated_to` in
the envelope; the F&T calls, calls for tenders, funded projects, the cohesion fund lists, their
outcomes, EAGF/EAFRD and the Solidarity Fund filtered on it and said nothing. And the programmes
directory, CAP payments and the Solidarity Fund described their fields with the cohesion lists'
words ("the programme's status / adoption date"). These call the real funding router.
"""
import pathlib
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Query

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402


class _Empty:
    def mappings(self): return self
    def all(self): return []
    def fetchall(self): return []
    def first(self): return None
    def fetchone(self): return None
    def scalar(self): return 0


class _NoRowsQuery(Query):
    def count(self): return 0
    def all(self): return []


class _Db:
    def execute(self, stmt, params=None): return _Empty()
    def query(self, *entities): return _NoRowsQuery(list(entities))


def _client():
    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: _Db()
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


@pytest.mark.parametrize("path", ["ft-calls-for-proposals", "ft-calls-for-tenders", "ft-funded-projects",
                                  "erdf", "erdf/outcomes", "eagf", "eafrd", "eusf"])
def test_the_window_is_said_back(path):
    r = _client().get(f"/api/v2/funding/{path}",
                      params={"updated_from": "2026-10-22T08:00:00Z", "updated_to": "2026-10-22"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated_from"].startswith("2026-10-22T08:00"), path
    assert body["updated_to"].startswith("2026-10-22T23:59"), path      # the whole day


def test_no_funding_schema_but_cohesion_finances_uses_the_cohesion_date_wording():
    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    schemas = app.openapi()["components"]["schemas"]
    for name in ("ProgrammeItem", "CAPPaymentItem", "EUSFCase"):
        props = schemas[name]["properties"]
        assert "adoption date" not in props["document_date"].get("description", ""), name
    # The directory links each programme's own Commission page, not a Cohesion Open Data page.
    assert "Cohesion Open Data" not in schemas["ProgrammeItem"]["properties"]["public_url"]["description"]
