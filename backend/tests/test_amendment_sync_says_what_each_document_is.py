"""The nightly amendment sync was red every night from 29 Sep to 12 Oct 2026 for two reasons
that were neither "amendments are not syncing" (they were) nor what its errors said.

1. 38 documents of 2005-2016 are legacy Word `.doc` files that doceo serves, whole, under a
   `.docx` address. The browser fetched them (HTTP 200); the code kept only bytes that open
   with "PK", threw the rest away, asked again over plain HTTP (202, zero bytes) and recorded
   "behind the WAF". They were retried every night, and each one was also a RUN error, so
   the `degraded` state meant for them could never be reached.
2. A single HTTP 500 on one of the ~25 listing pages raised on the first try and aborted
   the run (offsets 300, 900 and 1200 on three different nights)."""
import asyncio
import pathlib
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

import services.api_clients.ep_open_data_client as ep_mod
from services.api_clients.ep_open_data_client import EPOpenDataClient, EPOpenDataUpstreamError
from services.scrapers import bulk_amendment_sync_service as svc

BACKEND = pathlib.Path(__file__).resolve().parents[1]
URL = "https://www.europarl.europa.eu/doceo/document/PECH-PR-504146_EN.docx"


# ---- the listing ---------------------------------------------------------------------

class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code, self._payload, self.headers = status_code, payload or {"data": [{"identifier": "X"}]}, {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self):
        return self._payload


def _client_answering(*answers):
    """An EP client whose successive GETs give `answers` (a status code or an exception)."""
    c, calls = EPOpenDataClient(), {"n": 0}

    class _Fake:
        async def get(self, url, params=None):
            a = answers[min(calls["n"], len(answers) - 1)]
            calls["n"] += 1
            if isinstance(a, Exception):
                raise a
            return _Resp(a)

    async def _get():
        return _Fake()
    c._get_client = _get
    return c, calls


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    waits = []

    async def _sleep(seconds):
        waits.append(seconds)
    monkeypatch.setattr(ep_mod.asyncio, "sleep", _sleep)
    return waits


def test_one_http_500_on_a_page_is_retried_and_the_page_is_read(no_waiting):
    c, calls = _client_answering(500, 200)
    assert asyncio.run(c._list_endpoint("committee-documents", offset=300)) == [{"identifier": "X"}]
    assert calls["n"] == 2 and no_waiting == [EPOpenDataClient.TRANSIENT_WAITS[0]]


def test_a_dropped_connection_is_retried_too():
    c, calls = _client_answering(httpx.ReadTimeout("slow"), 502, 200)
    assert asyncio.run(c._list_endpoint("committee-documents", offset=900)) == [{"identifier": "X"}]
    assert calls["n"] == 3


def test_a_page_that_keeps_failing_still_fails_the_listing_and_says_how_often():
    c, calls = _client_answering(500)
    with pytest.raises(EPOpenDataUpstreamError) as e:
        asyncio.run(c._list_endpoint("committee-documents", offset=1200))
    assert calls["n"] == 3 and "HTTP 500" in str(e.value) and "3 tries" in str(e.value)


# ---- each document ---------------------------------------------------------------------

def _service(facts=None, cache=None):
    s = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService)
    s._docx_cache, s._fetch_facts = dict(cache or {}), dict(facts or {})
    return s


DOC = {"identifier": "PECH-PR-504146", "doceo_url": URL, "document_type": "PR"}


def test_a_legacy_word_file_is_an_unsupported_format_not_a_wall():
    s = _service(facts={URL: (200, "legacy_doc")})
    with pytest.raises(svc.UnsupportedDocumentFormat) as e:
        asyncio.run(s._fetch_and_parse_document(DOC))
    assert "legacy Word .doc" in str(e.value) and "WAF" not in str(e.value)


def test_a_404_is_not_found_not_a_wall():
    s = _service(facts={URL: (404, "not_found")})
    with pytest.raises(svc.DocumentNotFound):
        asyncio.run(s._fetch_and_parse_document(DOC))


def test_the_browser_answer_is_classified_by_its_first_bytes(monkeypatch):
    out = {"a": (200, svc.OLE2_MAGIC + b"rest", None), "b": (404, b"<!DOCTYPE html>", None),
           "c": (200, b"PK\x03\x04docx", None), "d": (202, b"", None)}
    fake = SimpleNamespace(fetch_bytes_isolated=lambda urls, warm_url, timeout_s: out)
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda m: None))
    monkeypatch.setattr("importlib.util.spec_from_file_location", lambda *a, **k: spec)
    monkeypatch.setattr("importlib.util.module_from_spec", lambda sp: fake)
    s = _service()
    asyncio.run(s._prefetch_walled_documents(list(out)))
    assert s._fetch_facts == {"a": (200, "legacy_doc"), "b": (404, "not_found"), "d": (202, "other")}
    assert list(s._docx_cache) == ["c"]


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *a):
        return self

    def first(self):
        return self.row


@pytest.mark.parametrize("row,settled", [
    (None, False),
    (("parsed", datetime.now()), True),
    (("unsupported", datetime.now() - timedelta(days=400)), True),     # a format does not change
    (("not_found", datetime.now() - timedelta(days=2)), True),          # asked this week
    (("not_found", datetime.now() - timedelta(days=8)), False),         # ask again
    (("failed", datetime.now()), False),                                # tried again every night
    (("pending", datetime.now()), False),
])
def test_what_the_nightly_run_leaves_alone(row, settled):
    s = _service()
    s.db = SimpleNamespace(query=lambda *a: _Query(row))
    assert s._is_settled("PECH-PR-504146") is settled


def test_a_document_that_cannot_be_read_degrades_the_run_and_does_not_fail_it():
    src = (BACKEND / "services" / "scrapers" / "bulk_amendment_sync_service.py").read_text()
    assert "result.document_errors.append(error_msg)" in src
    assert src.count("result.errors.append(error_msg)") == 1        # the listing only
    sched = (BACKEND / "services" / "schedulers" / "amendment_sync_scheduler.py").read_text()
    assert "list(result.errors) + list(result.document_errors)" in sched
    assert sched.index("if result.errors:") < sched.index("elif result.documents_failed:")
