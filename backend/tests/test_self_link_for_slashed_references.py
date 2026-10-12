"""A detail response's `self` when the identifier contains a slash (12 Oct 2026).

The list gave every resolution procedure a `self` link; the item route answered
`self: null`, because the middleware took an item to be ONE segment below its collection
and `/resolution-procedures/2026/2561(RSP)` is three."""
from core.self_links import attach_self, collection_of

BASE = "https://api.example"
COLL = "/api/v2/parliament/resolution-procedures"
ROUTES = {
    COLL: (COLL + "/{procedure_ref:path}", "procedure_ref"),
    "/api/v2/legislative/eur-lex/laws": ("/api/v2/legislative/eur-lex/laws/{celex}", "celex"),
}
CANONICAL = BASE + COLL + "/2026%2F2561%28RSP%29"


def test_a_reference_with_slashes_still_belongs_to_its_collection():
    assert collection_of(COLL + "/2026/2561(RSP)", ROUTES) == COLL
    assert collection_of(COLL + "/7fc220ce-57b5-4476-9075-99bdb9e20ace", ROUTES) == COLL


def test_a_sub_resource_of_a_plain_item_route_stays_out():
    assert collection_of("/api/v2/legislative/eur-lex/laws/32016R0679", ROUTES) == "/api/v2/legislative/eur-lex/laws"
    assert collection_of("/api/v2/legislative/eur-lex/laws/32016R0679/text", ROUTES) is None
    assert collection_of("/api/v2/somewhere/else", ROUTES) is None


def test_the_item_carries_the_same_link_the_list_gives_it():
    listed = {"data": [{"procedure_ref": "2026/2561(RSP)", "self": None}]}
    attach_self(listed, BASE, ROUTES, COLL)
    one = {"procedure_ref": "2026/2561(RSP)", "id": "7fc220ce", "self": None}
    assert attach_self(one, BASE, ROUTES, COLL + "/2026/2561(RSP)") is True
    assert one["self"] == listed["data"][0]["self"] == CANONICAL


def test_fetched_by_id_the_item_still_points_at_its_canonical_link():
    one = {"procedure_ref": "2026/2561(RSP)", "id": "7fc220ce", "self": None}
    attach_self(one, BASE, ROUTES, COLL + "/7fc220ce-57b5-4476-9075-99bdb9e20ace")
    assert one["self"] == CANONICAL


def test_a_self_set_by_the_handler_is_kept_and_an_unknown_path_falls_back_to_the_callers_url():
    kept = {"procedure_ref": "x", "self": "https://kept"}
    assert attach_self(kept, BASE, ROUTES, COLL + "/x") is False and kept["self"] == "https://kept"
    other = {"name": "n", "self": None}
    attach_self(other, BASE, ROUTES, "/api/v2/unmapped/thing")
    assert other["self"] == BASE + "/api/v2/unmapped/thing"
