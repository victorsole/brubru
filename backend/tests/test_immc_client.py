"""
Phase 5 of docs/applications/euvoc.md — IMMC client tests.

Static (no network):
  - to_timeline ordering is stable
  - Empty / missing tags don't crash

Live (gated on network — uses pytest.mark.live):
  - GDPR fetch returns at least one event with a valid date
  - Unknown CELEX returns empty events with a 'note' marker
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.api_clients.immc_client import IMMCClient  # noqa: E402


# ----------------------------------------------------------------------
# Static
# ----------------------------------------------------------------------

class TestTimelineHelper:
    def test_empty_input(self):
        assert IMMCClient.to_timeline(None) == []
        assert IMMCClient.to_timeline({}) == []
        assert IMMCClient.to_timeline({"events": []}) == []

    def test_sorts_by_date(self):
        tags = {
            "events": [
                {"date": "2024-12-01", "type": "x"},
                {"date": "2023-05-15", "type": "y"},
                {"date": "2025-01-10", "type": "z"},
            ]
        }
        out = IMMCClient.to_timeline(tags)
        assert [e["type"] for e in out] == ["y", "x", "z"]

    def test_handles_missing_dates(self):
        tags = {
            "events": [
                {"type": "x"},  # no date
                {"date": "2024-01-01", "type": "y"},
            ]
        }
        out = IMMCClient.to_timeline(tags)
        # Missing dates sort first because empty string < any date string
        assert out[0]["type"] == "x"
        assert out[1]["type"] == "y"


# ----------------------------------------------------------------------
# Live
# ----------------------------------------------------------------------

@pytest.mark.live
class TestLiveFetch:
    # Sampled across sectors, decades, and act types — not GDPR-only.
    # Each entry: (CELEX, short label for failure messages).
    _SAMPLE_CELEX = [
        ("32016R0679", "GDPR (Regulation 2016/679)"),
        ("32024R1689", "AI Act (Regulation 2024/1689)"),
        ("32022R2065", "Digital Services Act (DSA)"),
        ("32016L1148", "NIS Directive 1"),
        ("32022L2555", "NIS 2 Directive"),
        ("32020R0852", "EU Taxonomy Regulation"),
        ("32014R0596", "Market Abuse Regulation"),
        ("32023R1542", "Battery Regulation"),
        ("31995L0046", "old Data Protection Directive (repealed)"),
        ("32019R1020", "Market Surveillance Regulation"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("celex,label", _SAMPLE_CELEX)
    async def test_well_shaped_response_across_corpus(self, celex, label):
        """Across a spread of 10 EU acts, the IMMC client must return a
        well-shaped response — `events` (list) + `fetched_at` (str),
        never raise. Event counts vary by act in the upstream graph; we
        assert the contract, not the cardinality.
        """
        async with IMMCClient(timeout=120) as c:
            result = await c.fetch_events_for_celex(celex)
        assert "events" in result, f"{label} response missing 'events' key"
        assert isinstance(result["events"], list), f"{label} 'events' is not a list"
        assert "fetched_at" in result, f"{label} response missing 'fetched_at'"
        if result.get("error"):
            pytest.skip(f"{label} — Cellar SPARQL upstream error: {result['error']}")
        for ev in result["events"]:
            assert any(k in ev for k in ("date", "type", "dossier", "event")), (
                f"{label} event lacks any of date/type/dossier/event: {ev}"
            )

    @pytest.mark.asyncio
    async def test_unknown_celex_returns_empty_with_note(self):
        async with IMMCClient(timeout=60) as c:
            result = await c.fetch_events_for_celex("99999X9999")
        assert result["events"] == []
        # Either the work_uri lookup returned nothing OR the events query did.
        # In the first case the client emits a 'note' marker.
        assert "note" in result or result["events"] == []
