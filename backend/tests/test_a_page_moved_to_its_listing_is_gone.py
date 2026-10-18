"""An item whose URL now redirects up to its section's listing is gone: the listing is not
its body.

18 Oct 2026: EU-OSHA removed 11 highlights; each URL now leads to /en/highlights. The rows
held EU-OSHA's 6,389-character cookie notice, and a re-fetch was about to store the same
4,979 characters of listing under all 11 titles (the name check passed: the listing names
every highlight).
"""
import importlib
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
common = importlib.import_module("services.scrapers.economy_common")

ITEM = "https://osha.europa.eu/en/highlights/say-no-harassment-work-oira"


def test_a_redirect_to_the_parent_section_is_a_move():
    assert common.moved_to_parent(ITEM, "https://osha.europa.eu/en/highlights")
    assert common.moved_to_parent(ITEM, "https://osha.europa.eu/")


def test_ordinary_redirects_are_not():
    assert not common.moved_to_parent(ITEM, ITEM)
    assert not common.moved_to_parent(ITEM, ITEM + "/")
    assert not common.moved_to_parent("http://osha.europa.eu/en/highlights/x", "https://www.osha.europa.eu/en/highlights/x")
    assert not common.moved_to_parent(ITEM, "https://osha.europa.eu/en/highlights/say-no-harassment-work-oira-0")
    assert not common.moved_to_parent(ITEM, "https://other.europa.eu/en/highlights")
    assert not common.moved_to_parent(ITEM, None)


LISTING = ("<html><body><main><h1>Highlights</h1>" +
           "".join(f"<article><h2>Highlight number {k} about workplace safety</h2><p>{k}/10/2026</p></article>"
                   for k in range(10)) + "<p>" + "Text " * 200 + "</p></main></body></html>")


def test_the_economy_detail_fetch_stores_nothing(monkeypatch):
    monkeypatch.setattr(common, "stored_complete", lambda url: False)
    monkeypatch.setattr(common, "http_get", lambda url: SimpleNamespace(
        url="https://osha.europa.eu/en/highlights", text=LISTING, headers={"content-type": "text/html"}))
    assert common.fetch_detail(ITEM) == (None, None, "moved")


def test_the_body_fetcher_stores_nothing_and_tries_no_other_route(monkeypatch):
    fetcher = importlib.import_module("scripts.fetch_institutional_news_bodies")
    monkeypatch.setattr(fetcher, "_read", lambda url, timeout, accept="*/*", with_url=False:
                        (LISTING.encode(), "https://osha.europa.eu/en/highlights") if with_url else LISTING.encode())
    monkeypatch.setattr(fetcher, "_browser_page", lambda *a: (_ for _ in ()).throw(AssertionError("browser")))
    txt, html, err = fetcher.fetch(ITEM)
    assert txt is None and html is None and err.startswith("moved")
