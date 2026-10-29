"""amount_eur at the ECB reference rate of the item's own day (funding standard Phase 2 step 6, 29 Oct 2026).

Until then a figure in another currency than the euro had no amount_eur: about 10,000 TED notices (RON,
CZK, SEK, PLN ...), 5 F&T Portal tenders and 21 TED award notices. The tender awards' amount filters
read only the notices in euros and their amount order ranked raw figures across currencies. One SQL
rule (services/funding/shared_fields.amount_eur_sql) now gives the figure every list shows, filters
and orders on; the rates come from the ECB Data Portal (services/funding/ecb_rates.py).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from services.funding import ecb_rates, shared_fields as S

_TITLES = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,TITLE_COMPL
EXR.D.ARS.EUR.SP00.A,D,ARS,EUR,SP00,A,2020-10-30,91.5953,"Indicative exchange rate, Euro/Argentine peso, 2:15 pm (C.E.T.)"
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-10-28,1.1133,"ECB reference exchange rate, US dollar/Euro, 2.15 pm (C.E.T.)"
EXR.D.PLN.EUR.SP00.A,D,PLN,EUR,SP00,A,2026-10-28,4.2105,"ECB reference exchange rate, Polish zloty/Euro, 2.15 pm (C.E.T.)"
"""
_DATA = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE
EXR.D.PLN.EUR.SP00.A,D,PLN,EUR,SP00,A,2025-12-24,4.2135
EXR.D.PLN.EUR.SP00.A,D,PLN,EUR,SP00,A,2025-12-29,
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2025-12-29,1.1766
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2025-12-30,0
EXR.D.ARS.EUR.SP00.A,D,ARS,EUR,SP00,A,2020-10-30,91.5953
"""


def test_the_reader_keeps_the_ecb_reference_rates_and_never_an_indicative_one():
    assert ecb_rates.reference_currencies(_TITLES) == ["PLN", "USD"]
    rows = ecb_rates.parse_rates(_DATA, ["PLN", "USD"])
    assert [(r["currency"], r["rate_date"], r["rate"]) for r in rows] == [
        ("PLN", date(2025, 12, 24), "4.2135"), ("USD", date(2025, 12, 29), "1.1766")]   # no blank, no zero, no ARS
    assert rows[0]["series_key"] == "EXR.D.PLN.EUR.SP00.A"
    assert rows[0]["source_url"] == "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.PLN.EUR.SP00.A"


def test_the_reader_asks_for_the_titles_then_the_reference_series_only():
    asked = []

    class Session:
        def get(self, url, params, headers, timeout):
            asked.append((url, dict(params)))
            return SimpleNamespace(text=_TITLES if len(asked) == 1 else _DATA, raise_for_status=lambda: None)
    rows = ecb_rates.fetch_rates(date(2025, 12, 20), session=Session())
    assert asked[0] == ("https://data-api.ecb.europa.eu/service/data/EXR/D..EUR.SP00.A",
                        {"lastNObservations": 1, "format": "csvdata"})
    assert asked[1] == ("https://data-api.ecb.europa.eu/service/data/EXR/D.PLN+USD.EUR.SP00.A",
                        {"startPeriod": "2025-12-20", "format": "csvdata", "detail": "dataonly"})
    assert len(rows) == 2


def test_the_rule_keeps_euros_as_stated_and_converts_the_rest_at_the_rate_of_the_day_or_the_week_before():
    sql = " ".join(S.amount_eur_sql("t.v", "t.cur", "t.d").split())
    assert sql.startswith("(CASE WHEN t.v IS NULL THEN NULL WHEN upper(btrim(t.cur)) = 'EUR' THEN (t.v)::numeric ")
    assert "WHEN upper(btrim(t.cur)) = 'BGN' THEN round((t.v)::numeric / 1.95583, 2)" in sql
    assert ("ELSE round((t.v)::numeric / (SELECT r.rate FROM ecb_reference_rates r WHERE r.currency = upper(btrim(t.cur)) "
            "AND r.rate_date <= (t.d) AND r.rate_date >= (t.d) - 7 ORDER BY r.rate_date DESC LIMIT 1), 2) END)") in sql
    # Christmas leaves five days without a rate (24 to 29 Dec 2025): the window must cover it.
    assert S.RATE_DAYS_BACK >= 5


def test_a_column_named_like_a_rates_column_must_be_qualified():
    for bad in (("amount", "currency", "d"), ("v", "t.cur", "rate_date"), ("v", "c", "first_seen")):
        with pytest.raises(ValueError):
            S.amount_eur_sql(*bad)
    S.amount_eur_sql("n.rate", "n.currency", "n.rate_date")          # qualified: fine
    S.amount_eur_sql("v", "c", S.brussels_day("published_at", "utc_timestamp"))   # 'UTC' is a string, not a column


def test_a_day_is_the_brussels_calendar_day_of_its_column():
    assert S.brussels_day("d", "date") == "d"
    assert S.brussels_day("p", "timestamptz") == "((p) AT TIME ZONE 'Europe/Brussels')::date"
    assert S.brussels_day("p", "utc_timestamp") == "(((p) AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Brussels')::date"
    with pytest.raises(ValueError):
        S.brussels_day("p", "timestamp")


class _ConvDb:
    """A session answering the conversion query with `converted`, recording what it was asked."""
    def __init__(self, converted=None):
        self.converted, self.sql = dict(converted or {}), []

    def execute(self, stmt, params=None):
        self.sql.append((str(stmt), dict(params or {})))
        keys = (params or {}).get("keys", [])
        return SimpleNamespace(fetchall=lambda: [SimpleNamespace(k=k, eur=self.converted.get(k)) for k in keys],
                               all=lambda: [], scalar=lambda: 0)


def test_a_page_in_euros_asks_nothing_and_a_mixed_page_asks_for_its_other_currencies_only():
    rows = [SimpleNamespace(id=1, cur="EUR", v=10.0), SimpleNamespace(id=2, cur="PLN", v=4210.5),
            SimpleNamespace(id=3, cur=None, v=None), SimpleNamespace(id=4, cur=" usd ", v=1.0)]
    db = _ConvDb({2: 1000.0, 4: None})
    assert S.page_amounts_eur(db, rows[:1], table="t", key="id", amount="v", currency="cur", day="d") == {}
    assert db.sql == []
    got = S.page_amounts_eur(db, rows, table="t", key="id", amount="v", currency="cur", day="d")
    assert got == {2: 1000.0, 4: None} and db.sql[0][1] == {"keys": [2, 4]}
    assert "FROM t WHERE id = ANY(:keys)" in db.sql[0][0]
    assert S.item_amount_eur(10, "EUR", got, 1) == 10.0
    assert S.item_amount_eur(4210.5, "PLN", got, 2) == 1000.0
    assert S.item_amount_eur(None, "PLN", got, 2) is None
    assert S.item_amount_eur(1.0, "USD", got, 4) is None         # the ECB had no rate that week: null, not a guess


def _client(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.funding import router
    from core.database import get_db
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_a_ted_notice_in_zloty_shows_its_value_in_euros_on_the_list_and_the_item_route():
    from sqlalchemy.orm import Query
    from models.tender import Tender

    def row(**kw):
        r = {c.name: None for c in Tender.__table__.columns}
        r.update(has_lots=False, cpv_codes=[], title="T", **kw)
        return SimpleNamespace(**r)
    rows = [row(id=5, publication_number="1-2026", estimated_value=4210.5, estimated_value_currency="PLN",
                publication_date=datetime(2026, 10, 1)),
            row(id=6, publication_number="2-2026", estimated_value=99.5, estimated_value_currency="EUR",
                publication_date=datetime(2026, 10, 1))]

    class Q(Query):
        def count(self): return len(rows)
        def all(self): return rows
        def first(self): return rows[0]

    class Db(_ConvDb):
        def query(self, *entities): return Q(list(entities))
    db = Db({5: 1000.0})
    listed = _client(db).get("/api/v2/funding/tenders")
    assert listed.status_code == 200, listed.text
    assert [i["amount_eur"] for i in listed.json()["data"]] == [1000.0, 99.5]
    sql, params = next((q, p) for q, p in db.sql if "keys" in p)      # the conversion (same_as is asked after it)
    assert params == {"keys": [5]} and "FROM tenders WHERE id = ANY(:keys)" in sql
    assert "((publication_date) AT TIME ZONE 'Europe/Brussels')::date" in sql
    item = _client(db).get("/api/v2/funding/tenders/5")
    assert item.status_code == 200, item.text
    assert item.json()["amount_eur"] == 1000.0


def test_a_portal_tender_in_pounds_is_converted_by_its_reference():
    from api.v1.funding_tenders_collections import _FT_TENDER_AMOUNT, _tender_to_item
    base = dict(id="u", contracting_authority="EEAS", title="T", description=None, status="open", deadline=None,
                source_url="https://x.eu", documents_url=None, cpv_codes=[], contract_type="Services",
                published_at=datetime(2026, 3, 2, 23, 0), content_updated_at=None, last_updated=None, first_seen_at=None)
    gbp = SimpleNamespace(**base, tender_reference="R-1", estimated_value=838.0, value_currency="GBP")
    eur = SimpleNamespace(**base, tender_reference="R-2", estimated_value=5.0, value_currency="EUR")
    assert _tender_to_item(gbp, converted={"R-1": 1000.0}).amount_eur == 1000.0
    assert _tender_to_item(gbp).amount_eur is None
    assert _tender_to_item(eur).amount_eur == 5.0
    assert _FT_TENDER_AMOUNT["key"] == "tender_reference"        # the id is a uuid: the reference is text and unique
    assert "AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Brussels'" in _FT_TENDER_AMOUNT["day"]


def test_the_tender_awards_filter_and_order_on_the_value_in_euros():
    from api.v2.funding import tender_awards as A
    expr = S.amount_eur_sql("n.awarded_value", "n.awarded_value_currency", "n.publication_date")
    assert f"{expr} AS amount_eur" in A._COLS
    assert A._ORDER_SQL["amount"].startswith(expr)

    class Db(_ConvDb):
        def execute(self, stmt, params=None):
            self.sql.append((str(stmt), dict(params or {})))
            return SimpleNamespace(scalar=lambda: 0, fetchall=lambda: [], mappings=lambda: SimpleNamespace(all=lambda: []),
                                   all=lambda: [])
    db = Db()
    r = _client(db).get("/api/v2/funding/tender-awards", params={"min_amount_eur": 1000, "max_amount_eur": 5000, "order": "amount"})
    assert r.status_code == 200, r.text
    page_sql = next(s for s, _ in db.sql if "LIMIT :limit" in s)
    assert f"{expr} >= :min_eur" in page_sql and f"{expr} <= :max_eur" in page_sql
    assert "upper(n.awarded_value_currency) = 'EUR' AND" not in page_sql          # the euro-only filter is gone
    assert f"ORDER BY {expr} DESC NULLS LAST" in page_sql
    fields = {k: None for k in A.TenderAwardItem.model_fields}
    fields.update(publication_number="1-2026", notice_uuid=None, procedure_uuid=None, description=None, awarded_value=838,
                  awarded_value_currency="GBP", amount_eur=1000.0, lot_count=0, lots=[], cpv_codes=[], winner_count=0,
                  publication_date=date(2026, 1, 5), first_seen=None, last_updated=None, title="T",
                  public_url="https://ted.europa.eu/en/notice/-/detail/1-2026")
    item = A._item(SimpleNamespace(**fields), [], False)
    assert (item.awarded_value, item.awarded_value_currency, item.amount_eur) == (838.0, "GBP", 1000.0)


def test_a_cascade_call_reads_its_budget_in_euros_from_the_same_rule():
    from api.v2.funding import ft_cascade_calls as C
    assert S.amount_eur_sql("indicative_budget", "budget_currency", S.brussels_day("published_at", "timestamptz")) + " AS amount_eur" in C._COLS


def test_no_funding_description_still_promises_a_later_conversion():
    from fastapi import FastAPI
    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    spec = str(app.openapi())
    assert not re.search(r"conversion (comes later|is added)", spec)
    assert "ECB reference rate" in spec


def test_the_rates_job_runs_daily_and_the_tier_records_it():
    import ast
    from pathlib import Path
    from api import cron
    tree = ast.parse((Path(cron.__file__)).read_text())
    daily = next(n for n in tree.body if getattr(n, "name", "") == "cron_sync_daily")
    jobs = {(c.args[0].value, c.args[1].value) for c in ast.walk(daily)
            if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_run_script_async"
            and all(isinstance(a, ast.Constant) for a in c.args[:2])}
    assert ("ecb_reference_rates", "scripts/sync_ecb_reference_rates.py") in jobs
    assert "ecb_reference_rates" in cron._DAILY_TIER_RECORDED


def test_the_rates_table_is_readable_through_the_data_api_and_touched_only_on_change():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "318_ecb_reference_rates.sql").read_text()
    for needed in ("ENABLE ROW LEVEL SECURITY", "CREATE POLICY ecb_reference_rates_public_read",
                   "GRANT SELECT ON public.ecb_reference_rates TO anon, authenticated",
                   "GRANT ALL ON public.ecb_reference_rates TO service_role", "PRIMARY KEY (currency, rate_date)",
                   "brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen')"):
        assert needed in sql, needed
