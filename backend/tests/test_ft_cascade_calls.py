"""Calls for funding in cascade get their own table, loader and list (23 Oct 2026).

The portal files each cascade call (issued by an EU-funded project, SEDIA type 8) under the
identifier of the topic that funds it; Brubru kept one row per identifier, so topic and cascade
calls merged (111 topic rows carried a cascade call's dates, none held as itself; 1,420 calls in
the census). Each call has its own number, `callccm2Id`, which is also the id of the portal's page
for it; the record's `ccm2Id` and `url` belong to the topic. The fixture is the portal's real record
for "Cultural Horizons: Artistic Mobility" (16842), read 23 Oct 2026.
"""
import copy
import datetime as dt
import importlib
import json
import pathlib
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402

cascade = importlib.import_module("ingest_ft_cascade_calls")
sedia = importlib.import_module("ingest_funding_sedia")
RECORD = json.loads((BACKEND / "tests" / "fixtures" / "ft" / "sedia_cascade_call_16842.json").read_text(encoding="utf-8"))
TODAY = dt.date(2026, 10, 23)


def test_a_record_becomes_its_own_call_with_its_own_page(monkeypatch):
    monkeypatch.setitem(sedia._PROGRAMME_LABELS, "43251814", "Creative Europe Programme (CREA)")
    row = cascade.normalise(RECORD, today=TODAY)
    assert row["call_id"] == "16842" and row["title"] == "Cultural Horizons: Artistic Mobility"
    assert row["topic_id"] == "CREA-CULT-2025-COOP-UA-2"
    assert row["topic_title"] == "Fostering Ukrainians’ access to culture and cultural heritage"
    assert (row["project_id"], row["project_acronym"]) == ("101237681", "Cultural Horizons")
    assert row["source_url"].endswith("/competitive-calls-cs/16842")          # not the topic's 47365875
    assert row["status"] == "forthcoming"                                      # opens 26 Oct
    assert row["published_at"].date() == dt.date(2026, 10, 26)
    assert row["deadline"].date() == dt.date(2026, 12, 28)
    assert row["indicative_budget"] == 220000.0 and row["deadline_model"] == "single-stage"
    assert row["framework_programme"] == "Creative Europe Programme (CREA)"
    text = row["description"]
    assert text.index("Task description") < text.index("Submission & evaluation process") < text.index("Further information")
    assert "<h2>Further information</h2>" in row["description_html"] and "ucf.in.ua" in row["description_html"]


def test_a_call_indexed_twice_keeps_the_record_read_last():
    older, newer = copy.deepcopy(RECORD), copy.deepcopy(RECORD)
    older["metadata"]["esDA_IngestDate"] = ["2026-09-01T10:00:00.000+0200"]
    older["metadata"]["budget"] = ["1"]
    rows, seen = cascade.collect([(1, [newer, older])])
    assert seen == 2 and list(rows) == ["16842"] and rows["16842"]["indicative_budget"] == 220000.0


def test_a_failed_page_and_an_empty_index_fail_the_run(monkeypatch):
    with pytest.raises(RuntimeError):
        cascade.collect([(1, None)])
    monkeypatch.setattr(cascade, "load_programme_labels", lambda: 0)
    monkeypatch.setattr(cascade, "iter_structured", lambda q, **kw: iter([(1, [])]))
    assert cascade.main([]) == 1


def test_a_dry_run_reads_every_cascade_record(monkeypatch, tmp_path):
    asked = []
    monkeypatch.setattr(cascade, "load_programme_labels", lambda: 0)

    def fake_iter(query, **kw):
        asked.append(query["bool"]["must"][0]["terms"]["type"])
        yield 1, [RECORD]

    monkeypatch.setattr(cascade, "iter_structured", fake_iter)
    dump = tmp_path / "rows.json"
    assert cascade.main(["--dump-json", str(dump)]) == 0
    assert asked == [["8"]] and "16842" in json.loads(dump.read_text())


def test_the_topic_jobs_no_longer_take_cascade_records(monkeypatch, tmp_path):
    monkeypatch.setattr(sedia, "load_programme_labels", lambda: 0)
    asked = []

    def fake_iter(query, **kw):
        asked.append(query["bool"]["must"][0]["terms"]["type"])
        yield 1, [RECORD]

    monkeypatch.setattr(sedia, "iter_structured", fake_iter)
    monkeypatch.setenv("DATABASE_URL", "postgresql://not-used/when-not-applying")
    dump = tmp_path / "rows.json"
    monkeypatch.setattr(sys, "argv", ["ingest_funding_sedia.py", "--skip-refresh", "--dump-json", str(dump)])
    with pytest.raises(SystemExit) as stopped:      # nothing collected: the only record was a cascade call
        sedia.main()
    assert stopped.value.code == 2
    assert all("8" not in types for types in asked)
    assert "CREA-CULT-2025-COOP-UA-2" not in json.loads(dump.read_text())   # no topic row from a cascade record

    programme = importlib.import_module("ingest_ft_programme_calls")
    topic = copy.deepcopy(RECORD)
    topic["metadata"].update({"type": ["1"], "identifier": ["JUST-2025-JCOO"], "title": ["Judicial cooperation"]})
    casc = copy.deepcopy(RECORD)
    casc["metadata"]["identifier"] = ["JUST-2025-JCOO-CASCADE"]
    monkeypatch.setattr(programme, "fetch_sedia_page", lambda page, **kw: {"results": [topic, casc]} if page == 1 else None)
    written = programme.ingest_programme(SimpleNamespace(execute=lambda *a, **k: None), "justice", apply=True)
    assert written == 1


class _Rows:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def all(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None
    def scalar(self): return len(self.rows)


ROW = {"id": 1, "call_id": "16842", "title": "Cultural Horizons: Artistic Mobility", "topic_id": "CREA-CULT-2025-COOP-UA-2",
       "topic_title": None, "project_id": "101237681", "project_acronym": "Cultural Horizons", "project_name": None,
       "framework_programme": "Creative Europe Programme (CREA)", "status": "forthcoming", "deadline_model": "single-stage",
       "deadline": dt.datetime(2026, 12, 28, 17, tzinfo=dt.timezone.utc), "deadline_secondary": None, "duration": None,
       "indicative_budget": 220000.0, "budget_currency": "EUR",
       "public_url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/competitive-calls-cs/16842",
       "document_date": dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc), "creation_date": dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc),
       "updated_date": dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc), "body_txt": "Task description\n...", "body_html": "<h2>Task description</h2>"}


def _client(rows):
    from api.v2.funding import router
    seen = []

    class _Db:
        def execute(self, stmt, params=None):
            seen.append((str(stmt), dict(params or {})))
            return _Rows(rows)

    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: _Db()
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app), seen


def test_the_list_serves_full_text_by_default_and_filters_as_the_standard_says():
    client, seen = _client([ROW])
    r = client.get("/api/v2/funding/ft-cascade-calls",
                   params={"status": "open,forthcoming", "programme": "Creative", "updated_from": "2026-10-22", "order": "updated_asc"})
    assert r.status_code == 200, r.text
    item = r.json()["data"][0]
    assert item["item_type"] == "cascade_call" and item["body_txt"].startswith("Task description")
    assert item["public_url"].endswith("/competitive-calls-cs/16842") and item["document_date"].startswith("2026-10-26")
    count_sql, page_sql = seen[0][0], seen[1][0]
    for sql in (count_sql, page_sql):
        assert "status = ANY(:st)" in sql and "last_updated >= :updated_from" in sql
    assert "description AS body_txt" in page_sql and "ORDER BY last_updated ASC, id ASC" in page_sql
    assert seen[1][1]["st"] == ["open", "forthcoming"] and r.json()["limit"] == 50


def test_the_item_route_and_a_missing_id():
    client, _ = _client([ROW])
    assert client.get("/api/v2/funding/ft-cascade-calls/1").json()["call_id"] == "16842"
    client, _ = _client([])
    r = client.get("/api/v2/funding/ft-cascade-calls/999999")
    assert r.status_code == 404 and r.json()["detail"]["reason_code"] == "not_found"
