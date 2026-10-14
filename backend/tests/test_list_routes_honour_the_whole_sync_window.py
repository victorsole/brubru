"""Every list route that takes `updated_from` also honours `updated_to` (14 Oct 2026).

12 of 56 v2 list routes accepted updated_from and silently ignored updated_to: a
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
    (w5_endpoints, ("list_tenders",)),
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
