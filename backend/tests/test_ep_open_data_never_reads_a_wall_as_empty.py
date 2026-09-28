"""Two ways EP made "nothing there" indistinguishable from "we failed to look".

1. data.europarl.europa.eu answers HTTP 200 with an `error` key instead of `data`
   when its own backend 500s. `data.get("data", [])` turned that into an empty page,
   the paginator read it as the end of the list, and the amendment sync recorded
   "0 documents discovered" as success.
2. doceo answers 202 with an EMPTY body for every document, present or not. The AM
   probe required status 200, so it broke out of its range on the first candidate and
   discovered zero amendment documents on every run; the DOCX download passed
   raise_for_status (202 is not an error) and handed 0 bytes to the parser, which was
   recorded as a parse failure rather than as a document we never received.

Nothing has been stored in mep_amendments since 3 May 2026 as a result.
"""
import asyncio
import pytest

from services.api_clients.ep_open_data_client import (
    EPOpenDataClient, EPOpenDataUpstreamError)


class _Resp:
    """Enough of httpx.Response for the client: status, headers, body."""

    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
    """Always answers with EP's 200-plus-error-body."""
    def __init__(self):
        self.calls = 0

    async def get(self, url, params=None):
        self.calls += 1
        return _Resp({"@id": "x", "error": "500 Internal Server Error from POST ..."})


def test_an_error_body_raises_instead_of_looking_empty():
    c = EPOpenDataClient()
    fake = _Client()
    c._get_client = lambda: _done(fake)
    with pytest.raises(EPOpenDataUpstreamError):
        asyncio.run(c._list_endpoint("committee-documents", offset=0, limit=100))
    assert fake.calls == 3, "an intermittent upstream fault deserves retries before giving up"


def test_a_real_page_still_returns_its_rows():
    c = EPOpenDataClient()

    class OK(_Client):
        async def get(self, url, params=None):
            return _Resp({"data": [{"identifier": "AFCO-PR-630640"}]})

    c._get_client = lambda: _done(OK())
    rows = asyncio.run(c._list_endpoint("committee-documents", offset=0, limit=100))
    assert [r["identifier"] for r in rows] == ["AFCO-PR-630640"]


def test_an_empty_page_is_still_an_empty_page():
    """A genuine end-of-list has `data`, empty. That must NOT raise."""
    c = EPOpenDataClient()

    class Empty(_Client):
        async def get(self, url, params=None):
            return _Resp({"data": []})

    c._get_client = lambda: _done(Empty())
    assert asyncio.run(c._list_endpoint("committee-documents", offset=0, limit=100)) == []


async def _done(value):
    return value


def test_a_429_is_retried_and_then_raises_rather_than_reading_as_empty():
    """EP sends `Retry-After: 60` with its 429. Waiting is right; so is giving up
    loudly. Returning an empty page would say the corpus ended here."""
    import services.api_clients.ep_open_data_client as mod

    class Throttled(_Client):
        async def get(self, url, params=None):
            self.calls += 1
            return _Resp({}, status_code=429, headers={"Retry-After": "1"})

    c = EPOpenDataClient()
    fake = Throttled()
    c._get_client = lambda: _done(fake)
    slept = []

    async def _no_wait(seconds):
        slept.append(seconds)

    original = mod.asyncio.sleep
    mod.asyncio.sleep = _no_wait
    try:
        with pytest.raises(EPOpenDataUpstreamError):
            asyncio.run(c._list_endpoint("committee-documents", offset=0, limit=100))
    finally:
        mod.asyncio.sleep = original
    assert fake.calls == 3, "a throttle deserves retries before giving up"
    assert slept and all(s >= 5 for s in slept), "Retry-After must be honoured, with a floor"
