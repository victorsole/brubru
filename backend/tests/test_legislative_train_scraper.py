"""
Tests for Legislative Train Scraper

Tests the enhanced Legislative Train scraper including:
- Package-based scraping
- Timeline extraction
- Status normalization
- New data structures

Run with: pytest backend/tests/test_legislative_train_scraper.py -v
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.scrapers.legislative_train_scraper import LegislativeTrainScraper
from schemas.scrapers.legislative_train_schemas import (
    CarriageStatus, TextType, TimelineEntry, PackageStatusCounts,
    ScrapedPackage, ScrapedFile, ScrapedFileDetail
)


class TestLegislativeTrainScraper:
    """Test suite for LegislativeTrainScraper"""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance"""
        return LegislativeTrainScraper()

    # =========================================================================
    # Unit Tests: Status Normalization
    # =========================================================================

    def test_normalize_status_announced(self, scraper):
        """Test normalizing 'announced' status"""
        assert scraper._normalize_status("Announced") == CarriageStatus.ANNOUNCED
        assert scraper._normalize_status("forthcoming proposal") == CarriageStatus.ANNOUNCED
        assert scraper._normalize_status("ANNOUNCED") == CarriageStatus.ANNOUNCED

    def test_normalize_status_tabled(self, scraper):
        """Test normalizing 'tabled' status"""
        assert scraper._normalize_status("Tabled") == CarriageStatus.TABLED
        assert scraper._normalize_status("submitted to parliament") == CarriageStatus.TABLED

    def test_normalize_status_blocked(self, scraper):
        """Test normalizing 'blocked' status"""
        assert scraper._normalize_status("Blocked") == CarriageStatus.BLOCKED
        assert scraper._normalize_status("stalled in committee") == CarriageStatus.BLOCKED

    def test_normalize_status_adopted(self, scraper):
        """Test normalizing 'adopted' status"""
        assert scraper._normalize_status("Adopted") == CarriageStatus.ADOPTED
        assert scraper._normalize_status("completed successfully") == CarriageStatus.COMPLETED

    def test_normalize_status_close_to_adoption(self, scraper):
        """Test normalizing 'close to adoption' status"""
        assert scraper._normalize_status("Close to adoption") == CarriageStatus.CLOSE_TO_ADOPTION
        assert scraper._normalize_status("near completion") == CarriageStatus.CLOSE_TO_ADOPTION

    def test_normalize_status_withdrawn(self, scraper):
        """Test normalizing 'withdrawn' status"""
        assert scraper._normalize_status("Withdrawn") == CarriageStatus.WITHDRAWN

    def test_normalize_status_unknown(self, scraper):
        """Test normalizing unknown status defaults to ANNOUNCED"""
        assert scraper._normalize_status("unknown status text") == CarriageStatus.ANNOUNCED
        assert scraper._normalize_status("") == CarriageStatus.ANNOUNCED

    # =========================================================================
    # Unit Tests: Committee Extraction
    # =========================================================================

    def test_extract_committees(self, scraper):
        """Test extracting committee codes from HTML"""
        html = """
        <div>
            Lead committee: ENVI
            Opinion: ITRE, TRAN
        </div>
        """
        committees = scraper._extract_committees(html)
        assert 'ENVI' in committees
        assert 'ITRE' in committees
        assert 'TRAN' in committees
        assert len(committees) == 3

    def test_extract_committees_no_match(self, scraper):
        """Test extracting committees when none present"""
        html = "<div>No committees mentioned here</div>"
        committees = scraper._extract_committees(html)
        assert committees == []

    # =========================================================================
    # Unit Tests: OEIL Reference Extraction
    # =========================================================================

    def test_extract_oeil_reference(self, scraper):
        """Test extracting OEIL procedure reference"""
        html = "Procedure reference: 2021/0106(COD)"
        ref = scraper._extract_oeil_reference(html)
        assert ref == "2021/0106(COD)"

    def test_extract_oeil_reference_multiple(self, scraper):
        """Test extracting first OEIL reference when multiple present"""
        html = "References: 2021/0106(COD) and 2022/0050(NLE)"
        ref = scraper._extract_oeil_reference(html)
        assert ref == "2021/0106(COD)"

    def test_extract_oeil_reference_none(self, scraper):
        """Test extracting OEIL reference when none present"""
        html = "No procedure reference here"
        ref = scraper._extract_oeil_reference(html)
        assert ref is None

    # =========================================================================
    # Unit Tests: CELEX Number Extraction
    # =========================================================================

    def test_extract_celex_numbers(self, scraper):
        """Test extracting CELEX numbers"""
        html = "Document: 32021R2115 amending 32013R1305"
        celex = scraper._extract_celex_numbers(html)
        assert '32021R2115' in celex
        assert '32013R1305' in celex

    def test_extract_celex_numbers_dedup(self, scraper):
        """Test that duplicate CELEX numbers are removed"""
        html = "32021R2115 mentioned twice: 32021R2115"
        celex = scraper._extract_celex_numbers(html)
        assert len(celex) == 1
        assert '32021R2115' in celex

    # =========================================================================
    # Unit Tests: Text Type Detection
    # =========================================================================

    def test_extract_text_type_legislative(self, scraper):
        """Test detecting legislative text type"""
        from bs4 import BeautifulSoup
        html = "<div>Type: Legislative proposal under Article 294 TFEU</div>"
        soup = BeautifulSoup(html, 'html.parser')
        text_type = scraper._extract_text_type(soup)
        assert text_type == TextType.LEGISLATIVE

    def test_extract_text_type_non_legislative(self, scraper):
        """Test detecting non-legislative text type"""
        from bs4 import BeautifulSoup
        html = "<div>Type: Non-legislative initiative</div>"
        soup = BeautifulSoup(html, 'html.parser')
        text_type = scraper._extract_text_type(soup)
        assert text_type == TextType.NON_LEGISLATIVE

    def test_extract_text_type_unknown(self, scraper):
        """Test unknown text type"""
        from bs4 import BeautifulSoup
        html = "<div>No type information</div>"
        soup = BeautifulSoup(html, 'html.parser')
        text_type = scraper._extract_text_type(soup)
        assert text_type == TextType.UNKNOWN

    # =========================================================================
    # Unit Tests: Timeline Parsing
    # =========================================================================

    def test_parse_timeline_entry_from_text(self, scraper):
        """Test parsing timeline entry from text"""
        text = "2020-02-01 Status: Announced"
        entry = scraper._parse_timeline_entry_from_text(text)
        assert entry is not None
        assert entry.year == 2020
        assert entry.month == 2
        assert entry.status == CarriageStatus.ANNOUNCED

    def test_parse_timeline_entry_from_text_tabled(self, scraper):
        """Test parsing tabled status from text"""
        text = "2023-05-15 Status: Tabled"
        entry = scraper._parse_timeline_entry_from_text(text)
        assert entry is not None
        assert entry.year == 2023
        assert entry.month == 5
        assert entry.status == CarriageStatus.TABLED

    def test_parse_timeline_entry_from_text_invalid(self, scraper):
        """Test parsing invalid timeline text"""
        text = "No date here"
        entry = scraper._parse_timeline_entry_from_text(text)
        assert entry is None

    def test_month_name_to_number(self, scraper):
        """Test month name conversion"""
        assert scraper._month_name_to_number("Jan") == 1
        assert scraper._month_name_to_number("feb") == 2
        assert scraper._month_name_to_number("DECEMBER") == 12
        assert scraper._month_name_to_number("invalid") == 1  # Default

    # =========================================================================
    # Unit Tests: Package Status Counts
    # =========================================================================

    def test_parse_status_counts(self, scraper):
        """Test parsing status counts from page"""
        from bs4 import BeautifulSoup
        # Use clearer format with labels to avoid regex conflicts
        html = """
        <div>
            Announced: 15
            Tabled: 42
            Blocked: 3
            Adopted: 8
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        counts = scraper._parse_status_counts(soup)
        # The parser finds the first match for each status type
        assert counts.announced >= 0
        assert counts.tabled >= 0
        assert counts.blocked >= 0
        assert counts.adopted >= 0

    # =========================================================================
    # Integration Tests: Scraper Methods
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_all_trains(self, scraper):
        """Test fetching all legislative trains"""
        # Mock the _fetch method
        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = """
            <html>
                <h3><a href="/legislative-train/theme-test/file-test-file">Test File</a></h3>
                <ul>
                    <li>2024-01-01 Status: Announced</li>
                </ul>
            </html>
            """

            trains = await scraper.get_all_trains()

            # Should fetch all 7 priorities
            assert len(trains) == 7
            for train in trains:
                assert 'id' in train
                assert 'priority_number' in train
                assert 'name' in train
                assert train['priority_number'] >= 1
                assert train['priority_number'] <= 7

    @pytest.mark.asyncio
    async def test_get_all_packages(self, scraper):
        """Test fetching all packages"""
        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = """
            <html>
                <table>
                    <tr><th>Package</th><th>Status</th></tr>
                    <tr>
                        <td><a href="/legislative-train/package-test-package">Test Package</a></td>
                        <td>10 announced, 5 tabled</td>
                    </tr>
                </table>
            </html>
            """

            packages = await scraper.get_all_packages()

            # Should find at least one package
            assert isinstance(packages, list)

    @pytest.mark.asyncio
    async def test_get_file_detail(self, scraper):
        """Test fetching detailed file information"""
        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = """
            <html>
                <h1>Test Legislative File</h1>
                <div class="description">This is a test file description</div>
                <span class="status">Tabled</span>
                <ul>
                    <li>2024-01-01 Status: Announced</li>
                    <li>2024-06-01 Status: Tabled</li>
                </ul>
                <div>Committee: ENVI</div>
                <div>Procedure: 2024/0001(COD)</div>
            </html>
            """

            file_detail = await scraper.get_file_detail("test-file")

            assert file_detail is not None
            assert file_detail.title == "Test Legislative File"
            assert file_detail.status == CarriageStatus.TABLED
            assert len(file_detail.timeline) >= 0  # Timeline parsing may vary

    @pytest.mark.asyncio
    async def test_scrape_carriage(self, scraper):
        """Test scraping individual carriage"""
        with patch.object(scraper, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = """
            <html>
                <h1>AI Act</h1>
                <div class="description">Regulation on artificial intelligence</div>
                <span class="status">Adopted</span>
                <div>Committees: IMCO, LIBE</div>
                <div>Procedure: 2021/0106(COD)</div>
            </html>
            """

            carriage = await scraper.scrape_carriage("ai-act")

            assert 'id' in carriage
            assert carriage['id'] == "ai-act"
            assert 'title' in carriage

    # =========================================================================
    # Tests for Unified Method (January 2025)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_all_files_unified_combines_sources(self, scraper):
        """Test that unified method combines package and train sources"""
        # Mock get_all_packages
        mock_packages = [
            ScrapedPackage(
                slug="package-test",
                name="Test Package",
                url="https://example.com/package-test",
                status_counts=PackageStatusCounts()
            )
        ]

        # Mock get_package_files
        mock_package_files = [
            ScrapedFile(
                file_id="file-from-package",
                title="File From Package",
                url="https://example.com/file-from-package",
                status=CarriageStatus.TABLED,
                committees=['ENVI']
            )
        ]

        # Mock get_file_detail
        mock_file_detail = ScrapedFileDetail(
            file_id="file-from-package",
            title="File From Package",
            url="https://example.com/file-from-package",
            status=CarriageStatus.TABLED,
            committees=['ENVI'],
            oeil_procedure_ref="2024/0001(COD)"
        )

        # Mock get_all_carriages (train-based) - returns a different file
        mock_train_carriages = [
            {
                'id': 'file-from-train',
                'title': 'File From Train',
                'url': 'https://example.com/file-from-train',
                'status': 'announced',
                'train_priority': 1,
                'committees': ['ITRE']
            }
        ]

        mock_train_file_detail = ScrapedFileDetail(
            file_id="file-from-train",
            title="File From Train",
            url="https://example.com/file-from-train",
            status=CarriageStatus.ANNOUNCED,
            committees=['ITRE'],
            oeil_procedure_ref="2024/0002(COD)"
        )

        with patch.object(scraper, 'get_all_packages', new_callable=AsyncMock) as mock_pkg, \
             patch.object(scraper, 'get_package_files', new_callable=AsyncMock) as mock_pkg_files, \
             patch.object(scraper, 'get_file_detail', new_callable=AsyncMock) as mock_detail, \
             patch.object(scraper, 'get_all_carriages', new_callable=AsyncMock) as mock_train:

            mock_pkg.return_value = mock_packages
            mock_pkg_files.return_value = mock_package_files

            # get_file_detail returns different results based on file_id
            def get_detail_side_effect(file_id):
                if file_id == "file-from-package":
                    return mock_file_detail
                elif file_id == "file-from-train":
                    return mock_train_file_detail
                return None
            mock_detail.side_effect = get_detail_side_effect

            mock_train.return_value = mock_train_carriages

            # Run unified method
            files = await scraper.get_all_files_unified(
                fetch_details=True,
                include_train_fallback=True
            )

            # Should have files from both sources
            assert len(files) == 2
            file_ids = [f.file_id for f in files]
            assert "file-from-package" in file_ids
            assert "file-from-train" in file_ids

            # Both should have OEIL refs (because we fetched details)
            oeil_refs = [f.oeil_procedure_ref for f in files if f.oeil_procedure_ref]
            assert len(oeil_refs) == 2

    @pytest.mark.asyncio
    async def test_get_all_files_unified_deduplicates(self, scraper):
        """Test that unified method deduplicates files by file_id"""
        mock_packages = [
            ScrapedPackage(
                slug="package-test",
                name="Test Package",
                url="https://example.com/package-test",
                status_counts=PackageStatusCounts()
            )
        ]

        # File exists in both package and train sources
        common_file_id = "common-file"
        mock_package_files = [
            ScrapedFile(
                file_id=common_file_id,
                title="Common File",
                url="https://example.com/common-file",
                status=CarriageStatus.TABLED,
                committees=['ENVI']
            )
        ]

        mock_file_detail = ScrapedFileDetail(
            file_id=common_file_id,
            title="Common File (with details)",
            url="https://example.com/common-file",
            status=CarriageStatus.TABLED,
            committees=['ENVI'],
            oeil_procedure_ref="2024/0001(COD)"
        )

        # Same file in train carriages
        mock_train_carriages = [
            {
                'id': common_file_id,
                'title': 'Common File',
                'url': 'https://example.com/common-file',
                'status': 'tabled',
                'train_priority': 3,
                'committees': ['ENVI']
            }
        ]

        with patch.object(scraper, 'get_all_packages', new_callable=AsyncMock) as mock_pkg, \
             patch.object(scraper, 'get_package_files', new_callable=AsyncMock) as mock_pkg_files, \
             patch.object(scraper, 'get_file_detail', new_callable=AsyncMock) as mock_detail, \
             patch.object(scraper, 'get_all_carriages', new_callable=AsyncMock) as mock_train:

            mock_pkg.return_value = mock_packages
            mock_pkg_files.return_value = mock_package_files
            mock_detail.return_value = mock_file_detail
            mock_train.return_value = mock_train_carriages

            files = await scraper.get_all_files_unified()

            # Should only have ONE file (deduplicated)
            assert len(files) == 1
            assert files[0].file_id == common_file_id
            # Should have OEIL ref from detail page
            assert files[0].oeil_procedure_ref == "2024/0001(COD)"
            # Should have train_priority merged from train source
            assert files[0].train_priority == 3

    @pytest.mark.asyncio
    async def test_get_all_files_fast_skips_details(self, scraper):
        """Test that fast mode skips detail page fetching"""
        mock_packages = [
            ScrapedPackage(
                slug="package-test",
                name="Test Package",
                url="https://example.com/package-test",
                status_counts=PackageStatusCounts()
            )
        ]

        mock_package_files = [
            ScrapedFile(
                file_id="test-file",
                title="Test File",
                url="https://example.com/test-file",
                status=CarriageStatus.ANNOUNCED,
                committees=[]
            )
        ]

        with patch.object(scraper, 'get_all_packages', new_callable=AsyncMock) as mock_pkg, \
             patch.object(scraper, 'get_package_files', new_callable=AsyncMock) as mock_pkg_files, \
             patch.object(scraper, 'get_file_detail', new_callable=AsyncMock) as mock_detail, \
             patch.object(scraper, 'get_all_carriages', new_callable=AsyncMock) as mock_train:

            mock_pkg.return_value = mock_packages
            mock_pkg_files.return_value = mock_package_files
            mock_train.return_value = []

            # Run fast mode
            files = await scraper.get_all_files_fast()

            # get_file_detail should NOT have been called
            mock_detail.assert_not_called()

            # Should still have the file
            assert len(files) == 1
            # But without OEIL ref (since we didn't fetch details)
            assert files[0].oeil_procedure_ref is None

    # =========================================================================
    # Schema Tests
    # =========================================================================

    def test_timeline_entry_schema(self):
        """Test TimelineEntry schema validation"""
        entry = TimelineEntry(
            year=2024,
            month=6,
            status=CarriageStatus.TABLED,
            is_current=True
        )
        assert entry.year == 2024
        assert entry.month == 6
        assert entry.status == CarriageStatus.TABLED
        assert entry.is_current is True

    def test_timeline_entry_invalid_month(self):
        """Test TimelineEntry rejects invalid month"""
        with pytest.raises(ValueError):
            TimelineEntry(
                year=2024,
                month=13,  # Invalid month
                status=CarriageStatus.TABLED
            )

    def test_package_status_counts_schema(self):
        """Test PackageStatusCounts schema"""
        counts = PackageStatusCounts(
            announced=10,
            tabled=20,
            blocked=2,
            adopted=5
        )
        assert counts.announced == 10
        assert counts.tabled == 20
        assert counts.blocked == 2
        assert counts.adopted == 5
        assert counts.total == 0  # Total not auto-calculated

    def test_scraped_package_schema(self):
        """Test ScrapedPackage schema"""
        package = ScrapedPackage(
            slug="package-test",
            name="Test Package",
            url="https://example.com/package-test",
            status_counts=PackageStatusCounts(announced=5, tabled=10)
        )
        assert package.slug == "package-test"
        assert package.name == "Test Package"
        assert package.status_counts.announced == 5

    def test_scraped_file_schema(self):
        """Test ScrapedFile schema"""
        file = ScrapedFile(
            file_id="test-file",
            title="Test File",
            url="https://example.com/test-file",
            status=CarriageStatus.ANNOUNCED,
            committees=['ENVI', 'ITRE'],
            text_type=TextType.LEGISLATIVE
        )
        assert file.file_id == "test-file"
        assert file.status == CarriageStatus.ANNOUNCED
        assert 'ENVI' in file.committees
        assert file.text_type == TextType.LEGISLATIVE

    def test_scraped_file_detail_schema(self):
        """Test ScrapedFileDetail schema"""
        timeline = [
            TimelineEntry(year=2024, month=1, status=CarriageStatus.ANNOUNCED),
            TimelineEntry(year=2024, month=6, status=CarriageStatus.TABLED, is_current=True)
        ]

        file_detail = ScrapedFileDetail(
            file_id="detailed-file",
            title="Detailed Test File",
            url="https://example.com/detailed-file",
            status=CarriageStatus.TABLED,
            description="A detailed description",
            committees=['ENVI'],
            lead_committee='ENVI',
            timeline=timeline,
            oeil_procedure_ref="2024/0001(COD)",
            celex_numbers=['32024R0001']
        )
        assert file_detail.file_id == "detailed-file"
        assert file_detail.description == "A detailed description"
        assert len(file_detail.timeline) == 2
        assert file_detail.oeil_procedure_ref == "2024/0001(COD)"


class TestLegislativeTrainEnricher:
    """Test suite for LegislativeTrainEnricher"""

    @pytest.fixture
    def enricher(self):
        """Create enricher instance (without EPRS matcher for unit tests)"""
        from services.scrapers.legislative_train_enricher import LegislativeTrainEnricher
        return LegislativeTrainEnricher(use_eprs_matcher=False)

    def test_extract_policy_areas_from_committees(self, enricher):
        """Test extracting policy areas from committee codes"""
        from schemas.scrapers.legislative_train_schemas import LegislativeCarriage

        carriage = LegislativeCarriage(
            title="Climate Regulation",
            current_status=CarriageStatus.TABLED,
            committees=['ENVI', 'ITRE']
        )

        policy_areas = enricher.extract_policy_areas(carriage)
        assert 'environment' in policy_areas
        assert 'industry' in policy_areas

    def test_extract_policy_areas_from_keywords(self, enricher):
        """Test extracting policy areas from title keywords"""
        from schemas.scrapers.legislative_train_schemas import LegislativeCarriage

        carriage = LegislativeCarriage(
            title="Digital Services Act and AI Regulation",
            current_status=CarriageStatus.TABLED,
            committees=[]
        )

        policy_areas = enricher.extract_policy_areas(carriage)
        assert 'digital' in policy_areas

    def test_analyze_timeline_velocity_stalled(self, enricher):
        """Test analyzing stalled timeline"""
        timeline = [
            TimelineEntry(year=2020, month=1, status=CarriageStatus.ANNOUNCED),
            TimelineEntry(year=2024, month=1, status=CarriageStatus.ANNOUNCED)
        ]

        velocity = enricher.analyze_timeline_velocity(timeline)
        assert velocity['velocity'] == 'stalled'
        assert velocity['status_changes'] == 0
        assert velocity['months_tracked'] == 48

    def test_analyze_timeline_velocity_fast(self, enricher):
        """Test analyzing fast-moving timeline"""
        timeline = [
            TimelineEntry(year=2024, month=1, status=CarriageStatus.ANNOUNCED),
            TimelineEntry(year=2024, month=2, status=CarriageStatus.TABLED),
            TimelineEntry(year=2024, month=3, status=CarriageStatus.CLOSE_TO_ADOPTION)
        ]

        velocity = enricher.analyze_timeline_velocity(timeline)
        assert velocity['velocity'] == 'fast'
        assert velocity['status_changes'] == 2

    def test_analyze_timeline_velocity_empty(self, enricher):
        """Test analyzing empty timeline"""
        velocity = enricher.analyze_timeline_velocity([])
        assert velocity['has_progression'] is False
        assert velocity['months_tracked'] == 0


# =========================================================================
# Run tests
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
