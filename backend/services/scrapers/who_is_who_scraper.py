"""
Who's Who Scraper

Scrapes the EU Who's Who directory for information about:
- European Commission officials (Directors-General, Commissioners)
- EU institution leadership
- Department/DG structure

Source: https://op.europa.eu/en/web/who-is-who

This uses the Publications Office's Who's Who API and web interface.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, ScraperError
from schemas.scrapers.base_schemas import (
    ScrapedPerson,
    ScrapedOrganisation,
    DataSource,
    DocumentType,
    ScrapeBatchResult,
)

logger = logging.getLogger(__name__)


class WhoIsWhoScraper(BaseScraper):
    """
    Scraper for the EU Who's Who directory.

    Provides access to:
    - Commission officials and their roles
    - DG structure and leadership
    - Commissioner portfolios

    Example usage:
        scraper = WhoIsWhoScraper()
        commissioners = await scraper.get_commissioners()
        dgs = await scraper.get_dgs()
        person = await scraper.get_person("person-id")
    """

    # Who's Who base URLs
    WHOISWHO_URL = "https://op.europa.eu/en/web/who-is-who"
    API_BASE = "https://op.europa.eu/en/web/who-is-who/service"

    # Commission structure
    COMMISSION_URL = "https://op.europa.eu/en/web/who-is-who/organization/COM"

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://op.europa.eu/en/web/who-is-who",
            name="WhoIsWho",
            rate_limit_delay=2.0,
            **kwargs
        )
        self._commissioners_cache: List[ScrapedPerson] = []
        self._dgs_cache: List[ScrapedOrganisation] = []

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search for people or organisations in Who's Who.

        Args:
            query: Search term (name, role, department)
            limit: Maximum results (default: 20)

        Returns:
            List of search results
        """
        limit = kwargs.get('limit', 20)

        search_url = f"{self.WHOISWHO_URL}/search"
        params = {
            'q': query,
            'rows': limit,
        }

        try:
            html = await self._fetch(search_url, params=params)
            soup = self._parse_html(html)

            results = []
            for item in soup.select('.search-result-item, .result-item'):
                name_elem = item.select_one('.name, .title, h3')
                role_elem = item.select_one('.role, .subtitle, .position')
                link_elem = item.select_one('a[href]')

                if name_elem:
                    result = {
                        'name': name_elem.get_text(strip=True),
                        'role': role_elem.get_text(strip=True) if role_elem else None,
                        'url': self._make_absolute_url(link_elem['href']) if link_elem else None,
                        'source': 'who_is_who',
                    }
                    results.append(result)

            return results[:limit]

        except Exception as e:
            logger.error(f"Who's Who search failed: {e}")
            return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get details for a specific person or organisation.

        Args:
            document_id: Who's Who ID

        Returns:
            Person or organisation details
        """
        person = await self.get_person(document_id)
        if person:
            return person.model_dump()
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent updates to Who's Who directory.

        Note: Who's Who doesn't have a dedicated updates feed,
        so this returns recently modified entries if available.
        """
        # Who's Who doesn't have a dedicated updates endpoint
        # Return empty list for now
        return []

    async def get_commissioners(self) -> List[ScrapedPerson]:
        """
        Get all current European Commissioners.

        Returns:
            List of Commissioner profiles
        """
        if self._commissioners_cache:
            return self._commissioners_cache

        logger.info("Fetching Commissioners from Who's Who")

        # The Commissioners are under the Commission structure
        url = f"{self.WHOISWHO_URL}/organization/COM/COMM"

        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            commissioners = []

            # Find commissioner entries
            for person_elem in soup.select('.person-card, .member-card, .official'):
                commissioner = self._parse_person_card(person_elem)
                if commissioner:
                    commissioner.role = commissioner.role or "Commissioner"
                    commissioners.append(commissioner)

            # Also try the college of commissioners page
            college_url = f"{self.WHOISWHO_URL}/organization/COM/COMM/COLLEGE"
            try:
                college_html = await self._fetch(college_url)
                college_soup = self._parse_html(college_html)

                for person_elem in college_soup.select('.person-card, .member-card, .official'):
                    commissioner = self._parse_person_card(person_elem)
                    if commissioner and commissioner.full_name not in [c.full_name for c in commissioners]:
                        commissioner.role = commissioner.role or "Commissioner"
                        commissioners.append(commissioner)
            except Exception:
                pass  # College page might not exist

            self._commissioners_cache = commissioners
            logger.info(f"Found {len(commissioners)} Commissioners")
            return commissioners

        except Exception as e:
            logger.error(f"Failed to fetch Commissioners: {e}")
            return []

    async def get_dgs(self) -> List[ScrapedOrganisation]:
        """
        Get all Commission Directorates-General.

        Returns:
            List of DG profiles
        """
        if self._dgs_cache:
            return self._dgs_cache

        logger.info("Fetching DGs from Who's Who")

        url = f"{self.WHOISWHO_URL}/organization/COM"

        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            dgs = []

            # Find DG entries
            for org_elem in soup.select('.organization-card, .org-item, .department'):
                dg = self._parse_org_card(org_elem)
                if dg:
                    dgs.append(dg)

            # Also look for DG list in table format
            for row in soup.select('table tr, .dg-list li'):
                name_elem = row.select_one('a, .name')
                if name_elem and ('DG' in name_elem.get_text() or 'Directorate' in name_elem.get_text()):
                    link = name_elem.get('href', '')
                    dg = ScrapedOrganisation(
                        source=DataSource.WHO_IS_WHO,
                        source_url=self._make_absolute_url(link) if link else None,
                        title=name_elem.get_text(strip=True),
                        full_name=name_elem.get_text(strip=True),
                        org_type="Directorate-General",
                        parent_org="European Commission",
                    )
                    if dg.full_name not in [d.full_name for d in dgs]:
                        dgs.append(dg)

            self._dgs_cache = dgs
            logger.info(f"Found {len(dgs)} DGs")
            return dgs

        except Exception as e:
            logger.error(f"Failed to fetch DGs: {e}")
            return []

    async def get_person(self, person_id: str) -> Optional[ScrapedPerson]:
        """
        Get detailed information about a specific person.

        Args:
            person_id: Who's Who person ID or URL path

        Returns:
            Person profile or None
        """
        # Handle both ID and full URL
        if person_id.startswith('http'):
            url = person_id
        else:
            url = f"{self.WHOISWHO_URL}/person/{person_id}"

        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            # Extract person details
            name_elem = soup.select_one('h1, .person-name, .name')
            role_elem = soup.select_one('.position, .role, .title')
            dept_elem = soup.select_one('.department, .organization, .unit')
            email_elem = soup.select_one('a[href^="mailto:"]')
            phone_elem = soup.select_one('.phone, .telephone')
            photo_elem = soup.select_one('img.photo, img.portrait, .person-photo img')

            if not name_elem:
                return None

            full_name = name_elem.get_text(strip=True)

            # Try to split first/last name
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else None
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else None

            person = ScrapedPerson(
                source=DataSource.WHO_IS_WHO,
                source_url=url,
                source_id=person_id,
                title=full_name,
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                role=role_elem.get_text(strip=True) if role_elem else None,
                institution="European Commission",
                department=dept_elem.get_text(strip=True) if dept_elem else None,
                email=email_elem.get('href', '').replace('mailto:', '') if email_elem else None,
                phone=phone_elem.get_text(strip=True) if phone_elem else None,
                photo_url=self._make_absolute_url(photo_elem['src']) if photo_elem and photo_elem.get('src') else None,
                person_id=person_id,
            )

            return person

        except Exception as e:
            logger.error(f"Failed to fetch person {person_id}: {e}")
            return None

    async def get_organisation(self, org_id: str) -> Optional[ScrapedOrganisation]:
        """
        Get detailed information about an organisation/DG.

        Args:
            org_id: Who's Who organisation ID or code (e.g., "AGRI", "COMP")

        Returns:
            Organisation profile or None
        """
        # Handle both ID and full URL
        if org_id.startswith('http'):
            url = org_id
        else:
            url = f"{self.WHOISWHO_URL}/organization/COM/{org_id}"

        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            name_elem = soup.select_one('h1, .org-name, .name')
            head_elem = soup.select_one('.director-general, .head, .leadership .name')
            head_role_elem = soup.select_one('.director-general .role, .head .title')

            if not name_elem:
                return None

            org = ScrapedOrganisation(
                source=DataSource.WHO_IS_WHO,
                source_url=url,
                source_id=org_id,
                title=name_elem.get_text(strip=True),
                full_name=name_elem.get_text(strip=True),
                short_name=org_id.upper() if len(org_id) <= 6 else None,
                org_type="Directorate-General",
                parent_org="European Commission",
                website=url,
                head_name=head_elem.get_text(strip=True) if head_elem else None,
                head_role=head_role_elem.get_text(strip=True) if head_role_elem else "Director-General",
            )

            return org

        except Exception as e:
            logger.error(f"Failed to fetch organisation {org_id}: {e}")
            return None

    async def get_dg_by_policy_area(self, policy_area: str) -> Optional[ScrapedOrganisation]:
        """
        Find the DG responsible for a policy area.

        Args:
            policy_area: Policy area name (e.g., "agriculture", "competition", "digital")

        Returns:
            DG profile or None
        """
        # Mapping of policy areas to DG codes
        policy_to_dg = {
            'agriculture': 'AGRI',
            'budget': 'BUDG',
            'climate': 'CLIMA',
            'communication': 'COMM',
            'competition': 'COMP',
            'defence': 'DEFIS',
            'digital': 'CNECT',
            'economy': 'ECFIN',
            'education': 'EAC',
            'employment': 'EMPL',
            'energy': 'ENER',
            'environment': 'ENV',
            'enlargement': 'NEAR',
            'health': 'SANTE',
            'home': 'HOME',
            'humanitarian': 'ECHO',
            'internal market': 'GROW',
            'justice': 'JUST',
            'maritime': 'MARE',
            'migration': 'HOME',
            'mobility': 'MOVE',
            'neighbourhood': 'NEAR',
            'regional': 'REGIO',
            'research': 'RTD',
            'taxation': 'TAXUD',
            'trade': 'TRADE',
            'transport': 'MOVE',
        }

        # Find matching DG
        policy_lower = policy_area.lower()
        for key, dg_code in policy_to_dg.items():
            if key in policy_lower or policy_lower in key:
                return await self.get_organisation(dg_code)

        return None

    def _parse_person_card(self, elem) -> Optional[ScrapedPerson]:
        """Parse a person card element into ScrapedPerson"""
        name_elem = elem.select_one('.name, .person-name, h3, h4')
        if not name_elem:
            return None

        role_elem = elem.select_one('.role, .position, .title')
        link_elem = elem.select_one('a[href]')
        photo_elem = elem.select_one('img')
        country_elem = elem.select_one('.country, .nationality')

        full_name = name_elem.get_text(strip=True)
        name_parts = full_name.split()

        return ScrapedPerson(
            source=DataSource.WHO_IS_WHO,
            source_url=self._make_absolute_url(link_elem['href']) if link_elem else None,
            title=full_name,
            full_name=full_name,
            first_name=name_parts[0] if name_parts else None,
            last_name=' '.join(name_parts[1:]) if len(name_parts) > 1 else None,
            role=role_elem.get_text(strip=True) if role_elem else None,
            institution="European Commission",
            country=country_elem.get_text(strip=True) if country_elem else None,
            photo_url=self._make_absolute_url(photo_elem['src']) if photo_elem and photo_elem.get('src') else None,
        )

    def _parse_org_card(self, elem) -> Optional[ScrapedOrganisation]:
        """Parse an organisation card element into ScrapedOrganisation"""
        name_elem = elem.select_one('.name, .org-name, h3, h4, a')
        if not name_elem:
            return None

        link_elem = elem.select_one('a[href]')

        return ScrapedOrganisation(
            source=DataSource.WHO_IS_WHO,
            source_url=self._make_absolute_url(link_elem['href']) if link_elem else None,
            title=name_elem.get_text(strip=True),
            full_name=name_elem.get_text(strip=True),
            org_type="Directorate-General",
            parent_org="European Commission",
        )
