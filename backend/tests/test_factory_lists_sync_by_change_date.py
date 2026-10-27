"""Every list built by register_resource takes the incremental-sync window (23 Oct 2026).

334 v2 lists read from economy_items carried `updated_date` on each item and accepted no
`updated_from` / `updated_to`, 32 of them under /funding: a partner had to re-read a whole
list to find what changed, and the parameter was silently ignored. These call real factory
routes (an agency procurement list and the FTS recipients list) with a session that records
the SQL they send.
"""
import pathlib
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402

CHANGED = datetime(2026, 10, 22, 9, 30, tzinfo=timezone.utc)


class _Row(dict):
    __getattr__ = dict.__getitem__


class _Result:
    def __init__(self, rows): self.rows = rows
    def scalar(self): return len(self.rows)
    def fetchall(self): return self.rows


class _Db:
    def __init__(self, row): self.row, self.sql = _Row(row), []

    def execute(self, stmt, params=None):
        self.sql.append((str(stmt), dict(params or {})))
        return _Result([self.row])


_ROW = dict(id=11, body_code="ecdc", item_type="tender", title="Framework contract for epidemic intelligence",
            summary="Open procedure", public_url="https://www.ecdc.europa.eu/en/about-us/procurement/x",
            document_date=CHANGED, creation_date=CHANGED, source_kind="html", updated_at=CHANGED,
            tender_reference="ECDC/2026/012", status="open", deadline=None,
            # A funding list carries bodies by default (the funding standard, 27 Oct 2026).
            body_txt="Framework contract for epidemic intelligence.", body_html="<p>Framework contract.</p>")
# The FTS lists read the file's columns beside the row (migration 313, 26 Oct 2026).
from api.v2.funding._fts import FILE_COLUMNS  # noqa: E402
_ROW.update(dict.fromkeys(FILE_COLUMNS))


def _get(router, path, params):
    db = _Db(_ROW)
    app = FastAPI()
    app.include_router(router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app).get(path, params=params), db


def test_a_procurement_list_filters_and_echoes_the_change_window():
    from api.v2.funding import agency_procurement as ap
    r, db = _get(ap.router, "/api/v2/funding/ecdc-tenders",
                 {"updated_from": "2026-10-22T08:00:00Z", "updated_to": "2026-10-22"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"][0]["updated_date"].startswith("2026-10-22T09:30")
    assert body["updated_from"].startswith("2026-10-22T08:00") and body["updated_to"].startswith("2026-10-22T23:59")
    count_sql, params = db.sql[0]
    page_sql, _ = db.sql[1]
    for sql in (count_sql, page_sql):                    # the total and the page use one window
        assert "updated_at >= :updated_from" in sql and "updated_at <= :updated_to" in sql
    assert params["updated_to"].hour == 23                 # a bare date covers the whole day


def test_the_recipients_list_takes_the_created_window_and_the_sync_order():
    from api.v2.funding import eu_funding_recipients as fr
    r, db = _get(fr.router, "/api/v2/funding/eu-funding-recipients",
                 {"created_from": "2026-10-01", "order": "updated_asc"})
    assert r.status_code == 200, r.text
    page_sql, params = db.sql[1]
    assert "creation_date >= :created_from" in page_sql
    # The row's change or its FTS values' change, whichever is later (26 Oct 2026).
    assert "ORDER BY greatest(e.updated_at, c.last_updated) ASC, e.id ASC" in page_sql
    assert "ignored_parameters" not in r.json()


def test_an_inverted_window_and_an_unknown_order_are_refused():
    from api.v2.funding import eu_funding_recipients as fr
    r, _ = _get(fr.router, "/api/v2/funding/eu-funding-recipients",
                {"updated_from": "2026-10-23", "updated_to": "2026-10-01"})
    assert r.status_code == 422 and r.json()["detail"]["reason_code"] == "invalid_date_range"
    r, _ = _get(fr.router, "/api/v2/funding/eu-funding-recipients", {"order": "sideways"})
    assert r.status_code == 400


def test_without_a_window_the_query_is_unchanged():
    from api.v2.funding import eu_funding_recipients as fr
    r, db = _get(fr.router, "/api/v2/funding/eu-funding-recipients", {})
    assert r.status_code == 200
    assert "updated_at >=" not in db.sql[1][0] and "creation_date >=" not in db.sql[1][0]


# ---- the five funding lists that are not built by the factory ---------------------------

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import Query  # noqa: E402


class _RecordingQuery(Query):
    """A real ORM query: the route builds it as in production; count/all compile it instead of running it."""
    seen: list = []

    def _sql(self):
        return str(self.statement.compile(dialect=postgresql.dialect()))

    def count(self):
        _RecordingQuery.seen.append(self._sql()); return 0

    def all(self):
        _RecordingQuery.seen.append(self._sql()); return []


class _OrmDb:
    def query(self, *entities):
        return _RecordingQuery(list(entities))


def _orm_get(router, path, params):
    _RecordingQuery.seen = []
    app = FastAPI()
    app.include_router(router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: _OrmDb()
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app).get(path, params=params), _RecordingQuery.seen


def test_startups_filter_on_the_columns_ft_calls_serves():
    from api.v2.funding import startups
    r, (count_sql, page_sql) = _orm_get(startups.router, "/api/v2/funding/startups",
                                        {"updated_from": "2026-10-22", "order": "updated_asc"})
    assert r.status_code == 200, r.text
    assert "ft_calls_for_proposals.content_updated_at >=" in count_sql
    assert "ORDER BY ft_calls_for_proposals.content_updated_at ASC, ft_calls_for_proposals.id ASC" in page_sql
    assert r.json()["updated_from"].startswith("2026-10-22")


def test_entrepreneur_instruments_take_the_created_window_and_keep_their_default_order():
    from api.v2.funding import entrepreneur_instruments as ei
    r, (count_sql, page_sql) = _orm_get(ei.router, "/api/v2/funding/entrepreneur-instruments",
                                        {"created_from": "2026-10-01", "created_to": "2026-10-22"})
    assert r.status_code == 200, r.text
    assert "ft_calls_for_proposals.first_seen_at >=" in count_sql and "first_seen_at <=" in count_sql
    assert "ORDER BY ft_calls_for_proposals.deadline DESC NULLS LAST" in page_sql


def test_international_cooperation_counts_a_change_window_live():
    from api.v2.funding import international_cooperation as ic
    row = dict(_ROW, body_code="commission", item_type="funding_recipient",
               body_txt="Beneficiary: X\nProgramme: NDICI - Global Europe", body_html=None)
    db = _Db(row)
    app = FastAPI()
    app.include_router(ic.router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    client = TestClient(app)
    for _ in range(2):                                   # the cached total would skip the second count
        assert client.get("/api/v2/funding/international-cooperation",
                          params={"updated_from": "2026-10-22", "order": "updated_asc"}).status_code == 200
    counts = [sql for sql, _ in db.sql if sql.startswith("SELECT count(*)")]
    assert len(counts) == 2 and all("greatest(e.updated_at, c.last_updated) >= :updated_from" in sql for sql in counts)
    assert "ORDER BY greatest(e.updated_at, c.last_updated) ASC, e.id ASC" in db.sql[-1][0]


def test_funding_all_applies_the_window_to_the_whole_union():
    from api.v2.funding import funding_all as fa
    r, db = _get(fa.router, "/api/v2/funding/all", {"updated_from": "2026-10-22", "updated_to": "2026-10-23"})
    assert r.status_code == 200, r.text
    count_sql, page_sql = db.sql[0][0], db.sql[1][0]
    for sql in (count_sql, page_sql):
        tail = sql.split("FROM all_funding", 1)[1]      # filtered on the union, not on one side
        assert "updated_at >= :updated_from" in tail and "updated_at <= :updated_to" in tail


def test_programmes_keep_or_drop_the_whole_list_by_its_own_revision_date():
    from api.v2.funding import funding_programmes as fp
    created, updated = fp._config_dates()
    before, after = updated.date().isoformat(), (updated.replace(year=updated.year + 1)).date().isoformat()
    r, _ = _get(fp.router, "/api/v2/funding/programmes", {"updated_from": before})
    assert r.status_code == 200 and r.json()["total"] > 0
    r, _ = _get(fp.router, "/api/v2/funding/programmes", {"updated_from": after})
    assert r.status_code == 200 and r.json()["total"] == 0
