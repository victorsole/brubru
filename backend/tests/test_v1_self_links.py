"""v1 items fill the `self` their schema declares (17 Oct 2026).

`/api/v1/laws` and `/api/v1/resolutions` printed `self: null` on every item, on the list
and on the item route, while their docs said "follow it rather than building a URL": the
self-link middleware mapped v2 only. v1 is now mapped where the item schema declares
`self`, and there the field is filled, never added to a schema that lacks it.
"""
from core.self_links import attach_self, build_route_map

BASE = "https://api.example"
LAWS = "/api/v1/laws"
ROUTES = {LAWS: (LAWS + "/{celex}", "celex"),
          "/api/v1/resolutions": ("/api/v1/resolutions/{procedure_ref:path}", "procedure_ref")}


def test_v1_is_mapped_only_where_the_item_schema_declares_self():
    from main import app
    v1 = {k: v for k, v in build_route_map(app).items() if k.startswith("/api/v1/")}
    assert v1 == {
        "/api/v1/laws": ("/api/v1/laws/{celex}", "celex"),
        "/api/v1/resolutions": ("/api/v1/resolutions/{procedure_ref:path}", "procedure_ref"),
        "/api/v1/advisory-opinions/eesc": ("/api/v1/advisory-opinions/eesc/{item_id}", "item_id"),
        "/api/v1/advisory-opinions/cor": ("/api/v1/advisory-opinions/cor/{item_id}", "item_id"),
    }


def test_a_listed_law_gets_its_v1_link_escaped():
    page = {"data": [{"id": 6983, "celex": "32016R0679", "self": None},
                     {"id": 1, "celex": "32016R0679R(02)", "self": None}]}
    assert attach_self(page, BASE, ROUTES, LAWS) is True
    assert [it["self"] for it in page["data"]] == [BASE + "/api/v1/laws/32016R0679",
                                                   BASE + "/api/v1/laws/32016R0679R%2802%29"]


def test_v1_fills_a_declared_field_and_never_adds_one():
    page = {"data": [{"id": 1, "celex": "32016R0679"}]}  # a schema without `self`
    assert attach_self(page, BASE, ROUTES, LAWS) is False and "self" not in page["data"][0]


def test_a_link_set_by_the_handler_stays():
    page = {"data": [{"id": 1, "celex": "32016R0679", "self": "https://elsewhere/x"}]}
    attach_self(page, BASE, ROUTES, LAWS)
    assert page["data"][0]["self"] == "https://elsewhere/x"


def test_the_v1_item_reads_the_link_the_list_gives_it():
    one = {"id": 6983, "celex": "32016R0679", "self": None}
    assert attach_self(one, BASE, ROUTES, LAWS + "/6983") is True  # fetched by id
    assert one["self"] == BASE + "/api/v1/laws/32016R0679"
    res = {"id": "7fc220ce", "procedure_ref": "2025/2125(INI)", "self": None}
    attach_self(res, BASE, ROUTES, "/api/v1/resolutions/2025/2125(INI)")
    assert res["self"] == BASE + "/api/v1/resolutions/2025%2F2125%28INI%29"
