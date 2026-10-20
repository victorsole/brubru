"""A list route reads the bodies only when it serves them (17 Oct 2026).

Supabase billed Beresol over its egress quota: the database sends every column a query selects,
uncompressed. /laws, /news/all and /funding/international-cooperation blanked body_txt and
body_html on include_body=false only AFTER the database had sent them (an eu_laws row is 107 KB,
103 KB of it the two bodies: a metadata walk of the corpus moved 3.4 GB). Each route now leaves
them out of the query; with include_body=true the query, and so the response, is what it was.
/laws (20 Oct 2026) never reads the bodies with the rows: a second query reads the page's own, up to a size
(tests/test_laws_list_body_cap.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import Query, Session  # noqa: E402

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402

_USER = lambda: SimpleNamespace(role="admin", email="t@example.com")  # noqa: E731


# ------------------------------------------------------------------------------- /laws
class _CountZero(Query):
    """A real ORM query on a session with no database: counts nothing, compiles everything."""

    def count(self):
        return 0


def _laws_sql(monkeypatch, params):
    import api.v1.laws as laws

    sent = {}

    class _Capture:
        def __init__(self, q):
            self.q = q

        def offset(self, n):
            self.q = self.q.offset(n)
            return self

        def limit(self, n):
            self.q = self.q.limit(n)
            return self

        def all(self):
            sent["sql"] = str(self.q.statement.compile(dialect=postgresql.dialect()))
            return []

    monkeypatch.setattr(laws, "stable", lambda query, *a: _Capture(query))
    app = FastAPI()
    app.include_router(laws.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: Session(query_cls=_CountZero)
    app.dependency_overrides[api_user_with_rate_limit] = _USER
    r = TestClient(app).get("/api/v1/laws", params=params)
    assert r.status_code == 200, r.text
    return sent["sql"]


@pytest.mark.parametrize("params", [{"include_body": "false"}, {"include_body": "false", "updated_from": "2026-10-01"},
                                    {"include_body": "false", "sector": "3", "year": "2024"}])
def test_laws_without_bodies_does_not_read_them(monkeypatch, params):
    sql = _laws_sql(monkeypatch, params)
    assert "eu_laws.body_html" not in sql and "eu_laws.body_txt" not in sql, sql[:400]
    assert "eu_laws.title" in sql and "eu_laws.legal_basis" in sql and "eu_laws.eurovoc" in sql


@pytest.mark.parametrize("params", [{}, {"include_body": "true"}])
def test_laws_with_bodies_reads_them_apart_from_the_rows(monkeypatch, params):
    sql = _laws_sql(monkeypatch, params)  # the page query: the bodies come in a second query, for the page's rows
    assert "eu_laws.body_html" not in sql and "eu_laws.body_txt" not in sql, sql[:400]


def test_a_law_item_without_bodies_never_touches_them():
    from api.v1.laws import _law_item

    class _Row:
        id, celex, title, doc_type, doc_type_normalized, date = 1, "32016R0679", "GDPR", "Regulation", "Regulation", None
        oj_reference, legal_basis, created_at, updated_at = "OJ L 119, 4.5.2016, p. 1", [], None, None

        @property
        def body_txt(self):
            raise AssertionError("body_txt read")

        body_html = body_txt

    item = _law_item(_Row(), include_body=False)
    assert item.body_txt is None and item.body_html is None and item.title == "GDPR"


# ----------------------------------------------- /news/all and /funding/international-cooperation
class _Result:
    def scalar(self):
        return 0

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def __iter__(self):
        return iter([])


class _SQLRecorder:
    def __init__(self):
        self.sql = []

    def execute(self, stmt, *a, **k):
        self.sql.append(str(stmt))
        return _Result()


def _sent(router, prefix, path, params):
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    db = _SQLRecorder()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = _USER
    r = TestClient(app).get(path, params=params)
    assert r.status_code == 200, r.text
    rows = [s for s in db.sql if " LIMIT :limit" in s]
    assert len(rows) == 1, db.sql
    return rows[0]


def test_news_without_bodies_does_not_read_them():
    from api.v2 import news

    sql = _sent(news.router, "/api/v2", "/api/v2/news/all", {"include_body": "false"})
    assert "n.body_html" not in sql and "n.body_txt" not in sql
    assert sql.count("NULL::text AS body_txt, NULL::text AS body_html") == 2  # both halves of the union
    with_bodies = _sent(news.router, "/api/v2", "/api/v2/news/all", {})
    assert "coalesce(n.body_txt, n.summary) AS body_txt, n.body_html" in with_bodies
    assert "NULL::text AS body_txt" not in with_bodies


def test_international_cooperation_reads_body_html_only_when_served():
    from api.v2.funding import international_cooperation as ic

    without = _sent(ic.router, "/api/v2/funding", "/api/v2/funding/international-cooperation", {"include_body": "false"})
    assert "NULL::text AS body_html" in without and "body_txt" in without  # the award fields are parsed from it
    served = _sent(ic.router, "/api/v2/funding", "/api/v2/funding/international-cooperation", {"include_body": "true"})
    assert "NULL::text AS body_html" not in served and "body_html" in served
