"""
NANDO / Single Market Compliance Space Scraper

Scrapes notified body data from the EC Single Market Compliance Space
(formerly NANDO-IS). Notified bodies are organisations designated by
EU/EEA countries to assess product conformity before market placement.

Source: https://webgate.ec.europa.eu/single-market-compliance-space/
Redirected from: https://ec.europa.eu/growth/tools-databases/nando/

Integration with Tenderator:
- Maps notified bodies to CPV codes via directive-to-sector mapping
- Enriches Bid Checklist with relevant conformity assessment bodies
- Alerts users when their tender sector requires notified body involvement
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Directive-to-CPV mapping for Tenderator integration
# Maps EU harmonisation directives to relevant CPV code categories
DIRECTIVE_CPV_MAP = {
    # Construction Products Regulation
    "305/2011": ["44", "45"],  # Construction materials, construction work
    # Machinery Directive
    "2006/42/EC": ["42", "43"],  # Industrial machinery, special-purpose machinery
    # Medical Devices Regulation
    "2017/745": ["33"],  # Medical equipment
    # In Vitro Diagnostic Regulation
    "2017/746": ["33"],  # Medical equipment (IVD)
    # Personal Protective Equipment
    "2016/425": ["18", "35"],  # Clothing, safety equipment
    # Low Voltage Directive
    "2014/35/EU": ["31"],  # Electrical equipment
    # EMC Directive
    "2014/30/EU": ["31", "32"],  # Electrical, telecom equipment
    # ATEX Directive
    "2014/34/EU": ["42", "43"],  # Equipment for explosive atmospheres
    # Pressure Equipment Directive
    "2014/68/EU": ["42"],  # Industrial machinery (pressure vessels)
    # Lifts Directive
    "2014/33/EU": ["42", "45"],  # Lifts, construction
    # Pyrotechnic Articles
    "2013/29/EU": ["35"],  # Security equipment
    # Marine Equipment
    "2014/90/EU": ["34"],  # Transport equipment
    # Radio Equipment Directive
    "2014/53/EU": ["32"],  # Telecoms equipment
    # Toys Safety
    "2009/48/EC": ["37"],  # Recreational goods
    # Gas Appliances Regulation
    "2016/426": ["39", "42"],  # Heating equipment
    # Measuring Instruments
    "2014/32/EU": ["38"],  # Lab/measuring instruments
    # Non-automatic Weighing Instruments
    "2014/31/EU": ["38"],  # Weighing instruments
    # Ecodesign Directive
    "2009/125/EC": ["31", "39"],  # Electrical, heating equipment
    # RoHS Directive
    "2011/65/EU": ["31", "32"],  # Electrical, electronic equipment
    # Simple Pressure Vessels
    "2014/29/EU": ["42"],  # Industrial machinery
    # Cableway Installations
    "2016/424": ["34"],  # Transport equipment
    # Explosives for Civil Uses
    "2014/28/EU": ["43"],  # Special-purpose machinery
}


class NANDOScraper(BaseScraper):
    """
    Scraper for NANDO / Single Market Compliance Space.

    The SMCS is a SPA backed by an API. This scraper attempts
    to use the API directly, falling back to HTML parsing.
    """

    # Known API base (discovered from SPA network calls)
    SMCS_API_BASE = "https://webgate.ec.europa.eu/single-market-compliance-space/api"

    def __init__(self):
        super().__init__(
            base_url="https://webgate.ec.europa.eu/single-market-compliance-space",
            name="NANDO",
            rate_limit_delay=2.0,
            cache_ttl=86400,  # 24h cache - notified bodies change infrequently
        )

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search notified bodies by name or number."""
        bodies = await self.search_notified_bodies(query=query, **kwargs)
        return bodies

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get a specific notified body by ID."""
        return await self.get_notified_body(document_id)

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently updated notified bodies."""
        return await self.search_notified_bodies(limit=limit)

    async def search_notified_bodies(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        directive: Optional[str] = None,
        body_number: Optional[str] = None,
        status: str = "active",
        page: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search notified bodies with filters.

        NOTE: The SMCS (Single Market Compliance Space) backend API requires
        EU Login (ECAS) authentication. The SPA at webgate.ec.europa.eu loads
        data via authenticated XHR calls. Public API access is not available.

        Current approach:
        1. Try the SMCS API (may work with session cookies)
        2. Fall back to HTML parsing of the SPA shell (limited data)
        3. Use reference data from directive-to-CPV mappings

        For full NANDO data, a manual CSV export from the SMCS portal
        or ECAS-authenticated scraping would be needed.

        Args:
            query: Free-text search (body name)
            country: ISO 3166-1 alpha-2 country code
            directive: EU directive reference
            body_number: 4-digit notified body number
            status: active, suspended, withdrawn
            page: Page number (0-based)
            limit: Results per page

        Returns:
            List of notified body records
        """
        # Try API first (requires ECAS auth - may fail)
        try:
            return await self._search_via_api(
                query=query, country=country, directive=directive,
                body_number=body_number, status=status, page=page, limit=limit
            )
        except Exception as e:
            logger.warning(f"NANDO API search failed (ECAS auth required): {e}")

        # SMCS requires EU Login — return empty for now
        # NANDO data must be seeded via CSV import or manual extraction
        logger.info("NANDO: SMCS API requires EU Login. Use CSV import for notified body data.")
        return []

    async def _search_via_api(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        directive: Optional[str] = None,
        body_number: Optional[str] = None,
        status: str = "active",
        page: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Try the SMCS REST API."""
        params = {"page": page, "size": limit}
        if query:
            params["name"] = query
        if country:
            params["country"] = country
        if directive:
            params["legislation"] = directive
        if body_number:
            params["notifiedBodyNumber"] = body_number
        if status:
            params["status"] = status.upper()

        url = f"{self.SMCS_API_BASE}/notified-bodies"
        content = await self._fetch(url, params=params, headers={
            "Accept": "application/json",
        })

        import json
        data = json.loads(content)

        results = []
        items = data if isinstance(data, list) else data.get("content", data.get("results", []))

        for item in items:
            results.append(self._parse_api_body(item))

        logger.info(f"[OK] NANDO API returned {len(results)} notified bodies")
        return results

    async def _search_via_html(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        directive: Optional[str] = None,
        body_number: Optional[str] = None,
        page: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fallback: scrape the legacy NANDO HTML interface."""
        # The old NANDO interface may still serve some pages
        url = f"{self.base_url}/#/notified-bodies"
        params = {}
        if country:
            params["country"] = country
        if body_number:
            params["number"] = body_number

        try:
            content = await self._fetch(url, params=params)
            soup = self._parse_html(content)
            return self._parse_html_results(soup)
        except Exception as e:
            logger.error(f"NANDO HTML scraping also failed: {e}")
            return []

    def _parse_api_body(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a notified body from the SMCS API response."""
        directives = []
        directive_names = []

        # Extract legislation references
        legislations = item.get("legislations", item.get("directives", []))
        for leg in legislations:
            if isinstance(leg, dict):
                ref = leg.get("reference", leg.get("id", ""))
                name = leg.get("name", leg.get("title", ""))
            else:
                ref = str(leg)
                name = ""
            directives.append(ref)
            if name:
                directive_names.append(name)

        # Map directives to CPV codes
        cpv_codes = set()
        for d in directives:
            for directive_key, cpv_list in DIRECTIVE_CPV_MAP.items():
                if directive_key in d:
                    cpv_codes.update(cpv_list)

        return {
            "nando_id": str(item.get("id", item.get("notifiedBodyId", ""))),
            "body_name": item.get("name", item.get("organisationName", "")),
            "body_number": str(item.get("notifiedBodyNumber", item.get("number", ""))),
            "country": item.get("country", item.get("countryCode", "")),
            "address": item.get("address", ""),
            "city": item.get("city", ""),
            "postal_code": item.get("postalCode", ""),
            "phone": item.get("phone", item.get("telephone", "")),
            "email": item.get("email", ""),
            "website": item.get("website", item.get("url", "")),
            "directives": directives,
            "directive_names": directive_names,
            "product_areas": item.get("productAreas", []),
            "cpv_mapping": list(cpv_codes),
            "status": (item.get("status", "active") or "active").lower(),
            "raw_data": item,
        }

    def _parse_html_results(self, soup) -> List[Dict[str, Any]]:
        """Parse notified bodies from HTML page."""
        results = []
        # Look for table rows or card elements
        rows = soup.select("table tbody tr, .notified-body-card, .result-item")

        for row in rows:
            try:
                cols = row.find_all("td") if row.name == "tr" else []
                if len(cols) >= 3:
                    results.append({
                        "nando_id": cols[0].get_text(strip=True),
                        "body_number": cols[0].get_text(strip=True),
                        "body_name": cols[1].get_text(strip=True),
                        "country": cols[2].get_text(strip=True)[:2],
                        "directives": [],
                        "cpv_mapping": [],
                        "status": "active",
                        "raw_data": {"html": str(row)},
                    })
            except Exception as e:
                logger.debug(f"Failed to parse NANDO row: {e}")
                continue

        return results

    async def get_notified_body(self, body_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific notified body."""
        try:
            url = f"{self.SMCS_API_BASE}/notified-bodies/{body_id}"
            content = await self._fetch(url, headers={"Accept": "application/json"})
            import json
            data = json.loads(content)
            return self._parse_api_body(data)
        except Exception as e:
            logger.error(f"Failed to fetch notified body {body_id}: {e}")
            return {}

    async def get_bodies_for_directive(self, directive: str, country: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all notified bodies for a specific EU directive."""
        return await self.search_notified_bodies(directive=directive, country=country, limit=200)

    async def get_bodies_for_cpv(self, cpv_code: str) -> List[Dict[str, Any]]:
        """
        Get notified bodies relevant to a CPV code category.

        Maps CPV codes back to directives, then finds notified bodies.
        Used by Tenderator to enrich bid checklists.
        """
        # Reverse lookup: CPV category -> directives
        relevant_directives = []
        cpv_category = cpv_code[:2]  # First 2 digits = category

        for directive, cpv_list in DIRECTIVE_CPV_MAP.items():
            if cpv_category in cpv_list:
                relevant_directives.append(directive)

        if not relevant_directives:
            logger.info(f"No directive mapping found for CPV category {cpv_category}")
            return []

        # Fetch bodies for each relevant directive
        all_bodies = []
        seen_ids = set()

        for directive in relevant_directives:
            bodies = await self.search_notified_bodies(directive=directive, limit=100)
            for body in bodies:
                body_id = body.get("nando_id") or body.get("body_number")
                if body_id and body_id not in seen_ids:
                    seen_ids.add(body_id)
                    all_bodies.append(body)

        logger.info(f"[OK] Found {len(all_bodies)} notified bodies for CPV {cpv_code} "
                     f"via {len(relevant_directives)} directive(s)")
        return all_bodies
