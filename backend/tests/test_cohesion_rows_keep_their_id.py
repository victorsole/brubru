"""Cohesion finances, outcomes and CAP payments keep their rows across runs (20 Oct 2026).

Their writers deleted a fund and inserted it again every week: new ids each run (982 finance rows
held ids 16,910-17,891), creation_date = the last run, every row "changed" for a partner syncing
by date, and every row linked the fund's page. They now upsert on a key (migration 307), delete
only what the source no longer lists, and link each programme's own page.
"""
import importlib
import pathlib
import sys
from datetime import datetime, timezone

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

STARTED = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


class _Cur:
    def __init__(self): self.sql = []
    def execute(self, sql, params=None): self.sql.append((sql, params))
    def fetchone(self): return (STARTED,)
    def mogrify(self, sql, args): return b"(x)"


class _Db:
    def __init__(self): self.cur = _Cur()
    def execute(self, sql, params=None): self.cur.execute(sql, params)


def _first_statement_kinds(db):
    return [" ".join(sql.split())[:40] for sql, _ in db.cur.sql]


def test_finances_upsert_on_the_key_and_link_the_programme():
    cf = importlib.import_module("backfill_cohesion_finances")
    db = _Db()
    cf.upsert_fund(db, "ERDF", [{"cci": "2021ES16RFPR001", "cci_title": "Plurirregional - ES - ERDF", "ms": "ES",
                                 "financial_allocation_category": None, "total": "1"}])
    kinds = _first_statement_kinds(db)
    assert not any(k.startswith("DELETE") for k in kinds[:-1])       # nothing deleted before the writes
    insert = next(sql for sql, _ in db.cur.sql if "INSERT INTO eu_cohesion_finances" in sql)
    assert "ON CONFLICT (fund, cci, (coalesce(financial_allocation_category, '')))" in insert
    params = next(p for sql, p in db.cur.sql if "INSERT INTO eu_cohesion_finances" in sql)
    assert params["public_url"] == "https://cohesiondata.ec.europa.eu/programmes/2021ES16RFPR001"
    last_sql, last_params = db.cur.sql[-1]
    assert last_sql.startswith("DELETE FROM eu_cohesion_finances") and "fetched_at <" in last_sql
    assert last_params == ("ERDF", STARTED)


def test_outcomes_upsert_on_the_record_key(monkeypatch):
    co = importlib.import_module("backfill_cohesion_outcomes")
    seen = {}

    def fake_execute_values(cur, sql, tuples, template=None, page_size=None):
        seen.update(sql=sql, tuples=list(tuples), template=template)
    monkeypatch.setattr(co, "execute_values", fake_execute_values)
    db = _Db()
    row = {"cci": "2021PL16FFPR001", "ind_code": "RCO01", "indicator_long_name": "Enterprises supported"}
    co.upsert_fund(db, "ERDF", [row, dict(row)])                     # an exact repeat
    assert len(seen["tuples"]) == 1
    assert "ON CONFLICT (fund, source_dataset, row_key)" in seen["sql"] and "md5(%s::jsonb::text)" in seen["template"]
    assert "https://cohesiondata.ec.europa.eu/programmes/2021PL16FFPR001" in seen["tuples"][0]
    assert db.cur.sql[-1][0].startswith("DELETE FROM eu_cohesion_outcomes") and "fetched_at <" in db.cur.sql[-1][0]


def test_cap_keys_the_eu_total_without_its_date():
    cap = importlib.import_module("backfill_cap_payments")
    assert cap._ms_key("TOTAL (20/10/26)") == "TOTAL" and cap._ms_key("ES") == "ES"
