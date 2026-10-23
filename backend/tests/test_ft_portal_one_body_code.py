"""The Funding & Tenders Portal answers to one body code and one family (23 Oct 2026).

/events/all served the portal's events under two codes: `funding` for the calendar's copy (typed:
conference, webinar...) and `ftportal` for the economy copy (untyped), so `body=ftportal` returned
271 untyped events and never the typed ones; its news carried `families: []`, so no `family=`
found them. All 271 economy copies share a unique link with a calendar copy (measured 23 Oct), so
with one code the deduplication keeps the typed copy. `funding` stays accepted as an alias.
"""
import pathlib
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.economy.body_families import (  # noqa: E402
    BODY_TO_CAL_INSTITUTION, CAL_INSTITUTION_TO_BODY, body_codes, bodies_for_family, families_for_body,
)

URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/events/40056"


def test_one_code_one_family_and_the_old_code_as_an_alias():
    assert CAL_INSTITUTION_TO_BODY["FUNDING"] == "ftportal" and BODY_TO_CAL_INSTITUTION["ftportal"] == "FUNDING"
    assert body_codes(" funding, ecb ") == {"ftportal", "ecb"}
    assert families_for_body("ftportal") == ["funding"] and "ftportal" in bodies_for_family("funding")


class _Result:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return self.rows


class _Db:
    def __init__(self): self.calls = []

    def execute(self, stmt, params=None):
        sql = str(stmt); self.calls.append((sql, dict(params or {})))
        if "FROM economy_items" in sql:
            return _Result([SimpleNamespace(id=3694992, body_code="ftportal", title="Vivatech 2027", summary="",
                                            public_url=URL, document_date=datetime(2027, 6, 16, 7, tzinfo=timezone.utc),
                                            creation_date=None, updated_at=None)])
        return _Result([SimpleNamespace(id=64513, institution="FUNDING", title="Vivatech 2027", description="",
                                        source_url=URL, agenda_url=None, start_date=date(2027, 6, 16), start_time=None,
                                        first_seen=None, last_updated=None, event_type="conference", venue="Paris")])


def test_events_all_scoped_to_the_portal_reads_both_stores_and_keeps_the_typed_copy():
    from api.v2 import events
    db = _Db()
    items = events._fetch(db, codes=events._resolve_scope("funding", None), since=None, until=None,
                          when="all", q=None, sources={"economy", "calendar"})
    econ_sql = next(p for s, p in db.calls if "FROM economy_items" in s)
    cal_sql = next(p for s, p in db.calls if "FROM eu_calendar_events" in s)
    assert econ_sql["codes"] == ["ftportal"] and cal_sql["insts"] == ["FUNDING"]
    assert len(items) == 1                                   # one event, not two
    assert items[0]["source"] == "calendar" and items[0]["body_code"] == "ftportal"
    assert items[0]["event_type"] == "conference"


def test_news_scope_takes_the_family():
    from api.v2 import news
    assert "ftportal" in news._resolve_scope(None, "funding")
