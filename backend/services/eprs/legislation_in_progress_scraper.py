"""
EU Legislation in Progress Scraper

Scrapes the curated "EU Legislation in Progress" page from epthinktank.eu.
This page contains ~180+ legislative procedures with EPRS coverage.

The page is organized by policy area clusters:
- Economic and Social Policies
- Environment, Climate and Energy
- External Policies
- etc.

Each entry contains:
- Title (linked to EPRS briefing)
- Procedure reference (e.g., "2021/0106(COD)")
- Policy area

This scraper extracts all procedure references and can sync them
to the database as carriages with source='oeil_direct'.
"""

import logging
import re
import aiohttp
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LegislationInProgressEntry:
    """Single entry from EU Legislation in Progress page."""
    procedure_ref: str  # e.g., "2021/0106(COD)"
    title: str
    eprs_url: str  # Link to EPRS briefing
    policy_area: Optional[str] = None
    policy_cluster: Optional[str] = None
    com_reference: Optional[str] = None  # e.g., "COM(2021)206"
    scraped_at: datetime = field(default_factory=datetime.now)


class LegislationInProgressScraper:
    """
    Scraper for epthinktank.eu "EU Legislation in Progress" page.

    This page contains a curated list of ~180+ active legislative
    procedures that have EPRS coverage (briefings, at-a-glance, etc.).

    Usage:
        scraper = LegislationInProgressScraper()

        # Get all procedures
        procedures = await scraper.get_procedures()

        # Get procedures by policy area
        env_procedures = await scraper.get_procedures_by_policy_area("Environment")

        # Sync to database (create carriages)
        stats = await scraper.sync_to_database()
    """

    PAGE_URL = "https://epthinktank.eu/eu-legislation-in-progress/"

    # Regex patterns
    PROCEDURE_REF_PATTERN = re.compile(r'(\d{4}/\d{3,4}\([A-Z]+\))')
    COM_REF_PATTERN = re.compile(r'COM\(\d{4}\)\s*\d+')

    # Policy area mappings (from page structure)
    POLICY_CLUSTERS = {
        "Economic and Social Policies": [
            "Consumer Protection",
            "Employment and Social Affairs",
            "Economic Affairs",
            "Taxation",
            "Internal Market",
            "Competition",
            "Budgets and Financial Programming",
        ],
        "Environment, Climate and Energy": [
            "Environment",
            "Climate Action",
            "Energy",
            "Agriculture and Fisheries",
            "Transport",
        ],
        "External Policies": [
            "Foreign Affairs",
            "International Trade",
            "Development",
            "Humanitarian Aid",
        ],
        "Justice, Home Affairs and Citizens' Rights": [
            "Justice and Home Affairs",
            "Civil Liberties",
            "Citizens' Rights",
            "Data Protection",
        ],
        "Institutional Affairs": [
            "Constitutional Affairs",
            "Legal Affairs",
            "Petitions",
        ],
    }

    def __init__(
        self,
        cache_ttl_seconds: int = 3600,  # 1 hour
        timeout: int = 60
    ):
        """
        Initialize scraper.

        Args:
            cache_ttl_seconds: Cache TTL for scraped data
            timeout: HTTP request timeout
        """
        self._cache: Optional[List[LegislationInProgressEntry]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._timeout = timeout

        logger.info("Initialized LegislationInProgressScraper")

    async def get_procedures(
        self,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all procedures from EU Legislation in Progress page.

        Args:
            force_refresh: Force re-scrape even if cached

        Returns:
            List of procedure dicts with:
                - procedure_ref: "2021/0106(COD)"
                - title: Procedure title
                - eprs_url: Link to EPRS briefing
                - policy_area: Policy area if available
                - policy_cluster: Parent policy cluster
        """
        entries = await self._get_entries(force_refresh=force_refresh)

        return [
            {
                'procedure_ref': entry.procedure_ref,
                'title': entry.title,
                'eprs_url': entry.eprs_url,
                'policy_area': entry.policy_area,
                'policy_cluster': entry.policy_cluster,
                'com_reference': entry.com_reference,
                'scraped_at': entry.scraped_at.isoformat()
            }
            for entry in entries
        ]

    async def get_procedures_by_policy_area(
        self,
        policy_area: str
    ) -> List[Dict[str, Any]]:
        """
        Get procedures filtered by policy area.

        Args:
            policy_area: Policy area to filter by (case-insensitive partial match)

        Returns:
            Filtered list of procedures
        """
        entries = await self._get_entries()

        filtered = [
            entry for entry in entries
            if entry.policy_area and policy_area.lower() in entry.policy_area.lower()
        ]

        return [
            {
                'procedure_ref': entry.procedure_ref,
                'title': entry.title,
                'eprs_url': entry.eprs_url,
                'policy_area': entry.policy_area,
                'policy_cluster': entry.policy_cluster,
            }
            for entry in filtered
        ]

    async def get_procedure_refs(self) -> List[str]:
        """
        Get just the procedure references.

        Returns:
            List of procedure refs like ["2021/0106(COD)", ...]
        """
        entries = await self._get_entries()
        return [entry.procedure_ref for entry in entries]

    async def sync_to_database(self) -> Dict[str, Any]:
        """
        Sync procedures to database as carriages.

        Creates or updates carriages in legislative_carriages table
        with source='oeil_direct'.

        Returns:
            Sync statistics:
                - total_procedures: int
                - created: int
                - updated: int
                - errors: List[str]
        """
        from sqlalchemy.orm import Session
        from core.database import get_db
        from models.legislative_train import LegislativeCarriage, CarriageSourceEnum, CarriageStatusEnum
        from services.scrapers.oeil_scraper import OEILScraper

        logger.info("Syncing EU Legislation in Progress to database")

        entries = await self._get_entries(force_refresh=True)

        stats = {
            'total_procedures': len(entries),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }

        oeil_scraper = OEILScraper()

        # Get database session
        db: Session = next(get_db())

        try:
            for entry in entries:
                try:
                    # Check if carriage already exists
                    existing = db.query(LegislativeCarriage).filter(
                        LegislativeCarriage.oeil_procedure_ref == entry.procedure_ref
                    ).first()

                    if existing:
                        # Update with EPRS info
                        if entry.eprs_url and not existing.eprs_matched_briefings:
                            existing.eprs_matched_briefings = [{
                                'url': entry.eprs_url,
                                'title': entry.title,
                                'source': 'legislation_in_progress'
                            }]
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                        continue

                    # Fetch OEIL data for the procedure
                    try:
                        oeil_data = await oeil_scraper.get_procedure_full(entry.procedure_ref)

                        # Create new carriage
                        carriage = LegislativeCarriage(
                            file_id=f"lip-{entry.procedure_ref.replace('/', '-').replace('(', '-').replace(')', '')}",
                            title=oeil_data.basic_info.title if oeil_data.basic_info else entry.title,
                            oeil_procedure_ref=entry.procedure_ref,
                            source=CarriageSourceEnum.OEIL_DIRECT,
                            current_status=CarriageStatusEnum.TABLED,  # Default, will be updated
                            lead_committee=oeil_data.key_players.committee_responsible.committee_code if oeil_data.key_players and oeil_data.key_players.committee_responsible else None,
                            eprs_matched_briefings=[{
                                'url': entry.eprs_url,
                                'title': entry.title,
                                'source': 'legislation_in_progress'
                            }],
                            policy_areas=[entry.policy_area] if entry.policy_area else [],
                        )

                        db.add(carriage)
                        stats['created'] += 1

                    except Exception as oeil_error:
                        # Create basic carriage without OEIL enrichment
                        logger.warning(f"OEIL fetch failed for {entry.procedure_ref}: {oeil_error}")

                        carriage = LegislativeCarriage(
                            file_id=f"lip-{entry.procedure_ref.replace('/', '-').replace('(', '-').replace(')', '')}",
                            title=entry.title,
                            oeil_procedure_ref=entry.procedure_ref,
                            source=CarriageSourceEnum.OEIL_DIRECT,
                            current_status=CarriageStatusEnum.TABLED,
                            eprs_matched_briefings=[{
                                'url': entry.eprs_url,
                                'title': entry.title,
                                'source': 'legislation_in_progress'
                            }],
                            policy_areas=[entry.policy_area] if entry.policy_area else [],
                        )

                        db.add(carriage)
                        stats['created'] += 1

                except Exception as e:
                    error_msg = f"Failed to sync {entry.procedure_ref}: {str(e)}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # Commit all changes
            db.commit()

            logger.info(
                f"Sync complete: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['skipped']} skipped"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Database sync failed: {str(e)}")
            stats['errors'].append(f"Database error: {str(e)}")

        finally:
            db.close()
            await oeil_scraper.close()

        return stats

    async def _get_entries(
        self,
        force_refresh: bool = False
    ) -> List[LegislationInProgressEntry]:
        """
        Get entries with caching.

        Args:
            force_refresh: Force re-scrape

        Returns:
            List of LegislationInProgressEntry objects
        """
        # Check cache
        if not force_refresh and self._cache and self._cache_time:
            age = datetime.now() - self._cache_time
            if age < self._cache_ttl:
                logger.debug(f"Using cached data (age: {age.seconds}s)")
                return self._cache

        # Scrape page
        entries = await self._scrape_page()

        # Update cache
        self._cache = entries
        self._cache_time = datetime.now()

        return entries

    async def _scrape_page(self) -> List[LegislationInProgressEntry]:
        """
        Scrape the EU Legislation in Progress page.

        Returns:
            List of LegislationInProgressEntry objects
        """
        logger.info(f"Scraping {self.PAGE_URL}")

        entries: List[LegislationInProgressEntry] = []
        seen_procedures: Set[str] = set()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.PAGE_URL,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch page: HTTP {response.status}")
                        return entries

                    html = await response.text()

            soup = BeautifulSoup(html, 'html.parser')

            # The page structure has tables with policy areas
            # Each row contains briefing links with procedure refs in text

            current_policy_area = None
            current_cluster = None

            # Find all table cells and text blocks
            for element in soup.find_all(['td', 'p', 'strong', 'b']):
                text = element.get_text(strip=True)

                # Check if this is a policy area header
                if element.name in ['strong', 'b'] or (element.name == 'td' and len(text) < 100):
                    # Check against known policy areas
                    for cluster, areas in self.POLICY_CLUSTERS.items():
                        for area in areas:
                            if area.lower() in text.lower():
                                current_policy_area = area
                                current_cluster = cluster
                                break

                # Look for links with procedure references
                for link in element.find_all('a', href=True):
                    link_text = link.get_text(strip=True)
                    link_url = link['href']

                    # Skip non-briefing links
                    if 'wp.me' not in link_url and 'epthinktank.eu' not in link_url:
                        continue

                    # Get surrounding text which may contain procedure ref
                    parent_text = element.get_text(strip=True)

                    # Extract procedure reference
                    proc_match = self.PROCEDURE_REF_PATTERN.search(parent_text)
                    if proc_match:
                        procedure_ref = proc_match.group(1)

                        # Skip duplicates
                        if procedure_ref in seen_procedures:
                            continue
                        seen_procedures.add(procedure_ref)

                        # Extract COM reference if present
                        com_match = self.COM_REF_PATTERN.search(parent_text)
                        com_ref = com_match.group(0) if com_match else None

                        entry = LegislationInProgressEntry(
                            procedure_ref=procedure_ref,
                            title=link_text,
                            eprs_url=link_url,
                            policy_area=current_policy_area,
                            policy_cluster=current_cluster,
                            com_reference=com_ref
                        )

                        entries.append(entry)

            logger.info(f"Scraped {len(entries)} procedures from EU Legislation in Progress")
            return entries

        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            return entries

    def clear_cache(self):
        """Clear cached data."""
        self._cache = None
        self._cache_time = None
        logger.info("Cleared LegislationInProgressScraper cache")

    async def close(self):
        """Close any connections (placeholder for interface compatibility)."""
        self.clear_cache()
        logger.info("Closed LegislationInProgressScraper")

    async def health_check(self) -> bool:
        """
        Check if the page is accessible.

        Returns:
            True if page is accessible
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    self.PAGE_URL,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception:
            return False
