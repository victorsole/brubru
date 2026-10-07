"""/oeil/procedures: only OEIL procedure files we hold a page for, with OEIL's own stage (7 Oct 2026).

GovClipping's window held 1,159 EUR-Lex acts and 477 Legislative Train files served as
"procedures" (1,626 without a body), 15 procedures whose OEIL page answers 404, and
statuses that contradicted OEIL's "Stage reached in procedure" (24 lapsed or withdrawn
files still "tabled" or "completed").
"""
import pathlib
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

_BACKEND = pathlib.Path(__file__).resolve().parents[1]


class _Q:
    def __init__(self):
        self.filters = []

    def filter(self, *a):
        self.filters += a
        return self

    def count(self):
        return 0

    def order_by(self, *a):
        return self

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    def all(self):
        return []


def _list_sql(monkeypatch, query: str) -> str:
    from fastapi.testclient import TestClient
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    from main import app
    from models.user import User

    q = _Q()
    monkeypatch.setattr("api.v1.procedures.stable", lambda query_, *a: query_)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    app.dependency_overrides[get_db] = lambda: type("DB", (), {"query": lambda self, m: q})()
    try:
        r = TestClient(app).get(f"/api/v2/legislative/oeil/procedures?{query}")
    finally:
        app.dependency_overrides.pop(api_user_with_rate_limit, None)
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200, r.text
    return " ".join(str(f.compile(dialect=postgresql.dialect())) for f in q.filters)


def test_default_serves_only_oeil_files_with_a_page(monkeypatch):
    sql = _list_sql(monkeypatch, "page=1")
    assert "legislative_carriages.source = " in sql
    assert "oeil_missing_since IS NULL" in sql
    assert "length(legislative_carriages.oeil_text_body) >=" in sql
    assert " OR " not in sql


def test_other_sources_are_opt_in_and_still_drop_missing_pages(monkeypatch):
    sql = _list_sql(monkeypatch, "include_other_sources=true")
    assert "legislative_carriages.source != " in sql and " OR " in sql
    assert "oeil_missing_since IS NULL" in sql


def test_stage_is_read_word_for_word_from_the_stored_page():
    from api.v1.procedures import _oeil_stage
    body = "Technical information \n\n Stage reached in procedure \n Procedure lapsed or withdrawn \n\n Committee dossier"
    assert _oeil_stage(SimpleNamespace(oeil_text_body=body)) == "Procedure lapsed or withdrawn"
    assert _oeil_stage(SimpleNamespace(oeil_text_body="Status \n\n Awaiting committee decision \n")) == "Awaiting committee decision"
    assert _oeil_stage(SimpleNamespace(oeil_text_body=None)) is None


def test_the_updater_hides_404s_withdraws_lapsed_files_and_rereads_adopted_ones():
    src = (_BACKEND / "scripts" / "update_carriage_statuses_from_oeil.py").read_text()
    assert "row.oeil_missing_since = datetime.now(timezone.utc)" in src          # 404: kept out of the API
    assert "carriage.oeil_missing_since = None" in src                            # page back: served again
    assert '"lapsed or withdrawn" in (data.basic_info.status or "").lower()' in src
    assert "LegislativeCarriage.oeil_body_fetched_at < _month_ago" in src        # adopted pages refreshed


def test_policy_areas_are_oeils_subjects_word_for_word():
    from api.v1.procedures import _oeil_subjects
    body = ("Basic information \n\n 2026/0211(COD) \n\n Subject \n\n 3.40 Industrial policy\n\n"
            " 3.70.03 Climate policy, climate change, ozone layer\n\n Status \n\n Awaiting committee decision")
    assert _oeil_subjects(SimpleNamespace(oeil_text_body=body)) == [
        "3.40 Industrial policy", "3.70.03 Climate policy, climate change, ozone layer"]
    assert _oeil_subjects(SimpleNamespace(oeil_text_body="Subject \n\n 8 State and evolution of the Union\n\n Geographical area \n\n Latvia")) == [
        "8 State and evolution of the Union"]
    assert _oeil_subjects(SimpleNamespace(oeil_text_body=None)) == []
