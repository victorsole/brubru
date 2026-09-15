"""OFFSET pagination needs a UNIQUE sort key, or pages overlap.

Incident (FD8, Sep 2026): /api/v1/tenders ordered only by
`publication_date DESC` and then applied OFFSET/LIMIT. TED stamps every notice
of one day with the same publication_date (02:00Z), so Postgres was free to
return a day's rows in any order on each page request: a harvest of 2,014 rows
held only 1,446 distinct ids. The same shape (a non-unique sort column alone
before OFFSET) sat in five more list endpoints.

These tests drive each endpoint through FastAPI with a recording fake DB and
assert the ORDER BY it sends ends in a key that is unique for that result set:
the table's primary key, or (id, item_type) for the /funding/all UNION whose
member tables have overlapping id spaces.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

from core.database import get_db  # noqa: E402
from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from api.v1 import w5_endpoints  # noqa: E402
import api.v2.funding as v2_funding  # noqa: E402


class _Result:
    def scalar(self):
        return 0

    def mappings(self):
        return self

    def all(self):
        return []

    def fetchall(self):
        return []


class _FakeQuery:
    def __init__(self, rec):
        self._rec = rec

    def filter(self, *a, **k):
        return self

    def order_by(self, *clauses):
        self._rec.orm_order.append(
            [str(c.compile(dialect=postgresql.dialect())) for c in clauses]
        )
        return self

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def count(self):
        return 0

    def all(self):
        return []


class _FakeDB:
    def __init__(self):
        self.orm_order: list[list[str]] = []
        self.sql: list[str] = []

    def query(self, *_):
        return _FakeQuery(self)

    def execute(self, stmt, *a, **k):
        self.sql.append(str(stmt))
        return _Result()


class _User:
    id = 1
    email = "probe@example.org"
    role = "admin"
    subscription_tier = "blue"


@pytest.fixture()
def harness():
    db = _FakeDB()
    app = FastAPI()
    app.include_router(w5_endpoints.tenders_router, prefix="/v1")
    app.include_router(w5_endpoints.research_router, prefix="/v1")
    app.include_router(w5_endpoints.officials_router, prefix="/v1")
    app.include_router(v2_funding.router, prefix="/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: _User()
    return TestClient(app), db


@pytest.mark.parametrize(
    "path,table",
    [
        ("/v1/tenders", "tenders"),
        ("/v2/funding/tenders", "tenders"),  # v2 delegates to the v1 handler
        ("/v1/research-publications", "eprs_publications"),
        ("/v1/officials", "eu_officials"),
    ],
)
def test_orm_list_orders_by_primary_key_last(harness, path, table):
    client, db = harness
    resp = client.get(path, params={"page": 3, "limit": 10})
    assert resp.status_code == 200, resp.text
    assert db.orm_order, f"{path} never called order_by"
    last = db.orm_order[-1][-1]
    assert re.fullmatch(rf"{table}\.id( DESC| ASC)?", last), (
        f"{path} ORDER BY {db.orm_order[-1]} does not end in the primary key"
    )


def _order_by_of_paged_sql(sql_list):
    paged = [s for s in sql_list if "OFFSET" in s.upper()]
    assert paged, "no OFFSET query was issued"
    m = re.search(r"ORDER BY (.+?) LIMIT", paged[-1], flags=re.S | re.I)
    assert m, paged[-1]
    return [p.strip() for p in m.group(1).split(",")]


@pytest.mark.parametrize(
    "path",
    [
        "/v2/funding/eusf",
        "/v2/funding/erdf",
        "/v2/funding/erdf/outcomes",
        "/v2/funding/eagf",
        "/v2/funding/international-cooperation",
    ],
)
def test_raw_sql_list_orders_by_primary_key_last(harness, path):
    client, db = harness
    resp = client.get(path, params={"page": 2, "limit": 5})
    assert resp.status_code == 200, resp.text
    keys = _order_by_of_paged_sql(db.sql)
    assert re.fullmatch(r"id( DESC| ASC)?", keys[-1]), f"{path} ORDER BY {keys}"


@pytest.mark.parametrize("order", ["recent", "oldest", "title"])
def test_funding_all_union_orders_by_id_and_item_type(harness, order):
    """The UNION mixes four tables whose id ranges overlap, so `id` alone is not
    unique across it; (id, item_type) is, because every non-economy_items member
    has a constant item_type of its own."""
    client, db = harness
    resp = client.get("/v2/funding/all", params={"order": order, "page": 2, "limit": 5})
    assert resp.status_code == 200, resp.text
    keys = [re.sub(r"\s+(ASC|DESC)$", "", k) for k in _order_by_of_paged_sql(db.sql)]
    assert keys[-2:] == ["id", "item_type"], f"ORDER BY {keys}"


def test_detector_rejects_a_non_unique_sort(harness):
    """Poisoned input: prove the parser would flag `ORDER BY date DESC` alone."""
    _, db = harness
    db.sql.append("SELECT * FROM t ORDER BY publication_date DESC NULLS LAST LIMIT :limit OFFSET :offset")
    keys = _order_by_of_paged_sql(db.sql)
    assert not re.fullmatch(r"id( DESC| ASC)?", keys[-1])
