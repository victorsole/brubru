"""The live conformance checker (scripts/check_funding_standard.py, Phase 2 step 7, 29 Oct 2026) flags
each rule it claims to check: a conforming list passes, and each broken variant fails on its rule."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_funding_standard", Path(__file__).resolve().parents[1] / "scripts" / "check_funding_standard.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

BASE = "https://api.example"
PATH = "/api/v2/funding/demo"
OP = {"parameters": [{"name": n} for n in C.EVERY_LIST + ("min_amount_eur", "max_amount_eur")]}


def _item(n, **kw):
    it = {"id": n, "self": f"{BASE}{PATH}/{n}", "public_url": f"https://src.example/{n}", "item_type": "tender",
          "title": "T", "summary": "S", "status": "open", "body_code": "x", "body_name": "X", "amount_eur": 1000.0 * n,
          "creation_date": "2026-01-01T00:00:00Z", "updated_date": f"2026-10-{10 + n:02d}T00:00:00Z",
          "body_txt": "text", "body_html": "<p>text</p>"}
    it.update(kw)
    return it


class FakeApi(C.Api):
    """A list of 4 items that follows every rule, unless a flaw is named."""
    def __init__(self, flaw=None):
        super().__init__(BASE, "k")
        self.flaw = flaw

    def get(self, path, **params):
        self.calls += 1
        f = self.flaw
        items = [_item(n) for n in range(1, 5)]
        if f == "no_self":
            items[1]["self"] = None
        if f == "created_after_updated":
            items[2]["creation_date"] = "2026-12-31T00:00:00Z"
        if f == "no_shared":
            del items[0]["body_name"]
        if f == "bad_status":
            items[0]["status"] = "awarded"
        if path.startswith(BASE + PATH + "/"):                     # the item route
            n = int(path.rsplit("/", 1)[1])
            return (404, None) if f == "self_404" else (200, _item(n))
        limit = int(params.get("limit", 100 if f == "default_100" else 50))
        top = 500 if f == "no_max" else 200
        if limit > top:
            return 422, {"detail": "limit"}
        if params.get("order") == "zz_not_an_order":
            return (200, {"data": []}) if f == "order_accepted" else (400, {"detail": "order"})
        if params.get("include_body") == "false" and f != "body_stays":
            items = [{**i, "body_txt": None, "body_html": None} for i in items]
        if "min_amount_eur" in params and f != "min_leaks":
            items = [i for i in items if i["amount_eur"] >= float(params["min_amount_eur"])]
        if "updated_from" in params and f != "window_leaks":
            items = [i for i in items if i["updated_date"][:19] >= params["updated_from"][:19]]
        env = {"data": items[:limit], "limit": limit, "total": len(items)}
        if "zz_unknown_parameter" in params and f != "unknown_silent":
            env["ignored_parameters"] = ["zz_unknown_parameter"]
        return 200, env


def test_a_conforming_list_passes():
    assert C.check_list(FakeApi(), PATH, OP) == []


@pytest.mark.parametrize("flaw, rule", [
    ("no_self", "datapoints"), ("created_after_updated", "datapoints"), ("no_shared", "shared"),
    ("bad_status", "shared"), ("self_404", "self"), ("default_100", "defaults"), ("no_max", "defaults"),
    ("body_stays", "defaults"), ("order_accepted", "parameters"), ("unknown_silent", "parameters"),
    ("min_leaks", "parameters"), ("window_leaks", "parameters"),
])
def test_each_broken_rule_is_flagged(flaw, rule):
    problems = C.check_list(FakeApi(flaw), PATH, OP)
    assert rule in {r for r, _ in problems}, (flaw, problems)


def test_a_missing_standard_parameter_is_flagged_unless_a_rule_exempts_it():
    op = {"parameters": [{"name": n} for n in C.EVERY_LIST if n != "order"]}
    assert ("every list", "no `order` parameter") in C.check_list(FakeApi(), PATH, op)
    assert "programmes" in C.EXEMPT and "order" in C.EXEMPT["programmes"][0]
