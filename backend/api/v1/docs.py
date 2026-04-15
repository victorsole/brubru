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
    summary="Scalar API reference page for /api/v1/*",
    include_in_schema=False,
)
def scalar_docs() -> HTMLResponse:
    return HTMLResponse(content=_SCALAR_HTML)
