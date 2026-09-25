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


def test_a_missing_print_pdf_falls_through_to_the_page(monkeypatch):
    """A presscorner item without a print PDF still has an article.

    speech_26_911 serves a print PDF; ip_26_1129 and ip_25_2000 return 404 for theirs while
    their detail pages return 200. The code used to return that 404 as the answer, which
    filed 22 Commission rows as unreachable.
    """
    monkeypatch.setattr(m.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(404)))
    called = {}

    def fake_scrapedo(url, timeout=150, render=True):
        called["url"], called["render"] = url, render
        return "The Commission published guidance today. " * 20, "<p>x</p>", None

    monkeypatch.setattr(m, "fetch_via_scrapedo", fake_scrapedo)
    url = "https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1129"
    body_txt, _, reason = m.fetch(url, render=True)
    assert reason is None and body_txt, "the article was not recovered from the page"
    assert called["url"] == url and called["render"] is True


def test_without_render_a_missing_pdf_still_reports_the_reason(monkeypatch):
    """The fall-through is opt-in; without it the failure must still be named, not silent."""
    monkeypatch.setattr(m.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(404)))
    body_txt, _, reason = m.fetch(
        "https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1129", render=False)
    assert body_txt is None
    assert reason and "404" in reason


def test_an_eurlex_link_is_fetched_from_cellar(monkeypatch):
    """EUR-Lex renders a page; Cellar serves the act.

    The rendered EUR-Lex page for CJEU judgment 62024TJ0239 yields 116,974 characters opening
    with "Skip to main content ... Help Print Menu"; Cellar yields 113,938 opening with
    "JUDGMENT OF THE GENERAL COURT". Same document, none of the furniture, and no render credit.
    """
    called = {}

    def fake_cellar(celex, timeout=90):
        called["celex"] = celex
        return "JUDGMENT OF THE GENERAL COURT " * 100, "<html>x</html>", None

    monkeypatch.setattr(m, "fetch_cellar", fake_cellar)
    body_txt, _, reason = m.fetch(
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62024TJ0239")
    assert reason is None and body_txt.startswith("JUDGMENT")
    assert called["celex"] == "62024TJ0239"


def test_cellar_tries_both_manifestations_before_giving_up(monkeypatch):
    """Asking Cellar for the wrong type is a flat 404, not a redirect to what exists.

    62024TJ0239 serves text/html and holds no XHTML; ECB decision 32026D2039 serves
    application/xhtml+xml and holds no HTML. Asking only for the first left four whole slices
    (ecb/legal, fra/charter_article, ema/mrl and part of cjeu/case_law) reading "no text".
    """
    asked = []

    def fake_urlopen(req, timeout=None):
        accept = req.headers.get("Accept")
        asked.append(accept)
        if accept == "text/html":
            raise _http_error(404)

        class R:
            def read(self_inner):
                return ("<html><body>" + "The Governing Council has adopted this Decision. " * 60
                        + "</body></html>").encode()
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
        return R()

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    body_txt, _, reason = m.fetch_cellar("32026D2039")
    assert reason is None, f"gave up with {reason!r}"
    assert "Governing Council" in body_txt
    assert asked == ["text/html", "application/xhtml+xml"], f"asked {asked}"


def test_cellar_reports_which_types_it_tried_when_nothing_is_there(monkeypatch):
    """A document Cellar really does not hold must say so, naming what was asked."""
    monkeypatch.setattr(m.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(_http_error(404)))
    body_txt, _, reason = m.fetch_cellar("39999X9999")
    assert body_txt is None
    assert reason and "404" in reason and "xhtml" in reason
