"""
Filtered OpenAPI spec for the v1 API at /api/v1/openapi.json.

The human-facing Scalar docs viewer that used to live here (and at /api/docs)
has been retired: v2 is now the only public API reference (see api/v2/docs.py).
This module keeps serving only the raw, filtered v1 spec so existing partner
integrations (Postman imports, SDK generators, audit scripts) keep working.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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
