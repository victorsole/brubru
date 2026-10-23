"""funding_opportunities is retired; everything reads ft_calls_for_proposals (23 Oct 2026, Victor).

It was a second copy of the same 2,836 calls, written by the same ingester in the same step, that
the later repairs never reached (1,089 shorter descriptions, 4 deadlines, 27 programmes), plus 208
calls for tenders filed as calls, 15 of them still open or forthcoming. The chat and the MCP
search_funding tool read it. The chat block also failed on every question naming a programme: it
rewrote "programme" inside "framework_programme" and asked for framework_framework_programme.
"""
import asyncio
import pathlib
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402


class _RecordingQuery(Query):
    seen: list = []

    def _sql(self):
        return str(self.statement.compile(dialect=postgresql.dialect()))

    def count(self):
        _RecordingQuery.seen.append(self._sql()); return 0

    def all(self):
        _RecordingQuery.seen.append(self._sql()); return []


def test_the_route_reads_the_calls_table_and_is_marked_deprecated():
    from api.v2.funding import router
    _RecordingQuery.seen = []
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *e: _RecordingQuery(list(e)))
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    r = TestClient(app).get("/api/v2/funding/funding-opportunities", params={"programme": "Horizon", "q": "soil"})
    assert r.status_code == 200, r.text
    count_sql = _RecordingQuery.seen[0]
    assert "FROM ft_calls_for_proposals" in count_sql and "funding_opportunities" not in count_sql
    assert "ft_calls_for_proposals.framework_programme ILIKE" in count_sql
    assert "ft_calls_for_proposals.description ILIKE" in count_sql
    assert app.openapi()["paths"]["/api/v2/funding/funding-opportunities"]["get"]["deprecated"] is True


def test_an_item_keeps_the_funding_item_shape():
    from api.v1 import infringements_funding as inf
    row = SimpleNamespace(id="5f0c", topic_id="HORIZON-CL6-2026-01-01", call_id="HORIZON-CL6-2026-01",
                          framework_programme="Horizon Europe (HORIZON)", title="Soil health",
                          description="First paragraph.\n\nSecond paragraph.", status="open",
                          type_of_action="RIA", deadline=None, deadline_secondary=None, indicative_budget=None,
                          budget_currency="EUR", source_url="https://ec.europa.eu/x", documents_url=None,
                          keywords=[], target_audience=[], published_at=None, content_updated_at=None,
                          first_seen_at=None)
    item = inf._funding_to_item(row)
    assert item.programme == "Horizon Europe (HORIZON)" and item.short_summary == "First paragraph."


def test_the_ingester_writes_calls_into_one_table_only():
    sedia = __import__("ingest_funding_sedia")
    seen = []
    cur = SimpleNamespace(execute=lambda sql, params=None: seen.append(sql))
    row = {"topic_id": "HORIZON-CL6-2026-01-01", "record_type": "1", "is_tender": False, "call_id": None,
           "programme": "Horizon Europe (HORIZON)", "title": "Soil health", "short_summary": "", "description": "",
           "status": "open", "type_of_action": None, "deadline": None, "deadline_secondary": None,
           "indicative_budget": None, "budget_currency": "EUR", "source_url": "https://ec.europa.eu/x",
           "documents_url": None, "keywords": [], "target_audience": None, "published_at": None}
    sedia._write(cur, row, write_ft=False)
    writes = [s for s in seen if "INSERT INTO" in s]
    assert len(writes) == 1 and "INSERT INTO ft_calls_for_proposals" in writes[0]
    assert not hasattr(sedia, "upsert")


class _Exec:
    def __init__(self): self.sql = []

    def execute(self, stmt, params=None):
        self.sql.append(str(stmt))
        return SimpleNamespace(fetchall=lambda: [], mappings=lambda: SimpleNamespace(all=lambda: []))

    def close(self): pass


def test_the_mcp_search_reads_the_calls_table(monkeypatch):
    from services.mcp import tools
    db = _Exec()
    monkeypatch.setattr(tools, "_get_db", lambda: db)
    tools._handle_search_funding("soil health")
    assert db.sql and all("FROM ft_calls_for_proposals" in s for s in db.sql)
    assert "description ILIKE" in db.sql[0] and "framework_programme ILIKE" in db.sql[0]


def test_the_chat_block_names_a_real_column_when_a_programme_is_asked(monkeypatch):
    from services.ai import context_builder as cb
    db = _Exec()
    monkeypatch.setattr(cb, "SessionLocal", lambda: db)
    builder = cb.ContextBuilder.__new__(cb.ContextBuilder)
    builder._FUNDING_STOP = set()
    asyncio.run(builder._fetch_funding_block("soil calls in Horizon Europe", {"programme": "Horizon", "keyword": "soil"}))
    assert len(db.sql) == 1
    assert "FROM ft_calls_for_proposals" in db.sql[0] and "framework_programme ILIKE :prog" in db.sql[0]
    assert "framework_framework" not in db.sql[0] and "funding_opportunities" not in db.sql[0]
