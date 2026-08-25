"""
Canonical error envelope + X-Request-Id middleware for /api/v1/*.

Every 4xx/5xx response on v1 is wrapped to:
    {"error": "human message", "reason_code": "auth_missing_key", "request_id": "uuid4"}

reason_code is a stable machine-readable identifier partners can switch on.
request_id equals the X-Request-Id response header for traceability.

An error body deliberately carries NO `data` key
------------------------------------------------
This is load-bearing, not an oversight, and it was nearly changed the wrong way.

A caller reading a list endpoint typically writes `len(body.get("data") or [])`.
On an error body that yields 0, which is indistinguishable from a successful but
empty result -- twice in August 2026 an unauthenticated call to
`/api/v2/news/all` was read as "no EU news today" for exactly this reason.

The instinct is to add `data: []` to error bodies so the shape is uniform. That
makes it strictly WORSE: today `body.get("data")` returns None on an error and []
on a genuinely empty result, so the two ARE distinguishable. Adding `data: []`
would erase the only signal a naive client has.

The contract is therefore:
    success -> `data` is always present (possibly [])
    error   -> `data` is always ABSENT; `error` and `reason_code` are present

Check the HTTP status, or `"error" in body`, or `body.get("data") is None`.
`tests/test_v1_error_envelope_shape.py` pins all of this.
"""

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


REASON_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    422: "invalid_query",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
}


def _build_error_body(message: str, reason_code: str, request_id: str, **extra: Any) -> dict:
    body: dict = {"error": message, "reason_code": reason_code, "request_id": request_id}
    body.update({k: v for k, v in extra.items() if v is not None})
    return body


def _unwrap_detail(detail: Any, status_code: int, request_id: str) -> dict:
    """Convert FastAPI's flexible `detail` into our canonical envelope."""
    default_reason = REASON_CODE_BY_STATUS.get(status_code, f"http_{status_code}")
    if isinstance(detail, dict):
        message = detail.get("error") or detail.get("detail") or detail.get("message") or ""
        reason = detail.get("reason_code") or default_reason
        extra = {k: v for k, v in detail.items() if k not in {"error", "detail", "message", "reason_code"}}
        return _build_error_body(message, reason, request_id, **extra)
    if isinstance(detail, str):
        return _build_error_body(detail, default_reason, request_id)
    return _build_error_body(str(detail) if detail else f"HTTP {status_code}", default_reason, request_id)


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if rid:
        return rid
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    return rid


def register_v1_error_handlers(app: FastAPI) -> None:
    """Register exception handlers + X-Request-Id middleware for /api/v1/*."""

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):
        # Generate or accept inbound request id
        inbound = request.headers.get("X-Request-Id")
        rid = inbound if inbound and len(inbound) <= 64 else str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(request: Request, exc: StarletteHTTPException):
        # Only wrap the paid Data Provider surface (/api/v1/* + /api/v2/*);
        # leave legacy app routes untouched.
        if not request.url.path.startswith(("/api/v1/", "/api/v2/")):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=dict(exc.headers or {}))
        rid = _request_id(request)
        body = _unwrap_detail(exc.detail, exc.status_code, rid)
        return JSONResponse(status_code=exc.status_code, content=body, headers=dict(exc.headers or {}))

    @app.exception_handler(RequestValidationError)
    async def _validation_exc_handler(request: Request, exc: RequestValidationError):
        if not request.url.path.startswith(("/api/v1/", "/api/v2/")):
            # exc.errors() carries the offending INPUT, and on a multipart
            # endpoint that input is an UploadFile, which json cannot encode.
            # The handler then raised inside itself and the caller got an opaque
            # 500 with no field named, on every validation error of every
            # file-upload route in the legacy app. Drop the input; the location
            # and the message are what a caller can act on.
            safe = [
                {k: v for k, v in err.items() if k not in ("input", "ctx")}
                for err in exc.errors()
            ]
            return JSONResponse(status_code=422, content={"detail": jsonable_encoder(safe)})
        rid = _request_id(request)
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p not in ("query", "body", "path"))
        message = first.get("msg", "Invalid request parameters")
        body = _build_error_body(
            f"Invalid query: {field}: {message}" if field else message,
            "invalid_query",
            rid,
            field=field or None,
            errors=exc.errors(),
        )
        return JSONResponse(status_code=422, content=body)
