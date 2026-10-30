"""/funding/partners keeps the funding standard (O103, Victor's go of 30 Oct 2026): the three windows (the
activities' dates, and the organisation's own creation_date and updated_date), the sync orders, and an
amount_eur that is the figure its range compares (EU contribution plus payments), the payments alone
kept as payments_eur."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Rows:
    def __init__(self, rows=()): self.rows = list(rows)
    def scalar(self): return 0
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None


class _Db:
    def __init__(self): self.calls = []
    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        return _Rows()


def _client(db):
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.funding import router
    from core.database import get_db
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def _query(params):
    db = _Db()
    r = _client(db).get("/api/v2/funding/partners", params={"q": "battery", **params})
    assert r.status_code == 200, r.text
    return next(c for c in db.calls if "WITH proj AS" in c[0])


def test_the_three_windows_reach_the_query():
    sql, params = _query({"published_from": "2025-01-01", "published_to": "2025-12-31",
                          "created_from": "2026-10-01", "updated_from": "2026-10-20", "updated_to": "2026-10-30"})
    assert params["since"].isoformat() == "2025-01-01" and params["until"].isoformat() == "2025-12-31"
    assert "p.start_date >= :since" in sql and "p.start_date < CAST(:until AS date) + 1" in sql
    assert "s.requested_date < CAST(:until AS date) + 1" in sql
    assert "min(created) >= :created_from" in sql and "max(changed) >= :updated_from" in sql
    assert "max(changed) <= :updated_to" in sql
    # since / until stay aliases
    sql2, params2 = _query({"since": "2025-01-01", "until": "2025-06-30"})
    assert params2["since"].isoformat() == "2025-01-01" and params2["until"].isoformat() == "2025-06-30"


def test_a_window_can_be_paged_by_the_change_date():
    sql, _ = _query({"updated_from": "2026-10-20", "order": "updated_asc"})
    assert sql.rstrip().endswith("ORDER BY max(changed) ASC, key ASC\n     LIMIT :limit OFFSET :offset") or \
        "ORDER BY max(changed) ASC, key ASC" in sql
    assert _client(_Db()).get("/api/v2/funding/partners", params={"q": "x", "order": "deadline"}).status_code == 400


def test_amount_eur_is_the_figure_the_range_compares_and_the_payments_stay_apart():
    sql, _ = _query({"min_amount_eur": 1000})
    assert "sum(amount_eur) AS payments_eur" in sql
    assert ("CASE WHEN sum(eu_contribution) IS NULL AND sum(amount_eur) IS NULL THEN NULL\n"
            "                ELSE coalesce(sum(eu_contribution), 0) + coalesce(sum(amount_eur), 0) END AS amount_eur") in sql
    assert "coalesce(sum(eu_contribution), 0) + coalesce(sum(amount_eur), 0) >= :min_amt" in sql
    from api.v2.funding.partners import _item
    row = SimpleNamespace(key="pic:1", pic="1", vat=None, name="X", short_name=None, country="BE", city=None,
                          activity_type=None, is_sme=None, projects=1, coordinated=0, payments=1, contracts=0, awards=0,
                          announcements=0, eu_contribution=300.0, payments_eur=200.0, amount_eur=500.0, matches=[],
                          last_day=None, created=None, changed=None)
    item = _item(row, "https://h")
    assert (item.eu_contribution, item.payments_eur, item.amount_eur) == (300.0, 200.0, 500.0)
