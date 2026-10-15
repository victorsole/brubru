"""Every consultation carries its publication date and its feedback period, and nothing
erases them (15 Oct 2026).

GovClipping found 2,488 consultations whose only date was the day Brubru stored them.
The 2 Oct backfill had dated them, writing the initiative's first publication into
start_date; the nightly Have Your Say sync owns start_date (the current feedback period)
and erased 2,474 of those dates on 3 Oct. The date now has its own column, published_date,
with one writer. /consultations/all also served the closing date as document_date, capped
the register at 4,000 of 4,892 rows, matched nothing for the Commission and carried no
updated_date. GovClipping then set the contract: publication date, the day feedback opens,
the day it closes, on every consultation."""
from __future__ import annotations

import asyncio
import inspect
import pathlib
import sys
import uuid
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

from models.public_consultation import PublicConsultation

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _call(fn, **given):
    kwargs = {name: given.get(name) for name in inspect.signature(fn).parameters}
    kwargs.update(given)
    out = fn(**kwargs)
    return asyncio.run(out) if inspect.iscoroutine(out) else out


def _consultation(**kw):
    row = PublicConsultation(
        id=uuid.uuid4(), initiative_id="1859", title="Evaluation of the EU agricultural promotion policy",
        consultation_type="initiative", status="closed", policy_areas=[], com_references=[],
        celex_numbers=[], feedback_count=0, start_date=None, end_date=None, published_date=date(2017, 5, 8),
        feedback_start_date=date(2020, 5, 8), feedback_end_date=date(2020, 9, 11),
        portal_url="https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/1859-x_en",
        first_seen=datetime(2026, 8, 11, 4, 2), last_updated=datetime(2026, 10, 15, 11, 0))
    for k, v in kw.items():
        setattr(row, k, v)
    return row


class _Rows:
    """Builds and compiles the real query; answers with the rows given."""

    def __init__(self, q, rows, sql):
        self.q, self.rows, self.sql = q, rows, sql

    def __getattr__(self, name):
        attr = getattr(self.q, name)
        if name in ("filter", "order_by", "offset", "limit", "filter_by"):
            return lambda *a, **k: _Rows(attr(*a, **k), self.rows, self.sql)
        return attr

    def _compile(self):
        self.sql.append(str(self.q.statement.compile(dialect=postgresql.dialect())))

    def count(self):
        self._compile()
        return len(self.rows)

    def all(self):
        self._compile()
        return self.rows

    def first(self):
        self._compile()
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self, rows):
        self.rows, self.sql = rows, []

    def query(self, *models):
        return _Rows(Query(models), self.rows, self.sql)


@pytest.mark.parametrize("module_path", ["api.v1.consultations", "api.v2.commission.consultations"])
def test_every_consultation_carries_publication_and_feedback_dates(module_path):
    import importlib
    fn = importlib.import_module(module_path).list_consultations
    closed = _consultation()
    open_now = _consultation(start_date=date(2026, 9, 9), end_date=date(2026, 11, 4))
    agency = _consultation(published_date=None, feedback_start_date=None, feedback_end_date=None,
                           start_date=date(2026, 7, 1), end_date=date(2026, 9, 30), source_body="EBA")
    db = _DB([closed, open_now, agency])
    env = _call(fn, db=db, limit=50, page=1, published_from=date(2017, 1, 1))
    c, o, a = env.data
    # A closed initiative: first publication, and the last period that took feedback.
    assert (c.document_date, c.start_date, c.end_date) == (date(2017, 5, 8), date(2020, 5, 8), date(2020, 9, 11))
    # Open for feedback: the current period, never its start with the old period's end.
    assert (o.document_date, o.start_date, o.end_date) == (date(2017, 5, 8), date(2026, 9, 9), date(2026, 11, 4))
    # An agency consultation has no separate publication: the day it opened.
    assert (a.document_date, a.start_date, a.end_date) == (date(2026, 7, 1), date(2026, 7, 1), date(2026, 9, 30))
    # Never the day Brubru stored it.
    assert c.document_date != c.creation_date.date()
    # The filter and the order use the value served.
    assert "coalesce(public_consultations.published_date, public_consultations.start_date) >=" in db.sql[0]


def test_only_the_dates_job_writes_published_date():
    sync = (BACKEND / "scripts" / "sync_have_your_say.py").read_text(encoding="utf-8")
    assert "published_date" not in sync
    from scripts import backfill_consultation_dates as job
    store = str(job.STORE)
    assert "SET published_date = :p, feedback_start_date = :fs, feedback_end_date = :fe" in store
    # The sync's columns are never written by this job.
    assert " start_date" not in store.replace("feedback_start_date", "") and \
        " end_date" not in store.replace("feedback_end_date", "")


def test_a_night_with_only_unpublished_initiatives_is_not_a_failure(monkeypatch, capsys):
    """331 upcoming initiatives have no publication yet and are asked every night: a run
    that stores nothing because none is published yet must exit 0, or the cron goes red."""
    from scripts import backfill_consultation_dates as job

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=None):
            if "SELECT id, portal_url" in str(sql):
                return [SimpleNamespace(id=1, portal_url="https://x/initiatives/19479-y_en")]
            return SimpleNamespace(scalar_one=lambda: 331)

    eng = SimpleNamespace(connect=_Conn, begin=_Conn, dispose=lambda: None)
    monkeypatch.setattr(job, "create_engine", lambda *a, **k: eng)
    monkeypatch.setattr(job, "_db", lambda: "postgresql://x")
    monkeypatch.setattr(job, "_dates", lambda iid, ctx: None)
    monkeypatch.setattr(sys, "argv", ["x", "--apply", "--pause", "0"])
    assert job.main() == 0
    # ...but a night the API never answered is a failure.
    monkeypatch.setattr(job, "_dates", lambda iid, ctx: "http_503")
    assert job.main() == 1


# --------------------------------------------------------------------------- /consultations/all
class _Result(list):
    def fetchall(self):
        return list(self)

    def fetchone(self):
        return self[0] if self else None


class _AllDB:
    """Answers the route's raw SQL: the register rows, no economy rows, no body names."""

    def __init__(self, rows):
        self.rows, self.sql = rows, []

    def execute(self, sql, params=None):
        s = str(sql)
        self.sql.append((s, params or {}))
        if "FROM public_consultations WHERE" in s and "SELECT DISTINCT" not in s:
            return _Result(self.rows)
        if "SELECT DISTINCT" in s:
            return _Result([("commission",)])
        return _Result([])


def _hys_row(**kw):
    base = dict(id=uuid.uuid4(), title="Evaluation of the EU agricultural promotion policy", short_title=None,
                description="d", consultation_type="initiative", status="closed", dg_responsible="AGRI",
                policy_areas=None, start_date=None, published_date=date(2017, 5, 8), end_date=None,
                feedback_start_date=date(2020, 5, 8), feedback_end_date=date(2020, 9, 11),
                first_seen=datetime(2026, 8, 11, 4, 2), last_updated=datetime(2026, 10, 15, 11, 0),
                portal_url="https://ec.europa.eu/x", feedback_url=None, feedback_count=0,
                source_body="European Commission")
    base.update(kw)
    return SimpleNamespace(**base)


def test_all_serves_the_publication_date_and_the_feedback_period_apart():
    from api.v2.consultations import consultations_all as m
    db = _AllDB([_hys_row()])
    env = _call(m.consultations_all, request=None, db=db, user=None, order="recent", page=1, limit=20,
                include_body=False)
    it = env.data[0]
    assert it.document_date.date() == date(2017, 5, 8)
    assert (it.start_date.date(), it.end_date.date()) == (date(2020, 5, 8), date(2020, 9, 11))
    assert it.updated_date == datetime(2026, 10, 15, 11, 0)
    assert it.body_code == "commission" and it.institution == "European Commission"


def test_all_reads_the_whole_register_and_finds_the_commission():
    from api.v2.consultations import consultations_all as m
    db = _AllDB([_hys_row()])
    _call(m.consultations_all, request=None, db=db, user=None, institution="European Commission",
          order="recent", page=1, limit=20, include_body=False)
    register = [s for s, _ in db.sql if "FROM public_consultations WHERE" in s and "DISTINCT" not in s][0]
    assert "LIMIT" not in register
    assert "lower(source_body) = 'european commission' THEN 'commission'" in register
    assert register.rstrip().endswith("= 'commission'")
    db = _AllDB([_hys_row()])
    _call(m.consultations_all, request=None, db=db, user=None, body="commission",
          order="recent", page=1, limit=20, include_body=False)
    register, params = [(s, p) for s, p in db.sql if "FROM public_consultations WHERE" in s and "DISTINCT" not in s][0]
    assert "= ANY(:codes)" in register and params["codes"] == ["commission"]
