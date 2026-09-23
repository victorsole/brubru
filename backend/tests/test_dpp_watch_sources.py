"""dpp_watch: SQL regexes, TRIS and the JRC Product Bureau (23 Sep 2026).

Reads the database (read-only). Guards three defects found the day a client
reported a Spanish textile decree we had not seen: the watch never read TRIS,
never read the Product Bureau, and every `\\b` in its scope patterns was a
BACKSPACE in PostgreSQL, so "DPP" and "ESPR" never matched in SQL.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib

import pytest
from sqlalchemy import text

from core.database import SessionLocal

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "dpp_watch.py"


@pytest.fixture(scope="module")
def watch():
    spec = importlib.util.spec_from_file_location("dpp_watch", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_word_boundaries_match_in_postgres(watch, db):
    rx = watch.SCOPES["A"]["rx"].replace("\\b", "\\y")
    assert "\\b" not in rx
    assert db.execute(text("SELECT 'the DPP registry opened' ~* :rx"), {"rx": rx}).scalar() is True
    assert db.execute(text("SELECT 'ESPR working plan' ~* :rx"), {"rx": rx}).scalar() is True


def test_python_boundary_does_not_match_in_postgres(db):
    # The defect itself, pinned: if this ever starts passing, Postgres changed.
    assert db.execute(text("SELECT 'the DPP registry' ~* '\\bDPP\\b'")).scalar() is False


def test_tris_is_in_the_freshness_check(watch, db):
    rows = {r["body"]: r for r in watch.body_freshness(db)}
    assert "tris" in rows and rows["tris"]["news_rows"] > 0


def test_imminent_jrc_workshop_is_urgent(watch, db):
    nxt = db.execute(text(
        "SELECT min(document_date::date) FROM economy_items WHERE body_code='dpp' "
        "AND guid LIKE 'jrc-pb-%' AND item_type='event' AND document_date::date >= current_date "
        "AND title !~* 'day not yet fixed'")).scalar()
    if nxt is None or (nxt - dt.date.today()).days > 30:
        pytest.skip("no dated JRC workshop within 30 days")
    hits = watch.sweep(db, "A", 7)
    ws = [h for h in hits if h["item_type"] == "jrc_workshop"]
    assert ws and all(h["urgent"] for h in ws)


def test_old_jrc_documents_are_not_news(watch, db):
    hits = watch.sweep(db, "A", 7)
    since = dt.date.today() - dt.timedelta(days=7)
    for h in hits:
        if h["item_type"] == "jrc_study_document":
            assert h["d"] >= since


def test_sweep_sends_postgres_boundaries(watch):
    seen = []

    class _R:
        def mappings(self):
            return self

        def all(self):
            return []

    class _DB:
        def execute(self, stmt, params=None):
            seen.append((params or {}).get("rx"))
            return _R()

    watch.sweep(_DB(), "A", 7)
    rxs = [r for r in seen if r]
    assert rxs and all("\\b" not in r and "\\y" in r for r in rxs)


def test_watch_tris_scan_uses_the_product_domain_filter(watch):
    seen = []

    class _R:
        def mappings(self):
            return self

        def all(self):
            return []

    class _DB:
        def execute(self, stmt, params=None):
            seen.append(params or {})
            return _R()

    watch.sweep(_DB(), "A", 7)
    assert any("trx" in p for p in seen)
