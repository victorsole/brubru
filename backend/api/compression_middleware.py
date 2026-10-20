"""Gzip JSON responses inside the container, for clients that accept it (20 Oct 2026).

Why
---
Railway bills the bytes that LEAVE the container. Its edge gzips a response for a client
that asks, but after the container: we paid for every uncompressed byte. On 13-20 Oct 2026
that was 130 GB (USD 6.53 of a USD 10.22 bill), about 90% of it one partner's sync reading
API pages of 12-18 MB (implementing acts, EUR-Lex laws). At level 5 those pages are 5.8 to
10 times smaller (12.0 MB -> 2.05 MB, 18.1 MB -> 1.76 MB; about 0.2 s of CPU each).

What it touches, and what it never does
---------------------------------------
* Only `application/json` bodies, only when the request's Accept-Encoding allows gzip, and
  only from `minimum_size` bytes. Everything else passes through byte for byte.
* Never `text/event-stream`: /api/chat/stream is the only path the UI calls, and a buffered
  stream would arrive in one piece at the end. Never file downloads, CSV or Excel exports.
* The JSON body is collected before it is compressed. Every BaseHTTPMiddleware in the stack
  re-sends a finished response as a stream of chunks, so "is it streamed?" cannot be read
  from the messages; the content type is the test. JSON responses are built whole anyway.
* A large body is compressed in a worker thread, so a 15 MB page does not hold the event
  loop for the other requests.

Ordering: registered LAST in main.py, so it is the OUTERMOST layer and compresses the final
body, after the self links, the billing refund and the tabular export have read it as JSON.
"""
from __future__ import annotations

import gzip

import anyio
from starlette.datastructures import Headers, MutableHeaders

_THREAD_FROM = 256 * 1024


def accepts_gzip(accept_encoding: str) -> bool:
    """True when the header lists gzip (or *) without q=0."""
    for part in (accept_encoding or "").lower().split(","):
        coding, _, params = part.strip().partition(";")
        if coding.strip() not in ("gzip", "*"):
            continue
        q = params.replace(" ", "")
        if q.startswith("q="):
            try:
                if float(q[2:]) == 0:
                    continue
            except ValueError:
                continue
        return True
    return False


class JsonGzipMiddleware:
    def __init__(self, app, minimum_size: int = 1024, compresslevel: int = 5) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def __call__(self, scope, receive, send) -> None:
        if (scope["type"] != "http" or scope.get("method") == "HEAD"
                or not accepts_gzip(Headers(scope=scope).get("accept-encoding", ""))):
            await self.app(scope, receive, send)
            return

        start: dict | None = None
        chunks: list[bytes] = []
        passthrough = False

        async def send_wrapper(message) -> None:
            nonlocal start, passthrough
            kind = message["type"]
            if kind == "http.response.start":
                headers = Headers(raw=message.get("headers") or [])
                media = headers.get("content-type", "").split(";")[0].strip().lower()
                if (media != "application/json" or "content-encoding" in headers
                        or message.get("status") in (204, 304)):
                    passthrough = True
                    await send(message)
                else:
                    start = message
                return
            if kind != "http.response.body" or passthrough or start is None:
                await send(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return
            body = b"".join(chunks)
            headers = MutableHeaders(raw=list(start.get("headers") or []))
            headers.add_vary_header("Accept-Encoding")
            if len(body) >= self.minimum_size:
                if len(body) >= _THREAD_FROM:
                    body = await anyio.to_thread.run_sync(gzip.compress, body, self.compresslevel)
                else:
                    body = gzip.compress(body, self.compresslevel)
                headers["Content-Encoding"] = "gzip"
            headers["Content-Length"] = str(len(body))
            await send({**start, "headers": headers.raw})
            await send({"type": "http.response.body", "body": body, "more_body": False})

        await self.app(scope, receive, send_wrapper)
