"""
Phase 13 of docs/applications/euvoc.md — standard-identifier resolver
+ ShowVoc deep-link tests.

Per OP Standards v4.0.0 §2, Brubru recognises every EU identifier
type. Tests use VARIED real CELEX / ECLI / ISBN / ISSN / DOI examples,
not GDPR-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.api_clients.showvoc_client import (  # noqa: E402
    deep_link,
    deep_link_for_authority,
    deep_link_for_eurovoc,
)
from services.identifiers.standard_identifier_resolver import (  # noqa: E402
    IdentifierKind,
    parse_all,
    recognise,
)


# ----------------------------------------------------------------------
# CELEX — sample varied across sectors / decades / types
# ----------------------------------------------------------------------

class TestCelex:
    @pytest.mark.parametrize("celex", [
        "32016R0679",   # GDPR — sector 3, regulation
        "32024R1689",   # AI Act
        "32022R2065",   # DSA
        "32016L1148",   # NIS 1 — directive
        "32011L0083",   # Consumer Rights Directive
        "32023R1542",   # Battery Regulation
        "31995L0046",   # repealed DPD — 1995
        "32020D2229",   # decision
        "52021PC0206",  # COM proposal — sector 5
        "52026M12201",  # merger notification
        "32016R0679R(01)",  # corrigendum
    ])
    def test_recognises_celex(self, celex):
        m = recognise(celex)
        assert m is not None, f"failed to recognise {celex}"
        assert m.kind == IdentifierKind.CELEX
        assert m.brubru_url and "/api/v1/laws" in m.brubru_url
        assert "eur-lex.europa.eu" in m.canonical_url

    def test_celex_parts_decoded(self):
        m = recognise("32016R0679")
        assert m.parts == {
            "sector": "3", "year": "2016", "type_letter": "R",
            "serial": "0679", "corrigendum": None,
        }


# ----------------------------------------------------------------------
# ECLI
# ----------------------------------------------------------------------

class TestECLI:
    @pytest.mark.parametrize("ecli", [
        "ECLI:EU:C:2023:123",
        "ECLI:EU:C:2014:317",   # Google Spain (right to be forgotten)
        "ECLI:EU:C:2018:585",   # Schrems II
        "ECLI:DE:BVerfG:2020:rs20200505",  # German Constitutional Court (PSPP)
        "ECLI:NL:HR:2021:1234",
    ])
    def test_recognises_ecli(self, ecli):
        m = recognise(ecli)
        assert m is not None, f"failed to recognise {ecli}"
        assert m.kind == IdentifierKind.ECLI
        assert m.canonical_url.startswith("https://e-justice.europa.eu/ecli/")

    def test_ecli_parts_decoded(self):
        m = recognise("ECLI:EU:C:2023:123")
        assert m.parts == {
            "country": "EU", "court": "C", "year": "2023", "ordinal": "123",
        }


# ----------------------------------------------------------------------
# ISBN / ISSN / DOI
# ----------------------------------------------------------------------

class TestIsbnIssn:
    @pytest.mark.parametrize("text", [
        "978-92-78-41349-1",
        "ISBN: 978-92-78-41349-1",
        "9789278413491",
    ])
    def test_recognises_isbn(self, text):
        m = recognise(text)
        assert m is not None
        assert m.kind == IdentifierKind.ISBN

    @pytest.mark.parametrize("text", [
        "1234-5678",
        "ISSN: 1234-567X",
    ])
    def test_recognises_issn(self, text):
        m = recognise(text)
        assert m is not None
        assert m.kind == IdentifierKind.ISSN


class TestDOI:
    def test_recognises_doi(self):
        m = recognise("10.2775/123456")
        assert m is not None
        assert m.kind == IdentifierKind.DOI
        assert m.canonical_url == "https://doi.org/10.2775/123456"

    def test_recognises_doi_with_prefix(self):
        m = recognise("doi:10.2775/123456")
        assert m is not None
        assert m.kind == IdentifierKind.DOI


# ----------------------------------------------------------------------
# URIs
# ----------------------------------------------------------------------

class TestUris:
    def test_eurovoc_uri(self):
        m = recognise("http://eurovoc.europa.eu/5460")
        assert m is not None
        assert m.kind == IdentifierKind.EUROVOC_URI
        assert m.brubru_url and "/eurovoc/5460/acts" in m.brubru_url

    def test_authority_uri_corporate_body(self):
        m = recognise("http://publications.europa.eu/resource/authority/corporate-body/EP")
        assert m is not None
        assert m.kind == IdentifierKind.AUTHORITY_URI
        assert m.brubru_url == "https://brubru.beresol.eu/api/v1/vocabularies/corporate-bodies"

    def test_authority_uri_procedure(self):
        m = recognise("http://publications.europa.eu/resource/authority/procedure/COD")
        assert m is not None
        assert m.brubru_url == "https://brubru.beresol.eu/api/v1/vocabularies/procedures"

    def test_eli_uri(self):
        m = recognise("http://publications.europa.eu/resource/eli/reg/2016/679/oj")
        assert m is not None
        assert m.kind == IdentifierKind.ELI_URI


# ----------------------------------------------------------------------
# OJ + catalogue number
# ----------------------------------------------------------------------

class TestOjCatalogue:
    def test_oj_jol(self):
        m = recognise("JOL_2014_001_R_0001_01")
        assert m is not None and m.kind == IdentifierKind.OJ_REF

    def test_oj_l(self):
        m = recognise("L_202401689")
        assert m is not None and m.kind == IdentifierKind.OJ_REF

    def test_catalogue_number(self):
        m = recognise("OA-AS-16-001-EN-N")
        assert m is not None and m.kind == IdentifierKind.CATALOGUE_NUMBER


# ----------------------------------------------------------------------
# Negative cases
# ----------------------------------------------------------------------

class TestNoMatch:
    @pytest.mark.parametrize("text", ["", None, "hello world", "12345", "foo"])
    def test_unrecognised_returns_none(self, text):
        assert recognise(text) is None


# ----------------------------------------------------------------------
# parse_all (embedded in longer text)
# ----------------------------------------------------------------------

class TestParseAll:
    def test_finds_multiple(self):
        para = (
            "Reading 32016R0679 alongside ECLI:EU:C:2014:317 — "
            "see also doi:10.2775/123456 and ISSN: 1234-5678."
        )
        matches = parse_all(para)
        kinds = {m.kind for m in matches}
        assert IdentifierKind.CELEX in kinds
        assert IdentifierKind.ECLI in kinds
        assert IdentifierKind.DOI in kinds
        assert IdentifierKind.ISSN in kinds

    def test_dedupe(self):
        text = "32016R0679 32016R0679 32016R0679"
        matches = parse_all(text)
        assert len([m for m in matches if m.kind == IdentifierKind.CELEX]) == 1


# ----------------------------------------------------------------------
# ShowVoc
# ----------------------------------------------------------------------

class TestShowVoc:
    def test_eurovoc_deep_link(self):
        url = deep_link_for_eurovoc("5460")
        assert "showvoc" in url
        assert "EuroVoc" in url
        assert "5460" in url

    def test_eurovoc_full_uri(self):
        url = deep_link_for_eurovoc("http://eurovoc.europa.eu/8500")
        assert "8500" in url

    def test_authority_deep_link(self):
        url = deep_link_for_authority(
            "http://publications.europa.eu/resource/authority/corporate-body/EP"
        )
        assert url and "showvoc" in url

    def test_unknown_uri_returns_none(self):
        assert deep_link("http://example.org/x") is None

    def test_dispatch_by_uri_type(self):
        # EuroVoc URI dispatches to deep_link_for_eurovoc
        u = deep_link("http://eurovoc.europa.eu/5460")
        assert u and "EuroVoc" in u
        # Authority URI dispatches to deep_link_for_authority
        u = deep_link("http://publications.europa.eu/resource/authority/corporate-body/EP")
        assert u and "CommonAuthorityTables" in u
