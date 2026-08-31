"""Attach a `self` URL to every item of a v2 collection response.

One middleware rather than 429 handler edits, for the same reason the identifier
resolver is one function: the 660 routes built by a single factory are mutually
consistent, and the 76 written by hand use 25 different conventions. A property
that must hold everywhere belongs in one place.

It only touches 200 JSON responses on `/api/v2/` GET collections that the route
map recognises, and it is wrapped so that a failure can never break a response --
a missing `self` is a smaller problem than a 500.

Ordering: added AFTER the tabular-export middleware so it runs INSIDE it, and the
`self` field is therefore present in a CSV/Excel export too.
"""
from __future__ import annotations

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.self_links import attach_self

logger = logging.getLogger(__name__)

_DROP_HEADERS = {"content-length", "content-encoding"}


class SelfLinkMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, route_map_factory=None):
        super().__init__(app)
        # Two traps here, both hit on the way in:
        #  1. `app` is the NEXT middleware in the stack, not the FastAPI
        #     instance, so the route table cannot be read from it.
        #  2. Middleware is registered BEFORE the routers are included, so a map
        #     built at registration time is empty. Hence a factory, called once
        #     on the first request, when the route table is complete.
        self._factory = route_map_factory
        self._route_map = None

    @property
    def route_map(self):
        if self._route_map is None:
            self._route_map = (self._factory() if self._factory else {}) or {}
            logger.info("[self-links] %d v2 collections mapped to an item route",
                        len(self._route_map))
        return self._route_map

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method != "GET" or path not in self.route_map:
            return await call_next(request)

        response = await call_next(request)
        if response.status_code != 200:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        headers = {k: v for k, v in response.headers.items()
                   if k.lower() not in _DROP_HEADERS}
        media = response.media_type or response.headers.get("content-type", "")
        if "json" not in (media or ""):
            return Response(content=body, status_code=response.status_code,
                            headers=headers, media_type=response.media_type)
        try:
            payload = json.loads(body)
            base = str(request.base_url)
            if attach_self(payload, base, self.route_map, path):
                body = json.dumps(payload, default=str).encode()
        except Exception as exc:  # noqa: BLE001 - a self link is never worth a 500
            logger.warning("[self-links] %s: %s: %s", path, type(exc).__name__, exc)

        return Response(content=body, status_code=response.status_code,
                        headers=headers, media_type=response.media_type)
