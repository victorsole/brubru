"""/laws: a list page reads its rows' texts in one query, up to a size, and says when it leaves one out (20 Oct 2026).

A page of the "Postman testing" client's updated_from sync held the 20-40 MB EBA benchmarking regulations: the
backend loaded and serialised hundreds of MB and stopped answering for 50 minutes. Above LIST_BODY_MAX_CHARS a text
is never read for a list; the item says so in body_withheld, and the single-law route serves it.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import Query, Session  # noqa: E402

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402


class _Row(SimpleNamespace):
    @property
    def body_txt(self):
        raise AssertionError("a list row's own body was read")

    body_html = body_txt


def _row(i, celex, chars):
    return _Row(id=i, celex=celex, title=f"Act {i}", doc_type="Regulation", doc_type_normalized="Regulation", date=None,
                oj_reference=None, legal_basis=[], created_at=datetime(2026, 10, 1), updated_at=datetime(2026, 10, 2),
                body_chars=chars)


def test_a_page_reads_its_texts_up_to_the_cap_and_names_the_one_it_leaves_out(monkeypatch):
    import api.v1.laws as laws
    sent = []

    class _Bodies(Query):
        def count(self):
            return 2

        def all(self):
            sent.append(str(self.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})))
            return [(1, "small text", "<p>small text</p>")]  # the database returns only the row under the cap

    class _Page:
        def __init__(self, q): pass
        def offset(self, n): return self
        def limit(self, n): return self
        def all(self): return [_row(1, "32026R2266", 9_000), _row(2, "32018R0688", 41_728_429)]

    monkeypatch.setattr(laws, "stable", lambda query, *a: _Page(query))
    app = FastAPI()
    app.include_router(laws.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: Session(query_cls=_Bodies)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(role="admin", email="t@example.com")
    r = TestClient(app).get("/api/v1/laws", params={"include_body": "true"})
    assert r.status_code == 200, r.text
    small, giant = r.json()["data"]
    assert (small["body_txt"], small["body_html"], small["body_withheld"]) == ("small text", "<p>small text</p>", None)
    assert giant["body_txt"] is None and giant["body_html"] is None
    assert giant["body_withheld"].startswith("The text is 41,728,429 characters") and "(self)" in giant["body_withheld"]
    assert len(sent) == 1, sent  # one query for the page's texts
    sql = sent[0]
    assert "eu_laws.body_txt" in sql and "eu_laws.body_html" in sql
    assert "IN (1, 2)" in sql and f"<= {laws.LIST_BODY_MAX_CHARS}" in sql, sql


def test_without_bodies_no_text_query_is_sent(monkeypatch):
    import api.v1.laws as laws
    sent = []

    class _Q(Query):
        def count(self):
            return 1

        def all(self):
            sent.append("query")
            return []

    class _Page:
        def __init__(self, q): pass
        def offset(self, n): return self
        def limit(self, n): return self
        def all(self): return [_row(1, "32026R2266", 9_000)]

    monkeypatch.setattr(laws, "stable", lambda query, *a: _Page(query))
    app = FastAPI()
    app.include_router(laws.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: Session(query_cls=_Q)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(role="admin", email="t@example.com")
    item = TestClient(app).get("/api/v1/laws", params={"include_body": "false"}).json()["data"][0]
    assert sent == [] and item["body_txt"] is None and item["body_withheld"] is None


def test_the_single_law_route_serves_the_whole_text():
    from api.v1.laws import _law_item
    row = SimpleNamespace(**{**vars(_row(2, "32018R0688", 41_728_429)), "body_txt": "x" * 10, "body_html": "<p>x</p>"})
    item = _law_item(row)  # no `bodies`: the item route
    assert item.body_txt == "x" * 10 and item.body_withheld is None
