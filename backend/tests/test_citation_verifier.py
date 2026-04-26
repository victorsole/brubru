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
