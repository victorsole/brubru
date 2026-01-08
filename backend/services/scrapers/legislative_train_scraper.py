"""
Legislative Train Scraper

Enhanced scraper for European Parliament Legislative Train Schedule.
Tracks EU legislative priorities through web scraping (no API available).

Features:
- Scrape all 7 EC priority "trains"
- Extract ~490 legislative file "carriages"
- Track status progression through 7 stages
- Link to OEIL procedures
- Committee-based filtering
- Temporal status tracking
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class CarriageStatus:
    """Legislative file status categories"""
    ANNOUNCED = "announced"
    LEGISLATIVE_INITIATIVE = "legislative_initiative"
    TABLED = "tabled"
    CLOSE_TO_ADOPTION = "close_to_adoption"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class LegislativeTrainScraper(BaseScraper):
    """
    Scraper for EP Legislative Train Schedule.

    The Legislative Train uses a train metaphor:
    - Trains = EC priorities (7 main priorities)
    - Carriages = Individual legislative files (~490 total)
    - Status = Progress through legislative process

    Data access: Web scraping only (no API/RSS available)
    Update frequency: Monthly (end of each month)
    """

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

        # Theme slug mapping (2024-29 Commission priorities)
        self.theme_slugs = {
            'priority-1': 'theme-a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness',
            'priority-2': 'theme-a-new-era-for-european-defence-and-security',
            'priority-3': 'theme-supporting-people-strengthening-our-societies-and-our-social-model',
            'priority-4': 'theme-sustaining-our-quality-of-life-food-security-water-and-nature',
            'priority-5': 'theme-protecting-our-democracy-upholding-our-values',
            'priority-6': 'theme-a-global-europe-leveraging-our-power-and-partnerships',
            'priority-7': 'theme-delivering-together-and-preparing-our-union-for-the-future'
        }

        logger.info("Initialized Legislative Train scraper")

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
            # Get all carriages
            all_carriages = await self.get_all_carriages()

            # Filter by query
            query_lower = query.lower()
            results = [
                c for c in all_carriages
                if query_lower in c.get('title', '').lower()
                or query_lower in c.get('description', '').lower()
            ]

            # Apply additional filters
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
        """
        Get specific legislative file (carriage) by ID.

        Args:
            document_id: Carriage ID

        Returns:
            Carriage details
        """
        try:
            carriage = await self.scrape_carriage(document_id)
            return carriage

        except Exception as e:
            logger.error(f"Failed to get carriage {document_id}: {str(e)}")
            return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recently updated legislative files.

        Args:
            limit: Maximum results

        Returns:
            List of recently updated carriages
        """
        try:
            all_carriages = await self.get_all_carriages()

            # Sort by last updated (if available)
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
        """
        Find carriage by OEIL procedure reference.

        Args:
            procedure_ref: OEIL procedure reference (e.g., "2021/0106(COD)")

        Returns:
            Carriage details
        """
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

    # ===== New Enhanced Methods =====

    async def get_all_trains(self) -> List[Dict[str, Any]]:
        """
        Get all 7 EC priority trains with statistics.

        Returns:
            List of trains with file counts by status
        """
        logger.info("Fetching all Legislative Trains")

        try:
            trains = []

            # Iterate through all 7 known priorities directly
            # This is more reliable than trying to parse the homepage
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
                    # Get theme slug
                    theme_slug = self.theme_slugs.get(priority_id, priority_id)
                    url = f"{self.base_url}{theme_slug}"

                    # Fetch train page to get statistics
                    html = await self._fetch(url)
                    soup = self._parse_html(html)

                    # Parse train metadata
                    train = {
                        'id': priority_id,
                        'priority_number': int(priority_id.split('-')[1]),
                        'name': priority_name,
                        'theme_slug': theme_slug,
                        'url': url
                    }

                    # Extract statistics from the page
                    # Parse carriages using the correct method
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
                    # Continue with next train even if one fails
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
        """
        Get all legislative files for a specific train.

        Args:
            train_id: Train/priority ID
            status: Filter by status
            committee: Filter by committee

        Returns:
            List of carriages
        """
        logger.info(f"Fetching carriages for train {train_id}")

        try:
            # Get theme slug from mapping
            theme_slug = self.theme_slugs.get(train_id, train_id)
            url = f"{self.base_url}{theme_slug}"
            html = await self._fetch(url)
            soup = self._parse_html(html)

            carriages = await self._parse_train_carriages(soup)

            # Apply filters
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
        """
        Get all ~490 legislative files across all trains.

        Returns:
            List of all carriages
        """
        logger.info("Fetching all legislative carriages")

        try:
            trains = await self.get_all_trains()
            all_carriages = []

            for train in trains:
                train_id = train.get('id')
                train_priority = train.get('priority_number')
                if train_id:
                    carriages = await self.get_train_carriages(train_id)
                    # Add train priority number to each carriage for database linking
                    for carriage in carriages:
                        carriage['train_priority'] = train_priority
                    all_carriages.extend(carriages)

            logger.info(f"Total carriages fetched: {len(all_carriages)}")
            return all_carriages

        except Exception as e:
            logger.error(f"Failed to get all carriages: {str(e)}")
            return []

    async def scrape_carriage(self, carriage_id: str) -> Dict[str, Any]:
        """
        Scrape detailed information for a specific legislative file.

        Args:
            carriage_id: Carriage ID

        Returns:
            Detailed carriage information
        """
        logger.info(f"Scraping carriage: {carriage_id}")

        try:
            url = f"{self.base_url}carriage/{carriage_id}/"
            html = await self._fetch(url)
            soup = self._parse_html(html)

            carriage = {
                'id': carriage_id,
                'scraped_at': datetime.now().isoformat(),
            }

            # Extract title
            title_elem = soup.find('h1') or soup.find('h2', class_=re.compile(r'title'))
            if title_elem:
                carriage['title'] = title_elem.get_text(strip=True)

            # Extract description
            desc_elem = soup.find('div', class_=re.compile(r'description|summary'))
            if desc_elem:
                carriage['description'] = desc_elem.get_text(strip=True)

            # Extract status
            status_elem = soup.find('span', class_=re.compile(r'status|badge'))
            if status_elem:
                carriage['status'] = self._normalize_status(status_elem.get_text(strip=True))

            # Extract OEIL procedure reference
            oeil_pattern = r'\b\d{4}/\d{4}\([A-Z]{3,4}\)\b'
            oeil_matches = re.findall(oeil_pattern, html)
            if oeil_matches:
                carriage['oeil_procedure_ref'] = oeil_matches[0]

            # Extract CELEX numbers
            celex_pattern = r'\b\d{1,2}[A-Z]{1,2}\d{4}[A-Z]{1,2}\d{4}\b'
            celex_matches = re.findall(celex_pattern, html)
            if celex_matches:
                carriage['celex_numbers'] = list(set(celex_matches))

            # Extract committees
            committees = []
            for code in self.committee_codes:
                if re.search(rf'\b{code}\b', html):
                    committees.append(code)
            carriage['committees'] = committees

            # Extract links to EPRS briefings
            briefing_links = []
            eprs_links = soup.find_all('a', href=re.compile(r'epthinktank\.eu'))
            for link in eprs_links:
                briefing_links.append({
                    'url': link.get('href'),
                    'title': link.get_text(strip=True)
                })
            carriage['eprs_briefings'] = briefing_links

            logger.info(f"Successfully scraped carriage: {carriage.get('title', carriage_id)}")
            return carriage

        except Exception as e:
            logger.error(f"Failed to scrape carriage {carriage_id}: {str(e)}")
            return {'id': carriage_id, 'error': str(e)}

    async def get_blocked_files(self, min_days: int = 270) -> List[Dict[str, Any]]:
        """
        Find legislative files blocked for 9+ months.

        Args:
            min_days: Minimum days to consider blocked (default: 270 = 9 months)

        Returns:
            List of blocked carriages
        """
        logger.info(f"Finding files blocked for {min_days}+ days")

        try:
            all_carriages = await self.get_all_carriages()

            blocked = [
                c for c in all_carriages
                if c.get('status') == CarriageStatus.BLOCKED
                or c.get('days_in_current_status', 0) >= min_days
            ]

            logger.info(f"Found {len(blocked)} blocked files")
            return blocked

        except Exception as e:
            logger.error(f"Failed to get blocked files: {str(e)}")
            return []

    async def get_by_committee(self, committee_code: str) -> List[Dict[str, Any]]:
        """
        Get all legislative files for a specific committee.

        Args:
            committee_code: Committee code (e.g., "LIBE", "ENVI")

        Returns:
            List of carriages
        """
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

    # ===== Helper Methods =====

    def _normalize_status(self, status_text: str) -> str:
        """Normalize status text to standard status enum"""
        status_lower = status_text.lower()

        if 'announce' in status_lower or 'forthcoming' in status_lower:
            return CarriageStatus.ANNOUNCED
        elif 'legislative initiative' in status_lower:
            return CarriageStatus.LEGISLATIVE_INITIATIVE
        elif 'tabled' in status_lower or 'submitted' in status_lower:
            return CarriageStatus.TABLED
        elif 'close to adoption' in status_lower or 'near completion' in status_lower:
            return CarriageStatus.CLOSE_TO_ADOPTION
        elif 'completed' in status_lower or 'adopted' in status_lower or 'done' in status_lower:
            return CarriageStatus.COMPLETED
        elif 'blocked' in status_lower or 'stalled' in status_lower:
            return CarriageStatus.BLOCKED
        elif 'withdrawn' in status_lower:
            return CarriageStatus.WITHDRAWN
        else:
            return status_lower

    async def _parse_train_element(self, element, priority_number: int) -> Optional[Dict[str, Any]]:
        """Parse train element from HTML"""
        try:
            train = {
                'id': f"priority-{priority_number}",
                'priority_number': priority_number,
            }

            # Extract name
            name_elem = element.find('h2') or element.find('h3')
            if name_elem:
                train['name'] = name_elem.get_text(strip=True)

            # Extract description
            desc_elem = element.find('p', class_=re.compile(r'description'))
            if desc_elem:
                train['description'] = desc_elem.get_text(strip=True)

            # Extract statistics
            stat_elements = element.find_all('span', class_=re.compile(r'stat|count'))
            files_by_status = {}
            for stat in stat_elements:
                # Try to extract status and count
                text = stat.get_text(strip=True)
                match = re.search(r'(\d+)\s+(\w+)', text)
                if match:
                    count, status = match.groups()
                    files_by_status[status.lower()] = int(count)

            if files_by_status:
                train['files_by_status'] = files_by_status
                train['total_files'] = sum(files_by_status.values())

            return train

        except Exception as e:
            logger.error(f"Failed to parse train element: {str(e)}")
            return None

    async def _parse_train_carriages(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse carriage elements from train page HTML"""
        carriages = []

        try:
            # Find all h3 elements containing carriage titles
            h3_elements = soup.find_all('h3')

            for h3 in h3_elements:
                carriage = {}

                # Extract ID and title from link
                link_elem = h3.find('a', href=re.compile(r'/file-'))
                if link_elem:
                    href = link_elem.get('href')
                    # Extract file ID from URL: /theme-.../file-[slug]
                    id_match = re.search(r'/file-([^/]+)', href)
                    if id_match:
                        carriage['id'] = id_match.group(1)
                        carriage['title'] = link_elem.get_text(strip=True)
                        carriage['url'] = self._make_absolute_url(href)

                        # Find status information in following ul/li elements
                        # Status appears as: "2020-02-01 Status: Announced"
                        next_ul = h3.find_next_sibling('ul')
                        if next_ul:
                            status_items = next_ul.find_all('li')
                            if status_items:
                                # Get the most recent status (last item)
                                last_status_text = status_items[-1].get_text(strip=True)
                                # Extract status from text like "2020-02-01 Status: Announced"
                                status_match = re.search(r'Status:\s*(.+)', last_status_text)
                                if status_match:
                                    carriage['status'] = self._normalize_status(status_match.group(1))

                        # Only add carriage if it has required fields
                        if carriage.get('id') and carriage.get('title'):
                            carriages.append(carriage)

        except Exception as e:
            logger.error(f"Failed to parse carriages: {str(e)}")

        return carriages
