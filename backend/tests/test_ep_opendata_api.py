"""
Test EP Open Data API v2 Enhancements

Tests the enhanced European Parliament API client and scraper
with voting records, speeches, questions, and procedure events.
"""

import asyncio
import pytest
from datetime import datetime, timedelta

from services.api_clients.european_parliament_client import EuropeanParliamentClient
from services.scrapers.european_parliament_scraper import EuropeanParliamentScraper


class TestEPOpenDataAPI:
    """Test suite for EP Open Data API v2 enhancements"""

    @pytest.fixture
    def client(self):
        """Create EP client instance"""
        return EuropeanParliamentClient()

    @pytest.fixture
    def scraper(self):
        """Create EP scraper instance"""
        return EuropeanParliamentScraper()

    # =========================================================================
    # MEP Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_current_meps(self, client):
        """Test fetching current MEPs"""
        try:
            meps = await client.get_current_meps(limit=10)

            print(f"\n Current MEPs: {len(meps)}")
            for mep in meps[:3]:
                print(f"  - {mep.get('name', 'N/A')} ({mep.get('country', 'N/A')})")

            assert isinstance(meps, list)
            if meps:
                assert "id" in meps[0] or "name" in meps[0]

        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_get_meps_by_country(self, client):
        """Test fetching MEPs filtered by country"""
        try:
            meps = await client.get_current_meps(country="ES", limit=10)

            print(f"\n Spanish MEPs: {len(meps)}")
            for mep in meps[:3]:
                print(f"  - {mep.get('name', 'N/A')}")

            assert isinstance(meps, list)

        finally:
            await client.close()

    # =========================================================================
    # Meeting Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_meetings(self, client):
        """Test fetching parliamentary meetings"""
        try:
            meetings = await client.get_meetings(limit=10)

            print(f"\n Meetings: {len(meetings)}")
            for meeting in meetings[:3]:
                print(f"  - {meeting.date}: {meeting.meeting_type} - {meeting.title or 'No title'}")

            assert isinstance(meetings, list)

        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_get_meetings_by_date_range(self, client):
        """Test fetching meetings within a date range"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            meetings = await client.get_meetings(
                start_date=start_date,
                end_date=end_date,
                limit=20
            )

            print(f"\n Meetings in last 30 days: {len(meetings)}")
            for meeting in meetings[:5]:
                print(f"  - {meeting.date}: {meeting.meeting_type}")

            assert isinstance(meetings, list)

        finally:
            await client.close()

    # =========================================================================
    # Vote Results Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_meeting_vote_results(self, client):
        """Test fetching vote results from a meeting"""
        try:
            # First get a recent meeting
            meetings = await client.get_meetings(limit=20)

            sitting_id = None
            for meeting in meetings:
                if meeting.meeting_id:
                    sitting_id = meeting.meeting_id
                    break

            if not sitting_id:
                print("\n No meetings found to test vote results")
                return

            votes = await client.get_meeting_vote_results(sitting_id)

            print(f"\n Vote results for {sitting_id}: {len(votes)}")
            for vote in votes[:3]:
                print(f"  - {vote.title or 'N/A'}: {vote.result}")
                if vote.votes_for:
                    print(f"    For: {vote.votes_for}, Against: {vote.votes_against}, Abstentions: {vote.abstentions}")

            assert isinstance(votes, list)

        finally:
            await client.close()

    # =========================================================================
    # Procedure Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_procedures(self, client):
        """Test fetching legislative procedures"""
        try:
            procedures = await client.get_procedures(limit=10)

            print(f"\n Procedures: {len(procedures)}")
            for proc in procedures[:3]:
                print(f"  - {proc.get('reference', proc.get('label', 'N/A'))}")

            assert isinstance(procedures, list)

        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_get_procedure_by_reference(self, client):
        """Test fetching a specific procedure by reference"""
        try:
            # Use a known procedure reference
            procedure_ref = "2021/0106(COD)"  # AI Act
            procedure = await client.get_procedure_by_reference(procedure_ref)

            if procedure:
                print(f"\n Procedure found: {procedure_ref}")
                print(f"  ID: {procedure.get('identifier', procedure.get('id', 'N/A'))}")
                print(f"  Label: {procedure.get('label', 'N/A')}")
            else:
                print(f"\n Procedure not found: {procedure_ref}")

        finally:
            await client.close()

    # =========================================================================
    # Speech Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_speeches(self, client):
        """Test fetching MEP speeches"""
        try:
            speeches = await client.get_speeches(limit=10)

            print(f"\n Speeches: {len(speeches)}")
            for speech in speeches[:3]:
                print(f"  - {speech.mep_name or speech.mep_id}: {speech.title or 'No title'}")

            assert isinstance(speeches, list)

        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_get_speeches_by_text(self, client):
        """Test searching speeches by text"""
        try:
            speeches = await client.get_speeches(text="artificial intelligence", limit=10)

            print(f"\n Speeches about AI: {len(speeches)}")
            for speech in speeches[:3]:
                print(f"  - {speech.mep_name or speech.mep_id}: {speech.title or 'No title'}")

            assert isinstance(speeches, list)

        finally:
            await client.close()

    # =========================================================================
    # Parliamentary Questions Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_parliamentary_questions(self, client):
        """Test fetching parliamentary questions"""
        try:
            questions = await client.get_parliamentary_questions(limit=10)

            print(f"\n Parliamentary questions: {len(questions)}")
            for q in questions[:3]:
                print(f"  - {q.question_reference or q.question_id}: {q.title[:50]}...")

            assert isinstance(questions, list)

        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_get_questions_by_text(self, client):
        """Test searching questions by text"""
        try:
            questions = await client.get_parliamentary_questions(
                text="climate",
                limit=10
            )

            print(f"\n Questions about climate: {len(questions)}")
            for q in questions[:3]:
                print(f"  - {q.title[:60]}...")

            assert isinstance(questions, list)

        finally:
            await client.close()

    # =========================================================================
    # MEP Declarations Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_mep_declarations(self, client):
        """Test fetching MEP declarations"""
        try:
            declarations = await client.get_mep_declarations(limit=10)

            print(f"\n MEP declarations: {len(declarations)}")
            for decl in declarations[:3]:
                print(f"  - {decl.mep_name or decl.mep_id}: {decl.declaration_type}")

            assert isinstance(declarations, list)

        finally:
            await client.close()

    # =========================================================================
    # Scraper Integration Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_scraper_get_meetings(self, scraper):
        """Test scraper's meeting method"""
        try:
            meetings = await scraper.get_meetings(limit=5)

            print(f"\n [Scraper] Meetings: {len(meetings)}")
            assert isinstance(meetings, list)

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_scraper_get_speeches(self, scraper):
        """Test scraper's speeches method"""
        try:
            speeches = await scraper.get_speeches(limit=5)

            print(f"\n [Scraper] Speeches: {len(speeches)}")
            assert isinstance(speeches, list)

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_scraper_get_questions(self, scraper):
        """Test scraper's parliamentary questions method"""
        try:
            questions = await scraper.get_parliamentary_questions(limit=5)

            print(f"\n [Scraper] Questions: {len(questions)}")
            assert isinstance(questions, list)

        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_scraper_get_current_meps(self, scraper):
        """Test scraper's current MEPs method"""
        try:
            meps = await scraper.get_current_meps(limit=5)

            print(f"\n [Scraper] Current MEPs: {len(meps)}")
            assert isinstance(meps, list)

        finally:
            await scraper.close()


# ============================================================================
# Manual Test Function
# ============================================================================

async def manual_test():
    """Manual test function for quick verification"""
    print("=" * 60)
    print("EP Open Data API v2 - Manual Test")
    print("=" * 60)

    client = EuropeanParliamentClient()

    try:
        # Test 1: Current MEPs
        print("\n1. Current MEPs")
        print("-" * 40)
        meps = await client.get_current_meps(limit=5)
        print(f"   Found {len(meps)} MEPs")
        for mep in meps[:3]:
            print(f"   - {mep.get('name', 'N/A')} ({mep.get('country', 'N/A')})")

        # Test 2: Meetings
        print("\n2. Recent Meetings")
        print("-" * 40)
        meetings = await client.get_meetings(limit=5)
        print(f"   Found {len(meetings)} meetings")
        for meeting in meetings[:3]:
            print(f"   - {meeting.date}: {meeting.meeting_type}")

        # Test 3: Procedures
        print("\n3. Legislative Procedures")
        print("-" * 40)
        procedures = await client.get_procedures(limit=5)
        print(f"   Found {len(procedures)} procedures")
        for proc in procedures[:3]:
            print(f"   - {proc.get('label', proc.get('reference', 'N/A'))[:60]}")

        # Test 4: Speeches
        print("\n4. MEP Speeches")
        print("-" * 40)
        speeches = await client.get_speeches(limit=5)
        print(f"   Found {len(speeches)} speeches")
        for speech in speeches[:3]:
            print(f"   - {speech.mep_name or speech.mep_id}: {speech.title or 'No title'}")

        # Test 5: Parliamentary Questions
        print("\n5. Parliamentary Questions")
        print("-" * 40)
        questions = await client.get_parliamentary_questions(limit=5)
        print(f"   Found {len(questions)} questions")
        for q in questions[:3]:
            print(f"   - {q.title[:50] if q.title else 'No title'}...")

        # Test 6: Vote Results (if meetings available)
        if meetings:
            print("\n6. Vote Results (from first meeting)")
            print("-" * 40)
            sitting_id = meetings[0].meeting_id
            votes = await client.get_meeting_vote_results(sitting_id)
            print(f"   Found {len(votes)} vote results for {sitting_id}")
            for vote in votes[:3]:
                print(f"   - {vote.title or 'N/A'}: {vote.result}")

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(manual_test())
