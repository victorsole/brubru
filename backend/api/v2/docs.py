"""
Scalar-powered API reference at /api/docs (v2 — the canonical public surface).

Serves an HTML page that loads the official Scalar viewer from CDN and points
it at the FastAPI-generated OpenAPI spec at /api/v2/openapi.json, restricted to
/api/v2/* operations by a filter applied server-side.

This is the ONLY API reference Brubru exposes to the public: the institution-based
v2 surface. The legacy v1 viewer has been retired (its raw spec stays available at
/api/v1/openapi.json for existing integrations, but it is no longer linked).
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["v2-docs"])


@router.get(
    "/openapi.json",
    include_in_schema=False,
    summary="OpenAPI 3.1 spec for the v2 API — filtered to /api/v2/* paths only",
    description="""**What it does**
Returns the OpenAPI 3.1 specification for the v2 API, filtered to only include `/api/v2/*` operations. Internal Brubru routes are excluded. This is the source spec that powers the Scalar docs viewer at `/api/docs` and that partners can import into Postman / Insomnia / their own SDK generators.

**When to use it**
For OpenAPI tooling — import into Postman to auto-generate a collection, generate a client SDK with openapi-generator, or render an alternative docs viewer (Swagger UI, RapiDoc, Redoc). Internal endpoint hidden from the public schema.

**Input**
No parameters. The endpoint hides itself from the OpenAPI spec (`include_in_schema=False`).

**Try it**
```
GET /api/v2/openapi.json
```

**You get back**
A standard OpenAPI 3.1 JSON spec with `info`, `servers`, `paths` (only `/api/v2/*`), `components`, `tags` (only `v2-*`).

**Data freshness**
Live — auto-generated from the FastAPI router at request time. Reflects whatever code is deployed.""",
)
def v2_openapi(request: Request) -> JSONResponse:
    """OpenAPI spec filtered to /api/v2/* paths only.

    Partners should not see internal Brubru routes, only the paid surface.
    """
    full = request.app.openapi()
    paths = {p: v for p, v in full.get("paths", {}).items() if p.startswith("/api/v2/")}
    info = dict(full.get("info", {}))
    info["title"] = "Brubru EU Data API"
    info["description"] = (
        "Public paid REST surface for the Brubru Data Provider, organised by EU "
        "institution (Parliament, Commission, Council, European Council, Eurogroup) "
        "plus legislative, funding, open-data and proprietary collections. "
        "Authentication via the X-API-Key header (Professional subscription required). "
        "60 req/min soft rate limit per key."
    )
    info["version"] = "v2"
    spec = {
        "openapi": full.get("openapi", "3.1.0"),
        "info": info,
        "servers": [{"url": str(request.base_url).rstrip("/"), "description": "Current host"}],
        "paths": paths,
        "components": full.get("components", {}),
        "tags": [t for t in full.get("tags", []) if str(t.get("name", "")).startswith("v2-")],
    }
    return JSONResponse(content=spec)


_SCALAR_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Brubru EU Data API &mdash; Reference</title>
    <meta name="description" content="Brubru Data Provider API reference. EU legislation, legislative procedures, Parliament, Commission, Council, funding, open data and proprietary EU intelligence, organised by institution. Professional subscription required." />
    <link rel="icon" type="image/png" href="/favicon.png" />
    <style>
        body { margin: 0; background: #fff; }
    </style>
</head>
<body>
    <script id="api-reference" data-url="/api/v2/openapi.json"></script>
    <script>
      // Scalar config: point to our v2 OpenAPI spec, apply a light theme.
      window.configuration = {
        theme: "default",
        layout: "modern",
        hideDownloadButton: false,
        customCss: ""
      };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
"""


@router.get(
    "/docs",
    response_class=HTMLResponse,
    summary="Interactive API reference page for /api/v2/* — powered by Scalar",
    include_in_schema=False,
    description="""**What it does**
Renders a Scalar-powered HTML reference page for the v2 API. Scalar is a modern OpenAPI viewer (lighter + nicer than Swagger UI) that lets developers browse endpoints, try them inline, and view request/response schemas.

**When to use it**
The recommended discovery surface for partners exploring Brubru's API. Bookmarkable URL: `https://brubru-production.up.railway.app/api/docs`. For programmatic access to the underlying OpenAPI spec, hit `/api/v2/openapi.json` instead.

**Input**
No parameters. Returns HTML.

**Try it**
```
GET /api/docs
```

**You get back**
A complete HTML page that loads the Scalar viewer from CDN and points it at `/api/v2/openapi.json`. The viewer renders client-side.

**Data freshness**
Static HTML shell (changes only on Brubru redeploy). The OpenAPI spec it loads is auto-generated live per request.""",
)
def scalar_docs_v2() -> HTMLResponse:
    return HTMLResponse(content=_SCALAR_HTML)
