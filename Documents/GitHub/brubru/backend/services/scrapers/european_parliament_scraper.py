"""
European Parliament Scraper

Scrapes MEP information, committee activities, legislative proposals,
and plenary sessions from www.europarl.europa.eu
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, ScraperError
from ...schemas.scrapers.scraper_schemas import MEP, PoliticalGroup, SearchResult


class EuropeanParliamentScraper(BaseScraper):
    """
    Scraper for European Parliament website.

    Key Data Sources:
    - MEP directory and profiles
    - Committee compositions and activities
    - Plenary sessions and agendas
    - Legislative amendments
    - Voting records
    """

    MEP_DIRECTORY_URL = "https://www.europarl.europa.eu/meps/en/directory/xml"
    MEP_PROFILE_URL = "https://www.europarl.europa.eu/meps/en/{mep_id}"
    SEARCH_URL = "https://www.europarl.europa.eu/portal/en/search"

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://www.europarl.europa.eu/portal/en",
            name="EuropeanParliament",
            rate_limit_delay=2.0,  # Be respectful, 2 seconds between requests
            **kwargs
        )

    async def get_all_meps(self, country: Optional[str] = None) -> List[MEP]:
        """
        Retrieve all current MEPs.

        Args:
            country: Filter by country code (e.g., 'BE', 'FR')

        Returns:
            List of MEP objects
        """
        html = await self._fetch(self.MEP_DIRECTORY_URL)
        soup = self._parse_html(html)

        meps = []
        mep_elements = soup.find_all('mep')

        for mep_elem in mep_elements:
            try:
                mep_data = self._parse_mep_element(mep_elem)

                # Filter by country if specified
                if country and mep_data.get('country') != country:
                    continue

                meps.append(MEP(**mep_data))
            except Exception as e:
                self.stats['errors'] += 1
                continue

        return meps

    def _parse_mep_element(self, mep_elem) -> Dict[str, Any]:
        """Parse XML MEP element into dictionary"""
        mep_id = mep_elem.find('id').text if mep_elem.find('id') else None
        full_name_elem = mep_elem.find('fullName')
        country_elem = mep_elem.find('country')
        group_elem = mep_elem.find('politicalGroup')

        return {
            'source': self.name,
            'source_url': self.MEP_PROFILE_URL.format(mep_id=mep_id),
            'mep_id': mep_id,
            'full_name': full_name_elem.text if full_name_elem else "Unknown",
            'first_name': mep_elem.find('name', {'type': 'firstName'}).text if mep_elem.find('name', {'type': 'firstName'}) else None,
            'last_name': mep_elem.find('name', {'type': 'lastName'}).text if mep_elem.find('name', {'type': 'lastName'}) else None,
            'country': country_elem.text if country_elem else None,
            'political_group': PoliticalGroup(
                code=group_elem.get('code', ''),
                name=group_elem.text
            ) if group_elem else None,
            'profile_url': self.MEP_PROFILE_URL.format(mep_id=mep_id),
        }

    async def get_mep_details(self, mep_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific MEP.

        Args:
            mep_id: MEP identifier

        Returns:
            Detailed MEP data including committees, contact info, etc.
        """
        url = self.MEP_PROFILE_URL.format(mep_id=mep_id)
        html = await self._fetch(url)
        soup = self._parse_html(html)

        # Extract committees
        committees = []
        committee_section = soup.find('div', class_='erpl_meps-responsible')
        if committee_section:
            for committee in committee_section.find_all('li'):
                committees.append(committee.get_text(strip=True))

        # Extract contact information
        email = None
        phone = None
        contact_section = soup.find('div', class_='erpl_contacts')
        if contact_section:
            email_elem = contact_section.find('a', href=re.compile(r'^mailto:'))
            if email_elem:
                email = email_elem.get('href', '').replace('mailto:', '')

            phone_elem = contact_section.find(string=re.compile(r'\+\d+'))
            if phone_elem:
                phone = phone_elem.strip()

        # Extract delegations
        delegations = []
        delegation_section = soup.find('div', {'id': 'delegations'})
        if delegation_section:
            for delegation in delegation_section.find_all('li'):
                delegations.append(delegation.get_text(strip=True))

        return {
            'mep_id': mep_id,
            'committees': committees,
            'delegations': delegations,
            'email': email,
            'phone': phone,
            'source_url': url,
        }

    async def search_meps(self, query: str, **kwargs) -> List[MEP]:
        """
        Search for MEPs by name, country, or political group.

        Args:
            query: Search query
            **kwargs: Additional filters (country, political_group)

        Returns:
            List of matching MEPs
        """
        all_meps = await self.get_all_meps()

        # Simple text matching (can be improved with fuzzy matching)
        query_lower = query.lower()
        results = []

        for mep in all_meps:
            if (query_lower in mep.full_name.lower() or
                (mep.country and query_lower in mep.country.lower()) or
                (mep.political_group and query_lower in mep.political_group.name.lower())):

                # Apply additional filters
                if 'country' in kwargs and mep.country != kwargs['country']:
                    continue
                if 'political_group' in kwargs and mep.political_group and mep.political_group.code != kwargs['political_group']:
                    continue

                results.append(mep)

        return results

    async def get_committee_members(self, committee_code: str) -> List[str]:
        """
        Get list of MEPs who are members of a specific committee.

        Args:
            committee_code: Committee code (e.g., 'ENVI', 'ITRE')

        Returns:
            List of MEP IDs
        """
        url = f"https://www.europarl.europa.eu/committees/en/{committee_code}/members"
        html = await self._fetch(url)
        soup = self._parse_html(html)

        mep_ids = []
        member_links = soup.find_all('a', href=re.compile(r'/meps/en/\d+'))

        for link in member_links:
            mep_id = re.search(r'/meps/en/(\d+)', link['href'])
            if mep_id:
                mep_ids.append(mep_id.group(1))

        return list(set(mep_ids))  # Remove duplicates

    async def get_plenary_agenda(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get plenary session agenda for a specific date.

        Args:
            date: Date of plenary session (default: latest)

        Returns:
            Plenary agenda with scheduled items
        """
        # Implementation would scrape plenary schedule
        # This is a placeholder
        raise NotImplementedError("Plenary agenda scraping coming soon")

    # Implement abstract methods

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search European Parliament content.

        Args:
            query: Search query
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        meps = await self.search_meps(query, **kwargs)
        return [mep.dict() for mep in meps]

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get MEP profile by ID.

        Args:
            document_id: MEP identifier

        Returns:
            MEP data
        """
        return await self.get_mep_details(document_id)

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest Parliament updates (news, press releases).

        Args:
            limit: Maximum number of updates

        Returns:
            List of latest updates
        """
        # Would scrape news/press section
        # Placeholder implementation
        return []
