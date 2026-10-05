"""X throttling must be reported, never read as an empty timeline (5 Oct 2026)."""
import io
import pathlib
import sys
import urllib.error

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")

import pytest  # noqa: E402
from services.social import post_fetcher as pf  # noqa: E402


def _raise(code):
    def _f(*a, **k):
        raise urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b""))
    return _f


@pytest.mark.parametrize("code", [429, 403, 500, 503])
def test_refusal_is_throttled_not_empty(monkeypatch, code):
    monkeypatch.setattr(pf.urllib.request, "urlopen", _raise(code))
    posts, skip = pf.fetch_for_account("x", "https://x.com/EUCommission", 5)
    assert posts == [] and skip == f"throttled:http_{code}"


def test_404_is_a_definitive_empty(monkeypatch):
    monkeypatch.setattr(pf.urllib.request, "urlopen", _raise(404))
    assert pf.fetch_for_account("x", "https://x.com/gone", 5) == ([], None)


def test_transport_error_is_throttled(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("t")
    monkeypatch.setattr(pf.urllib.request, "urlopen", boom)
    posts, skip = pf.fetch_for_account("x", "https://x.com/a", 5)
    assert skip.startswith("throttled:transport_")
