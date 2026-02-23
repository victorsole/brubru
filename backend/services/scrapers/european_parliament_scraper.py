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
from schemas.scrapers.ep_schemas import (
    EPVoteResult, EPMeeting, EPSpeech, EPParliamentaryQuestion,
    EPProcedureEvent, EPDecision, EPMepDeclaration
)
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

    async def get_mep_assistants(self, mep_id: str, mep_name: str) -> List[Dict[str, Any]]:
        """
        Scrape assistant names from an MEP's profile page.

        Args:
            mep_id: MEP identifier (e.g. '257043')
            mep_name: MEP full name for URL slug construction

        Returns:
            List of assistants with name, guessed email, and type (APA/local/service)
        """
        import unicodedata

        # Build URL slug from MEP name: "Maravillas ABADIA JOVER" -> "MARAVILLAS_ABADIA+JOVER"
        slug = mep_name.upper().replace(' ', '_').replace('_', '_', 1)
        # EP uses + for spaces in surnames after first name
        parts = mep_name.strip().split()
        if len(parts) >= 2:
            first = parts[0].upper()
            surname = '+'.join(p.upper() for p in parts[1:])
            slug = f"{first}_{surname}"
        else:
            slug = mep_name.upper().replace(' ', '_')

        url = f"https://www.europarl.europa.eu/meps/en/{mep_id}/{slug}/assistants"

        assistants = []
        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            # EP groups assistants under headings like "Accredited assistants",
            # "Local assistants", "Service providers" etc.
            current_type = "APA"  # Default type

            # Look for assistant sections - the page uses various structures
            # Try the detailed card section first
            assistant_sections = soup.find_all('div', class_='erpl_meps-assistants-detail')
            if not assistant_sections:
                # Fallback: look for any list items under assistants content
                assistant_sections = soup.find_all('div', class_='erpl_type-assistants')

            # Parse section headings to determine type
            for section in soup.find_all(['h3', 'h4', 'span'], class_=re.compile(r'erpl_|sln-')):
                heading_text = section.get_text(strip=True).lower()
                if 'accredited' in heading_text:
                    current_type = "APA"
                elif 'local' in heading_text:
                    current_type = "Local"
                elif 'service' in heading_text or 'paying agent' in heading_text:
                    current_type = "Service provider"

            # Extract assistant names from the page
            # The EP website lists assistants as text within spans or divs
            for elem in soup.find_all('span', class_='t-x'):
                text = elem.get_text(strip=True)
                if text and text.lower() == 'assistants':
                    continue  # Skip the section header itself

            # More reliable: find all name entries in the assistants section
            assistants_container = soup.find('div', id='detailedcardmep') or soup.find('div', class_='erpl_meps-assistants')
            if assistants_container:
                current_type = "APA"
                for elem in assistants_container.find_all(['h4', 'h3', 'li', 'span', 'div']):
                    text = elem.get_text(strip=True)
                    text_lower = text.lower()

                    # Detect type headings
                    if any(kw in text_lower for kw in ['accredited assistant', 'accredited parliamentary']):
                        current_type = "APA"
                        continue
                    elif 'local assistant' in text_lower:
                        current_type = "Local"
                        continue
                    elif any(kw in text_lower for kw in ['service provider', 'paying agent', 'trainee']):
                        current_type = "Service provider"
                        continue

                    # Skip non-name content
                    if not text or len(text) < 3 or len(text) > 100:
                        continue
                    if any(kw in text_lower for kw in ['assistant', 'provider', 'trainee', 'show', 'hide', 'more']):
                        continue

                    # Check if it looks like a name (at least 2 words, starts with capital)
                    name_parts = text.split()
                    if len(name_parts) >= 2 and name_parts[0][0].isupper():
                        # Guess email: strip accents, lowercase, firstname.surname
                        def strip_accents(s: str) -> str:
                            return ''.join(
                                c for c in unicodedata.normalize('NFD', s)
                                if unicodedata.category(c) != 'Mn'
                            )

                        clean_first = strip_accents(name_parts[0]).lower()
                        clean_surname = strip_accents('-'.join(name_parts[1:])).lower()
                        guessed_email = f"{clean_first}.{clean_surname}@europarl.europa.eu"

                        # Avoid duplicates
                        if not any(a['name'] == text for a in assistants):
                            assistants.append({
                                'name': text,
                                'guessed_email': guessed_email,
                                'type': current_type,
                            })

            logger.info(f"Found {len(assistants)} assistants for MEP {mep_name} ({mep_id})")

        except Exception as e:
            logger.warning(f"Failed to scrape assistants for MEP {mep_id}: {str(e)}")

        return assistants

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

        # Find all member sections (EP website redesign: erpl_ -> es_ class prefix)
        member_sections = (
            soup.find_all('div', class_='es_member-list-item')
            or soup.find_all('div', class_='erpl_member-list-item')
        )

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

                # Extract name from the dedicated title element (new format)
                name_elem = section.find('div', class_='es_title-h4')
                if name_elem:
                    name = name_elem.get_text(strip=True)
                else:
                    # Fallback: parse from link text (old format)
                    full_text = mep_link.get_text(strip=True)
                    name_match = re.match(
                        r'^([A-Za-zÀ-ÿ\s\-\'\.]+?)(?:Chair|Vice-Chair|Member|Substitute|S&D|EPP|Renew|ECR|Greens|ID|The Left|PPE|PfE)',
                        full_text, re.IGNORECASE
                    )
                    name = name_match.group(1).strip() if name_match else full_text

                # Extract role, political group, and country from sln-additional-info spans (new format)
                info_spans = section.find_all('span', class_='sln-additional-info')
                role = "Member"
                political_group = ""
                country = ""

                if info_spans:
                    # New format: spans are in order [role?, group, country]
                    # Roles: Chair, Vice-Chair, Member, Substitute
                    # Groups: S&D, EPP, PPE, Renew, ECR, Greens/EFA, The Left, PfE, ESN, NI
                    role_keywords = {'chair', 'vice-chair', 'member', 'substitute'}
                    group_keywords = {'s&d', 'epp', 'ppe', 'renew', 'ecr', 'greens/efa', 'the left', 'pfe', 'esn', 'ni', 'id', 'greens'}
                    for span in info_spans:
                        text = span.get_text(strip=True)
                        text_lower = text.lower()
                        if text_lower in role_keywords or 'chair' in text_lower:
                            if 'vice' in text_lower:
                                role = "Vice-Chair"
                            elif 'chair' in text_lower:
                                role = "Chair"
                            elif 'substitute' in text_lower:
                                role = "Substitute"
                        elif text_lower in group_keywords or '/' in text_lower:
                            political_group = text
                        else:
                            # Remaining span is the country
                            country = text
                else:
                    # Old format fallback
                    country_elem = section.find('span', class_='erpl_title-text') or section.find('span', class_='ep_name')
                    if country_elem:
                        country_text = country_elem.get_text(strip=True)
                        country = country_text.split('-')[0].strip()

                    group_elem = section.find('span', class_='ep_group')
                    political_group = group_elem.get_text(strip=True) if group_elem else ""

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
                    'profile_url': f"https://www.europarl.europa.eu{mep_link['href']}" if not mep_link['href'].startswith('http') else mep_link['href']
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

    # =========================================================================
    # NEW: EP Open Data API v2 Methods
    # =========================================================================

    async def get_meetings(
        self,
        meeting_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EPMeeting]:
        """
        Get parliamentary meetings (plenary sessions, committee meetings)

        Args:
            meeting_type: Filter by type (plenary-sitting, committee-meeting)
            start_date: Filter from this date
            end_date: Filter until this date
            limit: Maximum results

        Returns:
            List of EPMeeting objects
        """
        if not self.use_api:
            raise NotImplementedError("Meetings require API client")

        try:
            logger.info(f"Fetching meetings via scraper (type={meeting_type})")
            return await self.api_client.get_meetings(
                meeting_type=meeting_type,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to fetch meetings: {str(e)}")
            return []

    async def get_vote_results(
        self,
        sitting_id: str
    ) -> List[EPVoteResult]:
        """
        Get vote results from a specific meeting/sitting

        Args:
            sitting_id: Meeting/sitting identifier

        Returns:
            List of EPVoteResult objects
        """
        if not self.use_api:
            raise NotImplementedError("Vote results require API client")

        try:
            logger.info(f"Fetching vote results for sitting: {sitting_id}")
            return await self.api_client.get_meeting_vote_results(sitting_id)
        except Exception as e:
            logger.error(f"Failed to fetch vote results: {str(e)}")
            return []

    async def get_meeting_decisions(
        self,
        sitting_id: str
    ) -> List[EPDecision]:
        """
        Get decisions from a specific meeting/sitting

        Args:
            sitting_id: Meeting/sitting identifier

        Returns:
            List of EPDecision objects
        """
        if not self.use_api:
            raise NotImplementedError("Decisions require API client")

        try:
            logger.info(f"Fetching decisions for sitting: {sitting_id}")
            return await self.api_client.get_meeting_decisions(sitting_id)
        except Exception as e:
            logger.error(f"Failed to fetch decisions: {str(e)}")
            return []

    async def get_procedure_events(
        self,
        procedure_reference: str
    ) -> List[EPProcedureEvent]:
        """
        Get events timeline for a legislative procedure

        First looks up the procedure by reference, then fetches events.

        Args:
            procedure_reference: Procedure reference (e.g., 2025/0102(COD))

        Returns:
            List of EPProcedureEvent objects
        """
        if not self.use_api:
            raise NotImplementedError("Procedure events require API client")

        try:
            logger.info(f"Fetching procedure events for: {procedure_reference}")

            # First, find the procedure to get its process ID
            procedure = await self.api_client.get_procedure_by_reference(procedure_reference)

            if not procedure:
                logger.warning(f"Procedure not found: {procedure_reference}")
                return []

            process_id = procedure.get("identifier") or procedure.get("id")
            if not process_id:
                logger.warning(f"No process ID found for: {procedure_reference}")
                return []

            return await self.api_client.get_procedure_events(process_id)

        except Exception as e:
            logger.error(f"Failed to fetch procedure events: {str(e)}")
            return []

    async def get_speeches(
        self,
        mep_id: Optional[str] = None,
        text: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[EPSpeech]:
        """
        Search MEP speeches/interventions

        Args:
            mep_id: Filter by MEP identifier
            text: Search in speech text
            start_date: Filter from date
            end_date: Filter until date
            limit: Maximum results

        Returns:
            List of EPSpeech objects
        """
        if not self.use_api:
            raise NotImplementedError("Speeches require API client")

        try:
            logger.info(f"Fetching speeches (mep={mep_id}, text={text})")
            return await self.api_client.get_speeches(
                mep_id=mep_id,
                text=text,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to fetch speeches: {str(e)}")
            return []

    async def get_parliamentary_questions(
        self,
        author_mep_id: Optional[str] = None,
        text: Optional[str] = None,
        addressee: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[EPParliamentaryQuestion]:
        """
        Search parliamentary questions

        Args:
            author_mep_id: Filter by author MEP
            text: Search in question text
            addressee: Filter by addressee (Commission, Council)
            start_date: Filter from date
            end_date: Filter until date
            limit: Maximum results

        Returns:
            List of EPParliamentaryQuestion objects
        """
        if not self.use_api:
            raise NotImplementedError("Parliamentary questions require API client")

        try:
            logger.info(f"Fetching parliamentary questions (author={author_mep_id})")
            return await self.api_client.get_parliamentary_questions(
                author_mep_id=author_mep_id,
                text=text,
                addressee=addressee,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to fetch parliamentary questions: {str(e)}")
            return []

    async def get_mep_declarations(
        self,
        mep_id: Optional[str] = None,
        limit: int = 50
    ) -> List[EPMepDeclaration]:
        """
        Get MEP declarations of financial interests

        Args:
            mep_id: Filter by MEP identifier
            limit: Maximum results

        Returns:
            List of EPMepDeclaration objects
        """
        if not self.use_api:
            raise NotImplementedError("MEP declarations require API client")

        try:
            logger.info(f"Fetching MEP declarations (mep={mep_id})")
            return await self.api_client.get_mep_declarations(
                mep_id=mep_id,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to fetch MEP declarations: {str(e)}")
            return []

    async def get_current_meps(
        self,
        country: Optional[str] = None,
        political_group: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get current MEPs (as of today)

        Args:
            country: Filter by country code
            political_group: Filter by political group
            limit: Maximum results

        Returns:
            List of current MEPs
        """
        if not self.use_api:
            raise NotImplementedError("Current MEPs require API client")

        try:
            logger.info("Fetching current MEPs")
            return await self.api_client.get_current_meps(
                country=country,
                political_group=political_group,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to fetch current MEPs: {str(e)}")
            return []

    async def close(self):
        """Close API client connections"""
        if hasattr(self, 'api_client'):
            await self.api_client.close()
            logger.info("Closed European Parliament API client")
