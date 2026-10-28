"""Every list route that takes `updated_from` also honours `updated_to` (14 Oct 2026).

12 of the 45 v2 list routes that take updated_from accepted it and silently ignored updated_to: a
client's bounded window (GovClipping's scheduled requests end at {{$isoTimestamp}})
returned everything up to now, and the envelope echoed `updated_to: null`. Found
auditing /legislative/delegated-acts, whose item route also answered with an
implementing act and whose documented `status=scrutiny` example answered 500."""
from __future__ import annotations

import inspect
import re

import pytest
from fastapi import HTTPException

from api.v1 import committee_agendas, ep_entities, transcripts, w4_endpoints, w5_endpoints

HANDLERS = [
    (w4_endpoints, ("list_parliamentary_questions", "list_meetings", "list_rsb_opinions",
                    "list_tris_notifications", "_list_secondary_acts")),
    (ep_entities, ("list_amendments", "list_votes", "list_ep_documents")),
    (transcripts, ("list_committee_transcripts",)),
    (committee_agendas, ("list_committee_agendas",)),
    (w5_endpoints, ("tenders_page",)),          # list_tenders' query since 28 Oct 2026 (v2 calls it too)
]


def test_every_v2_route_with_updated_from_takes_updated_to_and_passes_it_on():
    from main import app
    seen = 0
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api/v2/") or "GET" not in getattr(r, "methods", set()):
            continue
        params = inspect.signature(r.endpoint).parameters
        if "updated_from" not in params:
            continue
        seen += 1
        assert "updated_to" in params, path
        # Used beyond its own declaration: passed on, filtered on, or handed to a window
        # helper (the infringement routes use sql_window(validate_window(...))).
        src = inspect.getsource(r.endpoint)
        uses = [ln for ln in src.splitlines() if re.search(r"\bupdated_to\b", ln) and "Query(" not in ln]
        assert uses, path
    assert seen >= 40, f"only {seen} routes found; the scan is broken (45 on 14 Oct 2026)"


@pytest.mark.parametrize("module,names", HANDLERS)
def test_each_handler_bounds_the_same_column_it_starts_from(module, names):
    for name in names:
        src = inspect.getsource(getattr(module, name))
        starts = src.count(">= updated_from")
        assert starts and src.count("<= updated_to") == starts, name
        assert "updated_to=updated_to" in src, name


def test_an_unknown_status_is_the_callers_error_not_a_500():
    with pytest.raises(HTTPException) as e:
        w4_endpoints._list_secondary_acts(None, "delegated", None, None, "scrutiny", None, None,
                                          None, None, None, 50, 1)
    assert e.value.status_code == 422
    assert "scrutiny_finished" in e.value.detail["allowed"]


def test_the_item_route_answers_its_own_type_by_any_identifier_it_has_carried():
    src = inspect.getsource(w4_endpoints._secondary_act_detail)
    assert 'natural_keys=("reference", "celex")' in src
    assert "extra_filters=(SecondaryAct.act_type == act_type,)" in src
    # Ids and references of rows merged into this one still resolve.
    assert 'merged_from.contains([{"id": raw}])' in src and 'merged_from.contains([{"reference": raw}])' in src
    # The other type's act is a 404 that says where it lives.
    assert 'detail["see"]' in src



# ---------------------------------------------------------------------------
# Behaviour, not source text. The source checks above passed while the implementing
# list raised NameError (updated_to passed, never declared) and the item routes raised
# AttributeError (merged_from not mapped on the model): both found by the Auditor, 14 Oct.
# ---------------------------------------------------------------------------
import ast as _ast
import asyncio
from datetime import datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

from models.w4_entities import SecondaryAct


class _FakeQuery:
    """Builds the real SQLAlchemy query and compiles it, returning no rows."""

    def __init__(self, q):
        self.q = q

    def __getattr__(self, name):
        attr = getattr(self.q, name)
        if name in ("filter", "order_by", "offset", "limit", "filter_by"):
            return lambda *a, **k: _FakeQuery(attr(*a, **k))
        return attr

    def _compile(self):
        str(self.q.statement.compile(dialect=postgresql.dialect()))

    def first(self):
        self._compile()
        return None

    def count(self):
        self._compile()
        return 0

    def all(self):
        self._compile()
        return []


class _FakeDB:
    def query(self, *models):
        return _FakeQuery(Query(models))


def _call(fn, **given):
    """Call a route function with every parameter it declares, None unless given."""
    kwargs = {name: given.get(name) for name in inspect.signature(fn).parameters}
    kwargs.update(given)
    out = fn(**kwargs)
    return asyncio.run(out) if inspect.iscoroutine(out) else out


@pytest.mark.parametrize("module_path", ["api.v1.w4_endpoints", "api.v2.legislative.secondary_acts"])
@pytest.mark.parametrize("name", ["list_delegated_acts", "list_implementing_acts"])
def test_the_secondary_act_lists_run_with_a_bounded_window(module_path, name):
    import importlib
    fn = getattr(importlib.import_module(module_path), name)
    env = _call(fn, db=_FakeDB(), limit=50, page=1, body_threshold=500,
                updated_from=datetime(2026, 10, 1), updated_to=datetime(2026, 10, 14, 23, 59))
    assert env.total == 0 and env.updated_to == datetime(2026, 10, 14, 23, 59)


@pytest.mark.parametrize("ref", ["C(2026)1234", "32026R1753", "00000000-0000-0000-0000-000000000000"])
def test_a_miss_on_the_item_route_is_a_404_not_a_crash(ref):
    with pytest.raises(HTTPException) as e:
        w4_endpoints._secondary_act_detail(_FakeDB(), ref, "delegated_act")
    assert e.value.status_code == 404


def _delegations(src):
    """(module name, function name, keyword names) for each `return await m.f(...)`."""
    for m in re.finditer(r"return await (\w+)\.(\w+)\(", src):
        i, depth = m.end(), 1
        while depth and i < len(src):
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        args = src[m.end():i - 1]
        yield m.group(1), m.group(2), set(re.findall(r"(?:^|[,(\s])(\w+)=(?!=)", args))


def test_every_keyword_a_v2_route_passes_is_one_its_v1_handler_accepts():
    """A v2 route that hands its v1 handler an argument it does not declare fails on
    every call, which no signature-only check of the v2 route can see."""
    from main import app
    checked = 0
    for r in app.routes:
        if not getattr(r, "path", "").startswith("/api/v2/"):
            continue
        fn = r.endpoint
        for mod_name, fn_name, keywords in _delegations(inspect.getsource(fn)):
            target = getattr(fn.__globals__.get(mod_name), fn_name, None)
            if target is None or not callable(target):
                continue
            params = inspect.signature(target).parameters
            if any(p.kind == p.VAR_KEYWORD for p in params.values()):
                continue
            missing = keywords - set(params)
            assert not missing, f"{r.path}: {fn_name}() has no parameter {sorted(missing)}"
            checked += 1
    assert checked >= 100, f"only {checked} delegations checked; the scan is broken"
