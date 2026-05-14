"""
Scalar-powered API reference at /api/docs.

Serves an HTML page that loads the official Scalar viewer from CDN and points
it at the FastAPI-generated OpenAPI spec at /openapi.json, restricted to
/api/v1/* operations by a small JS filter baked into the page.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["v1-docs"])


@router.get(
    "/openapi.json",
    include_in_schema=False,
    summary="OpenAPI 3.1 spec for the v1 API — filtered to /api/v1/* paths only",
    description="""**What it does**
Returns the OpenAPI 3.1 specification for the v1 API, filtered to only include `/api/v1/*` operations. Internal Brubru routes are excluded. This is the source spec that powers the Scalar docs viewer at `/api/docs` and that partners can import into Postman / Insomnia / their own SDK generators.

**When to use it**
For OpenAPI tooling — import into Postman to auto-generate a collection, generate a client SDK with openapi-generator, or render an alternative docs viewer (Swagger UI, RapiDoc, Redoc). Internal endpoint hidden from the public schema.

**Input**
No parameters. The endpoint hides itself from the OpenAPI spec (`include_in_schema=False`).

**Try it**
```
GET /api/v1/openapi.json
```

**You get back**
A standard OpenAPI 3.1 JSON spec with `info`, `servers`, `paths` (only `/api/v1/*`), `components`, `tags` (only `v1-*`).

**Data freshness**
Live — auto-generated from the FastAPI router at request time. Reflects whatever code is deployed.""",
)
def v1_openapi(request: Request) -> JSONResponse:
    """OpenAPI spec filtered to /api/v1/* paths only.

    Partners should not see internal Brubru routes, only the paid surface.
    """
    full = request.app.openapi()
    paths = {p: v for p, v in full.get("paths", {}).items() if p.startswith("/api/v1/")}
    info = dict(full.get("info", {}))
    info["title"] = "Brubru EU Data API"
    info["description"] = (
        "Public paid REST surface for the Brubru Data Provider. Authentication via "
        "the X-API-Key header (Professional subscription required). 60 req/min soft rate limit per key."
    )
    info["version"] = "v1"
    spec = {
        "openapi": full.get("openapi", "3.1.0"),
        "info": info,
        "servers": [{"url": str(request.base_url).rstrip("/"), "description": "Current host"}],
        "paths": paths,
        "components": full.get("components", {}),
        "tags": [t for t in full.get("tags", []) if str(t.get("name", "")).startswith("v1-")],
    }
    return JSONResponse(content=spec)


_SCALAR_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Brubru EU Data API &mdash; Reference</title>
    <meta name="description" content="Brubru Data Provider API reference. 28,500+ EU laws, 1,200+ legislative procedures, consultations, commissioner agendas, legal-text intelligence. Professional subscription required." />
    <link rel="icon" type="image/png" href="/favicon.png" />
    <style>
        body { margin: 0; background: #fff; }
    </style>
</head>
<body>
    <script id="api-reference" data-url="/api/v1/openapi.json"></script>
    <script>
      // Scalar config: point to our v1 OpenAPI spec, apply a light theme.
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
    summary="Interactive API reference page for /api/v1/* — powered by Scalar",
    include_in_schema=False,
    description="""**What it does**
Renders a Scalar-powered HTML reference page for the v1 API. Scalar is a modern OpenAPI viewer (lighter + nicer than Swagger UI) that lets developers browse endpoints, try them inline, and view request/response schemas.

**When to use it**
The recommended discovery surface for partners exploring Brubru's API. Bookmarkable URL: `https://brubru-production.up.railway.app/api/docs`. For programmatic access to the underlying OpenAPI spec, hit `/api/v1/openapi.json` instead.

**Input**
No parameters. Returns HTML.

**Try it**
```
GET /api/docs
```

**You get back**
A complete HTML page that loads the Scalar viewer from CDN and points it at `/api/v1/openapi.json`. The viewer renders client-side.

**Data freshness**
Static HTML shell (changes only on Brubru redeploy). The OpenAPI spec it loads is auto-generated live per request.""",
)
def scalar_docs() -> HTMLResponse:
    return HTMLResponse(content=_SCALAR_HTML)
