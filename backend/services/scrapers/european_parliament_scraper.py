"""
European Parliament Scraper

PHASE 4 UPGRADE: Integrated with API clients
- Open Data Portal API (primary)
- RSS feeds for real-time updates
- Web scraping as fallback

Scrapes MEP information, committee activities, legislative proposals,
and plenary sessions from www.europarl.europa.eu
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, ScraperError
from schemas.scrapers.scraper_schemas import MEP, PoliticalGroup, SearchResult
from services.api_clients.european_parliament_client import EuropeanParliamentClient

logger = logging.getLogger(__name__)


class EuropeanParliamentScraper(BaseScraper):
    """
    Scraper for European Parliament website.

    PHASE 4 UPGRADE:
    - Primary: Open Data Portal API + SPARQL
    - Secondary: RSS feeds (33+ feeds)
    - Fallback: Web scraping

    Key Data Sources:
    - MEP directory and profiles (API first, scraping fallback)
    - Committee compositions and activities (API)
    - Plenary sessions and agendas (API + RSS)
    - Legislative amendments (API)
    - Voting records (api.epdb.eu integration)
    - RSS feeds for real-time updates
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

        # PHASE 4: Initialize API client
        self.api_client = EuropeanParliamentClient()
        self.use_api = True  # Flag to toggle API vs scraping

        logger.info("European Parliament Scraper initialized with API client")

    async def get_all_meps(self, country: Optional[str] = None) -> List[MEP]:
        """
        Retrieve all current MEPs.

        PHASE 4: API first, scraping as fallback

        Args:
            country: Filter by country code (e.g., 'BE', 'FR')

        Returns:
            List of MEP objects
        """
        # PHASE 4: Try API first
        if self.use_api:
            try:
                logger.info("Fetching MEPs via API")
                api_meps = await self.api_client.get_mep_list(country=country)

                # Convert API response to MEP objects
                meps = []
                for mep_data in api_meps:
                    try:
                        # API returns identifier as just a number, construct full URL
                        mep_id = mep_data.get('id', '')
                        profile_url = f"https://www.europarl.europa.eu/meps/en/{mep_id}"

                        meps.append(MEP(
                            source=self.name,
                            source_url=profile_url,
                            mep_id=mep_id,
                            full_name=mep_data.get('name', 'Unknown'),
                            country=mep_data.get('country', ''),
                            political_group=None,  # REST API v2 doesn't return group in list
                            profile_url=profile_url
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse MEP from API: {str(e)}")
                        continue

                logger.info(f"Successfully fetched {len(meps)} MEPs via API")
                return meps

            except Exception as e:
                logger.error(f"API failed, falling back to scraping: {str(e)}")
                # Continue to scraping fallback

        # Fallback to scraping
        logger.info("Fetching MEPs via web scraping")
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

    async def get_all_committees(self) -> List[Dict[str, Any]]:
        """
        Get list of all EP committees.

        Returns:
            List of committees with code, name, and URL

        Example:
            [
                {
                    'code': 'ENVI',
                    'name': 'Environment, Public Health and Food Safety',
                    'url': 'https://www.europarl.europa.eu/committees/en/envi/home',
                    'type': 'standing'
                },
                ...
            ]
        """
        url = "https://www.europarl.europa.eu/committees/en/home"
        html = await self._fetch(url)
        soup = self._parse_html(html)

        committees = []

        # Find all committee options in the dropdown (more reliable than links)
        committee_options = soup.find_all('option', attrs={'data-organ-text': re.compile(r'^[A-Z]{4}$')})

        for option in committee_options:
            code = option.get('data-organ-text', '').upper()
            name = option.get_text(strip=True)

            if code and name and len(code) == 4:
                committees.append({
                    'code': code,
                    'name': name,
                    'url': f"https://www.europarl.europa.eu/committees/en/{code.lower()}/home",
                    'type': 'standing'  # Default to standing committee
                })

        logger.info(f"Found {len(committees)} committees")
        return committees

    async def get_committee_members(self, committee_code: str) -> List[Dict[str, Any]]:
        """
        Get detailed list of MEPs who are members of a specific committee.

        Args:
            committee_code: Committee code (e.g., 'ENVI', 'ITRE')

        Returns:
            List of committee members with details

        Example:
            [
                {
                    'mep_id': '123456',
                    'name': 'John Doe',
                    'country': 'BE',
                    'political_group': 'EPP',
                    'role': 'Chair',
                    'profile_url': 'https://www.europarl.europa.eu/meps/en/123456'
                },
                ...
            ]
        """
        url = f"https://www.europarl.europa.eu/committees/en/{committee_code.lower()}/home/members"
        html = await self._fetch(url)
        soup = self._parse_html(html)

        members = []

        # Find all member sections
        member_sections = soup.find_all('div', class_='erpl_member-list-item')

        for section in member_sections:
            try:
                # Extract MEP link and ID
                mep_link = section.find('a', href=re.compile(r'/meps/en/\d+'))
                if not mep_link:
                    continue

                mep_id_match = re.search(r'/meps/en/(\d+)', mep_link['href'])
                if not mep_id_match:
                    continue

                mep_id = mep_id_match.group(1)

                # Extract name - use regex to extract only the name before role/group/country
                # The link text is concatenated like "Antonio DECAROChairS&DItaly"
                # We want to extract just "Antonio DECARO"
                full_text = mep_link.get_text(strip=True)

                # Pattern: Name usually comes before keywords like Chair, Vice-Chair, S&D, EPP, etc.
                # Names contain letters, spaces, hyphens, apostrophes, and accented characters
                name_match = re.match(r'^([A-Za-zÀ-ÿ\s\-\'\.]+?)(?:Chair|Vice-Chair|Member|Substitute|S&D|EPP|Renew|ECR|Greens|ID|The Left|PPE|PfE)', full_text, re.IGNORECASE)

                if name_match:
                    name = name_match.group(1).strip()
                else:
                    # Fallback: just use the full text if pattern doesn't match
                    name = full_text

                # Extract country
                country_elem = section.find('span', class_='erpl_title-text') or section.find('span', class_='ep_name')
                country = ""
                if country_elem:
                    country_text = country_elem.get_text(strip=True)
                    # Country is usually in format "Belgium" or "Belgium - Group"
                    country_parts = country_text.split('-')[0].strip()
                    country = country_parts[:2].upper() if len(country_parts) >= 2 else country_parts

                # Extract political group
                group_elem = section.find('span', class_='ep_group')
                political_group = group_elem.get_text(strip=True) if group_elem else ""

                # Extract role (Chair, Vice-Chair, Member, Substitute)
                role = "Member"  # Default
                role_elem = section.find('span', class_='erpl_title-role') or section.find('em')
                if role_elem:
                    role_text = role_elem.get_text(strip=True).lower()
                    if 'chair' in role_text and 'vice' not in role_text:
                        role = "Chair"
                    elif 'vice' in role_text:
                        role = "Vice-Chair"
                    elif 'substitute' in role_text:
                        role = "Substitute"

                members.append({
                    'mep_id': mep_id,
                    'name': name,
                    'country': country,
                    'political_group': political_group,
                    'role': role,
                    'profile_url': f"https://www.europarl.europa.eu{mep_link['href']}"
                })

            except Exception as e:
                logger.warning(f"Failed to parse committee member: {str(e)}")
                continue

        logger.info(f"Found {len(members)} members for committee {committee_code}")
        return members

    async def get_committee_details(self, committee_code: str) -> Dict[str, Any]:
        """
        Get comprehensive details about a specific committee.

        Args:
            committee_code: Committee code (e.g., 'ENVI', 'ITRE')

        Returns:
            Committee details including members, description, and metadata
        """
        committee_code_lower = committee_code.lower()

        # Fetch committee home page for description
        home_url = f"https://www.europarl.europa.eu/committees/en/{committee_code_lower}/home"
        html = await self._fetch(home_url)
        soup = self._parse_html(html)

        # Extract committee name
        name_elem = soup.find('h1') or soup.find('title')
        name = name_elem.get_text(strip=True) if name_elem else committee_code

        # Extract description
        description = ""
        desc_elem = soup.find('div', class_='ep_description') or soup.find('p', class_='ep-a_text')
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Get committee members
        members = await self.get_committee_members(committee_code)

        return {
            'code': committee_code.upper(),
            'name': name,
            'description': description,
            'members': members,
            'member_count': len(members),
            'url': home_url,
            'last_updated': datetime.now().isoformat()
        }

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

        PHASE 4: RSS feeds integration

        Args:
            limit: Maximum number of updates

        Returns:
            List of latest updates
        """
        # PHASE 4: Use RSS feeds for real-time updates
        if self.use_api:
            try:
                logger.info("Fetching latest updates via RSS feeds")
                updates = await self.api_client.get_latest_news(hours=24)
                return updates[:limit]
            except Exception as e:
                logger.error(f"RSS fetch failed: {str(e)}")

        # Fallback to web scraping (placeholder)
        logger.info("RSS failed, scraping not implemented for updates")
        return []

    async def get_documents_by_date(
        self,
        date_from: datetime,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get EP documents by date range using API

        Args:
            date_from: Start date
            date_to: End date (default: now)
            limit: Maximum results

        Returns:
            List of documents
        """
        if not self.use_api:
            raise NotImplementedError("Scraping for documents not implemented")

        try:
            logger.info(f"Fetching EP documents from {date_from} via API")
            documents = await self.api_client.search_documents(
                query="",
                date_from=date_from,
                date_to=date_to,
                limit=limit
            )
            return documents
        except Exception as e:
            logger.error(f"Failed to fetch documents: {str(e)}")
            return []

    async def get_committee_info(self, committee_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get committee information via API

        Args:
            committee_code: Specific committee code (None for all)

        Returns:
            List of committees
        """
        if not self.use_api:
            raise NotImplementedError("Scraping for committees not implemented")

        try:
            logger.info(f"Fetching committee info via API: {committee_code or 'all'}")
            committees = await self.api_client.get_committee_info(committee_code=committee_code)
            return committees
        except Exception as e:
            logger.error(f"Failed to fetch committees: {str(e)}")
            return []

    async def get_rss_feed_by_topic(self, topic: str) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get RSS feed entries by topic

        Args:
            topic: Topic name (e.g., 'climate_change', 'economy', 'digital')

        Returns:
            RSS feed entries
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info(f"Fetching RSS feed for topic: {topic}")
            feed = await self.api_client.get_rss_feed(topic, since=datetime.now() - timedelta(days=7))

            entries = []
            for entry in feed.entries:
                entries.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published.isoformat(),
                    'summary': entry.summary
                })

            return entries
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed: {str(e)}")
            return []

    async def close(self):
        """Close API client connections"""
        if hasattr(self, 'api_client'):
            await self.api_client.close()
            logger.info("Closed European Parliament API client")
