"""EAGF and EAFRD payments carry the day the Commission states their figures as of (23 Oct 2026).

Every one of the 56 rows served document_date null. The rows carry no date, but each refresh of
the source writes one into its EU-total row: "TOTAL (10/10/26)" (EAGF) and "TOTAL (23/10/26)"
(EAFRD), the same days as the platform's last-refresh stamps. On 20 Oct that label was only
stripped to key the row; it is now each row's document_date.
"""
import importlib
import pathlib
import sys
from datetime import datetime, timezone

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

cap = importlib.import_module("backfill_cap_payments")
STARTED = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

EAGF_ROWS = [{"ms": "AT", "total": "2766716299.86", "fy_2023": "674550015.69"},
             {"ms": "TOTAL (10/10/26)", "total": "1"}]
EAFRD_ROWS = [{"fund": "IT", "total_net_payments": "2253674207.52"},
              {"fund": "TOTAL (23/10/26)", "total_net_payments": "1"}]


class _Cur:
    def __init__(self): self.sql = []
    def execute(self, sql, params=None): self.sql.append((sql, params))
    def fetchone(self): return (STARTED,)


class _Db:
    def __init__(self): self.cur = _Cur()
    def execute(self, sql, params=None): self.cur.execute(sql, params)


def test_the_date_comes_from_the_total_rows_label():
    assert cap.figures_date(EAGF_ROWS) == datetime(2026, 10, 10, tzinfo=timezone.utc)
    assert cap.figures_date(EAFRD_ROWS) == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert cap.figures_date([{"ms": "TOTAL (23/10/2026)"}]) == datetime(2026, 10, 23, tzinfo=timezone.utc)


def test_no_label_or_an_impossible_day_gives_no_date():
    assert cap.figures_date([{"ms": "AT"}, {"ms": "TOTAL"}]) is None
    assert cap.figures_date([{"ms": "TOTAL (31/02/26)"}]) is None


def test_every_row_is_written_with_the_figures_date(monkeypatch):
    monkeypatch.setattr(cap, "fetch", lambda dataset: EAFRD_ROWS)
    db = _Db()
    assert cap.upsert(db, "EAFRD") == 2
    inserts = [(sql, p) for sql, p in db.cur.sql if "INSERT INTO eu_cap_payments" in sql]
    assert len(inserts) == 2
    for sql, params in inserts:
        assert "document_date = EXCLUDED.document_date" in sql      # a refresh moves it
        assert params["as_of"] == datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert {p["ms"] for _, p in inserts} == {"IT", "TOTAL"}


def test_an_undated_refresh_is_reported_and_left_empty(monkeypatch, capsys):
    monkeypatch.setattr(cap, "fetch", lambda dataset: [{"ms": "AT", "total": "1"}])
    db = _Db()
    cap.upsert(db, "EAGF")
    assert "[SYNC_STATUS] degraded: EAGF figures carry no 'TOTAL (dd/mm/yy)' date" in capsys.readouterr().out
    params = next(p for sql, p in db.cur.sql if "INSERT INTO eu_cap_payments" in sql)
    assert params["as_of"] is None
