"""
Test OEIL Scraper

Tests the enhanced OEIL scraper with full procedure page parsing.
"""

import asyncio
import json
import pytest
from datetime import datetime

from services.scrapers.oeil_scraper import OEILScraper
from schemas.scrapers.oeil_schemas import OEILProcedure


# Test procedure references
TEST_PROCEDURES = [
    "2024/0176(COD)",  # AI Act amendment
    "2021/0106(COD)",  # AI Act (original)
    "2022/0066(COD)",  # Cyber Resilience Act
]


class TestOEILScraper:
    """Test suite for OEIL Scraper"""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance"""
        return OEILScraper()

    @pytest.mark.asyncio
    async def test_get_procedure_full_returns_oeil_procedure(self, scraper):
        """Test that get_procedure_full returns OEILProcedure object"""
        procedure_ref = "2025/0102(COD)"

        try:
            result = await scraper.get_procedure_full(procedure_ref)

            # Verify type
            assert isinstance(result, OEILProcedure)

            # Verify basic info
            assert result.basic_info.reference == procedure_ref
            assert result.source_url is not None

            print(f"\n✓ Successfully fetched procedure: {procedure_ref}")
            print(f"  Title: {result.basic_info.title}")
            print(f"  Status: {result.basic_info.status}")
            print(f"  Type: {result.basic_info.procedure_type}")

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_get_procedure_returns_dict(self, scraper):
        """Test that get_procedure returns dictionary"""
        procedure_ref = "2025/0102(COD)"

        try:
            result = await scraper.get_procedure(procedure_ref)

            # Verify type
            assert isinstance(result, dict)

            # Verify no error
            assert "error" not in result or result.get("error") is None

            # Verify basic fields
            assert "basic_info" in result
            assert result["basic_info"]["reference"] == procedure_ref

            print(f"\n✓ get_procedure returned valid dictionary")

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_key_players_extraction(self, scraper):
        """Test extraction of key players section"""
        procedure_ref = "2025/0102(COD)"

        try:
            result = await scraper.get_procedure_full(procedure_ref)

            key_players = result.key_players

            # Check committee
            if key_players.committee_responsible:
                print(f"\n✓ Committee Responsible: {key_players.committee_responsible.code}")
                if key_players.committee_responsible.rapporteur:
                    print(f"  Rapporteur: {key_players.committee_responsible.rapporteur.name}")
                    if key_players.committee_responsible.rapporteur.mep_id:
                        print(f"  MEP ID: {key_players.committee_responsible.rapporteur.mep_id}")

            # Check Commission
            if key_players.commission_dg:
                print(f"  Commission DG: {key_players.commission_dg}")

            if key_players.commissioner:
                print(f"  Commissioner: {key_players.commissioner}")

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_key_events_extraction(self, scraper):
        """Test extraction of key events section"""
        procedure_ref = "2025/0102(COD)"

        try:
            result = await scraper.get_procedure_full(procedure_ref)

            events = result.key_events.events

            print(f"\n✓ Found {len(events)} key events")
            for event in events[:5]:  # Show first 5
                print(f"  - {event.date}: {event.event_type}")

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_documentation_extraction(self, scraper):
        """Test extraction of documentation gateway section"""
        procedure_ref = "2025/0102(COD)"

        try:
            result = await scraper.get_procedure_full(procedure_ref)

            docs = result.documentation

            print(f"\n✓ Documentation Gateway:")
            print(f"  EP Documents: {len(docs.ep_documents)}")
            print(f"  Commission Documents: {len(docs.commission_documents)}")
            print(f"  Council Documents: {len(docs.council_documents)}")
            print(f"  Other Documents: {len(docs.other_documents)}")
            print(f"  National Parliament Contributions: {len(docs.national_parliament_contributions)}")

        finally:
            await scraper.close()


async def manual_test():
    """Manual test function for quick verification"""
    print("=" * 60)
    print("OEIL Scraper Manual Test")
    print("=" * 60)

    scraper = OEILScraper()

    try:
        procedure_ref = "2025/0102(COD)"
        print(f"\nFetching procedure: {procedure_ref}")
        print("-" * 40)

        result = await scraper.get_procedure_full(procedure_ref)

        print(f"\n📋 BASIC INFO")
        print(f"   Reference: {result.basic_info.reference}")
        print(f"   Title: {result.basic_info.title}")
        print(f"   Type: {result.basic_info.procedure_type}")
        print(f"   Status: {result.basic_info.status}")
        print(f"   Subjects: {len(result.basic_info.subjects)}")

        print(f"\n👥 KEY PLAYERS")
        if result.key_players.committee_responsible:
            comm = result.key_players.committee_responsible
            print(f"   Committee: {comm.code}")
            if comm.rapporteur:
                print(f"   Rapporteur: {comm.rapporteur.name} ({comm.rapporteur.political_group or 'N/A'})")
                print(f"   MEP ID: {comm.rapporteur.mep_id or 'N/A'}")
            print(f"   Shadow Rapporteurs: {len(comm.shadow_rapporteurs)}")
        print(f"   Commission DG: {result.key_players.commission_dg or 'N/A'}")
        print(f"   Commissioner: {result.key_players.commissioner or 'N/A'}")
        print(f"   Opinion Committees: {len(result.key_players.committees_opinion)}")

        print(f"\n📅 KEY EVENTS")
        print(f"   Total events: {len(result.key_events.events)}")
        for event in result.key_events.events[:3]:
            print(f"   - {event.date}: {event.event_type[:50]}...")

        print(f"\n🔮 FORECASTS")
        print(f"   Total forecasts: {len(result.forecasts.forecasts)}")
        for forecast in result.forecasts.forecasts[:3]:
            print(f"   - {forecast.forecast_date}: {forecast.event_type}")

        print(f"\n⚙️ TECHNICAL INFO")
        if result.technical_info:
            print(f"   Procedure Type: {result.technical_info.procedure_type or 'N/A'}")
            print(f"   Stage Reached: {result.technical_info.stage_reached or 'N/A'}")
            print(f"   Legal Basis: {len(result.technical_info.legal_basis)} items")

        print(f"\n📁 DOCUMENTATION")
        docs = result.documentation
        print(f"   EP Documents: {len(docs.ep_documents)}")
        print(f"   Commission Documents: {len(docs.commission_documents)}")
        print(f"   National Parliament: {len(docs.national_parliament_contributions)}")

        print(f"\nℹ️ ADDITIONAL INFO")
        print(f"   EUR-Lex URL: {result.additional_info.eurlex_url or 'N/A'}")
        print(f"   CELEX: {result.additional_info.celex_number or 'N/A'}")
        print(f"   Related Procedures: {len(result.additional_info.related_procedures)}")

        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print("=" * 60)

        # Also output as JSON for inspection
        print("\n📄 JSON Output (truncated):")
        json_output = result.model_dump_json(indent=2)
        print(json_output[:2000] + "..." if len(json_output) > 2000 else json_output)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(manual_test())
