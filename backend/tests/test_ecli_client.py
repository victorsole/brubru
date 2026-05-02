"""
Phase 13 of docs/applications/euvoc.md — ECLI search-engine client tests.

Sample ECLIs cover CJEU + national courts (Germany, Netherlands, France,
Spain) per Victor's "use varied real cases" instruction.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.api_clients.ecli_client import (  # noqa: E402
    deep_link,
    eur_lex_url,
    is_cjeu,
    parse,
)


# ----------------------------------------------------------------------
# parse
# ----------------------------------------------------------------------

class TestParse:
    @pytest.mark.parametrize("ecli,expected", [
        ("ECLI:EU:C:2014:317", {"country": "EU", "court": "C", "year": "2014", "ordinal": "317"}),
        ("ECLI:EU:C:2018:585", {"country": "EU", "court": "C", "year": "2018", "ordinal": "585"}),
        ("ECLI:EU:T:2020:1234", {"country": "EU", "court": "T", "year": "2020", "ordinal": "1234"}),
        ("ECLI:DE:BVerfG:2020:RS20200505", {"country": "DE", "court": "BVERFG", "year": "2020", "ordinal": "RS20200505"}),
        ("ECLI:NL:HR:2021:1234", {"country": "NL", "court": "HR", "year": "2021", "ordinal": "1234"}),
        ("ECLI:FR:CCASS:2022:1A12345", {"country": "FR", "court": "CCASS", "year": "2022", "ordinal": "1A12345"}),
        ("ECLI:ES:TS:2023:5678", {"country": "ES", "court": "TS", "year": "2023", "ordinal": "5678"}),
    ])
    def test_parses_real_eclis(self, ecli, expected):
        assert parse(ecli) == expected

    @pytest.mark.parametrize("bad", ["", None, "ECLI:bad", "not-an-ecli", "ECLI:EU:C:2014"])
    def test_invalid_returns_empty(self, bad):
        assert parse(bad) == {}


# ----------------------------------------------------------------------
# is_cjeu
# ----------------------------------------------------------------------

class TestIsCJEU:
    @pytest.mark.parametrize("ecli", [
        "ECLI:EU:C:2014:317",   # Google Spain — Court of Justice
        "ECLI:EU:C:2018:585",   # Schrems II
        "ECLI:EU:T:2019:99",    # General Court
        "ECLI:EU:F:2010:50",    # historic Civil Service Tribunal
    ])
    def test_cjeu_eclis(self, ecli):
        assert is_cjeu(ecli) is True

    @pytest.mark.parametrize("ecli", [
        "ECLI:DE:BVerfG:2020:RS20200505",
        "ECLI:NL:HR:2021:1234",
        "ECLI:ES:TS:2023:5678",
        "ECLI:EU:CJ:2020:1",  # bogus court
    ])
    def test_non_cjeu_eclis(self, ecli):
        assert is_cjeu(ecli) is False


# ----------------------------------------------------------------------
# deep_link / eur_lex_url
# ----------------------------------------------------------------------

class TestDeepLink:
    def test_emits_e_justice_url(self):
        url = deep_link("ECLI:EU:C:2014:317")
        assert "e-justice.europa.eu" in url
        # ECLI is URL-encoded
        assert "ECLI%3AEU%3AC%3A2014%3A317" in url

    def test_inforcuria_for_cjeu(self):
        url = eur_lex_url("ECLI:EU:C:2014:317")
        assert url is not None
        assert "curia.europa.eu" in url

    def test_no_inforcuria_for_national(self):
        assert eur_lex_url("ECLI:DE:BVerfG:2020:RS20200505") is None
        assert eur_lex_url("ECLI:ES:TS:2023:5678") is None
