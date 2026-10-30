"""An FTS line's updated_date is the later of two tables' stamps, which no index serves: an updated_from
window read every line (34.4 s a count, O105). The lists find the lines through the two stamps' own
indexes and keep the exact rule beside it (migration 321, 30 Oct 2026: 0.29 s)."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Rows:
    def scalar(self): return 0
    def fetchall(self): return []
    def mappings(self): return self
    def all(self): return []


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


def test_the_fts_lists_take_the_indexed_way_only_for_an_updated_from_window():
    from api.v2.funding import _fts
    for path in ("/api/v2/funding/eu-funding-recipients", "/api/v2/funding/international-cooperation"):
        db = _Db()
        assert _client(db).get(path, params={"updated_from": "2026-10-29"}).status_code == 200
        lines = [s for s in db.sql if "FROM economy_items e LEFT JOIN fts_commitments" in s]   # the count and the page
        assert len(lines) == 2 and all(_fts.CHANGED_SINCE in s and f"{_fts.UPDATED} >= :updated_from" in s for s in lines), path
        db = _Db()
        _client(db).get(path)
        assert not any(_fts.CHANGED_SINCE in s for s in db.sql), path


def test_awards_adds_it_to_the_fts_side_alone():
    from api.v2.funding import _fts, awards
    assert _fts.CHANGED_SINCE in awards._side("fts", False, True)
    assert _fts.CHANGED_SINCE not in awards._side("fts", False, False)
    assert _fts.CHANGED_SINCE not in awards._side("project", False, True) + awards._side("ted_award", False, True)
    db = _Db()
    _client(db).get("/api/v2/funding/awards", params={"updated_from": "2026-10-29", "order": "updated_asc"})
    page = next(s for s in db.sql if "LIMIT :limit OFFSET :offset" in s)
    count = next(s for s in db.sql if s.startswith("SELECT (SELECT count(*)"))
    assert _fts.CHANGED_SINCE in page and _fts.CHANGED_SINCE in count


def test_a_wide_window_reads_the_lines_the_plain_way():
    """The indexed way is slower when most lines changed (104,320: 108 s against 68 s)."""
    from api.v2.funding import _fts

    class Wide(_Db):
        def execute(self, stmt, params=None):
            self.sql.append(str(stmt))
            r = _Rows()
            if "UNION SELECT economy_item_id FROM fts_commitments" in str(stmt) and "count(*)" in str(stmt):
                r.scalar = lambda: _fts.NARROW_WINDOW + 1
            return r
    db = Wide()
    assert _client(db).get("/api/v2/funding/eu-funding-recipients", params={"updated_from": "2026-10-26"}).status_code == 200
    page = [s for s in db.sql if "ORDER BY" in s][0]
    assert _fts.CHANGED_SINCE not in page and f"{_fts.UPDATED} >= :updated_from" in page
