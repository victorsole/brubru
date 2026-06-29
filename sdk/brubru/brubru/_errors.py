"""Typed errors. Every non-2xx response maps to one of these so callers can
branch on the failure (auth vs scope vs payment vs rate limit) instead of
parsing status codes by hand. All inherit BrubruError."""
from __future__ import annotations

from typing import Any, Optional


class BrubruError(Exception):
    """Base for every error raised by the client."""

    def __init__(self, message: str, *, status: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class AuthError(BrubruError):
    """401: missing, malformed or unknown API key."""


class PaymentRequiredError(BrubruError):
    """402: the key is valid but out of credits / unfunded."""


class ScopeError(BrubruError):
    """403: the key lacks the scope this endpoint needs."""


class NotFoundError(BrubruError):
    """404: no such resource (e.g. unknown post id)."""


class ValidationError(BrubruError):
    """422: the query parameters did not validate."""


class RateLimitError(BrubruError):
    """429: too many requests for the key's tier. Back off and retry."""


class ServerError(BrubruError):
    """5xx: upstream/server failure (the 502 'could not fetch' included).

    These are the metered-refund path server-side, so a retry is reasonable."""


_STATUS_MAP = {
    401: AuthError,
    402: PaymentRequiredError,
    403: ScopeError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
}


def error_for_status(status: int, payload: Any) -> BrubruError:
    """Build the right exception for an HTTP status and decoded body."""
    cls = _STATUS_MAP.get(status)
    if cls is None:
        cls = ServerError if status >= 500 else BrubruError
    # FastAPI puts the human message under "detail"; fall back to the raw body.
    detail = None
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
    msg = f"HTTP {status}: {detail or payload or cls.__name__}"
    return cls(msg, status=status, payload=payload)
