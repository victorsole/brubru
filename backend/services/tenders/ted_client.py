"""
TED REST API Client

Client for the Tenders Electronic Daily (TED) REST API v3.
Used for real-time tender searches and fetching notice content.

API Documentation: https://docs.ted.europa.eu/api/index.html
Base URL: https://api.ted.europa.eu/v3

Rate Limits:
- 700 requests/minute per IP (no authentication required)
- Recommended: 10 requests/second with backoff
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
from enum import Enum
import httpx

from services.api_clients.base_api_client import BaseAPIClient, AuthType, ResponseFormat

logger = logging.getLogger(__name__)


class NoticeType(Enum):
    """TED Notice Types"""
    COMPETITION = "cn-standard"  # Contract Notice
    PLANNING = "pin-only"  # Prior Information Notice
    RESULT = "can-standard"  # Contract Award Notice
    MODIFICATION = "can-modif"  # Contract Modification
    DESIGN_CONTEST = "cn-desg"  # Design Contest
    CORRIGENDUM = "corr"  # Corrigendum


class ProcedureType(Enum):
    """EU Procurement Procedure Types"""
    OPEN = "open"
    RESTRICTED = "restricted"
    NEGOTIATED = "neg-w-call"
    COMPETITIVE_DIALOGUE = "comp-dial"
    INNOVATION_PARTNERSHIP = "innovation"
    NEGOTIATED_WITHOUT_CALL = "neg-wo-call"


class SortField(Enum):
    """Sortable fields"""
    PUBLICATION_DATE = "PD"  # Publication date
    DEADLINE = "TD"  # Tender deadline
    COUNTRY = "CY"  # Country


# ISO 3166-1 alpha-2 to alpha-3 country code mapping for TED API v3
COUNTRY_CODE_MAP = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP",
    "CZ": "CZE", "DK": "DNK", "EE": "EST", "FI": "FIN", "FR": "FRA",
    "DE": "DEU", "GR": "GRC", "HU": "HUN", "IE": "IRL", "IT": "ITA",
    "LV": "LVA", "LT": "LTU", "LU": "LUX", "MT": "MLT", "NL": "NLD",
    "PL": "POL", "PT": "PRT", "RO": "ROU", "SK": "SVK", "SI": "SVN",
    "ES": "ESP", "SE": "SWE", "NO": "NOR", "IS": "ISL", "LI": "LIE",
    "CH": "CHE", "UK": "GBR", "GB": "GBR",
}


class TEDClient(BaseAPIClient):
    """
    TED REST API Client for searching and retrieving EU procurement notices.

    Example usage:
        async with TEDClient() as client:
            # Search for IT tenders in Belgium
            results = await client.search_notices(
                cpv_codes=["72000000"],  # IT services
                countries=["BE"],
                procedure_types=[ProcedureType.OPEN]
            )

            # Get full notice XML (requires API key)
            xml = await client.get_notice_xml("1776-2025")
    """

    TED_API_BASE = "https://api.ted.europa.eu/v3"

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit_calls: int = 600,  # Conservative limit (700 max)
        rate_limit_period: int = 60,
        timeout: int = 30
    ):
        """
        Initialize TED API client.

        Args:
            api_key: TED API key (UUID without hyphens) for authenticated endpoints
            rate_limit_calls: Max calls per minute (TED allows 700)
            rate_limit_period: Rate limit window in seconds
            timeout: Request timeout in seconds
        """
        # Get API key from settings if not provided
        if api_key is None:
            from core.config import settings
            api_key = settings.TENDERATOR_TED_API_KEY

        self.ted_api_key = api_key

        super().__init__(
            base_url=self.TED_API_BASE,
            auth_type=AuthType.NONE,  # We'll handle auth manually for specific endpoints
            rate_limit_calls=rate_limit_calls,
            rate_limit_period=rate_limit_period,
            timeout=timeout
        )

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def health_check(self) -> bool:
        """Check if TED API is accessible"""
        try:
            response = await self.get("notices/search", params={"limit": 1})
            return response.status_code == 200
        except Exception as e:
            logger.error(f"TED API health check failed: {e}")
            return False

    async def search_notices(
        self,
        query: Optional[str] = None,
        cpv_codes: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        procedure_types: Optional[List[ProcedureType]] = None,
        notice_types: Optional[List[NoticeType]] = None,
        publication_date_from: Optional[date] = None,
        publication_date_to: Optional[date] = None,
        deadline_from: Optional[date] = None,
        deadline_to: Optional[date] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        currency: str = "EUR",
        sort_by: SortField = SortField.PUBLICATION_DATE,
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Search TED notices with filters.

        Args:
            query: Free text search query
            cpv_codes: List of CPV codes (e.g., ["72000000", "48000000"])
            countries: List of ISO country codes (e.g., ["BE", "FR"])
            procedure_types: List of procedure types
            notice_types: List of notice types
            publication_date_from: Start of publication date range
            publication_date_to: End of publication date range
            deadline_from: Start of deadline range
            deadline_to: End of deadline range
            min_value: Minimum estimated value
            max_value: Maximum estimated value
            currency: Currency for value filtering
            sort_by: Field to sort by
            sort_order: "asc" or "desc"
            page: Page number (1-indexed)
            page_size: Results per page (max 100)

        Returns:
            {
                "notices": [...],
                "total": 1234,
                "page": 1,
                "page_size": 100,
                "total_pages": 13
            }
        """
        # Build query filter parts
        query_parts = []

        if query:
            query_parts.append(f'FT="{query}"')

        if cpv_codes:
            cpv_filter = " OR ".join([f'PC="{code}"' for code in cpv_codes])
            query_parts.append(f"({cpv_filter})")

        if countries:
            # Convert 2-letter to 3-letter country codes for TED API v3
            country_codes_3 = [COUNTRY_CODE_MAP.get(c.upper(), c) for c in countries]
            country_filter = " OR ".join([f'CY={code}' for code in country_codes_3])
            query_parts.append(f"({country_filter})")

        if procedure_types:
            proc_filter = " OR ".join([f'PR="{pt.value}"' for pt in procedure_types])
            query_parts.append(f"({proc_filter})")

        # Note: TD (notice type) filter values changed in TED API v3
        # Old values like "cn-standard" no longer work
        # Skip this filter for now - we filter by procedure type instead
        # if notice_types:
        #     type_filter = " OR ".join([f'TD="{nt.value}"' for nt in notice_types])
        #     query_parts.append(f"({type_filter})")

        if publication_date_from:
            query_parts.append(f'PD>={publication_date_from.strftime("%Y%m%d")}')

        if publication_date_to:
            query_parts.append(f'PD<={publication_date_to.strftime("%Y%m%d")}')

        if deadline_from:
            query_parts.append(f'DT>={deadline_from.strftime("%Y%m%d")}')

        if deadline_to:
            query_parts.append(f'DT<={deadline_to.strftime("%Y%m%d")}')

        # Build TED API v3 request body
        request_body = {
            "query": " AND ".join(query_parts) if query_parts else "*",
            "fields": ["ND", "TI", "CY", "DD", "PD", "PC", "PR", "TD", "OL", "AU", "TW"],
            "limit": min(page_size, 100),
            "page": page,
        }

        logger.info(f"TED search: {request_body}")

        try:
            # TED API v3 requires POST for search endpoint
            response = await self.post("notices/search", json=request_body)
            data = response.json()

            # Parse response - TED v3 uses different field names
            notices = data.get("notices", [])
            total = data.get("totalNoticeCount", 0)

            return {
                "notices": notices,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
            }

        except httpx.HTTPError as e:
            logger.error(f"TED search failed: {e}")
            raise

    async def search_sme_friendly(
        self,
        cpv_codes: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        max_value: float = 5_000_000,  # €5M default SME threshold
        min_deadline_days: int = 30,
        published_since_days: Optional[int] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Search for SME-friendly tenders.

        Pre-configured filters for small and medium enterprises:
        - Open procedures only (most accessible)
        - Value under threshold
        - Deadline at least N days away
        - Published within the last N days, when `published_since_days` is set

        Args:
            cpv_codes: Sector CPV codes
            countries: Target countries
            max_value: Maximum contract value in EUR
            min_deadline_days: Minimum days until deadline
            published_since_days: Only notices published in the last N days.
                Without it this method filters on deadline alone, so every run
                returns the same still-open backlog (sorted by soonest
                deadline) and a scheduled job re-reads notices it already has.
                A daily ingest wants the publication window; an ad-hoc "what
                can I still bid on" search wants the deadline sort. Both are
                reachable, the caller picks.
            page: Page number
            page_size: Results per page

        Returns:
            Search results with SME-friendly notices
        """
        deadline_from = date.today() + timedelta(days=min_deadline_days)
        publication_date_from = (
            date.today() - timedelta(days=published_since_days)
            if published_since_days
            else None
        )

        return await self.search_notices(
            cpv_codes=cpv_codes,
            countries=countries,
            procedure_types=[ProcedureType.OPEN],  # Most accessible for SMEs
            notice_types=[NoticeType.COMPETITION],  # Active tenders only
            deadline_from=deadline_from,
            publication_date_from=publication_date_from,
            max_value=max_value,
            # Newest first when we are sweeping a publication window, soonest
            # deadline first when we are not.
            sort_by=SortField.PUBLICATION_DATE if publication_date_from else SortField.DEADLINE,
            sort_order="desc" if publication_date_from else "asc",
            page=page,
            page_size=page_size
        )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers if API key is configured."""
        if self.ted_api_key:
            return {"Authorization": f"Bearer {self.ted_api_key}"}
        return {}

    async def get_notice(self, publication_number: str) -> Optional[Dict[str, Any]]:
        """
        Get notice metadata by publication number.

        Args:
            publication_number: TED publication number (e.g., "1776-2025")

        Returns:
            Notice metadata or None if not found

        Note:
            Requires TED API key for authentication.
        """
        if not self.ted_api_key:
            logger.warning("TED API key not configured - cannot fetch individual notices")
            return None

        try:
            response = await self.get(
                f"notices/{publication_number}",
                headers=self._get_auth_headers()
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("TED API authentication failed - check your API key")
                return None
            if e.response.status_code == 404:
                logger.warning(f"Notice {publication_number} not found")
                return None
            raise

    async def get_notice_xml(self, publication_number: str) -> Optional[str]:
        """
        Get full notice XML content (eForms format).

        Uses the public TED website endpoint which doesn't require authentication.

        Args:
            publication_number: TED publication number

        Returns:
            eForms XML content or None if not found
        """
        # Use the public TED website endpoint (no auth required)
        xml_url = f"https://ted.europa.eu/en/notice/{publication_number}/xml"

        try:
            response = await self.client.get(
                xml_url,
                headers={"Accept": "application/xml"},
                follow_redirects=True
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"XML for notice {publication_number} not found")
                return None
            logger.error(f"Failed to fetch XML for {publication_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching XML for {publication_number}: {e}")
            return None

    async def get_notice_pdf(self, publication_number: str) -> Optional[bytes]:
        """
        Get notice as PDF document.

        Args:
            publication_number: TED publication number

        Returns:
            PDF content as bytes or None if not found

        Note:
            Requires TED API key for authentication.
        """
        if not self.ted_api_key:
            logger.debug("TED API key not configured - cannot fetch notice PDF")
            return None

        try:
            headers = {
                "Accept": "application/pdf",
                **self._get_auth_headers()
            }
            response = await self.client.get(
                f"{self.base_url}/notices/{publication_number}/pdf",
                headers=headers
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("TED API authentication failed - check your API key")
                return None
            if e.response.status_code == 404:
                logger.warning(f"PDF for notice {publication_number} not found")
                return None
            raise

    async def get_recent_notices(
        self,
        days: int = 7,
        notice_types: Optional[List[NoticeType]] = None,
        countries: Optional[List[str]] = None,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get notices published in the last N days.

        Args:
            days: Number of days to look back
            notice_types: Filter by notice types
            countries: Filter by countries
            page_size: Results per page

        Returns:
            List of recent notices
        """
        publication_date_from = date.today() - timedelta(days=days)

        all_notices = []
        page = 1

        while True:
            result = await self.search_notices(
                notice_types=notice_types or [NoticeType.COMPETITION],
                countries=countries,
                publication_date_from=publication_date_from,
                page=page,
                page_size=page_size
            )

            notices = result.get("notices", [])
            all_notices.extend(notices)

            if page >= result.get("total_pages", 1):
                break

            page += 1

            # Safety limit
            if len(all_notices) >= 10000:
                logger.warning("Reached safety limit for recent notices")
                break

        return all_notices

    async def get_notices_by_cpv(
        self,
        cpv_code: str,
        include_subcodes: bool = True,
        days_back: int = 30,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get notices for a specific CPV code.

        Args:
            cpv_code: CPV code (e.g., "72000000" for IT services)
            include_subcodes: Include child CPV codes
            days_back: Number of days to search
            page_size: Results per page

        Returns:
            List of notices matching CPV code
        """
        # If including subcodes, use CPV prefix matching
        cpv_codes = [cpv_code]

        if include_subcodes:
            # TED API supports wildcards for CPV matching
            # e.g., "72*" matches all IT services
            cpv_codes = [cpv_code.rstrip("0")]

        return await self.get_recent_notices(
            days=days_back,
            page_size=page_size
        )

    async def get_statistics(
        self,
        countries: Optional[List[str]] = None,
        cpv_codes: Optional[List[str]] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics for notices.

        Args:
            countries: Filter by countries
            cpv_codes: Filter by CPV codes
            date_from: Start date
            date_to: End date

        Returns:
            Statistics including counts by country, CPV, procedure type, etc.
        """
        # Use search with aggregations
        params = {}

        if countries:
            params["countries"] = ",".join(countries)

        if cpv_codes:
            params["cpv"] = ",".join(cpv_codes)

        if date_from:
            params["dateFrom"] = date_from.isoformat()

        if date_to:
            params["dateTo"] = date_to.isoformat()

        try:
            response = await self.get("notices/statistics", params=params)
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get TED statistics: {e}")
            return {}

    def build_ted_url(self, publication_number: str) -> str:
        """
        Build public TED URL for a notice.

        Args:
            publication_number: TED publication number

        Returns:
            Public URL to view notice on TED website
        """
        return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{publication_number}:TEXT:EN:HTML"

    async def download_bulk_package(
        self,
        package_date: date,
        package_type: str = "daily"
    ) -> Optional[bytes]:
        """
        Download TED bulk data package.

        TED provides daily and monthly bulk packages containing all notices
        published on that day/month in XML format.

        Args:
            package_date: Date of the package to download
            package_type: "daily" or "monthly"

        Returns:
            ZIP file content as bytes, or None if not available

        Note:
            Bulk packages are available at:
            - Daily: https://ted.europa.eu/packages/daily/{YYYYMMDD}.tar.gz
            - Monthly: https://ted.europa.eu/packages/monthly/{YYYYMM}.tar.gz
        """
        if package_type == "daily":
            date_str = package_date.strftime("%Y%m%d")
            url = f"https://ted.europa.eu/packages/daily/{date_str}.tar.gz"
        elif package_type == "monthly":
            date_str = package_date.strftime("%Y%m")
            url = f"https://ted.europa.eu/packages/monthly/{date_str}.tar.gz"
        else:
            raise ValueError(f"Invalid package_type: {package_type}")

        logger.info(f"Downloading TED bulk package: {url}")

        try:
            response = await self.client.get(
                url,
                headers={"User-Agent": "Brubru/1.0 (EU Policy Intelligence)"},
                follow_redirects=True,
                timeout=300.0  # 5 minute timeout for large files
            )
            response.raise_for_status()

            logger.info(f"Downloaded {len(response.content)} bytes from {url}")
            return response.content

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Bulk package not found: {url}")
                return None
            raise

    async def get_available_bulk_packages(
        self,
        start_date: date,
        end_date: date,
        package_type: str = "daily"
    ) -> List[date]:
        """
        Get list of available bulk package dates in a range.

        Note: This checks which packages exist by making HEAD requests.

        Args:
            start_date: Start of date range
            end_date: End of date range
            package_type: "daily" or "monthly"

        Returns:
            List of dates for which packages are available
        """
        available = []
        current = start_date

        while current <= end_date:
            if package_type == "daily":
                date_str = current.strftime("%Y%m%d")
                url = f"https://ted.europa.eu/packages/daily/{date_str}.tar.gz"
            else:
                date_str = current.strftime("%Y%m")
                url = f"https://ted.europa.eu/packages/monthly/{date_str}.tar.gz"

            try:
                response = await self.client.head(url)
                if response.status_code == 200:
                    available.append(current)
            except Exception:
                pass

            # Increment date
            if package_type == "daily":
                current = current + timedelta(days=1)
            else:
                # Move to next month
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)

        return available
