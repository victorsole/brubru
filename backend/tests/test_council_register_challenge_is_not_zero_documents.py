"""A browser-challenge page must never be recorded as an empty Council register.

Incident (22 September 2026). The Council corpus had not moved since 27 August,
through a month containing a General Affairs Council, and
`ingest_council_documents.py --since-days 30` inserted 0 while reporting success.

`_fetch_rendered` guarded on SIZE (<500 bytes = failure) but not on CONTENT. What
came back was ~15,000 bytes of Cloudflare interstitial whose entire visible text
is "Just a moment... Checking your browser before accessing a GSC Managed Website
... Enable JavaScript and cookies to continue". It sailed past the size guard,
`_parse_results` found no result items and returned [], and the run logged
"0 document(s)". A hard block, reported as nothing-published.

Longer settle times do not help: measured byte-identical at 6s and 15s. This is a
block to be reported, not a timing problem to be tuned around, which is exactly
why it must raise rather than retry for ever.

These tests are offline: they feed HTML straight to the guard.
"""

import os
import pathlib
import sys

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# The real interstitial, trimmed. Note it is far larger than the 500-byte floor.
CHALLENGE = (
    "<html><head><title>Just a moment...</title></head><body>"
    "<div>Checking your browser before accessing a GSC Managed Website</div>"
    "<div>Enable JavaScript and cookies to continue</div>"
    + ("<!-- padding -->" * 900) +
    "</body></html>"
)


def _fetch_with(monkeypatch, html: str):
    """Run _fetch_rendered against canned HTML, with no browser involved."""
    import services.scrapers.council_register as cr
    import services.scrapers.waf_browser_fetcher as wbf

    class _Res:
        def __init__(self, h): self.html = h

    monkeypatch.setattr(wbf, "fetch_one", lambda *a, **k: _Res(html))
    return cr._fetch_rendered("https://www.consilium.europa.eu/whatever")


def test_a_challenge_page_raises_instead_of_returning_html(monkeypatch):
    import services.scrapers.council_register as cr  # noqa: F401  (import check)

    assert len(CHALLENGE) > 500, "the fixture must clear the size guard, or it proves nothing"

    with pytest.raises(RuntimeError) as exc:
        _fetch_with(monkeypatch, CHALLENGE)

    msg = str(exc.value)
    assert "CHALLENGE" in msg.upper(), msg
    assert "never record it as 'no documents'" in msg.lower(), (
        "the error must say what it must NOT be mistaken for; that sentence is the "
        "whole point of the guard"
    )


def test_a_tiny_response_still_raises(monkeypatch):
    """The original size guard must survive the new content guard."""
    with pytest.raises(RuntimeError, match="FETCH FAILURE"):
        _fetch_with(monkeypatch, "<html></html>")


def test_a_real_results_page_is_returned_untouched(monkeypatch):
    """The guard must not reject legitimate pages: no false positives."""
    good = (
        "<html><body><ul>"
        + '<li class="gsc-public-register__result-item">'
          '<a href="/doc/document/ST-12345-2026-INIT/en/pdf">ST 12345/26 NOTE 15/09/2026 '
          'Preparation of the Council meeting</a></li>' * 4
        + "</ul>" + ("<!-- pad -->" * 200) + "</body></html>"
    )
    out = _fetch_with(monkeypatch, good)
    assert out == good
