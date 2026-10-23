"""Funded projects serve one status vocabulary; the source's word is kept beside it (23 Oct 2026).

The CORDIS loader wrote closed / signed / terminated, the F&T Portal loader Ended / Ongoing /
Forthcoming / Suspended, into the same field, and neither was revisited: of 22,735 "signed",
8,511 had ended; 1,695 "Ongoing" had ended; 232 "Forthcoming" had started. The filter lowered the
value, so the F&T words could not be matched at all. Rule: services/funding/project_status.py.
"""
import importlib
import pathlib
import re
import sys
import uuid
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
from services.funding import project_status as ps  # noqa: E402


def test_source_facts_come_before_the_dates_and_the_dates_before_the_words():
    sql = " ".join(ps.STATUS_SQL.split())
    order = ["= 'terminated' THEN 'terminated'", "= 'suspended' THEN 'suspended'",
             "IN ('closed', 'ended') THEN 'ended'",
             "start_date > CURRENT_DATE THEN 'planned'", "end_date < CURRENT_DATE THEN 'ended'",
             "start_date IS NOT NULL THEN 'ongoing'",
             "= 'forthcoming' THEN 'planned'", "IN ('signed', 'ongoing') THEN 'ongoing'", "ELSE 'unknown'"]
    positions = [sql.index(clause) for clause in order]
    assert positions == sorted(positions)
    assert set(ps.VOCABULARY) == {"planned", "ongoing", "ended", "terminated", "suspended", "unknown"}


def test_refresh_casts_the_uuid_keys_and_works_in_chunks():
    calls = []
    keys = [uuid.uuid4() for _ in range(4500)]

    class _Db:
        def execute(self, stmt, params=None):
            calls.append((str(stmt), params))
            return SimpleNamespace(fetchall=lambda: [SimpleNamespace(id=k, status="signed", derived="ongoing") for k in keys])

        def commit(self): calls.append(("COMMIT", None))

    moves = ps.refresh(_Db(), apply=True)
    assert moves[("signed", "ongoing")] == 4500
    updates = [(s, p) for s, p in calls if s.startswith("UPDATE ft_funded_projects")]
    assert [len(p["ids"]) for _, p in updates] == [2000, 2000, 500]
    assert all("CAST(:ids AS uuid[])" in s and isinstance(p["ids"][0], str) for s, p in updates)


class _RecordingQuery(Query):
    seen: list = []

    def count(self):
        _RecordingQuery.seen.append(str(self.statement.compile(dialect=postgresql.dialect()))); return 0

    def all(self):
        _RecordingQuery.seen.append(str(self.statement.compile(dialect=postgresql.dialect()))); return []


def _sql_for(status):
    from api.v2.funding import router
    _RecordingQuery.seen = []
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *e: _RecordingQuery(list(e)))
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    r = TestClient(app).get("/api/v2/funding/ft-funded-projects", params={"status": status})
    assert r.status_code == 200, r.text
    return _RecordingQuery.seen[0]


def test_the_list_filters_the_new_vocabulary_and_still_takes_the_source_words():
    assert "ft_funded_projects.status = " in _sql_for("Ongoing")      # a vocabulary word, any case
    for word in ("signed", "Forthcoming", "closed"):                  # the sources' own words
        old = _sql_for(word)
        assert "lower(ft_funded_projects.source_status) = " in old and "ft_funded_projects.status = " not in old


def test_the_loaders_keep_the_source_word_and_leave_the_served_status_to_the_rule():
    cordis = importlib.import_module("ingest_cordis_projects")
    nonh = importlib.import_module("ingest_ft_projects_nonh2020")
    for sql in (cordis._UPSERT_SQL, nonh.UPSERT):
        conflict = " ".join(sql.split("ON CONFLICT", 1)[1].split())
        assert re.search(r"\bsource_status\s*=\s*EXCLUDED\.source_status\b", conflict)
        assert not re.search(r"\bstatus\s*=\s*EXCLUDED\.status\b", conflict)   # \b skips source_status
        assert "COALESCE(EXCLUDED.end_date, ft_funded_projects.end_date)" in conflict
        insert = sql.split("ON CONFLICT", 1)[0]
        assert "source_status" in insert


def test_the_migration_keeps_the_change_signal_still_while_copying():
    sql = (BACKEND / "migrations" / "311_funded_projects_source_status.sql").read_text()
    assert "brubru_touch_if_changed('last_updated', 'scraped_at,source_status', '')" in sql
    assert sql.index("CREATE TRIGGER") < sql.index("UPDATE ft_funded_projects SET source_status = status")
