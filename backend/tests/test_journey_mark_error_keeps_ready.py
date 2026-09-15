"""A failed journey RE-run must not hide a good analysis (E1, 15 Sep 2026).

The cron regenerates a dossier's journey analysis whenever its doc set changes.
When the AI call then failed, `_mark_error` did
`ON CONFLICT DO UPDATE SET status='error', generated_at=NOW()` unconditionally,
so a ready analysis with its comparison and summary intact flipped to 'error',
which the UI renders as "no analysis". Three dossiers were hidden that way.

The statement runs here against SQLite (which supports the same
`ON CONFLICT ... DO UPDATE ... WHERE` upsert) with a NOW() shim, so the test
exercises the real SQL text rather than a reimplementation of it.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from services.analysis import legislative_journey_service as svc  # noqa: E402

OLD_TS = "2026-09-01 10:00:00"
REF = "2025/0207(COD)"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _now_shim(dbapi_conn, _):
        dbapi_conn.create_function("NOW", 0, lambda: "2026-09-15 01:05:56")

    with engine.begin() as c:
        c.execute(text(
            """
            CREATE TABLE file_journey_analyses (
                procedure_ref TEXT NOT NULL UNIQUE,
                carriage_id TEXT,
                doc_set_hash TEXT NOT NULL,
                comparison TEXT NOT NULL DEFAULT '{}',
                summary TEXT,
                status TEXT NOT NULL DEFAULT 'ready',
                generated_at TEXT NOT NULL DEFAULT '2000-01-01'
            )
            """
        ))
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _row(db):
    return db.execute(text(
        "SELECT status, generated_at, doc_set_hash, summary, comparison "
        "FROM file_journey_analyses WHERE procedure_ref = :p"), {"p": REF}).mappings().first()


def _seed(db, status):
    db.execute(text(
        "INSERT INTO file_journey_analyses (procedure_ref, doc_set_hash, comparison, summary, status, generated_at) "
        "VALUES (:p, 'oldhash', '{\"overview\": \"x\"}', 'A good summary', :st, :ts)"),
        {"p": REF, "st": status, "ts": OLD_TS})
    db.commit()


CARRIAGE = SimpleNamespace(id="c-1")


def test_failed_rerun_keeps_a_ready_analysis_ready(db):
    _seed(db, "ready")
    svc._mark_error(db, REF, CARRIAGE)
    r = _row(db)
    assert r["status"] == "ready"
    assert r["generated_at"] == OLD_TS, "a kept ready row must not look freshly generated"
    assert r["summary"] == "A good summary"
    assert r["doc_set_hash"] == "oldhash", "old hash keeps it stale so the next run retries"


def test_failure_with_no_prior_row_inserts_error(db):
    svc._mark_error(db, REF, CARRIAGE)
    assert _row(db)["status"] == "error"


def test_failure_on_an_error_row_stays_error_and_moves_generated_at(db):
    _seed(db, "error")
    svc._mark_error(db, REF, CARRIAGE)
    r = _row(db)
    assert r["status"] == "error"
    assert r["generated_at"] != OLD_TS


def test_generate_journey_logs_why_it_failed(db, monkeypatch, caplog):
    _seed(db, "ready")
    monkeypatch.setattr(svc, "resolve_doc_set", lambda _db, _ref: [
        {"key": "draft_report", "label": "Draft report", "pdf_url": "u"}])
    monkeypatch.setattr(svc, "get_pdf_text", lambda _db, _u: {"text": "t", "char_count": 1})

    async def _fail(*_a, **_k):
        return None, None, None, TimeoutError("provider timed out")

    monkeypatch.setattr(svc, "_call_llm", _fail)
    import asyncio
    carriage = SimpleNamespace(id="c-1", oeil_procedure_ref=REF)
    with caplog.at_level(logging.WARNING, logger=svc.logger.name):
        assert asyncio.run(svc.generate_journey(db, carriage)) is None
    msgs = [rec.getMessage() for rec in caplog.records]
    assert any(REF in m and "TimeoutError" in m and "provider timed out" in m for m in msgs), msgs
    assert _row(db)["status"] == "ready"
