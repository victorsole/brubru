"""
Commission College Agenda (OJ) Scraper.

Fetches published Commission College meeting agendas from the
EC Register of Commission Documents via individual document lookups.

The paginated search API is still 503 (as of February 2026), so this
scraper uses sequential OJ(YYYY)NNNN reference enumeration with the
working GET /api/search/{reference}?lang=en endpoint.

Reference pattern: OJ(YYYY)NNNN
  - YYYY = year
  - NNNN = sequential meeting number (e.g. 2555)

Data source: https://ec.europa.eu/transparency/documents-register/

Created: February 2026
"""

import re
import logging
import asyncio
from datetime import datetime, date as date_type
from typing import List, Optional, Dict, Any, Tuple

import aiohttp
from aiohttp import ClientTimeout

from schemas.scrapers.college_oj_schemas import ScrapedCollegeAgenda

logger = logging.getLogger(__name__)

# Known baseline: OJ(2026)2550 = 14 Jan 2026 (first meeting of 2026)
BASELINE_OJ_NUMBER = 2550
BASELINE_YEAR = 2026

# Regex to parse meeting date and location from OJ title
# "Ordre du jour de la 2555ème réunion de la Commission (Bruxelles, 18.2.2026)"
# Also handles English: "Agenda of the 2555th meeting of the Commission (Brussels, 18.2.2026)"
TITLE_PATTERN = re.compile(
    r'(?:Ordre du jour|Agenda).*?'
    r'(\d{4})[eè]me|(\d{4})(?:st|nd|rd|th)\s+'
    r'.*?'
    r'\(([^,]+),\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\)',
    re.IGNORECASE | re.DOTALL,
)

# Simpler pattern that catches the date at the end
DATE_PATTERN = re.compile(
    r'\(([^,]+),\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\)'
)

# Location normalisation
LOCATION_MAP = {
    'bruxelles': 'Brussels',
    'brussels': 'Brussels',
    'strasbourg': 'Strasbourg',
}


class CollegeOJScraper:
    """
    Scraper for Commission College meeting agendas (Ordre du Jour).

    Uses sequential OJ(YYYY)NNNN reference enumeration since the
    paginated search API is unavailable (503).
    """

    API_BASE = "https://ec.europa.eu/transparency/documents-register/api"
    DETAIL_BASE = "https://ec.europa.eu/transparency/documents-register/detail"

    # Rate limiting (EC sites need conservative rate)
    RATE_LIMIT_DELAY = 3.0
    TIMEOUT = 30

    # Browser-like headers (required by EC server)
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        ),
        "Referer": "https://ec.europa.eu/transparency/documents-register/",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self):
        self._last_request_time: Optional[float] = None
        self._request_lock = asyncio.Lock()

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._request_lock:
            if self._last_request_time is not None:
                elapsed = asyncio.get_event_loop().time() - self._last_request_time
                if elapsed < self.RATE_LIMIT_DELAY:
                    wait_time = self.RATE_LIMIT_DELAY - elapsed
                    await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _fetch_oj_document(
        self,
        reference: str,
        lang: str = "en",
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single OJ document by reference.

        Returns raw API response dict, or None if not found (404).
        """
        await self._rate_limit()

        url = f"{self.API_BASE}/search/{reference}"
        timeout = ClientTimeout(total=self.TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url,
                    params={"lang": lang},
                    headers=self.HEADERS,
                ) as response:
                    if response.status == 404:
                        return None
                    if response.status == 503:
                        logger.warning(
                            f"[WARN] RegDoc API 503 for {reference}"
                        )
                        return None
                    response.raise_for_status()
                    return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"[ERROR] Failed to fetch {reference}: {e}")
            return None

    def _parse_oj_document(
        self,
        raw: Dict[str, Any],
        reference: str,
    ) -> Optional[ScrapedCollegeAgenda]:
        """Parse raw API response into a ScrapedCollegeAgenda."""
        try:
            # Verify it's an OJ/agenda document
            doc_type = raw.get("type", "")
            category = raw.get("category", "")
            if doc_type != "AGENDA_COM_MEETING" and category != "OJ":
                logger.debug(
                    f"Skipping {reference}: type={doc_type}, category={category}"
                )
                return None

            # Extract meeting number from reference: OJ(2026)2555 -> 2555
            ref_match = re.match(r'OJ\((\d{4})\)(\d+)', reference)
            if not ref_match:
                return None
            meeting_number = int(ref_match.group(2))

            # Extract title from attachments
            title = ""
            ers_id = None
            attachment_number = None
            languages = []

            attachments = raw.get("attachments", [])
            for att in attachments:
                if att.get("main"):
                    attachment_number = att.get("number")
                    ling_versions = att.get("linguisticVersions", {})
                    languages = [code.upper() for code in ling_versions.keys()]

                    # Prefer English, fall back to French, then first available
                    for lang in ["en", "fr"]:
                        if lang in ling_versions:
                            title = ling_versions[lang].get("title", "")
                            ers_id = ling_versions[lang].get("ersId")
                            break
                    if not title and ling_versions:
                        first_lang = next(iter(ling_versions))
                        title = ling_versions[first_lang].get("title", "")
                        ers_id = ling_versions[first_lang].get("ersId")
                    break

            if not title:
                title = reference

            # Parse meeting date and location from title
            meeting_date, location = self._parse_title(title)
            if not meeting_date:
                # Try to use the API date as fallback
                api_date = raw.get("date")
                if api_date:
                    try:
                        meeting_date = datetime.strptime(api_date, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        pass

            if not meeting_date:
                logger.warning(
                    f"[WARN] Could not parse date from {reference}: {title}"
                )
                return None

            # Publication date
            pub_date = None
            date_str = raw.get("date")
            if date_str:
                try:
                    pub_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass

            # Detail URL
            detail_url = f"{self.DETAIL_BASE}/{reference}"

            return ScrapedCollegeAgenda(
                oj_reference=reference,
                meeting_number=meeting_number,
                meeting_date=meeting_date,
                publication_date=pub_date,
                location=location,
                title=title,
                ers_id=ers_id,
                attachment_number=attachment_number,
                languages=languages if languages else ["EN", "FR"],
                detail_url=detail_url,
                scraped_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"[ERROR] Failed to parse {reference}: {e}")
            return None

    def _parse_title(
        self, title: str
    ) -> Tuple[Optional[date_type], Optional[str]]:
        """
        Parse meeting date and location from OJ title.

        Example: "Ordre du jour de la 2555ème réunion de la Commission
                  (Bruxelles, 18.2.2026)"
        Returns: (date(2026, 2, 18), "Brussels")
        """
        match = DATE_PATTERN.search(title)
        if not match:
            return None, None

        location_raw = match.group(1).strip().lower()
        day = int(match.group(2))
        month = int(match.group(3))
        year = int(match.group(4))

        location = LOCATION_MAP.get(location_raw, location_raw.title())

        try:
            meeting_date = date_type(year, month, day)
            return meeting_date, location
        except ValueError:
            return None, None

    async def scrape_recent_agendas(
        self,
        start_number: Optional[int] = None,
        max_lookups: int = 20,
        year: int = 2026,
    ) -> List[ScrapedCollegeAgenda]:
        """
        Scrape recent Commission College agendas by enumerating
        OJ references sequentially.

        Args:
            start_number: Starting OJ meeting number to scan from.
                         If None, starts from BASELINE_OJ_NUMBER.
            max_lookups: Maximum number of references to try.
            year: Year for OJ references.

        Returns:
            List of scraped agendas, ordered by meeting number.
        """
        if start_number is None:
            start_number = BASELINE_OJ_NUMBER

        agendas: List[ScrapedCollegeAgenda] = []
        consecutive_misses = 0
        max_consecutive_misses = 3  # Stop after 3 consecutive 404s

        current = start_number
        lookups_done = 0

        while lookups_done < max_lookups and consecutive_misses < max_consecutive_misses:
            reference = f"OJ({year}){current}"
            raw = await self._fetch_oj_document(reference)

            if raw is None:
                consecutive_misses += 1
                current += 1
                lookups_done += 1
                continue

            consecutive_misses = 0
            agenda = self._parse_oj_document(raw, reference)
            if agenda:
                agendas.append(agenda)
                logger.info(
                    f"[OK] Found {reference}: {agenda.location} "
                    f"{agenda.meeting_date.isoformat()}"
                )

            current += 1
            lookups_done += 1

        logger.info(
            f"[OK] Scraped {len(agendas)} College agendas "
            f"({lookups_done} lookups, year={year})"
        )
        return agendas

    async def scrape_for_date_range(
        self,
        date_from: date_type,
        date_to: date_type,
        year: int = 2026,
    ) -> List[ScrapedCollegeAgenda]:
        """
        Scrape agendas that fall within a date range.

        Estimates the starting OJ number from the date range and
        scans forward. Commission meets ~weekly, so we estimate
        ~1 meeting per week from the baseline.

        Args:
            date_from: Start of date range.
            date_to: End of date range.
            year: Year for OJ references.

        Returns:
            List of agendas within the date range.
        """
        # Estimate starting OJ number based on weeks from baseline
        baseline_date = date_type(2026, 1, 14)  # OJ(2026)2550 = 14 Jan 2026
        weeks_from_baseline = (date_from - baseline_date).days // 7
        estimated_start = BASELINE_OJ_NUMBER + max(0, weeks_from_baseline - 1)

        # Estimate how many lookups we need
        weeks_in_range = max(1, (date_to - date_from).days // 7 + 2)
        max_lookups = weeks_in_range + 5  # Extra buffer

        agendas = await self.scrape_recent_agendas(
            start_number=estimated_start,
            max_lookups=max_lookups,
            year=year,
        )

        # Filter to date range
        return [
            a for a in agendas
            if date_from <= a.meeting_date <= date_to
        ]
