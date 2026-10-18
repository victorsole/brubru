"""A Court of Auditors page is titled by its own heading, never by the breadcrumb.

ECA pages open with a SharePoint breadcrumb <h1>: "Skip Navigation Links" followed by the
page's internal name ("OrgChartStructure"); the heading the site shows comes second and in
og:title. 12 of 14 ECA topic rows were stored as "Skip Navigation Links Governance" and the
like (18 Oct 2026), and the body fetcher then refused each real page because its text did
not name such a title. The page markup below is the live one, reduced.
"""
import importlib
import pathlib
import sys

from bs4 import BeautifulSoup

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
eca = importlib.import_module("services.scrapers.economy_eca")

PAGE = ('<html><head><title>Organisation | European Court of Auditors</title>'
        '<meta property="og:title" content="Organisation"></head><body>'
        '<h1><a href="#skip">Skip Navigation Links</a>OrgChartStructure\r\n\t\t\t</h1>'
        '<main><h1>Organisation</h1><p>The ECA is organised in chambers.</p></main></body></html>')


def test_og_title_wins():
    assert eca._page_title(BeautifulSoup(PAGE, "html.parser")) == "Organisation"


def test_without_og_title_the_breadcrumb_heading_is_skipped():
    page = PAGE.replace('<meta property="og:title" content="Organisation">', "")
    assert eca._page_title(BeautifulSoup(page, "html.parser")) == "Organisation"


def test_the_topics_ingester_uses_it():
    import inspect
    src = inspect.getsource(eca._ingest_topics_async)
    assert "_page_title(soup)" in src and 'select_one("main h1, h1")' not in src
