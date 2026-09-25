"""A 429 says our request rate is too high. It says nothing about the document.

The euda slice failed 240 of 400 rows with HTTP 429 and moved on, which would later read as
"this body publishes nothing". These tests hold the fetcher to retrying instead.
"""
import io
import sys
import time
import urllib.error
import pathlib

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

from backend.scripts import fetch_institutional_news_bodies as m


def _http_error(code, retry_after=None):
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x", code, "rate", headers, None)


@pytest.fixture(autouse=True)
def _reset_backoff():
    m._BACKOFF_UNTIL = 0.0
    yield
    m._BACKOFF_UNTIL = 0.0


def test_a_429_is_retried_and_the_body_arrives(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise _http_error(429, "0.01")
        class R:
            def read(self_inner): return b"<html><body>the real article</body></html>"
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
        return R()

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    assert m._read("https://example.europa.eu/a", 10) == b"<html><body>the real article</body></html>"
    assert len(calls) == 2, "a rate limit must be retried, not surrendered to"


def test_a_404_is_not_retried(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        raise _http_error(404)

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        m._read("https://example.europa.eu/gone", 10)
    assert len(calls) == 1, "a missing page is not a rate limit; retrying it wastes the budget"


def test_a_rate_limit_pauses_every_thread():
    """One thread meeting a 429 must slow the whole run, not just its own retry.

    Asserted against the clock directly: driving it through _read would make the test
    actually sleep the backoff, which is the behaviour we want in production and a
    two-minute test suite here.
    """
    m._note_rate_limit(_http_error(429, "30"), 0)
    assert m._BACKOFF_UNTIL > time.time() + 20, "Retry-After must move the shared clock"


def test_retry_after_is_honoured_over_the_default():
    m._note_rate_limit(_http_error(429, "45"), 0)
    assert m._BACKOFF_UNTIL > time.time() + 40


def test_without_a_retry_after_the_wait_grows():
    first = m._note_rate_limit(_http_error(429), 0)
    second = m._note_rate_limit(_http_error(429), 1)
    assert second > first, "repeated rate limits must back off further, not hammer on"


def test_a_rate_limited_row_is_never_written_as_an_empty_body(monkeypatch):
    """The whole point: a 429 must leave the row untouched so the resume filter retries it."""
    monkeypatch.setattr(m.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(429, "0.01")))
    body_txt, body_html, error = m.fetch("https://www.euda.europa.eu/news/x")
    assert body_txt is None and body_html is None
    assert error and "429" in error, f"the reason must name the rate limit, got {error!r}"
