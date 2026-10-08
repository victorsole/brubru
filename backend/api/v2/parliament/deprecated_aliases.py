"""Deprecated aliases for three renamed European Parliament paths (8 Oct 2026).

The names read as if they served the same thing, so they were renamed by what ONE ROW
is, as one lifecycle (tabled -> adopted):

    /texts-submitted -> /plenary-tabled-texts    a document put to a plenary vote
    /texts-adopted   -> /plenary-adopted-texts   a text the plenary adopted (P10_TA...)
    /resolutions     -> /resolution-procedures   one INI / RSP / INL procedure and its outcome

The old paths keep answering for 12 months, with the same payload, because clients
(GovClipping) sync them. Each alias is the SAME endpoint function registered a second
time, so the two can never drift, plus three standard headers:
    Deprecation: @<epoch of 8 Oct 2026>                     (RFC 9745)
    Sunset: <8 Oct 2027>                                    (RFC 8594)
    Link: </api/v2/parliament/<new path>>; rel="successor-version"
and `deprecated: true` in the OpenAPI document.
Hand-written (not generated): the generated modules carry the new prefixes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.routing import APIRoute

DEPRECATED_ON = datetime(2026, 10, 8, tzinfo=timezone.utc)
SUNSET_ON = datetime(2027, 10, 8, tzinfo=timezone.utc)
_DEPRECATION = f"@{int(DEPRECATED_ON.timestamp())}"
_SUNSET = format_datetime(SUNSET_ON, usegmt=True)


def _headers(old_prefix: str, new_prefix: str):
    """The successor is the request's own path with the new name, so a lookup alias
    links to the real address, not to the route template."""
    old_full, new_full = f"/api/v2/parliament{old_prefix}", f"/api/v2/parliament{new_prefix}"

    async def _set(request: Request, response: Response) -> None:
        path = request.url.path
        successor = new_full + path[len(old_full):] if path.startswith(old_full) else new_full
        response.headers["Deprecation"] = _DEPRECATION
        response.headers["Sunset"] = _SUNSET
        response.headers["Link"] = f'<{successor}>; rel="successor-version"'
    return _set


def alias_of(new_router: APIRouter, old_prefix: str) -> APIRouter:
    """Every route of `new_router`, also served under `old_prefix`, marked deprecated."""
    new_prefix = new_router.prefix
    legacy = APIRouter(prefix=old_prefix, tags=[f"v2-parliament{old_prefix}-deprecated"])
    for route in new_router.routes:
        if not isinstance(route, APIRoute):
            continue
        sub = route.path[len(new_prefix):]
        successor = f"/api/v2/parliament{new_prefix}{sub}"
        note = (f"**Deprecated on 8 Oct 2026: renamed to `{successor}`.** This path answers "
                f"the same data until 8 Oct 2027 (`Sunset` header), then stops.\n\n")
        legacy.add_api_route(
            sub,
            route.endpoint,
            methods=sorted(route.methods),
            response_model=route.response_model,
            summary=f"[Deprecated] {route.summary or ''}".strip(),
            description=note + (route.description or ""),
            dependencies=[Depends(_headers(old_prefix, new_prefix))],
            deprecated=True,
            name=f"{route.name}_deprecated_alias",
        )
    return legacy
