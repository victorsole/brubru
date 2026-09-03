"""OEIL parsing must read the VALUE beside a label, never the label itself.

Regression tests for the 3 September 2026 fix. Three separate defects made the
scraper return page furniture instead of data, and every caller that treats OEIL
as the source of truth for rapporteur identity was reading it:

  * title  came from the <title> tag, so every procedure was called
    "Procedure File: <ref>"
  * status matched a regex and assigned group(0), the WHOLE match, so every
    procedure's status was the literal label "Stage reached in procedure"
  * committee walked a hardcoded list in fixed order and took the first code
    appearing anywhere on the page, so IMCO (first in that list) was reported
    as responsible for procedures belonging to TRAN and EMPL

These use a fixture shaped like the real page (label line, then value line)
rather than the network, so they stay fast and cannot go green because OEIL
changed.
"""
import pathlib
import sys

import pytest
from bs4 import BeautifulSoup

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, str(pathlib.Path(_REPO_ROOT) / "backend"))

from services.scrapers.oeil_scraper import (  # noqa: E402
    OEILScraper, _oeil_lines, _value_after, _OEIL_LABELS,
)

PAGE = """
<html><head><title>Procedure File: 2023/0437(COD) | Legislative Observatory</title></head>
<body>
<div>2023/0437(COD)</div><div>pdf</div><div>Full procedure</div>
<div>Transport: enforcement of passenger rights in the Union</div>
<div>Basic information</div><div>2023/0437(COD)</div>
<div>COD - Ordinary legislative procedure (ex-codecision procedure)</div>
<div>Status</div><div>Awaiting Parliament's position in 1st reading</div>
<div>Key players</div><div>Committee responsible</div>
<div>Rapporteur</div><div>Appointed</div>
<div>IMCO mentioned here only as an opinion committee</div>
<div>TRAN</div><div>Transport and Tourism</div>
<a href="/meps/en/257121">RICCI Matteo</a>
</body></html>
"""


@pytest.fixture
def soup():
    return BeautifulSoup(PAGE, "html.parser")


def test_value_after_returns_the_value_not_the_label(soup):
    lines = _oeil_lines(soup)
    assert _value_after(lines, "Status") == "Awaiting Parliament's position in 1st reading"
    assert _value_after(lines, "Full procedure") == (
        "Transport: enforcement of passenger rights in the Union")


def test_value_after_refuses_to_return_another_label(soup):
    lines = _oeil_lines(soup)
    # "Key players" is followed immediately by "Committee responsible", a label.
    assert _value_after(lines, "Key players") not in _OEIL_LABELS


def test_title_is_the_procedure_not_the_page_furniture(soup):
    info = OEILScraper()._parse_basic_info(soup, "2023/0437(COD)")
    assert info.title == "Transport: enforcement of passenger rights in the Union"
    assert "Procedure File" not in (info.title or "")


def test_status_is_the_value_not_the_label(soup):
    info = OEILScraper()._parse_basic_info(soup, "2023/0437(COD)")
    assert info.status == "Awaiting Parliament's position in 1st reading"
    assert info.status != "Stage reached in procedure"


def test_committee_responsible_is_the_one_under_the_label(soup):
    """IMCO appears on the page first and is NOT the responsible committee."""
    players = OEILScraper()._parse_key_players(soup)
    assert players.committee_responsible is not None
    assert players.committee_responsible.code == "TRAN"
    assert players.committee_responsible.code != "IMCO"
    assert players.committee_responsible.name == "Transport and Tourism"


def test_rapporteur_still_parsed(soup):
    players = OEILScraper()._parse_key_players(soup)
    rap = players.committee_responsible.rapporteur
    assert rap is not None and rap.name == "RICCI Matteo"
