"""TED notices get a status from their type and deadline; the list stops reading the XML (23 Oct 2026).

TED publishes no status, and every notice was stored "open" and never revisited: 28,032 said
"open" after their deadline, and all 104 award notices said "open". services/tenders/status.py
holds the rule; scripts/refresh_tender_status.py applies it daily after the fetch. The tenders list
also loaded each notice's stored eForms XML (57 KB on average), which it never serves.
"""
import pathlib
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402
from services.tenders import status as ted_status  # noqa: E402


def test_the_rule_closes_awards_and_passed_deadlines_and_keeps_undated_notices():
    sql = " ".join(ted_status.STATUS_SQL.split())
    assert "WHEN form_type IN ('result', 'cont-modif') THEN 'closed'" in sql
    assert "WHEN submission_deadline < now() THEN 'closed'" in sql
    assert "CASE WHEN form_type = 'planning' THEN 'forthcoming' ELSE status END" in sql
    assert sql.index("form_type IN ('result'") < sql.index("submission_deadline IS NULL") < sql.index("submission_deadline < now()")


def test_refresh_updates_only_what_differs_in_chunks():
    calls = []

    class _Db:
        def execute(self, stmt, params=None):
            calls.append((str(stmt), params))
            rows = [SimpleNamespace(id=i, status="open", derived="closed") for i in range(1, 2501)]
            return SimpleNamespace(fetchall=lambda: rows)

        def commit(self):
            calls.append(("COMMIT", None))

    moves = ted_status.refresh(_Db(), apply=True, chunk=1000)
    assert moves[("open", "closed")] == 2500
    updates = [p for s, p in calls if s.startswith("UPDATE tenders")]
    assert [len(p["ids"]) for p in updates] == [1000, 1000, 500]
    assert sum(1 for s, _ in calls if s == "COMMIT") == 3
    assert all("status IS DISTINCT FROM" in s for s, _ in calls if s.startswith("UPDATE tenders"))


def test_a_dry_run_writes_nothing():
    calls = []

    class _Db:
        def execute(self, stmt, params=None):
            calls.append(str(stmt))
            return SimpleNamespace(fetchall=lambda: [SimpleNamespace(id=1, status="open", derived="closed")])

        def commit(self): calls.append("COMMIT")

    assert ted_status.refresh(_Db(), apply=False)[("open", "closed")] == 1
    assert not any(c.startswith("UPDATE") or c == "COMMIT" for c in calls)


class _RecordingQuery(Query):
    seen: list = []

    def count(self):
        _RecordingQuery.seen.append(str(self.statement.compile(dialect=postgresql.dialect()))); return 0

    def all(self):
        _RecordingQuery.seen.append(str(self.statement.compile(dialect=postgresql.dialect()))); return []


def test_the_tenders_list_does_not_read_the_stored_xml():
    from api.v2.funding import router
    _RecordingQuery.seen = []
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *e: _RecordingQuery(list(e)))
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    r = TestClient(app).get("/api/v2/funding/tenders", params={"limit": 5})
    assert r.status_code == 200, r.text
    page_sql = _RecordingQuery.seen[-1]
    select_list = page_sql.split(" FROM ", 1)[0]
    for column in ("xml_content", "raw_json", "sme_analysis", "lots"):
        assert f"tenders.{column}" not in select_list, column
    assert "tenders.status" in select_list and "tenders.description" in select_list
