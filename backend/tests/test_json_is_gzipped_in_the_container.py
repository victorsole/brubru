"""JSON leaves the container gzipped; streams and files are untouched (20 Oct 2026).

Railway bills the bytes that leave the container, and its edge gzipped only after them:
130 GB in a week, about 90% one partner's sync reading 12-18 MB pages. These check the
middleware on its own (behind a BaseHTTPMiddleware, which re-sends every response as
chunks, as the real stack does) and on the real app.
"""
import asyncio
import gzip
import json
import pathlib
import sys

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.compression_middleware import JsonGzipMiddleware, accepts_gzip  # noqa: E402

PAGE = {"data": [{"celex": f"32026R{n:04d}", "body_txt": "The Commission adopts. " * 40} for n in range(200)],
        "total": 6247, "page": 1}


def _app():
    app = FastAPI()

    @app.get("/page")
    def page():
        return PAGE

    @app.get("/small")
    def small():
        return {"ok": True}

    @app.get("/csv")
    def csv():
        return PlainTextResponse("a,b\n" * 5000, media_type="text/csv")

    @app.get("/pdf")
    def pdf():
        return Response(b"%PDF-1.7 " + b"x" * 50_000, media_type="application/pdf")

    @app.get("/stream")
    def stream():
        def events():
            for n in range(3):
                yield f"data: {n}\n\n"
        return StreamingResponse(events(), media_type="text/event-stream")

    @app.middleware("http")
    async def rate_limit_headers(request, call_next):   # the real stack has one of these
        response = await call_next(request)
        response.headers["X-Powered-By"] = "Brubru"
        return response

    app.add_middleware(JsonGzipMiddleware, minimum_size=1024, compresslevel=5)
    return app


def _raw_get(client, path, accept):
    # Read the bytes as sent: httpx would otherwise decompress them for us.
    with client.stream("GET", path, headers={"Accept-Encoding": accept}) as r:
        return r, b"".join(r.iter_raw())


def test_a_json_page_is_gzipped_when_the_client_accepts_it():
    client = TestClient(_app())
    r, raw = _raw_get(client, "/page", "gzip, deflate, br")
    assert r.headers["content-encoding"] == "gzip"
    assert int(r.headers["content-length"]) == len(raw)
    assert "Accept-Encoding" in r.headers["vary"]
    assert r.headers["x-powered-by"] == "Brubru"          # the inner middleware still ran
    assert json.loads(gzip.decompress(raw)) == PAGE
    assert len(raw) * 5 < len(json.dumps(PAGE))


def test_a_client_that_does_not_accept_gzip_gets_the_plain_body():
    client = TestClient(_app())
    for accept in ("identity", "gzip;q=0", "br"):
        r, raw = _raw_get(client, "/page", accept)
        assert "content-encoding" not in r.headers, accept
        assert json.loads(raw) == PAGE


def test_small_json_csv_and_files_pass_through():
    client = TestClient(_app())
    r, raw = _raw_get(client, "/small", "gzip")
    assert "content-encoding" not in r.headers and json.loads(raw) == {"ok": True}
    for path in ("/csv", "/pdf"):
        r, raw = _raw_get(client, path, "gzip")
        assert "content-encoding" not in r.headers, path
    assert raw.startswith(b"%PDF-1.7")


def test_an_event_stream_is_forwarded_chunk_by_chunk():
    # The chat's stream must not be held back until it ends.
    sent = []

    async def sse_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/event-stream; charset=utf-8")]})
        for n in range(3):
            await send({"type": "http.response.body", "body": f"data: {n}\n\n".encode(), "more_body": True})
            assert len(sent) == n + 2, "the previous event was held back"
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def record(message):
        sent.append(message)

    scope = {"type": "http", "method": "GET", "path": "/api/chat/stream",
             "headers": [(b"accept-encoding", b"gzip, deflate, br")]}
    asyncio.run(JsonGzipMiddleware(sse_app)(scope, None, record))
    assert [m.get("body") for m in sent[1:4]] == [b"data: 0\n\n", b"data: 1\n\n", b"data: 2\n\n"]
    assert all(h != b"content-encoding" for h, _ in sent[0]["headers"])


def test_the_accept_encoding_parser():
    assert accepts_gzip("gzip") and accepts_gzip("deflate, gzip;q=0.5") and accepts_gzip("*")
    assert not accepts_gzip("") and not accepts_gzip("identity") and not accepts_gzip("gzip;q=0")
    assert not accepts_gzip("br, deflate")


def test_the_real_app_compresses_as_the_outermost_layer():
    from main import app
    assert app.user_middleware[0].cls is JsonGzipMiddleware   # outermost: reads the final body
    r, raw = _raw_get(TestClient(app), "/openapi.json", "gzip")
    assert r.status_code == 200 and r.headers["content-encoding"] == "gzip"
    spec = json.loads(gzip.decompress(raw))
    assert "/api/v2/legislative/implementing-acts" in spec["paths"]
