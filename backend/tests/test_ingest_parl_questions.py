"""EP parliamentary questions come from EP Open Data, and an empty source is a failure.

Until 25 Sep 2026 the job scraped a WAF-walled HTML page, parsed nothing and
exited 0 every day, so the newest stored question stayed at 24 April.
Fixtures are real EP Open Data records.
"""
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "ingest_parl_questions", HERE.parent / "scripts" / "ingest_parl_questions.py")
pq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pq)
ITEMS = json.loads((HERE / "fixtures" / "ep_parl_questions_2026_09_25.json").read_text())


def test_reference_matches_stored_form():
    assert pq.reference("E-10-2026-001683") == "E-001683/2026"
    assert pq.reference("P-10-2026-003747") == "P-003747/2026"


def test_priority_question_row():
    row = pq.to_row(ITEMS["P-10-2026-003747"], {"197818": "Some MEP"})
    assert row["question_reference"] == "P-003747/2026"
    assert row["question_type"] == "priority"
    assert row["submitted_date"] == "2026-09-17"
    assert row["asking_mep_ids"] == ["197818"] and row["asking_mep_names"] == ["Some MEP"]
    assert row["source_url"].endswith("/P-10-2026-003747_EN.html")
    assert row["subject"].startswith("Irish citizens")


def test_oral_question_keeps_only_person_authors():
    row = pq.to_row(ITEMS["O-10-2026-000030"], {})
    assert row["question_type"] == "oral"
    assert all(i.isdigit() for i in row["asking_mep_ids"])   # "org/PPE" is not an author id


def test_answered_question_carries_answer_date_and_url():
    row = pq.to_row(ITEMS["E-10-2026-000002"], {})
    assert row["answered_date"] == "2026-02-20"
    assert row["answer_url"].endswith("/E-10-2026-000002-ASW_EN.html")


class _Resp:
    def __init__(self, status, body, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.text = json.dumps(body)

    def json(self):
        return self._body


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, url, params=None):
        return self.responses.pop(0)


def test_200_without_data_is_retried_not_read_as_empty(monkeypatch):
    monkeypatch.setattr(pq.time, "sleep", lambda s: None)
    busy = _Resp(200, {"error": "Pending acquire queue has reached its maximum size"})
    ok = _Resp(200, {"data": [{"identifier": "E-10-2026-000001"}]})
    end = _Resp(200, {"data": []})
    assert pq.list_ids(_Client([busy, ok, end]), 2026, deadline=float("inf")) == ["E-10-2026-000001"]


def test_persistent_failure_raises(monkeypatch):
    monkeypatch.setattr(pq.time, "sleep", lambda s: None)
    busy = _Resp(200, {"error": "pool exhausted"})
    with pytest.raises(RuntimeError):
        pq.list_ids(_Client([busy] * 4), 2026, deadline=float("inf"))


def test_short_page_is_not_the_end(monkeypatch):
    monkeypatch.setattr(pq.time, "sleep", lambda s: None)
    short = _Resp(200, {"data": [{"identifier": f"E-10-2026-{i:06d}"} for i in range(300)]})
    more = _Resp(200, {"data": [{"identifier": "E-10-2026-000900"}]})
    empty = _Resp(200, {"data": []})
    ids = pq.list_ids(_Client([short, more, empty]), 2026, deadline=float("inf"))
    assert len(ids) == 301


def test_204_ends_the_list(monkeypatch):
    monkeypatch.setattr(pq.time, "sleep", lambda s: None)
    page = _Resp(200, {"data": [{"identifier": "E-10-2026-000001"}]})
    assert pq.list_ids(_Client([page, _Resp(204, {})]), 2026, deadline=float("inf")) == ["E-10-2026-000001"]
