"""Phase 2 of the funding standard: every funding list answers to the same parameters and fields.

Read from the app's own route table (the OpenAPI it serves), so a list added later is checked too.
"""
import pathlib
import sys

from fastapi import FastAPI

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

FUNDING = "/api/v2/funding/"


def _spec(router):
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    return app.openapi()


def _lists(spec):
    """The funding lists: GET routes whose last segment is not a path parameter; the files of a
    procedure (`.../{item_id}/documents`) are listed apart."""
    items, files = {}, {}
    for path, methods in spec["paths"].items():
        if not path.startswith(FUNDING) or "get" not in methods or path.rstrip("/").split("/")[-1].startswith("{"):
            continue
        params = {p["name"]: p for p in methods["get"].get("parameters", []) if p.get("in") == "query"}
        (files if path.endswith("/documents") else items)[path] = params
    return items, files


def test_every_funding_list_pages_by_50_up_to_200_with_bodies_on():
    from api.v2.funding import router
    items, files = _lists(_spec(router))
    assert len(items) >= 66, len(items)               # 66 item lists on 27 Oct 2026, beside 14 file lists
    wrong = {}
    for path, params in items.items():
        limit = params.get("limit", {}).get("schema", {})
        body = params.get("include_body", {}).get("schema", {})
        problems = []
        if limit.get("default") != 50:
            problems.append(f"limit default {limit.get('default')}")
        if (limit.get("maximum") or 0) < 200:
            problems.append(f"limit max {limit.get('maximum')}")
        if "include_body" not in params:
            problems.append("no include_body")
        elif body.get("default") is not True:
            problems.append(f"include_body default {body.get('default')}")
        if problems:
            wrong[path] = problems
    assert wrong == {}
    # A procedure's files keep bodies off: an extracted file text reaches 5 MB (27 Oct 2026).
    for path, params in files.items():
        assert params["include_body"]["schema"].get("default") is False, path


def test_a_folder_outside_funding_keeps_its_own_defaults():
    from fastapi import APIRouter
    from api.v2.economy_endpoints import register_resource
    router = APIRouter()
    register_resource(router, body_code="x", item_type="news", slug="x-news", noun="news items", body_name="X",
                      acronym="X", source="its site.", tag="v2-x")
    spec = _spec(router)
    params = {p["name"]: p for p in spec["paths"]["/api/v2/x-news"]["get"]["parameters"] if p.get("in") == "query"}
    assert params["limit"]["schema"].get("default") == 20 and params["limit"]["schema"].get("maximum") == 100
    assert params["include_body"]["schema"].get("default") is False


def test_include_body_false_takes_the_bodies_off_a_list_that_always_composes_them():
    from types import SimpleNamespace
    from api.v2.funding._standard import without_bodies
    env = SimpleNamespace(data=[SimpleNamespace(body_txt="t", body_html="<p>t</p>", title="x"), {"body_txt": "t", "title": "y"}])
    assert without_bodies(env, True).data[0].body_txt == "t"
    out = without_bodies(env, False)
    assert out.data[0].body_txt is None and out.data[0].body_html is None and out.data[0].title == "x"
    assert out.data[1]["body_txt"] is None and out.data[1]["title"] == "y"
