"""Economy routes serve updated_date, and it moves only when the content does (16 Oct 2026).

API audit, step 2 (Cedefop tenders): updated_date was null on 451 of 451 items and on
3,299 of 3,299 of their files. economy_items keeps updated_at and procurement_documents
keeps last_updated, but no SELECT named them, so row_updated() found nothing. Underneath,
economy_items.updated_at was the last FETCH, not the last change: the upsert sets
fetched_at = now() on every run and the change trigger counted it (migration 296).

The unit tests answer each query with exactly the columns its SELECT names, so a route
that forgets the change column serves null here as it did in production. The live tests
run the real SQL, which is what catches a UNION whose arms disagree (/funding/all).
"""
from __future__ import annotations

import asyncio
import inspect
import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import APIRouter

from api.v2 import economy_endpoints as ee

T = datetime(2026, 10, 15, 3, 11, tzinfo=timezone.utc)


def _call(fn, **given):
    kwargs = {name: given.get(name) for name in inspect.signature(fn).parameters}
    kwargs.update(given)
    out = fn(**kwargs)
    return asyncio.run(out) if inspect.iscoroutine(out) else out


def _select_columns(sql: str) -> list[str]:
    """The output names of the outermost SELECT ... FROM (aliases win)."""
    body = re.search(r"SELECT\s+(.*?)\s+FROM\s", sql, re.S | re.I).group(1)
    cols, depth, cur = [], 0, ""
    for ch in body:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            cols.append(cur)
            cur = ""
        else:
            cur += ch
    cols.append(cur)
    out = []
    for c in cols:
        m = re.search(r"\bAS\s+(\w+)\s*$", c.strip(), re.I)
        out.append(m.group(1) if m else re.findall(r"\w+", c)[-1])
    return out


def _value(col: str):
    if col == "id":
        return 1
    if col.endswith("_eur"):
        return 1.0
    if col == "year":
        return 2025
    if col.startswith(("is_", "has_")):
        return True
    if col in ("project_start", "project_end"):
        return None
    if col in ("economy_item_id", "file_size"):
        return 1
    if col.endswith(("date", "_at", "deadline")) or col in ("first_seen", "last_updated"):
        return T
    return "x"


class _DB:
    """Answers every query with one row holding exactly the columns its SELECT names."""

    def __init__(self):
        self.sql: list[str] = []

    def execute(self, clause, params=None):
        sql = str(clause)
        self.sql.append(sql)
        if re.match(r"\s*SELECT (count\(\*\)|1)\b", sql):
            return SimpleNamespace(scalar=lambda: 1, fetchone=lambda: (1,), fetchall=lambda: [(1,)])
        names = _select_columns(sql)
        row = SimpleNamespace(**{n: _value(n) for n in names})
        if "id" in names and "economy_item_id" in names:
            row.id = str(uuid.uuid4())
        return SimpleNamespace(fetchall=lambda: [row], fetchone=lambda: row, scalar=lambda: 1)


def _routes(procurement: bool, documents: bool):
    r = APIRouter()
    ee.register_resource(r, body_code="cedefop", item_type="tender", slug="cedefop-tenders",
                         noun="calls for tender", body_name="Cedefop", acronym="Cedefop",
                         source="s", tag="t", procurement=procurement, documents=documents)
    return {route.path: route.endpoint for route in r.routes}


def _items(env):
    data = env["data"] if isinstance(env, dict) else env.data
    return [d if isinstance(d, dict) else d.model_dump() for d in data]


_REQ = SimpleNamespace(url=SimpleNamespace(path="/api/v2/funding/cedefop-tenders/1/documents"),
                       base_url="https://h/")


@pytest.mark.parametrize("procurement", [False, True])
@pytest.mark.parametrize("include_body", [False, True])
def test_economy_list_serves_updated_date(procurement, include_body):
    ep = _routes(procurement, False)["/cedefop-tenders"]
    env = _call(ep, request=_REQ, db=_DB(), order="recent", page=1, limit=20, include_body=include_body)
    assert _items(env)[0]["updated_date"] == T


@pytest.mark.parametrize("procurement", [False, True])
def test_economy_detail_serves_updated_date(procurement):
    ep = _routes(procurement, False)["/cedefop-tenders/{item_id}"]
    item = _call(ep, request=_REQ, db=_DB(), item_id=1)
    assert item.updated_date == T


@pytest.mark.parametrize("include_body", [False, True])
def test_documents_list_and_item_serve_updated_date(include_body):
    routes = _routes(True, True)
    env = _call(routes["/cedefop-tenders/{item_id}/documents"], request=_REQ, db=_DB(), item_id=1,
                page=1, limit=50, include_body=include_body)
    assert _items(env)[0]["updated_date"] == T
    doc = _call(routes["/cedefop-tenders/{item_id}/documents/{document_id}"], request=_REQ, db=_DB(),
                item_id=1, document_id="d")
    assert doc.updated_date == T


def test_international_cooperation_serves_updated_date():
    from api.v2.funding import international_cooperation as ic
    env = _call(ic.list_intl_cooperation, request=_REQ, db=_DB(), order="recent", page=1, limit=20,
                include_body=False)
    assert _items(env)[0]["updated_date"] == T
    assert _call(ic.get_intl_cooperation, request=_REQ, db=_DB(), item_id=1).updated_date == T


def test_funding_all_projects_updated_at_in_every_union_arm():
    """Every arm of the UNION names updated_at, or Postgres refuses the query."""
    from api.v2.funding import funding_all as fa
    for body in (False, True):
        cte = fa._union_cte(body)
        arms = re.split(r"\bUNION ALL\b", cte)
        assert len(arms) == 4
        assert all(re.search(r"\bupdated_at\b", a) for a in arms)


# --------------------------------------------------------------------------- #
# Live: the real SQL against production data.
# --------------------------------------------------------------------------- #
@pytest.fixture
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.mark.live
def test_live_cedefop_tenders_and_files_carry_updated_date(db):
    routes = _routes(True, True)
    env = _call(routes["/cedefop-tenders"], request=_REQ, db=db, order="recent", page=1, limit=100,
                include_body=False)
    items = _items(env)
    assert items and all(i["updated_date"] for i in items)
    pid = next(i["id"] for i in items if db.execute(ee.text(
        "SELECT 1 FROM procurement_documents WHERE economy_item_id = :i"), {"i": i["id"]}).fetchone())
    env = _call(routes["/cedefop-tenders/{item_id}/documents"], request=_REQ, db=db, item_id=pid,
                page=1, limit=50, include_body=False)
    assert all(d["updated_date"] for d in _items(env))


@pytest.mark.live
@pytest.mark.parametrize("include_body", [False, True])
def test_live_funding_all_union_runs_and_dates_agency_items(db, include_body):
    from api.v2.funding import funding_all as fa
    env = _call(fa.funding_all, request=_REQ, db=db, order="recent", page=1, limit=100,
                include_body=include_body, type="tender")
    items = _items(env)
    assert items and all(i["updated_date"] for i in items)
    env = _call(fa.funding_all, request=_REQ, db=db, order="recent", page=1, limit=20,
                include_body=include_body, type="cohesion_allocation")
    assert _items(env)          # the other arms still answer (their updated_date is NULL)


@pytest.mark.live
def test_live_change_triggers_ignore_the_fetch_stamps(db):
    rows = dict(db.execute(ee.text(
        "SELECT c.relname, pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE t.tgname IN ('trg_economy_items_touch_if_changed', 'trg_eu_news_items_touch_if_changed')"
    )).fetchall())
    assert "'updated_at', 'fetched_at', 'creation_date'" in rows["economy_items"]
    assert "'updated_at', 'scraped_at,fetched_at', 'created_at'" in rows["eu_news_items"]
