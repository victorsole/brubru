"""The API's bundles and the routes in each (3 Nov 2026). Public and free: a user chooses from these before having a key."""
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Path, Request, Response
from fastapi.routing import APIRoute

from services.api_keys.bundles import API_BUNDLES, bundles_of, get_bundle

router = APIRouter(tags=["v2-docs"])

# Not /api/console: SiteGround's edge resets any browser request whose path ends in /console.
_CONSOLE = "https://brubru.beresol.eu/api/try?bundle="
_routes_cache: List[dict] = []


def _routes(request: Request) -> List[dict]:
    """Every GET route of the deployed API with its bundles. The route table does not change while the app runs."""
    if not _routes_cache:
        for route in request.app.routes:
            if isinstance(route, APIRoute) and route.path.startswith("/api/v2/") and route.include_in_schema and "GET" in route.methods:
                _routes_cache.append({
                    "path": route.path,
                    "summary": route.summary or "",
                    "kind": "item" if "{" in route.path else "list",
                    "deprecated": bool(route.deprecated),
                    "bundles": bundles_of(route.path),
                })
        _routes_cache.sort(key=lambda r: r["path"])
    return _routes_cache


def _summary(bundle, routes: List[dict]) -> Dict[str, object]:
    inside = [r for r in routes if bundle.id in r["bundles"]]
    return {
        "id": bundle.id,
        "label": bundle.label,
        "description": bundle.description,
        "routes": len(inside),
        "lists": sum(1 for r in inside if r["kind"] == "list"),
        "self": f"/api/v2/bundles/{bundle.id}",
        "console_url": _CONSOLE + bundle.id,
    }


@router.get(
    "/bundles",
    summary="The API's bundles: groups of routes by what you want",
    description="""**What it does**
Lists the bundles the API is grouped into, such as Official Journal, Funding and procurement, or People and organisations, with how many routes each holds. A route can sit in several: an agency's news is both Agencies and News.

**When to use it**
To find where to start among more than a thousand routes, and to choose what a key should open: a key can be limited to the bundles you pick when you mint it.

**Input**
None. No API key is needed and the call is free.

**Try it**
`GET /api/v2/bundles`

**You get back**
`data`, one item per bundle: `id`, `label`, `description`, `routes`, `lists`, `self` (its route list) and `console_url`.""",
)
def api_bundles(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "public, max-age=3600"
    routes = _routes(request)
    return {"total": len(API_BUNDLES), "data": [_summary(b, routes) for b in API_BUNDLES]}


@router.get(
    "/bundles/{bundle_id}",
    summary="The routes in one bundle",
    description="""**What it does**
Lists every route in one bundle, each with what it serves and whether it is a list or a single item.

**When to use it**
When you know what you want, such as `funding-procurement`, and need the routes that serve it.

**Input**
`bundle_id` in the path: one of the ids from `GET /api/v2/bundles`. No API key is needed and the call is free.

**Try it**
`GET /api/v2/bundles/official-journal`

**You get back**
The bundle's `id`, `label`, `description`, `lists` and `console_url`, and `data`: one item per route with `path`, `summary`, `kind` (list or item), `deprecated` and `bundles` (all the bundles it sits in). `total` counts the routes.""",
)
def api_bundle(request: Request, response: Response, bundle_id: str = Path(..., description="The bundle's id, from GET /api/v2/bundles.")) -> dict:
    bundle = get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail={"error": f"No bundle called {bundle_id!r}. See /api/v2/bundles.", "reason_code": "not_found"})
    response.headers["Cache-Control"] = "public, max-age=3600"
    routes = _routes(request)
    summary = _summary(bundle, routes)
    inside = [r for r in routes if bundle.id in r["bundles"]]
    return {"id": bundle.id, "label": bundle.label, "description": bundle.description, "total": len(inside),
            "lists": summary["lists"], "console_url": summary["console_url"], "data": inside}
