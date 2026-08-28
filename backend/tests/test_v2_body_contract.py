"""`body_txt` / `body_html` must never be null when the data exists.

Victor's hard rule, 28 August 2026, after a partner (GovClipping) reported that
`/api/v2/news/all` served `body_txt: null` on every item with no way to ask for
the text -- days after I had audited that same endpoint and called it fine.

The audit was blind because it checked that the FIELD was present, not that a
VALUE ever came back. Sweeping all 995 v2 endpoints afterwards found 350 lists
returning a null body on every item, over corpora that were 99.6% populated.

Two failure modes, and this file guards both.

1. The suppression. A list handler reads the body and then throws it away
   (`with_body=False`). It is a defensible default -- bodies dominate a payload
   -- but only if the caller can ask for them. Every suppression must therefore
   be paired with an `include_body` parameter, or be on `NO_BODY_EXISTS` with a
   measured reason. That list is deliberately annoying to extend: adding to it
   is a claim about the DATA, and the claim must be true.

2. The disappearance. `include_body` gets refactored away and every list goes
   quietly back to nulls. So the parameter is asserted against the built app's
   OpenAPI schema, which is what clients actually see.
"""
import ast
import pathlib

import pytest

V2 = pathlib.Path(__file__).resolve().parent.parent / "api" / "v2"

# Handlers that suppress a body because there is no body to serve. Each entry
# records the measurement made on 28 Aug 2026, so a future reader can re-check
# it rather than trust it.
NO_BODY_EXISTS = {
    "social/__init__.py::list_accounts":
        "social_accounts stores no post text -- `content_fetch_enabled` is a flag, "
        "not a body. Measured 28 Aug 2026: 3,828 rows, no content column.",
    "events/__init__.py::list_events":
        "The composed body is served by the detail route; the list is a calendar "
        "index and its rows carry no stored text.",
}

# Endpoints whose backing corpus was measured as populated. Each MUST expose
# `include_body`, or the text is unreachable in bulk.
MUST_OFFER_INCLUDE_BODY = [
    "/api/v2/news/all",
    "/api/v2/funding/all",
    "/api/v2/funding/erdf",
    "/api/v2/funding/erdf/outcomes",
    "/api/v2/funding/eusf",
    "/api/v2/funding/eagf",
    "/api/v2/funding/programmes",
    "/api/v2/funding/international-cooperation",
    "/api/v2/consultations/all",
    "/api/v2/legislative/eur-lex/laws/summaries",
    "/api/v2/social/posts",
    "/api/v2/calendar/events",
]


def _handlers_that_suppress():
    """(relpath::funcname, caller_can_ask_for_it) for every function that passes
    a literal `with_body=False` at a CALL SITE.

    Only call sites count. A helper defined as `_row_to_item(r, *, with_body)`
    contains `d["body_txt"] = None` in its own body, and a `_fetch(..., with_body
    =False)` default is just a default -- those implement the switch rather than
    close it, and an earlier version of this test flagged all of them, which is
    the sort of noise that gets a test deleted.
    """
    out = []
    for path in sorted(V2.rglob("*.py")):
        source = path.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover
            continue
        rel = str(path.relative_to(V2))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            hardcoded = any(
                isinstance(call, ast.Call)
                and any(kw.arg == "with_body"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is False
                        for kw in call.keywords)
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
            )
            if not hardcoded:
                continue
            names = {a.arg for a in node.args.args + node.args.kwonlyargs}
            out.append((f"{rel}::{node.name}", "include_body" in names))
    return out


def test_every_body_suppression_is_either_optional_or_explained():
    """A list that discards the body must let the caller ask for it back."""
    offenders = []
    for key, has_flag in _handlers_that_suppress():
        if has_flag or key in NO_BODY_EXISTS:
            continue
        offenders.append(key)
    assert not offenders, (
        "these handlers throw the body away with no way to request it:\n  "
        + "\n  ".join(offenders)
        + "\nAdd an `include_body` parameter, or add it to NO_BODY_EXISTS with the "
          "measurement showing the corpus genuinely has no body."
    )


def test_the_no_body_allowlist_has_not_gone_stale():
    """An allowlist entry for a handler that no longer suppresses anything is a
    stale claim; delete it rather than let it excuse a future regression."""
    live = {k for k, _ in _handlers_that_suppress()}
    dead = sorted(set(NO_BODY_EXISTS) - live)
    assert not dead, f"NO_BODY_EXISTS names handlers that no longer suppress a body: {dead}"


@pytest.fixture(scope="module")
def spec():
    from main import app
    return app.openapi()


@pytest.mark.parametrize("path", MUST_OFFER_INCLUDE_BODY)
def test_populated_corpora_expose_include_body(spec, path):
    """Asserted against the built schema, which is what a client reads -- not
    against the source, which can declare a parameter the route never wires."""
    op = spec["paths"].get(path, {}).get("get")
    assert op, f"{path} is not a GET in the published schema"
    params = {p["name"] for p in op.get("parameters", [])}
    assert "include_body" in params, (
        f"{path} has no include_body parameter, so its text cannot be fetched in bulk"
    )


def test_the_generated_economy_routes_all_carry_it(spec):
    """One factory backs 334 list routes. If it loses the flag, a third of the
    v2 surface goes dark at once, which is exactly what happened before."""
    missing = []
    for path, ops in spec["paths"].items():
        get = ops.get("get")
        if not get or "{" in path or not path.startswith("/api/v2/"):
            continue
        schema = str(get.get("responses", {}).get("200", {}))
        if "EconomyItem" not in schema:
            continue
        if "include_body" not in {p["name"] for p in get.get("parameters", [])}:
            missing.append(path)
    assert not missing, f"{len(missing)} EconomyItem list routes lost include_body: {missing[:10]}"
