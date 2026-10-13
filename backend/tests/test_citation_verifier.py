"""
Unit tests for citation_verifier (Sprint 1a).

Covers:
  - Reference extraction (CELEX, COM-to-CELEX, OEIL)
  - Cache read/write paths
  - Network success/failure paths (mocked, no live calls)
  - COM ambiguity dedup in the verify_text summary
  - Fail-open behaviour on network errors and budget exhaustion

Run: cd backend && python3.12 -m pytest tests/test_citation_verifier.py -v
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.citation_verifier import (
    CELEX_RE,
    COM_RE,
    OEIL_RE,
    RefMatch,
    VerifyResult,
    VerifyTextSummary,
    _cache_lookup,
    _cache_write,
    _com_to_celex_candidates,
    _url_for,
    extract_refs,
    verify_one,
    verify_text,
)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
class TestExtractRefs:
    def test_extract_single_celex(self):
        text = "See Regulation (EU) 2024/1689 (CELEX: 32024R1689)."
        refs = extract_refs(text)
        assert any(r.ref == "32024R1689" and r.kind == "celex" for r in refs)

    def test_extract_celex_with_two_letter_type(self):
        # Proposal CELEX e.g. 52021PC0206
        text = "Commission proposal 52021PC0206 was tabled."
        refs = extract_refs(text)
        assert any(r.ref == "52021PC0206" for r in refs)

    def test_extract_multiple_celex(self):
        text = "GDPR is 32016R0679, AI Act is 32024R1689."
        refs = extract_refs(text)
        celex_refs = [r.ref for r in refs if r.kind == "celex"]
        assert "32016R0679" in celex_refs
        assert "32024R1689" in celex_refs

    def test_extract_dedup_celex(self):
        text = "32024R1689 ... 32024R1689 ... 32024R1689"
        refs = extract_refs(text)
        assert sum(1 for r in refs if r.ref == "32024R1689") == 1

    def test_extract_com_produces_pc_and_dc_candidates(self):
        text = "See COM(2021) 206 final."
        refs = extract_refs(text)
        kinds = {r.kind for r in refs}
        com_refs = {r.ref for r in refs if r.kind == "com_as_celex"}
        assert "com_as_celex" in kinds
        assert "52021PC0206" in com_refs
        assert "52021DC0206" in com_refs
        # Both share the same original_form
        for r in refs:
            if r.kind == "com_as_celex":
                assert "COM" in r.original_form

    def test_extract_com_handles_short_number(self):
        text = "COM(2025) 22 final"
        refs = extract_refs(text)
        com_refs = {r.ref for r in refs if r.kind == "com_as_celex"}
        # 22 should be padded to 0022
        assert "52025PC0022" in com_refs

    def test_extract_oeil_procedure(self):
        text = "Procedure 2021/0106(COD) is the AI Act file."
        refs = extract_refs(text)
        assert any(r.ref == "2021/0106(COD)" and r.kind == "oeil" for r in refs)

    def test_extract_oeil_all_types(self):
        for t in ("COD", "NLE", "APP", "CNS", "INI", "INL", "RSP", "RPS", "BUD"):
            refs = extract_refs(f"reference 2024/1234({t}) here")
            assert any(r.kind == "oeil" and r.ref == f"2024/1234({t})" for r in refs)

    def test_extract_empty_text(self):
        assert extract_refs("") == []
        assert extract_refs("no refs at all here") == []

    def test_extract_mixed(self):
        text = (
            "The AI Act (Regulation (EU) 2024/1689, CELEX 32024R1689) "
            "originated from COM(2021) 206 under procedure 2021/0106(COD)."
        )
        refs = extract_refs(text)
        kinds = {r.kind for r in refs}
        assert kinds == {"celex", "com_as_celex", "oeil"}


# Real identifiers read from Cellar's own CELEX field on 13 Oct 2026 (one or
# more per shape class); the regex must take each whole, with no clipping.
REAL_CELEX_SHAPES = [
    "32024R1689", "52021PC0206", "32023D00161",          # 4- and 5-digit numbers
    "52026XC01937", "52026M12317",                          # sector 5, 5-digit
    "32000R1602R(05)", "52008DC0782R(01)", "42011D0050R(01)",  # corrigendum
    "32014H0729(21)", "22009A0619(01)", "52007XC0720(01)",     # further OJ publication
    "22009A0619(01)R(01)", "42006X1227(05)R(01)",             # both suffixes
    "02003D0565-20110614", "02006D0771(01)-20090514",         # consolidated
    "62012CJ0320", "62023CJ0294_SUM", "62025TO0653(01)",      # case-law
    "72015L2366HRV_279843", "72023L1791LVA_202601970",        # national transposition
    "82003PT1111(51)",                                        # national case-law
    "91980E001013", "91997E002167(01)",                       # parliamentary questions
    "E2016C0186", "E2014J0006", "E2008C0605(01)",            # EFTA
    "C/2026/01104",                                           # OJ C notice
]


class TestCelexShapes:
    @pytest.mark.parametrize("celex", REAL_CELEX_SHAPES)
    def test_whole_identifier_is_one_ref(self, celex):
        refs = [r.ref for r in extract_refs(f"The text cites {celex}.") if r.kind == "celex"]
        assert refs == [celex]

    def test_inside_urls(self):
        for text in (
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679&from=EN",
            "https://publications.europa.eu/resource/celex/32016R0679",
        ):
            assert [r.ref for r in extract_refs(text)] == ["32016R0679"]

    @pytest.mark.parametrize("text", [
        "Regulation 2024/1689", "COM(2021) 206 final", "2024/1689(COD)",
        "timestamp 20240315T120000", "code 12345A678", "IBAN ES9121000418450200051332",
        "glued x32024R1689", "52021PC0206X", "version v2.0.1R3",
    ])
    def test_things_that_are_not_celex(self, text):
        assert [r for r in extract_refs(text) if r.kind == "celex"] == []

    def test_treaties_are_deliberately_not_matched(self):
        # Sector 1 identifiers have no fixed shape (12005SA051, 12008M/PRO/07)
        assert [r for r in extract_refs("Treaty 12008M/PRO/07 and 12005SA051") if r.kind == "celex"] == []


class TestComToCelexCandidates:
    def test_pads_number(self):
        assert _com_to_celex_candidates("2024", "5") == ["52024PC0005", "52024DC0005"]

    def test_long_number_unchanged(self):
        assert _com_to_celex_candidates("2024", "1234") == ["52024PC1234", "52024DC1234"]

    def test_pc_first(self):
        # PC must come first because proposals are more commonly cited than communications
        out = _com_to_celex_candidates("2024", "100")
        assert out[0].endswith("PC0100")
        assert out[1].endswith("DC0100")


class TestUrlBuilders:
    def test_celex_url(self):
        assert _url_for("32024R1689", "celex") == \
            "https://publications.europa.eu/resource/celex/32024R1689"

    def test_com_as_celex_uses_cellar(self):
        assert _url_for("52021PC0206", "com_as_celex") == \
            "https://publications.europa.eu/resource/celex/52021PC0206"

    def test_oeil_url(self):
        assert _url_for("2021/0106(COD)", "oeil") == \
            "https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2021/0106(COD)"

    def test_celex_url_is_percent_encoded(self):
        # Cellar 404s `R(02)` with raw parentheses and 303s the %28/%29 form
        assert _url_for("31962R0031R(02)", "celex") == \
            "https://publications.europa.eu/resource/celex/31962R0031R%2802%29"
        assert _url_for("C/2026/01104", "celex").endswith("/C%2F2026%2F01104")


# ---------------------------------------------------------------------------
# Cache layer (sync helpers)
# ---------------------------------------------------------------------------
class TestCacheLookup:
    def test_no_db_returns_none(self):
        assert _cache_lookup(None, "32024R1689") is None

    def test_missing_row_returns_none(self):
        db = MagicMock()
        db.get.return_value = None
        assert _cache_lookup(db, "32024R1689") is None

    def test_fresh_row_returns_result(self):
        from models.citation_verification import CitationVerification
        row = CitationVerification(
            ref="32024R1689", kind="celex", status="ok",
            resolved_url="https://publications.europa.eu/resource/celex/32024R1689",
            http_status=200, latency_ms=350,
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db = MagicMock()
        db.get.return_value = row
        result = _cache_lookup(db, "32024R1689")
        assert result is not None
        assert result.from_cache is True
        assert result.status == "ok"
        assert result.ref == "32024R1689"

    def test_stale_row_treated_as_miss(self):
        from models.citation_verification import CitationVerification
        row = CitationVerification(
            ref="32024R1689", kind="celex", status="ok",
            verified_at=datetime.utcnow() - timedelta(days=60),
            expires_at=datetime.utcnow() - timedelta(days=30),  # expired
        )
        db = MagicMock()
        db.get.return_value = row
        assert _cache_lookup(db, "32024R1689") is None


class TestCacheWrite:
    def test_no_db_is_noop(self):
        result = VerifyResult(ref="X", kind="celex", status="ok")
        _cache_write(None, result)  # must not raise

    def test_creates_new_row_when_missing(self):
        db = MagicMock()
        db.get.return_value = None
        result = VerifyResult(ref="32024R1689", kind="celex", status="ok",
                              http_status=200, latency_ms=300,
                              resolved_url="https://example.eu/x")
        _cache_write(db, result)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_updates_existing_row(self):
        from models.citation_verification import CitationVerification
        existing = CitationVerification(ref="32024R1689", kind="celex", status="unknown",
                                        verified_at=datetime.utcnow(),
                                        expires_at=datetime.utcnow() + timedelta(hours=1))
        db = MagicMock()
        db.get.return_value = existing
        result = VerifyResult(ref="32024R1689", kind="celex", status="ok",
                              http_status=200, latency_ms=200)
        _cache_write(db, result)
        # No new add when row exists
        db.add.assert_not_called()
        db.commit.assert_called_once()
        assert existing.status == "ok"
        assert existing.http_status == 200

    def test_commit_failure_rolls_back(self):
        db = MagicMock()
        db.get.return_value = None
        db.commit.side_effect = Exception("DB down")
        result = VerifyResult(ref="X", kind="celex", status="ok")
        _cache_write(db, result)  # must not raise
        db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# verify_text (async, network mocked)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestVerifyText:
    async def test_no_refs_returns_empty_summary(self):
        s = await verify_text("hello world", db=None)
        assert s.total_refs == 0
        assert s.verified == 0
        assert s.broken == 0
        assert s.unknown == 0
        assert s.details == []

    async def test_all_cached_skips_network(self):
        from models.citation_verification import CitationVerification
        cached_row = CitationVerification(
            ref="32024R1689", kind="celex", status="ok",
            resolved_url="https://x", http_status=200, latency_ms=10,
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db = MagicMock()
        db.get.return_value = cached_row

        with patch("services.citation_verifier._verify_one_ref") as mock_net:
            s = await verify_text("32024R1689 says hi", db=db)
            mock_net.assert_not_called()
        assert s.cache_hits == 1
        assert s.cache_misses == 0
        assert s.verified == 1

    async def test_network_success_for_miss(self):
        db = MagicMock()
        db.get.return_value = None  # cache miss

        async def fake_verify(_session, match):
            return VerifyResult(
                ref=match.ref, kind=match.kind, status="ok",
                resolved_url="https://x", http_status=200, latency_ms=250,
                original_form=match.original_form,
            )

        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            s = await verify_text("Regulation 32024R1689 governs AI.", db=db)
        assert s.cache_misses == 1
        assert s.verified == 1
        assert s.broken == 0
        # Cache write was attempted
        db.add.assert_called()
        db.commit.assert_called()

    async def test_network_failure_marks_unknown(self):
        async def fake_verify(_session, match):
            return VerifyResult(
                ref=match.ref, kind=match.kind, status="unknown",
                http_status=None, latency_ms=2000,
                original_form=match.original_form,
            )
        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            s = await verify_text("32024R1689", db=None)
        assert s.unknown == 1
        assert s.verified == 0

    async def test_404_marks_broken(self):
        async def fake_verify(_session, match):
            return VerifyResult(
                ref=match.ref, kind=match.kind, status="broken",
                http_status=404, latency_ms=300,
                original_form=match.original_form,
            )
        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            s = await verify_text("Fictional 39999R9999 here", db=None)
        assert s.broken == 1

    async def test_com_pc_resolves_dc_skipped_in_count(self):
        """If COM resolves via PC, the DC sibling shouldn't double-count."""
        async def fake_verify(_session, match):
            # PC resolves OK, DC would 404
            if match.ref.endswith("PC0206"):
                status, http = "ok", 200
                resolved = "https://publications.europa.eu/resource/celex/52021PC0206"
            else:
                status, http = "broken", 404
                resolved = None
            return VerifyResult(
                ref=match.ref, kind=match.kind, status=status,
                resolved_url=resolved, http_status=http, latency_ms=200,
                original_form=match.original_form,
            )

        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            s = await verify_text("See COM(2021) 206 final", db=None)

        # Two details (PC + DC) but the AI wrote ONE COM, so summary counts ONE
        assert len(s.details) == 2
        assert s.total_refs == 1
        assert s.verified == 1
        assert s.broken == 0

    async def test_com_both_fail_counts_one_broken(self):
        """If both PC and DC fail, the COM is broken once, not twice."""
        async def fake_verify(_session, match):
            return VerifyResult(
                ref=match.ref, kind=match.kind, status="broken",
                http_status=404, latency_ms=200,
                original_form=match.original_form,
            )
        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            s = await verify_text("See COM(2099) 999 final", db=None)
        assert s.total_refs == 1
        assert s.broken == 1
        assert s.verified == 0

    async def test_mixed_response_counts(self):
        async def fake_verify(_session, match):
            if match.ref == "32024R1689":
                return VerifyResult(ref=match.ref, kind=match.kind, status="ok",
                                    http_status=200, latency_ms=200,
                                    original_form=match.original_form)
            if match.ref.startswith("5"):  # COM siblings broken
                return VerifyResult(ref=match.ref, kind=match.kind, status="broken",
                                    http_status=404, latency_ms=200,
                                    original_form=match.original_form)
            # OEIL
            return VerifyResult(ref=match.ref, kind=match.kind, status="ok",
                                http_status=200, latency_ms=200,
                                original_form=match.original_form)

        text = "AI Act is 32024R1689, file 2021/0106(COD), proposal COM(2099) 999 final"
        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            s = await verify_text(text, db=None)
        # 3 distinct originals: 1 CELEX + 1 OEIL + 1 COM
        assert s.total_refs == 3
        assert s.verified == 2     # CELEX + OEIL
        assert s.broken == 1       # COM


# ---------------------------------------------------------------------------
# verify_one (single-ref API path)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestVerifyOne:
    async def test_unparseable_returns_unknown(self):
        r = await verify_one("not-a-ref", db=None)
        assert r.status == "unknown"

    async def test_cache_hit_short_circuits(self):
        from models.citation_verification import CitationVerification
        row = CitationVerification(
            ref="32024R1689", kind="celex", status="ok",
            resolved_url="https://x", http_status=200, latency_ms=10,
            verified_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db = MagicMock()
        db.get.return_value = row
        with patch("services.citation_verifier._verify_one_ref") as mock_net:
            r = await verify_one("32024R1689", db=db)
            mock_net.assert_not_called()
        assert r.from_cache is True
        assert r.status == "ok"

    async def test_cache_miss_triggers_network(self):
        db = MagicMock()
        db.get.return_value = None

        async def fake_verify(_session, match):
            return VerifyResult(ref=match.ref, kind=match.kind, status="ok",
                                http_status=200, latency_ms=180)

        with patch("services.citation_verifier._verify_one_ref", side_effect=fake_verify):
            r = await verify_one("32024R1689", db=db)
        assert r.status == "ok"
        assert r.from_cache is False
        db.add.assert_called()
        db.commit.assert_called()


# ---------------------------------------------------------------------------
# Existence without an XHTML manifestation (13 Oct 2026)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestExistenceWithoutXhtml:
    """Cellar 404s an XHTML request for an act that has no XHTML (1986-1997
    regulations, most consolidated texts, sectors 7-9). A wildcard Accept
    answers 303/406 for a held identifier and 404 for an unknown one."""

    async def _run(self, answers):
        from services.citation_verifier import _verify_one_ref
        calls = []

        async def fake(session, url, *, accept, accept_language=None, follow=True):
            calls.append((accept, follow))
            return answers.pop(0), None

        match = RefMatch(ref="31997R0149", kind="celex", original_form="31997R0149")
        with patch("services.citation_verifier._head_or_get", side_effect=fake):
            return await _verify_one_ref(MagicMock(), match), calls

    async def test_xhtml_404_but_wildcard_303_is_ok(self):
        r, calls = await self._run([404, 303])
        assert r.status == "ok" and r.http_status == 303
        assert r.resolved_url is None  # nothing a machine can fetch as XHTML
        assert calls[1] == ("*/*", False)

    async def test_wildcard_406_is_ok(self):
        r, _ = await self._run([404, 406])
        assert r.status == "ok"

    async def test_unknown_identifier_stays_broken(self):
        r, _ = await self._run([404, 404, 404])  # xhtml, wildcard, EUR-Lex
        assert r.status == "broken"

    async def test_xhtml_200_needs_no_second_request(self):
        r, calls = await self._run([200])
        assert r.status == "ok" and len(calls) == 1


class TestDocumentDateFromBody:
    """parse_document_date_from_body read an undefined name and raised NameError
    for every non-empty body (found 13 Oct 2026); /verify-citation then failed for
    any CELEX that eu_laws does not hold (proposals, case-law, newest acts)."""

    def test_reads_the_adoption_date(self):
        from datetime import date
        from api.v1.citations import parse_document_date_from_body
        body = "REGULATION (EU) 2024/1689 OF THE EUROPEAN PARLIAMENT of 13 June 2024 laying down"
        assert parse_document_date_from_body(body) == date(2024, 6, 13)

    def test_empty_and_dateless_bodies_return_none(self):
        from api.v1.citations import parse_document_date_from_body
        assert parse_document_date_from_body(None) is None
        assert parse_document_date_from_body("no preamble date here") is None
