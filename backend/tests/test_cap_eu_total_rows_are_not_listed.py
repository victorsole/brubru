"""The CAP files' EU-total rows (ms TOTAL, the sum of the 27 Member States) are not items (O102, Victor's
decision of 30 Oct 2026): listed, they came first by amount and a sum over a list counted the money twice.
They stay stored (their label dates every CAP row, O56) and answer at their item route."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Rows:
    def __init__(self, rows=()): self.rows = list(rows)
    def scalar(self): return 0
    def mappings(self): return self
    def all(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows


class _Db:
    def __init__(self): self.sql = []
    def execute(self, stmt, params=None):
        self.sql.append(str(stmt))
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


def test_the_cap_lists_count_and_page_without_the_eu_total():
    for slug in ("eagf", "eafrd"):
        db = _Db()
        assert _client(db).get(f"/api/v2/funding/{slug}").status_code == 200
        count, page = db.sql[0], db.sql[1]
        assert "FROM eu_cap_payments WHERE" in count and "ms IS DISTINCT FROM 'TOTAL'" in count
        assert "ms IS DISTINCT FROM 'TOTAL'" in page


def test_funding_all_and_budgets_leave_it_out_too_and_the_item_route_still_answers():
    from api.v2.funding import budgets, funding_all
    assert "FROM eu_cap_payments) c\n    WHERE c.ms IS DISTINCT FROM 'TOTAL'" in funding_all._union_cte(False)
    assert "FROM eu_cap_payments WHERE ms IS DISTINCT FROM 'TOTAL'" in budgets._CAP_SIDE
    db = _Db()
    _client(db).get("/api/v2/funding/eagf/1092")
    assert "TOTAL" not in db.sql[0]            # the item route reads the row by id, whatever its ms
