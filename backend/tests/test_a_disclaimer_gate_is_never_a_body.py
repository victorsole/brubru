"""A page that redirects to a disclaimer or sign-in, and back once the reader accepts, has no
body we may store.

18 Oct 2026: the European Stability Mechanism answers every funding press release with its
investor disclaimer: /press-releases/<slug> -> /investors/esm/disclaimer?destination=/press-
releases/<slug> (or /disclaimer-us-investors). Proceeding means confirming that you are not
a U.S. person and "will not copy, transmit or otherwise send any information on this web
site to any person". 58 rows held the ESM/EFSF disclaimer as their article and 6 the U.S.
QIB disclaimer. The gate is never clicked through; the row keeps no body and the API
serves its title and summary.
"""
import importlib
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
common = importlib.import_module("services.scrapers.economy_common")

ITEM = "https://www.esm.europa.eu/press-releases/esm-raises-eu25-billion-sale-10-year-bond"
GATE = "https://www.esm.europa.eu/investors/esm/disclaimer?destination=/press-releases/esm-raises-eu25-billion-sale-10-year-bond"
DISCLAIMER = ("<html><body><main><h1>ESM/EFSF DISCLAIMER</h1><p>By clicking \"I confirm\" below, you represent "
              "that you will not copy, transmit or otherwise send any information on this web site to any person."
              "</p>" + "<p>Restrictions apply.</p>" * 40 + "</main></body></html>")


def test_the_esm_gates_are_recognised():
    assert common.redirected_to_a_gate(ITEM, GATE)
    assert common.redirected_to_a_gate(ITEM, GATE.replace("/disclaimer?", "/disclaimer-us-investors?"))
    assert common.redirected_to_a_gate(ITEM, "https://www.esm.europa.eu/user/login?Destination=%2Fpress-releases%2F"
                                             "esm-raises-eu25-billion-sale-10-year-bond")


def test_other_redirects_are_not_gates():
    assert not common.redirected_to_a_gate(ITEM, ITEM)
    assert not common.redirected_to_a_gate(ITEM, None)
    assert not common.redirected_to_a_gate(ITEM, "https://www.esm.europa.eu/search?destination=/press-releases/other")
    assert not common.redirected_to_a_gate(ITEM, "https://other.example/disclaimer?destination=/press-releases/"
                                                 "esm-raises-eu25-billion-sale-10-year-bond")


def test_the_economy_detail_fetch_stores_nothing(monkeypatch):
    monkeypatch.setattr(common, "stored_complete", lambda url: False)
    monkeypatch.setattr(common, "http_get", lambda url: SimpleNamespace(
        url=GATE, text=DISCLAIMER, headers={"content-type": "text/html"}))
    assert common.fetch_detail(ITEM) == (None, None, "gated")


def test_the_body_fetcher_stores_nothing_and_tries_no_other_route(monkeypatch):
    fetcher = importlib.import_module("scripts.fetch_institutional_news_bodies")
    monkeypatch.setattr(fetcher, "_read", lambda url, timeout, accept="*/*", with_url=False:
                        (DISCLAIMER.encode(), GATE) if with_url else DISCLAIMER.encode())
    monkeypatch.setattr(fetcher, "_browser_page", lambda *a: (_ for _ in ()).throw(AssertionError("browser")))
    txt, html, err = fetcher.fetch(ITEM)
    assert txt is None and html is None and err.startswith("gated")
