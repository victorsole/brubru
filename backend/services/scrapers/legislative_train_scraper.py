"""
Legislative Train Scraper

Enhanced scraper for European Parliament Legislative Train Schedule.
Tracks EU legislative priorities through web scraping (no API available).

ENHANCED (January 2025):
- Package-based entry point (/legislative-train/packages)
- Package hierarchy (parent/sub-packages)
- Monthly timeline extraction
- Text type detection (legislative/non-legislative)
- Spotlight tags and "recently updated" detection
- Backward compatible with existing methods

Features:
- Scrape all packages with status counts
- Extract ~490 legislative file "carriages"
- Track status progression through monthly timeline
- Link to OEIL procedures
- Committee-based filtering

DATA SOURCE UNIFICATION (January 2025):
=======================================
The EP Legislative Train website has TWO different views. This scraper now
provides a UNIFIED method that combines both:

1. TRAIN/THEME PAGES (/legislative-train/theme-*)
   - Old method: get_all_carriages() - still available for backward compatibility
   - Returns: ~366 files organized by EC priority
   - OEIL refs: NOT available (listing pages don't include them)

2. PACKAGE PAGES (/legislative-train/package-*)
   - Old method: get_package_files()
   - Returns: ~441 files organized by thematic package
   - OEIL refs: Available on file detail pages

3. NEW UNIFIED METHOD: get_all_files_unified()
   - Combines BOTH sources
   - Always fetches file detail pages to get OEIL refs
   - Deduplicates by file_id
   - Target: 95%+ of files have OEIL refs

See: https://www.europarl.europa.eu/legislative-train/
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper
from schemas.scrapers.legislative_train_schemas import (
    CarriageStatus, TextType, TimelineEntry, PackageStatusCounts,
    ScrapedPackage, ScrapedFile, ScrapedFileDetail, EPRSBriefingReference
)

logger = logging.getLogger(__name__)


class LegislativeTrainScraper(BaseScraper):
    """
    Scraper for EP Legislative Train Schedule.

    The Legislative Train uses a train metaphor:
    - Trains = EC priorities (7 main priorities)
    - Packages = Thematic groupings with sub-packages
    - Carriages = Individual legislative files (~490 total)
    - Status = Progress through legislative process

    Data access: Web scraping only (no API/RSS available)
    Update frequency: Monthly (end of each month)

    ENHANCED (January 2025):
    - Package-based entry point for hierarchical data
    - Timeline extraction for monthly status snapshots
    - Text type and spotlight detection
    """

    # URL patterns
    PACKAGES_URL = "https://www.europarl.europa.eu/legislative-train/packages"
    PACKAGE_URL_PATTERN = "https://www.europarl.europa.eu/legislative-train/{slug}"

    def __init__(self):
        super().__init__(
            base_url="https://www.europarl.europa.eu/legislative-train/",
            name="LegislativeTrain",
            rate_limit_delay=2.0,  # Respect EP servers
            cache_ttl=604800      # Cache for 1 week (updates monthly)
        )

        # Committee codes for filtering
        self.committee_codes = [
            'AFET', 'DROI', 'SEDE', 'DEVE', 'INTA', 'BUDG', 'CONT',
            'ECON', 'EMPL', 'ENVI', 'ITRE', 'IMCO', 'TRAN', 'REGI',
            'AGRI', 'PECH', 'CULT', 'JURI', 'LIBE', 'AFCO', 'FEMM', 'PETI'
        ]

        # Theme slug mapping (2024-29 Commission priorities) - for backward compatibility
        self.theme_slugs = {
            'priority-1': 'theme-a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness',
            'priority-2': 'theme-a-new-era-for-european-defence-and-security',
            'priority-3': 'theme-supporting-people-strengthening-our-societies-and-our-social-model',
            'priority-4': 'theme-sustaining-our-quality-of-life-food-security-water-and-nature',
            'priority-5': 'theme-protecting-our-democracy-upholding-our-values',
            'priority-6': 'theme-a-global-europe-leveraging-our-power-and-partnerships',
            'priority-7': 'theme-delivering-together-and-preparing-our-union-for-the-future'
        }

        # Status text normalization mapping
        self.status_mapping = {
            'announced': CarriageStatus.ANNOUNCED,
            'forthcoming': CarriageStatus.ANNOUNCED,
            'legislative initiative': CarriageStatus.LEGISLATIVE_INITIATIVE,
            'tabled': CarriageStatus.TABLED,
            'submitted': CarriageStatus.TABLED,
            'close to adoption': CarriageStatus.CLOSE_TO_ADOPTION,
            'near completion': CarriageStatus.CLOSE_TO_ADOPTION,
            'completed': CarriageStatus.COMPLETED,
            'adopted': CarriageStatus.ADOPTED,
            'done': CarriageStatus.COMPLETED,
            'blocked': CarriageStatus.BLOCKED,
            'stalled': CarriageStatus.BLOCKED,
            'withdrawn': CarriageStatus.WITHDRAWN,
        }

        logger.info("Initialized Legislative Train scraper (enhanced)")

    # =========================================================================
    # NEW: Package-based Methods (Primary Entry Point)
    # =========================================================================

    async def get_all_packages(self, include_sub_packages: bool = True) -> List[ScrapedPackage]:
        """
        Get all packages from the packages listing page.

        This is the new primary entry point for scraping.

        Args:
            include_sub_packages: Whether to include sub-packages

        Returns:
            List of ScrapedPackage objects
        """
        logger.info("Fetching all packages from /legislative-train/packages")

        try:
            html = await self._fetch(self.PACKAGES_URL)
            soup = self._parse_html(html)

            packages = []

            # Find the packages table
            # Based on the HTML structure: table with package rows
            table = soup.find('table')
            if not table:
                # Try finding package links directly
                # Match both full paths (/legislative-train/package-) and relative (package-)
                package_links = soup.find_all('a', href=re.compile(r'(?:/legislative-train/)?package-[a-z0-9-]+'))
                for link in package_links:
                    package = self._parse_package_from_link(link)
                    if package:
                        packages.append(package)
            else:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header row
                    package = self._parse_package_row(row)
                    if package:
                        packages.append(package)

            logger.info(f"Found {len(packages)} packages")
            return packages

        except Exception as e:
            logger.error(f"Failed to get all packages: {str(e)}")
            return []

    async def get_package_detail(self, package_slug: str) -> Optional[ScrapedPackage]:
        """
        Get detailed information for a specific package.

        Args:
            package_slug: Package URL slug (e.g., "package-vision-for-agriculture-and-food")

        Returns:
            ScrapedPackage with full details
        """
        logger.info(f"Fetching package detail: {package_slug}")

        try:
            url = self.PACKAGE_URL_PATTERN.format(slug=package_slug)
            html = await self._fetch(url)
            soup = self._parse_html(html)

            # Extract package name from h1 or title
            name = ""
            h1 = soup.find('h1')
            if h1:
                name = h1.get_text(strip=True)
            else:
                title = soup.find('title')
                if title:
                    name = title.get_text(strip=True).split('|')[0].strip()

            # Parse status counts from the page
            status_counts = self._parse_status_counts(soup)

            package = ScrapedPackage(
                slug=package_slug,
                name=name,
                url=url,
                status_counts=status_counts,
                scraped_at=datetime.now()
            )

            return package

        except Exception as e:
            logger.error(f"Failed to get package {package_slug}: {str(e)}")
            return None

    async def get_package_files(
        self,
        package_slug: str,
        status: Optional[CarriageStatus] = None,
        committee: Optional[str] = None
    ) -> List[ScrapedFile]:
        """
        Get all files within a package.

        Args:
            package_slug: Package URL slug
            status: Filter by status
            committee: Filter by committee code

        Returns:
            List of ScrapedFile objects
        """
        logger.info(f"Fetching files for package: {package_slug}")

        try:
            url = self.PACKAGE_URL_PATTERN.format(slug=package_slug)
            html = await self._fetch(url)
            soup = self._parse_html(html)

            files = self._parse_package_files(soup, package_slug)

            # Apply filters
            if status:
                files = [f for f in files if f.status == status]

            if committee:
                committee = committee.upper()
                files = [f for f in files if committee in f.committees]

            logger.info(f"Found {len(files)} files in package {package_slug}")
            return files

        except Exception as e:
            logger.error(f"Failed to get package files: {str(e)}")
            return []

    async def get_file_detail(self, file_slug: str, theme_slug: Optional[str] = None) -> Optional[ScrapedFileDetail]:
        """
        Get detailed information for a specific legislative file.

        Includes timeline extraction.

        Args:
            file_slug: File URL slug (e.g., "file-revision-of-the-packaging")
            theme_slug: Optional theme slug for URL construction

        Returns:
            ScrapedFileDetail with full details including timeline
        """
        logger.info(f"Fetching file detail: {file_slug}")

        try:
            # Determine the URL
            if file_slug.startswith('http'):
                # Full URL provided
                url = file_slug
            elif theme_slug:
                # Build URL from theme and file slug
                url = f"{self.base_url}{theme_slug}/file-{file_slug}"
            else:
                # Try the package-file pattern first (most common)
                url = f"{self.base_url}package-{file_slug}/file-{file_slug}"

            html = await self._fetch(url)
            soup = self._parse_html(html)

            # Parse basic info
            title = ""
            title_elem = soup.find('h1') or soup.find('h2', class_=re.compile(r'title'))
            if title_elem:
                title = title_elem.get_text(strip=True)

            description = ""
            desc_elem = soup.find('div', class_=re.compile(r'description|summary'))
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            # Parse status
            status = CarriageStatus.ANNOUNCED
            status_elem = soup.find('span', class_=re.compile(r'status|badge'))
            if status_elem:
                status = self._normalize_status(status_elem.get_text(strip=True))

            # Extract timeline
            timeline = self._parse_timeline(soup)

            # Extract committees
            committees = self._extract_committees(html)

            # Extract OEIL procedure reference
            oeil_ref = self._extract_oeil_reference(html)

            # Extract CELEX numbers
            celex_numbers = self._extract_celex_numbers(html)

            # Extract text type
            text_type = self._extract_text_type(soup)

            # Extract spotlight tags
            spotlight_tags = self._extract_spotlight_tags(soup)
            is_recently_updated = 'recently_updated' in spotlight_tags or 'Recently updated' in str(soup)

            # Extract EPRS briefings
            eprs_briefings = self._extract_eprs_briefings(soup)

            # Extract lead committee
            lead_committee = None
            if committees:
                lead_committee = committees[0]  # First committee is usually lead

            file_detail = ScrapedFileDetail(
                file_id=file_slug,
                title=title,
                url=url,
                status=status,
                description=description,
                committees=committees,
                lead_committee=lead_committee,
                text_type=text_type,
                is_recently_updated=is_recently_updated,
                timeline=timeline,
                oeil_procedure_ref=oeil_ref,
                celex_numbers=celex_numbers,
                eprs_briefings=eprs_briefings,
                spotlight_tags=spotlight_tags,
                scraped_at=datetime.now()
            )

            logger.info(f"Successfully scraped file: {title or file_slug}")
            return file_detail

        except Exception as e:
            logger.error(f"Failed to get file {file_slug}: {str(e)}")
            return None

    # =========================================================================
    # UNIFIED METHOD (January 2025) - Combines both data sources
    # =========================================================================

    async def get_all_files_unified(
        self,
        fetch_details: bool = True,
        include_train_fallback: bool = True,
        progress_callback: Optional[callable] = None
    ) -> List[ScrapedFileDetail]:
        """
        UNIFIED scraping method that combines package-based and train-based sources.

        This is the recommended method for comprehensive scraping with OEIL refs.

        Strategy:
        1. Get all packages from /legislative-train/packages
        2. For each package, get all files
        3. For each file, fetch detail page to get OEIL ref
        4. Optionally, also scrape train pages for any missing files
        5. Deduplicate by file_id, merging data when available

        Args:
            fetch_details: Whether to fetch detail pages for each file (slower but gets OEIL refs)
            include_train_fallback: Whether to also scrape train pages for completeness
            progress_callback: Optional callback(current, total, message) for progress updates

        Returns:
            List of ScrapedFileDetail objects with OEIL refs where available

        Example:
            scraper = LegislativeTrainScraper()
            files = await scraper.get_all_files_unified()
            oeil_count = sum(1 for f in files if f.oeil_procedure_ref)
            print(f"Files with OEIL refs: {oeil_count}/{len(files)} ({oeil_count/len(files)*100:.1f}%)")
        """
        logger.info("Starting UNIFIED scraping of Legislative Train files")

        files_by_id: Dict[str, ScrapedFileDetail] = {}
        total_packages = 0
        processed_packages = 0

        # -------------------------------------------------------------------------
        # PHASE 1: Package-based scraping (primary source - has OEIL refs)
        # -------------------------------------------------------------------------
        logger.info("Phase 1: Scraping via packages (primary source)")

        try:
            packages = await self.get_all_packages()
            total_packages = len(packages)
            logger.info(f"Found {total_packages} packages to process")

            for package in packages:
                processed_packages += 1
                if progress_callback:
                    progress_callback(
                        processed_packages,
                        total_packages,
                        f"Processing package: {package.name[:50]}..."
                    )

                try:
                    # Get files for this package
                    package_files = await self.get_package_files(package.slug)
                    logger.debug(f"Package {package.slug}: {len(package_files)} files")

                    for pf in package_files:
                        file_id = pf.file_id

                        if fetch_details:
                            # Fetch detail page to get OEIL ref and full data
                            detail = await self.get_file_detail(file_id)
                            if detail:
                                # Merge package info into detail
                                detail.package_slug = package.slug
                                files_by_id[file_id] = detail
                            else:
                                # Fallback: convert ScrapedFile to ScrapedFileDetail
                                files_by_id[file_id] = ScrapedFileDetail(
                                    file_id=pf.file_id,
                                    title=pf.title,
                                    url=pf.url,
                                    status=pf.status,
                                    package_slug=package.slug,
                                    committees=pf.committees,
                                    is_recently_updated=pf.is_recently_updated,
                                    scraped_at=datetime.now()
                                )
                        else:
                            # Fast mode: don't fetch details
                            files_by_id[file_id] = ScrapedFileDetail(
                                file_id=pf.file_id,
                                title=pf.title,
                                url=pf.url,
                                status=pf.status,
                                package_slug=package.slug,
                                committees=pf.committees,
                                is_recently_updated=pf.is_recently_updated,
                                scraped_at=datetime.now()
                            )

                except Exception as e:
                    logger.warning(f"Failed to process package {package.slug}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Phase 1 (package scraping) failed: {e}")

        logger.info(f"Phase 1 complete: {len(files_by_id)} files from packages")

        # -------------------------------------------------------------------------
        # PHASE 2: Train-based scraping (fallback for completeness)
        # -------------------------------------------------------------------------
        if include_train_fallback:
            logger.info("Phase 2: Scraping via trains (fallback for missing files)")

            try:
                train_carriages = await self.get_all_carriages()
                new_from_trains = 0

                for carriage in train_carriages:
                    file_id = carriage.get('id')
                    if not file_id:
                        continue

                    if file_id not in files_by_id:
                        # New file found via train view
                        new_from_trains += 1

                        if fetch_details:
                            # Try to get detail page for OEIL ref
                            detail = await self.get_file_detail(file_id)
                            if detail:
                                detail.train_priority = carriage.get('train_priority')
                                files_by_id[file_id] = detail
                            else:
                                # Fallback to train carriage data
                                files_by_id[file_id] = ScrapedFileDetail(
                                    file_id=file_id,
                                    title=carriage.get('title', ''),
                                    url=carriage.get('url', ''),
                                    status=self._normalize_status(carriage.get('status', 'announced')),
                                    train_priority=carriage.get('train_priority'),
                                    committees=carriage.get('committees', []),
                                    scraped_at=datetime.now()
                                )
                        else:
                            # Fast mode
                            files_by_id[file_id] = ScrapedFileDetail(
                                file_id=file_id,
                                title=carriage.get('title', ''),
                                url=carriage.get('url', ''),
                                status=self._normalize_status(carriage.get('status', 'announced')),
                                train_priority=carriage.get('train_priority'),
                                committees=carriage.get('committees', []),
                                scraped_at=datetime.now()
                            )
                    else:
                        # File already exists - merge train_priority if available
                        existing = files_by_id[file_id]
                        if carriage.get('train_priority') and not existing.train_priority:
                            existing.train_priority = carriage.get('train_priority')

                logger.info(f"Phase 2 complete: {new_from_trains} new files from trains")

            except Exception as e:
                logger.error(f"Phase 2 (train scraping) failed: {e}")

        # -------------------------------------------------------------------------
        # SUMMARY
        # -------------------------------------------------------------------------
        all_files = list(files_by_id.values())
        oeil_count = sum(1 for f in all_files if f.oeil_procedure_ref)
        oeil_percentage = (oeil_count / len(all_files) * 100) if all_files else 0

        logger.info(
            f"UNIFIED scraping complete: {len(all_files)} files, "
            f"{oeil_count} with OEIL refs ({oeil_percentage:.1f}%)"
        )

        return all_files

    async def get_all_files_fast(self) -> List[ScrapedFileDetail]:
        """
        Fast version of get_all_files_unified() that skips detail page fetching.

        Use this for quick scans when you don't need OEIL refs.
        ~10x faster but won't have OEIL procedure references.

        Returns:
            List of ScrapedFileDetail (without OEIL refs)
        """
        return await self.get_all_files_unified(
            fetch_details=False,
            include_train_fallback=True
        )

    # =========================================================================
    # Timeline Extraction (NEW)
    # =========================================================================

    def _parse_timeline(self, soup: BeautifulSoup) -> List[TimelineEntry]:
        """
        Extract monthly timeline from file page.

        Looks for the timeline rail visualization showing status by month.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of TimelineEntry objects
        """
        timeline = []

        try:
            # Look for timeline elements
            # Based on HTML: class="lt-timeline-rail-status" or similar
            timeline_container = soup.find('div', class_=re.compile(r'timeline|timetable'))
            if not timeline_container:
                # Try finding by other patterns
                timeline_container = soup.find('ul', class_=re.compile(r'timeline|status-history'))

            if not timeline_container:
                # Try parsing from status history list
                status_list = soup.find('ul')
                if status_list:
                    for li in status_list.find_all('li'):
                        entry = self._parse_timeline_entry_from_text(li.get_text(strip=True))
                        if entry:
                            timeline.append(entry)
                return timeline

            # Parse timeline entries
            entries = timeline_container.find_all(['li', 'div', 'span'], class_=re.compile(r'status|month|entry'))

            for entry in entries:
                timeline_entry = self._parse_timeline_entry(entry)
                if timeline_entry:
                    timeline.append(timeline_entry)

            # Sort by date
            timeline.sort(key=lambda x: (x.year, x.month))

        except Exception as e:
            logger.warning(f"Failed to parse timeline: {e}")

        return timeline

    def _parse_timeline_entry(self, element: Tag) -> Optional[TimelineEntry]:
        """Parse a single timeline entry from HTML element."""
        try:
            text = element.get_text(strip=True)

            # Try to extract date and status
            # Format could be: "2024-01 Tabled" or "Jan 2024: Tabled"
            date_match = re.search(r'(\d{4})-(\d{2})|(\w{3})\s+(\d{4})', text)
            if not date_match:
                return None

            if date_match.group(1):  # YYYY-MM format
                year = int(date_match.group(1))
                month = int(date_match.group(2))
            else:  # Month YYYY format
                month_name = date_match.group(3)
                year = int(date_match.group(4))
                month = self._month_name_to_number(month_name)

            # Extract status
            status = CarriageStatus.ANNOUNCED
            for status_text, status_enum in self.status_mapping.items():
                if status_text in text.lower():
                    status = status_enum
                    break

            # Check if current
            is_current = 'current' in element.get('class', []) or 'active' in element.get('class', [])

            return TimelineEntry(
                year=year,
                month=month,
                status=status,
                is_current=is_current
            )

        except Exception as e:
            logger.debug(f"Failed to parse timeline entry: {e}")
            return None

    def _parse_timeline_entry_from_text(self, text: str) -> Optional[TimelineEntry]:
        """Parse timeline entry from plain text like '2020-02-01 Status: Announced'"""
        try:
            # Match date pattern: YYYY-MM-DD or YYYY-MM
            date_match = re.search(r'(\d{4})-(\d{2})(?:-\d{2})?', text)
            if not date_match:
                return None

            year = int(date_match.group(1))
            month = int(date_match.group(2))

            # Extract status
            status = CarriageStatus.ANNOUNCED
            status_match = re.search(r'Status:\s*(.+)', text, re.IGNORECASE)
            if status_match:
                status = self._normalize_status(status_match.group(1))

            return TimelineEntry(
                year=year,
                month=month,
                status=status,
                is_current=False
            )

        except Exception as e:
            logger.debug(f"Failed to parse timeline from text: {e}")
            return None

    def _month_name_to_number(self, month_name: str) -> int:
        """Convert month name abbreviation to number."""
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        return months.get(month_name.lower()[:3], 1)

    # =========================================================================
    # Helper Extraction Methods
    # =========================================================================

    def _parse_package_row(self, row: Tag) -> Optional[ScrapedPackage]:
        """Parse a package from table row."""
        try:
            cells = row.find_all('td')
            if len(cells) < 2:
                return None

            # First cell usually contains the link
            # Match both absolute and relative paths
            link = row.find('a', href=re.compile(r'(?:/legislative-train/)?package-[a-z0-9-]+'))
            if not link:
                return None

            href = link.get('href', '')
            slug_match = re.search(r'(?:^|/)(package-[a-z0-9-]+)', href)
            if not slug_match:
                return None

            slug = slug_match.group(1)
            name = link.get_text(strip=True)

            # Parse status counts from cells
            status_counts = PackageStatusCounts()

            # Look for status count spans/cells
            for cell in cells:
                cell_text = cell.get_text(strip=True).lower()
                count_match = re.search(r'(\d+)', cell_text)
                if count_match:
                    count = int(count_match.group(1))
                    if 'announced' in cell_text:
                        status_counts.announced = count
                    elif 'tabled' in cell_text:
                        status_counts.tabled = count
                    elif 'blocked' in cell_text:
                        status_counts.blocked = count
                    elif 'adopted' in cell_text or 'completed' in cell_text:
                        status_counts.adopted = count

            status_counts.total = (
                status_counts.announced + status_counts.tabled +
                status_counts.blocked + status_counts.close_to_adoption +
                status_counts.adopted + status_counts.withdrawn
            )

            return ScrapedPackage(
                slug=slug,
                name=name,
                url=self._make_absolute_url(href),
                status_counts=status_counts,
                scraped_at=datetime.now()
            )

        except Exception as e:
            logger.debug(f"Failed to parse package row: {e}")
            return None

    def _parse_package_from_link(self, link: Tag) -> Optional[ScrapedPackage]:
        """Parse a package from an anchor tag."""
        try:
            href = link.get('href', '')
            # Match both absolute and relative paths
            slug_match = re.search(r'(?:^|/)(package-[a-z0-9-]+)', href)
            if not slug_match:
                return None

            slug = slug_match.group(1)
            name = link.get_text(strip=True)

            return ScrapedPackage(
                slug=slug,
                name=name,
                url=self._make_absolute_url(href),
                status_counts=PackageStatusCounts(),
                scraped_at=datetime.now()
            )

        except Exception as e:
            logger.debug(f"Failed to parse package from link: {e}")
            return None

    def _parse_status_counts(self, soup: BeautifulSoup) -> PackageStatusCounts:
        """Parse status counts from a package page."""
        counts = PackageStatusCounts()

        try:
            # Look for status count elements
            # Common patterns: span with count, filter badges, etc.
            page_text = soup.get_text()

            # Pattern: "15 Announced" or "Announced: 15"
            patterns = [
                (r'(\d+)\s*announced', 'announced'),
                (r'announced[:\s]*(\d+)', 'announced'),
                (r'(\d+)\s*tabled', 'tabled'),
                (r'tabled[:\s]*(\d+)', 'tabled'),
                (r'(\d+)\s*blocked', 'blocked'),
                (r'blocked[:\s]*(\d+)', 'blocked'),
                (r'(\d+)\s*adopted', 'adopted'),
                (r'adopted[:\s]*(\d+)', 'adopted'),
                (r'(\d+)\s*close to adoption', 'close_to_adoption'),
            ]

            for pattern, field in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    setattr(counts, field, int(match.group(1)))

            counts.total = (
                counts.announced + counts.tabled + counts.blocked +
                counts.close_to_adoption + counts.adopted + counts.withdrawn
            )

        except Exception as e:
            logger.warning(f"Failed to parse status counts: {e}")

        return counts

    def _parse_package_files(self, soup: BeautifulSoup, package_slug: str) -> List[ScrapedFile]:
        """Parse all files from a package page."""
        files = []

        try:
            # Find file links
            # Pattern: /legislative-train/{theme}/file-{slug}
            file_links = soup.find_all('a', href=re.compile(r'/file-'))

            for link in file_links:
                href = link.get('href', '')
                file_id_match = re.search(r'/file-([^/]+)', href)
                if not file_id_match:
                    continue

                file_id = file_id_match.group(1)
                title = link.get_text(strip=True)

                # Find status near the link
                status = CarriageStatus.ANNOUNCED
                parent = link.find_parent(['tr', 'li', 'div'])
                if parent:
                    status_text = parent.get_text(strip=True)
                    status = self._normalize_status(status_text)

                # Extract committees from nearby text
                committees = []
                if parent:
                    committees = self._extract_committees(str(parent))

                # Check for recently updated
                is_recently_updated = bool(parent and 'recently' in parent.get_text(strip=True).lower())

                file = ScrapedFile(
                    file_id=file_id,
                    title=title,
                    url=self._make_absolute_url(href),
                    status=status,
                    package_slug=package_slug,
                    committees=committees,
                    is_recently_updated=is_recently_updated,
                    scraped_at=datetime.now()
                )

                files.append(file)

        except Exception as e:
            logger.warning(f"Failed to parse package files: {e}")

        return files

    def _extract_committees(self, html: str) -> List[str]:
        """Extract committee codes from HTML text."""
        committees = []
        for code in self.committee_codes:
            if re.search(rf'\b{code}\b', html):
                committees.append(code)
        return committees

    def _extract_oeil_reference(self, html: str) -> Optional[str]:
        """Extract OEIL procedure reference from HTML."""
        # Pattern: 2021/0106(COD) - year/number(procedure type)
        oeil_pattern = r'\d{4}/\d{4}\([A-Z]{3,4}\)'
        matches = re.findall(oeil_pattern, html)
        return matches[0] if matches else None

    def _extract_celex_numbers(self, html: str) -> List[str]:
        """Extract CELEX numbers from HTML."""
        # CELEX format: 3YYYYR#### (e.g., 32021R2115)
        # Sector (1 digit) + Year (4 digits) + Type (1-2 letters) + Number (4+ digits)
        celex_pattern = r'\b[0-9][0-9]{4}[A-Z][0-9]{4,}\b'
        matches = re.findall(celex_pattern, html)
        return list(set(matches))

    def _extract_text_type(self, soup: BeautifulSoup) -> TextType:
        """Extract text type (legislative/non-legislative) from page."""
        page_text = soup.get_text().lower()

        if 'non-legislative' in page_text or 'non legislative' in page_text:
            return TextType.NON_LEGISLATIVE
        elif 'legislative' in page_text:
            return TextType.LEGISLATIVE

        return TextType.UNKNOWN

    def _extract_spotlight_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract spotlight tags from page."""
        tags = []

        # Look for spotlight/tag elements
        tag_elements = soup.find_all(['span', 'div'], class_=re.compile(r'tag|spotlight|badge'))
        for elem in tag_elements:
            tag_text = elem.get_text(strip=True)
            if tag_text and len(tag_text) < 50:
                tags.append(tag_text)

        # Check for "recently updated" indicator
        if 'recently updated' in soup.get_text().lower():
            tags.append('recently_updated')

        return tags

    def _extract_eprs_briefings(self, soup: BeautifulSoup) -> List[EPRSBriefingReference]:
        """Extract EPRS briefing links from page."""
        briefings = []

        eprs_links = soup.find_all('a', href=re.compile(r'epthinktank\.eu|europarl\.europa\.eu/thinktank'))
        for link in eprs_links:
            briefings.append(EPRSBriefingReference(
                url=link.get('href', ''),
                title=link.get_text(strip=True)
            ))

        return briefings

    def _normalize_status(self, status_text: str) -> CarriageStatus:
        """Normalize status text to CarriageStatus enum."""
        status_lower = status_text.lower().strip()

        for text, status in self.status_mapping.items():
            if text in status_lower:
                return status

        return CarriageStatus.ANNOUNCED

    # =========================================================================
    # Backward Compatible Methods (Existing API)
    # =========================================================================

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search legislative files by keyword.

        Args:
            query: Search query
            **kwargs: Additional filters (status, committee)

        Returns:
            List of matching legislative files
        """
        logger.info(f"Searching Legislative Train for: {query}")

        try:
            all_carriages = await self.get_all_carriages()

            query_lower = query.lower()
            results = [
                c for c in all_carriages
                if query_lower in c.get('title', '').lower()
                or query_lower in c.get('description', '').lower()
            ]

            if 'status' in kwargs:
                results = [c for c in results if c.get('status') == kwargs['status']]

            if 'committee' in kwargs:
                committee = kwargs['committee'].upper()
                results = [
                    c for c in results
                    if committee in c.get('committees', [])
                ]

            logger.info(f"Found {len(results)} matching carriages")
            return results

        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get specific legislative file (carriage) by ID."""
        try:
            carriage = await self.scrape_carriage(document_id)
            return carriage
        except Exception as e:
            logger.error(f"Failed to get carriage {document_id}: {str(e)}")
            return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently updated legislative files."""
        try:
            all_carriages = await self.get_all_carriages()

            sorted_carriages = sorted(
                all_carriages,
                key=lambda x: x.get('last_updated', datetime.min),
                reverse=True
            )

            return sorted_carriages[:limit]

        except Exception as e:
            logger.error(f"Failed to get latest updates: {str(e)}")
            return []

    async def get_procedure(self, procedure_ref: str) -> Dict[str, Any]:
        """Find carriage by OEIL procedure reference."""
        try:
            all_carriages = await self.get_all_carriages()

            for carriage in all_carriages:
                if carriage.get('oeil_procedure_ref') == procedure_ref:
                    return carriage

            logger.warning(f"No carriage found for procedure {procedure_ref}")
            return {}

        except Exception as e:
            logger.error(f"Failed to get procedure: {str(e)}")
            return {}

    async def get_all_trains(self) -> List[Dict[str, Any]]:
        """Get all 7 EC priority trains with statistics."""
        logger.info("Fetching all Legislative Trains")

        try:
            trains = []

            priority_names = {
                'priority-1': 'A NEW PLAN FOR EUROPE\'S SUSTAINABLE PROSPERITY AND COMPETITIVENESS',
                'priority-2': 'A NEW ERA FOR EUROPEAN DEFENCE AND SECURITY',
                'priority-3': 'SUPPORTING PEOPLE, STRENGTHENING OUR SOCIETIES AND OUR SOCIAL MODEL',
                'priority-4': 'SUSTAINING OUR QUALITY OF LIFE: FOOD SECURITY, WATER AND NATURE',
                'priority-5': 'PROTECTING OUR DEMOCRACY, UPHOLDING OUR VALUES',
                'priority-6': 'A GLOBAL EUROPE: LEVERAGING OUR POWER AND PARTNERSHIPS',
                'priority-7': 'DELIVERING TOGETHER AND PREPARING OUR UNION FOR THE FUTURE'
            }

            for priority_id, priority_name in priority_names.items():
                try:
                    theme_slug = self.theme_slugs.get(priority_id, priority_id)
                    url = f"{self.base_url}{theme_slug}"

                    html = await self._fetch(url)
                    soup = self._parse_html(html)

                    train = {
                        'id': priority_id,
                        'priority_number': int(priority_id.split('-')[1]),
                        'name': priority_name,
                        'theme_slug': theme_slug,
                        'url': url
                    }

                    carriages = await self._parse_train_carriages(soup)

                    files_by_status = {}
                    for carriage in carriages:
                        status = carriage.get('status', 'unknown')
                        files_by_status[status] = files_by_status.get(status, 0) + 1

                    if files_by_status:
                        train['files_by_status'] = files_by_status
                        train['total_files'] = sum(files_by_status.values())
                    else:
                        train['total_files'] = 0

                    trains.append(train)
                    logger.info(f"Fetched train {priority_id}: {priority_name} ({train.get('total_files', 0)} files)")

                except Exception as e:
                    logger.error(f"Failed to fetch train {priority_id}: {str(e)}")
                    continue

            logger.info(f"Successfully fetched {len(trains)} trains")
            return trains

        except Exception as e:
            logger.error(f"Failed to get all trains: {str(e)}")
            return []

    async def get_train_carriages(
        self,
        train_id: str,
        status: Optional[str] = None,
        committee: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all legislative files for a specific train."""
        logger.info(f"Fetching carriages for train {train_id}")

        try:
            theme_slug = self.theme_slugs.get(train_id, train_id)
            url = f"{self.base_url}{theme_slug}"
            html = await self._fetch(url)
            soup = self._parse_html(html)

            carriages = await self._parse_train_carriages(soup)

            if status:
                carriages = [c for c in carriages if c.get('status') == status]

            if committee:
                committee = committee.upper()
                carriages = [
                    c for c in carriages
                    if committee in c.get('committees', [])
                ]

            logger.info(f"Found {len(carriages)} carriages for train {train_id}")
            return carriages

        except Exception as e:
            logger.error(f"Failed to get train carriages: {str(e)}")
            return []

    async def get_all_carriages(self) -> List[Dict[str, Any]]:
        """Get all ~490 legislative files across all trains."""
        logger.info("Fetching all legislative carriages")

        try:
            trains = await self.get_all_trains()
            all_carriages = []

            for train in trains:
                train_id = train.get('id')
                train_priority = train.get('priority_number')
                if train_id:
                    carriages = await self.get_train_carriages(train_id)
                    for carriage in carriages:
                        carriage['train_priority'] = train_priority
                    all_carriages.extend(carriages)

            logger.info(f"Total carriages fetched: {len(all_carriages)}")
            return all_carriages

        except Exception as e:
            logger.error(f"Failed to get all carriages: {str(e)}")
            return []

    async def scrape_carriage(self, carriage_id: str) -> Dict[str, Any]:
        """Scrape detailed information for a specific legislative file."""
        logger.info(f"Scraping carriage: {carriage_id}")

        try:
            # Try using the new method first
            file_detail = await self.get_file_detail(carriage_id)

            if file_detail:
                return {
                    'id': file_detail.file_id,
                    'title': file_detail.title,
                    'description': file_detail.description,
                    'status': file_detail.status.value,
                    'committees': file_detail.committees,
                    'oeil_procedure_ref': file_detail.oeil_procedure_ref,
                    'celex_numbers': file_detail.celex_numbers,
                    'eprs_briefings': [b.model_dump() for b in file_detail.eprs_briefings],
                    'timeline': [t.model_dump() for t in file_detail.timeline],
                    'text_type': file_detail.text_type.value,
                    'is_recently_updated': file_detail.is_recently_updated,
                    'spotlight_tags': file_detail.spotlight_tags,
                    'scraped_at': file_detail.scraped_at.isoformat(),
                }

            # Fallback to old method
            url = f"{self.base_url}carriage/{carriage_id}/"
            html = await self._fetch(url)
            soup = self._parse_html(html)

            carriage = {
                'id': carriage_id,
                'scraped_at': datetime.now().isoformat(),
            }

            title_elem = soup.find('h1') or soup.find('h2', class_=re.compile(r'title'))
            if title_elem:
                carriage['title'] = title_elem.get_text(strip=True)

            desc_elem = soup.find('div', class_=re.compile(r'description|summary'))
            if desc_elem:
                carriage['description'] = desc_elem.get_text(strip=True)

            status_elem = soup.find('span', class_=re.compile(r'status|badge'))
            if status_elem:
                carriage['status'] = self._normalize_status(status_elem.get_text(strip=True)).value

            carriage['oeil_procedure_ref'] = self._extract_oeil_reference(html)
            carriage['celex_numbers'] = self._extract_celex_numbers(html)
            carriage['committees'] = self._extract_committees(html)

            logger.info(f"Successfully scraped carriage: {carriage.get('title', carriage_id)}")
            return carriage

        except Exception as e:
            logger.error(f"Failed to scrape carriage {carriage_id}: {str(e)}")
            return {'id': carriage_id, 'error': str(e)}

    async def get_blocked_files(self, min_days: int = 270) -> List[Dict[str, Any]]:
        """Find legislative files blocked for 9+ months."""
        logger.info(f"Finding files blocked for {min_days}+ days")

        try:
            all_carriages = await self.get_all_carriages()

            blocked = [
                c for c in all_carriages
                if c.get('status') == CarriageStatus.BLOCKED.value
                or c.get('days_in_current_status', 0) >= min_days
            ]

            logger.info(f"Found {len(blocked)} blocked files")
            return blocked

        except Exception as e:
            logger.error(f"Failed to get blocked files: {str(e)}")
            return []

    async def get_by_committee(self, committee_code: str) -> List[Dict[str, Any]]:
        """Get all legislative files for a specific committee."""
        committee_code = committee_code.upper()
        logger.info(f"Fetching files for committee {committee_code}")

        try:
            url = f"{self.base_url}committee/{committee_code.lower()}/"
            html = await self._fetch(url)
            soup = self._parse_html(html)

            carriages = await self._parse_train_carriages(soup)

            logger.info(f"Found {len(carriages)} files for {committee_code}")
            return carriages

        except Exception as e:
            logger.error(f"Failed to get committee files: {str(e)}")
            return []

    async def _parse_train_carriages(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse carriage elements from train page HTML."""
        carriages = []

        try:
            h3_elements = soup.find_all('h3')

            for h3 in h3_elements:
                carriage = {}

                link_elem = h3.find('a', href=re.compile(r'/file-'))
                if link_elem:
                    href = link_elem.get('href')
                    id_match = re.search(r'/file-([^/]+)', href)
                    if id_match:
                        carriage['id'] = id_match.group(1)
                        carriage['title'] = link_elem.get_text(strip=True)
                        carriage['url'] = self._make_absolute_url(href)

                        next_ul = h3.find_next_sibling('ul')
                        if next_ul:
                            status_items = next_ul.find_all('li')
                            if status_items:
                                last_status_text = status_items[-1].get_text(strip=True)
                                status_match = re.search(r'Status:\s*(.+)', last_status_text)
                                if status_match:
                                    carriage['status'] = self._normalize_status(status_match.group(1)).value

                        if carriage.get('id') and carriage.get('title'):
                            carriages.append(carriage)

        except Exception as e:
            logger.error(f"Failed to parse carriages: {str(e)}")

        return carriages

    async def close(self):
        """Close scraper connections."""
        logger.info("Closed Legislative Train scraper")
