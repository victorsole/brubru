"""euagenda: a blocked listing must never read as a quiet one.

15 Sep 2026: euagenda.eu went behind a Cloudflare managed challenge (403 "Just a
moment..."), scrape_listing swallowed the ScraperError and returned [], and
scripts/sync_euagenda.py printed added/updated/skipped/errors all 0, exit 0.
"""
import asyncio
import importlib.util
from pathlib import Path

import pytest

from services.scrapers import euagenda_scraper as mod
from services.scrapers.base_scraper import ScraperError

_BACKEND = Path(__file__).resolve().parents[1]

_CARD_HTML = (
    '<div class="event-box card"><a href="/events/2026/10/01/eu-ai-summit">x</a>'
    "EU AI Summit\nsub\nBelgium\n1 Oct 2026\nOrg</div>"
)
_CHALLENGE = "<html><head><title>Just a moment...</title></head>challenges.cloudflare.com</html>"


def _scraper(monkeypatch, *, http=None, http_exc=None, browser=("", "boom")):
    s = mod.EuAgendaScraper()

    async def fake_fetch(url, use_cache=True):
        if http_exc:
            raise http_exc
        return http

    monkeypatch.setattr(s, "_fetch", fake_fetch)
    calls = []

    def fake_browser(url):
        calls.append(url)
        return browser

    monkeypatch.setattr(mod, "_browser_fetch", fake_browser)
    return s, calls


def test_waf_403_falls_back_to_browser_and_uses_it(monkeypatch):
    s, calls = _scraper(monkeypatch, http_exc=ScraperError("HTTP 403: Forbidden"),
                        browser=(_CARD_HTML, None))
    cards = asyncio.run(s.scrape_listing())
    assert calls, "a WAF status must trigger the Playwright fallback"
    assert len(cards) == 1 and s.listing_via == "browser" and s.listing_error is None


def test_waf_403_and_browser_blocked_reports_error(monkeypatch):
    s, _ = _scraper(monkeypatch, http_exc=ScraperError("HTTP 403: Forbidden"),
                    browser=(_CHALLENGE, "challenge page still served"))
    assert asyncio.run(s.scrape_listing()) == []
    assert s.listing_via is None and s.listing_cards == 0
    assert "403" in s.listing_error and "challenge" in s.listing_error


def test_200_with_no_cards_is_treated_as_a_wall(monkeypatch):
    s, calls = _scraper(monkeypatch, http=_CHALLENGE, browser=("", "timeout"))
    assert asyncio.run(s.scrape_listing()) == []
    assert calls and s.listing_error


def test_plain_fetch_success_does_not_launch_browser(monkeypatch):
    s, calls = _scraper(monkeypatch, http=_CARD_HTML)
    assert len(asyncio.run(s.scrape_listing())) == 1
    assert not calls and s.listing_via == "http"


def test_non_waf_http_error_skips_browser(monkeypatch):
    s, calls = _scraper(monkeypatch, http_exc=ScraperError("HTTP 404: Not Found"))
    assert asyncio.run(s.scrape_listing()) == []
    assert not calls and "404" in s.listing_error


def _script():
    spec = importlib.util.spec_from_file_location("sync_euagenda", _BACKEND / "scripts" / "sync_euagenda.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("result,code", [
    ({"fetched": 0, "errors": 0, "fetch_error": "HTTP 403"}, 2),
    ({"fetched": 0, "errors": 0}, 2),
    ({"fetched": 10, "errors": 1}, 1),
    ({"fetched": 10, "errors": 0}, 0),
])
def test_script_exit_code(result, code, capsys):
    assert _script().exit_code(result) == code
    out = capsys.readouterr().out
    assert ("[ERROR]" in out) == (code != 0)
