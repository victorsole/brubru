"""Solidarity Fund cases are dated by the Commission's publication of the dataset (23 Oct 2026).

document_date held each disaster's first-damage date: not a publication date, and unreliable at
the source (13 of 197 cases dated after their own application, day and month swapped: Storm
Gudrun 2005, Lorca 2011, Lesbos 2017). The source gives no per-case publication date, so each
case now carries the dataset's last publication (the platform's rowsUpdatedAt), and the damage
date is no longer served (Victor).
"""
import importlib
import io
import json
import pathlib
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

eusf = importlib.import_module("backfill_eusf")
PUBLISHED = datetime(2025, 12, 3, 15, 22, 27, tzinfo=timezone.utc)
CASES = [{"cci_number": "2017GR16SPO001", "name_of_disaster": "Lesbos earthquake 2017", "applicant_country": "EL",
          "year_of_occurance": "2017", "first_damage_date": "2017-12-06T00:00:00.000",
          "date_of_initial_application": "2017-09-01T00:00:00.000", "paid": "2"}]


class _Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Cur:
    def __init__(self): self.sql, self.last = [], None
    def execute(self, sql, params=None):
        self.sql.append((sql, params)); self.last = sql
    def fetchone(self):
        return (True,) if "INSERT INTO" in (self.last or "") else (len(CASES),)
    def fetchall(self): return [(f"{c['cci_number']}|{c['name_of_disaster']}",) for c in CASES]


class _ChunkedDb:
    last = None
    def __init__(self): self.cur, self.conn = _Cur(), SimpleNamespace(rollback=lambda: None)
    def execute(self, sql, params=None): self.cur.execute(sql, params)
    def commit(self): _ChunkedDb.last = self
    def close(self): pass


def _run(monkeypatch, stamp):
    def urlopen(req, timeout=None):
        if isinstance(stamp, Exception):
            raise stamp
        return _Response(json.dumps({"rowsUpdatedAt": stamp}).encode())
    monkeypatch.setattr(eusf.ureq, "urlopen", urlopen)
    monkeypatch.setattr(eusf, "fetch", lambda: CASES)
    monkeypatch.setattr(eusf, "ChunkedDb", _ChunkedDb)
    monkeypatch.setattr(sys, "argv", ["backfill_eusf.py", "--apply"])
    eusf.main()
    return next((sql, p) for sql, p in _ChunkedDb.last.cur.sql if "INSERT INTO eu_solidarity_fund" in sql)


def test_every_case_carries_the_datasets_publication(monkeypatch):
    sql, params = _run(monkeypatch, int(PUBLISHED.timestamp()))
    assert params["docdate"] == PUBLISHED                   # not 2017-12-06, the swapped damage date
    assert "coalesce(EXCLUDED.document_date, eu_solidarity_fund.document_date)" in sql
    assert "eu_solidarity_fund.document_date)" in sql.split("IS DISTINCT FROM")[0]   # a new date updates the row


def test_an_unreadable_record_keeps_the_held_date_and_says_so(monkeypatch, capsys):
    _, params = _run(monkeypatch, OSError("timed out"))
    assert params["docdate"] is None                        # coalesce keeps what the row holds
    assert "[SYNC_STATUS] degraded: EUSF dataset publication date unreadable" in capsys.readouterr().out


def test_the_route_serves_no_damage_date():
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    from api.v2.funding import cohesion_eusf as ce
    seen = []

    class _Rows:
        def __init__(self, row): self.row = row
        def mappings(self): return self
        def all(self): return [self.row]
        def fetchall(self): return [self.row]
        def first(self): return self.row
        def scalar(self): return 1

    row = {"id": 7, "year_of_occurrence": 2017, "cci_number": "2017GR16SPO001", "applicant_country": "EL",
           "name_of_disaster": "Lesbos earthquake 2017", "disaster_type": "Earthquake", "status": "Accepted",
           "category": "Regional", "total_direct_damage_meur": 1.0, "eligible_emergency_cost_meur": None,
           "damage_pct": None, "eusf_grant_paid_meur": 2.0, "public_url": eusf.PUBLIC_URL,
           "document_date": PUBLISHED, "creation_date": PUBLISHED, "updated_date": PUBLISHED}

    class _Db:
        def execute(self, stmt, params=None):
            seen.append(str(stmt)); return _Rows(row)

    app = FastAPI()
    app.include_router(ce.router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: _Db()
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    r = TestClient(app).get("/api/v2/funding/eusf")
    assert r.status_code == 200, r.text
    item = r.json()["data"][0]
    assert "first_damage_date" not in item and item["document_date"].startswith("2025-12-03T15:22:27")
    assert not any("first_damage_date" in sql for sql in seen)
