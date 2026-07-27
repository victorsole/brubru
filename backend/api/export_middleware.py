"""
Tabular-export middleware. When a GET on an /api/ route carries ?format=csv or ?format=xlsx,
run the endpoint as normal (so auth, scope, rate-limit and billing all apply exactly as for
JSON), then transform the JSON list response into a downloadable CSV / Excel file.

Only fires when the caller explicitly asks (format param present) and the response is a 200
JSON list envelope — otherwise the response passes through untouched, so zero impact on
normal traffic. See services/export_tabular.py for the flatten/serialise rules.
"""
from __future__ import annotations

import json

import anyio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.export_tabular import CONTENT_TYPES, extract_records, serialize

_FORMATS = {"csv", "xlsx"}
_DROP_HEADERS = {"content-length", "content-encoding", "content-type"}


class TabularExportMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        fmt = request.query_params.get("format")
        if (
            fmt not in _FORMATS
            or request.method != "GET"
            or not request.url.path.startswith("/api/")
        ):
            return await call_next(request)

        response = await call_next(request)

        # collect the body regardless (we consumed the iterator by reading it)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        passthrough_headers = {
            k: v for k, v in response.headers.items() if k.lower() not in _DROP_HEADERS
        }

        # only transform a successful JSON list; else hand the original body back
        if response.status_code != 200 or "application/json" not in response.headers.get("content-type", ""):
            return Response(content=body, status_code=response.status_code,
                            media_type=response.headers.get("content-type"), headers=passthrough_headers)
        try:
            records = extract_records(json.loads(body))
        except Exception:
            records = None
        if records is None:
            return Response(content=body, status_code=200, media_type="application/json",
                            headers=passthrough_headers)

        # serialise off the event loop — openpyxl/csv on a big export is CPU-bound and
        # would otherwise block the single worker (the documented event-loop-starvation
        # pattern behind the prod 502 freezes). If it fails (an un-encodable value),
        # degrade gracefully to the JSON body rather than a 500.
        try:
            data = await anyio.to_thread.run_sync(serialize, records, fmt)
        except Exception:
            return Response(content=body, status_code=200, media_type="application/json",
                            headers=passthrough_headers)
        fname = (request.url.path.strip("/").split("/")[-1] or "export").replace(".", "_")
        passthrough_headers["Content-Disposition"] = f'attachment; filename="{fname}.{fmt}"'
        passthrough_headers["X-Export-Rows"] = str(len(records))
        return Response(content=data, status_code=200, media_type=CONTENT_TYPES[fmt],
                        headers=passthrough_headers)
