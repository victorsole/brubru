"""
EMI - European Monitor of Industrial Ecosystems Scraper

Scrapes data from the EMI dashboard tracking green and digital transition
across 14 EU industrial ecosystems and 27 member states.

Source: https://monitor-industrial-ecosystems.ec.europa.eu

Integration with Tenderator:
- Provides sector health data for tender analysis (e.g., is a sector growing?)
- Maps ecosystems to CPV codes for sector-based enrichment
- Feeds chatbot with industrial ecosystem intelligence
"""

import logging
import re
from typing import List, Dict, Any, Optional

from services.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# 14 EMI Industrial Ecosystems with CPV mappings
ECOSYSTEMS = {
    "Aerospace & Defence": {
        "cpv": ["35"],  # Security/defence equipment
        "indicators": ["patent_applications", "venture_capital", "ghg_emissions", "digital_intensity"],
    },
    "Agri-food": {
        "cpv": ["03", "15", "16"],  # Agriculture, food, farm machinery
        "indicators": ["patent_applications", "ghg_emissions", "water_use", "startup_activity"],
    },
    "Construction": {
        "cpv": ["44", "45"],  # Construction materials, construction work
        "indicators": ["patent_applications", "ghg_emissions", "materials_extraction", "digital_intensity"],
    },
    "Creative & Cultural Industries": {
        "cpv": ["22", "92"],  # Printed matter, recreational/cultural/sporting
        "indicators": ["startup_activity", "venture_capital", "digital_intensity"],
    },
    "Digital": {
        "cpv": ["30", "32", "48", "72"],  # IT equipment, telecom, software, IT services
        "indicators": ["patent_applications", "venture_capital", "startup_activity", "digital_intensity"],
    },
    "Electronics": {
        "cpv": ["31", "32"],  # Electrical/electronic equipment
        "indicators": ["patent_applications", "ghg_emissions", "venture_capital", "digital_intensity"],
    },
    "Energy Intensive Industries": {
        "cpv": ["09", "24", "27"],  # Petroleum, chemicals, metals
        "indicators": ["ghg_emissions", "energy_consumption", "patent_applications", "capital_investment"],
    },
    "Energy - Renewables": {
        "cpv": ["09", "31"],  # Energy, electrical equipment
        "indicators": ["patent_applications", "venture_capital", "ghg_emissions", "capital_investment"],
    },
    "Health": {
        "cpv": ["33", "85"],  # Medical equipment, health services
        "indicators": ["patent_applications", "venture_capital", "startup_activity", "r_and_d_funding"],
    },
    "Mobility, Transport & Automotive": {
        "cpv": ["34", "60"],  # Transport equipment, transport services
        "indicators": ["patent_applications", "ghg_emissions", "venture_capital", "digital_intensity"],
    },
    "Proximity, Social Economy & Civil Security": {
        "cpv": ["75", "85"],  # Public admin, health/social services
        "indicators": ["startup_activity", "digital_intensity", "skilled_professionals"],
    },
    "Retail": {
        "cpv": ["55"],  # Hotel/restaurant services (proxy)
        "indicators": ["digital_intensity", "startup_activity", "ghg_emissions"],
    },
    "Textiles": {
        "cpv": ["18", "19"],  # Clothing, leather/textile
        "indicators": ["patent_applications", "ghg_emissions", "water_use", "digital_intensity"],
    },
    "Tourism": {
        "cpv": ["55", "63"],  # Hotel services, travel services
        "indicators": ["digital_intensity", "startup_activity", "ghg_emissions"],
    },
}

# Full indicator definitions
INDICATORS = {
    "patent_applications": {
        "name": "Green/Digital Patent Applications",
        "dimension": "transition_efforts",
        "sub_dimension": "technology",
        "unit": "count",
    },
    "venture_capital": {
        "name": "Venture Capital Investment",
        "dimension": "transition_efforts",
        "sub_dimension": "investment",
        "unit": "EUR millions",
    },
    "startup_activity": {
        "name": "Startup & Scale-up Activity",
        "dimension": "transition_efforts",
        "sub_dimension": "technology",
        "unit": "count",
    },
    "capital_investment": {
        "name": "Capital Investment Volume",
        "dimension": "transition_efforts",
        "sub_dimension": "investment",
        "unit": "EUR millions",
    },
    "ghg_emissions": {
        "name": "GHG Emissions",
        "dimension": "impact",
        "sub_dimension": "environmental",
        "unit": "Mt CO2eq",
    },
    "water_use": {
        "name": "Blue Water Use",
        "dimension": "impact",
        "sub_dimension": "environmental",
        "unit": "million m3",
    },
    "materials_extraction": {
        "name": "Materials Extraction",
        "dimension": "impact",
        "sub_dimension": "environmental",
        "unit": "Mt",
    },
    "energy_consumption": {
        "name": "Energy Consumption",
        "dimension": "impact",
        "sub_dimension": "environmental",
        "unit": "Mtoe",
    },
    "digital_intensity": {
        "name": "Digital Intensity Index",
        "dimension": "impact",
        "sub_dimension": "digital",
        "unit": "percentage",
    },
    "r_and_d_funding": {
        "name": "EU R&D Funding",
        "dimension": "enabling_framework",
        "sub_dimension": "skills",
        "unit": "EUR millions",
    },
    "skilled_professionals": {
        "name": "Skilled Professionals Availability",
        "dimension": "enabling_framework",
        "sub_dimension": "skills",
        "unit": "index",
    },
}


class EMIScraper(BaseScraper):
    """
    Scraper for the European Monitor of Industrial Ecosystems.

    Since the EMI dashboard is a complex SPA without a public API,
    this scraper fetches ecosystem reports and factsheets which are
    available as downloadable documents.
    """

    BASE_URL = "https://monitor-industrial-ecosystems.ec.europa.eu"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            name="EMI",
            rate_limit_delay=3.0,
            cache_ttl=86400,  # 24h - data updates infrequently
        )

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search ecosystem data."""
        return self.get_ecosystem_data(query)

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get ecosystem summary."""
        return self.get_ecosystem_summary(document_id)

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest reports."""
        return await self.scrape_reports(limit=limit)

    def get_ecosystem_data(self, ecosystem_name: str) -> List[Dict[str, Any]]:
        """
        Get reference data for an industrial ecosystem.

        Since the EMI dashboard doesn't expose a public API,
        this returns structured reference data from our mappings
        that can be enriched by scraping reports.

        Args:
            ecosystem_name: Name of the ecosystem

        Returns:
            List of indicator definitions for the ecosystem
        """
        # Find best matching ecosystem
        best_match = None
        query_lower = ecosystem_name.lower()

        for name in ECOSYSTEMS:
            if query_lower in name.lower() or name.lower() in query_lower:
                best_match = name
                break

        if not best_match:
            return []

        ecosystem = ECOSYSTEMS[best_match]
        results = []

        for indicator_key in ecosystem["indicators"]:
            indicator = INDICATORS.get(indicator_key, {})
            results.append({
                "ecosystem": best_match,
                "indicator": indicator.get("name", indicator_key),
                "dimension": indicator.get("dimension", ""),
                "sub_dimension": indicator.get("sub_dimension", ""),
                "unit": indicator.get("unit", ""),
                "cpv_categories": ecosystem["cpv"],
            })

        return results

    def get_ecosystem_summary(self, ecosystem_name: str) -> Dict[str, Any]:
        """Get a summary of an ecosystem including CPV mappings."""
        for name, data in ECOSYSTEMS.items():
            if ecosystem_name.lower() in name.lower():
                return {
                    "ecosystem": name,
                    "cpv_categories": data["cpv"],
                    "tracked_indicators": [
                        INDICATORS.get(i, {"name": i})
                        for i in data["indicators"]
                    ],
                    "source_url": f"{self.BASE_URL}/ecosystems",
                }
        return {}

    async def scrape_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Scrape available EMI reports and factsheets.

        Returns:
            List of report metadata
        """
        reports = []

        # Try reports page
        for page_path in ["/reports", "/tools/reports", "/latest"]:
            try:
                url = f"{self.BASE_URL}{page_path}"
                content = await self._fetch(url)
                soup = self._parse_html(content)
                reports.extend(self._parse_reports_page(soup))
                if reports:
                    break
            except Exception:
                continue

        # Also try ecosystem pages for data
        try:
            url = f"{self.BASE_URL}/ecosystems"
            content = await self._fetch(url)
            soup = self._parse_html(content)

            # Find ecosystem links
            for link in soup.find_all("a", href=re.compile(r"/ecosystem")):
                href = link.get("href", "")
                name = link.get_text(strip=True)
                if name and len(name) > 3:
                    reports.append({
                        "title": f"EMI Ecosystem: {name}",
                        "type": "ecosystem_page",
                        "url": self._make_absolute_url(href),
                        "ecosystem": name,
                    })
        except Exception as e:
            logger.debug(f"EMI ecosystems page scraping failed: {e}")

        logger.info(f"[OK] EMI: found {len(reports)} reports/pages")
        return reports[:limit]

    def _parse_reports_page(self, soup) -> List[Dict[str, Any]]:
        """Parse EMI reports page."""
        reports = []

        # Look for report cards/links
        for card in soup.select(".report-card, .view-content .views-row, article, .card"):
            title_el = card.find(["h2", "h3", "h4", "a"])
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = card.find("a", href=True)
            href = link.get("href", "") if link else ""

            # Look for download links (PDF, Excel)
            downloads = []
            for dl_link in card.find_all("a", href=re.compile(r"\.(pdf|xlsx?|csv)", re.I)):
                downloads.append({
                    "url": self._make_absolute_url(dl_link.get("href", "")),
                    "format": re.search(r"\.(pdf|xlsx?|csv)", dl_link.get("href", ""), re.I).group(1),
                })

            # Try to identify ecosystem
            ecosystem = ""
            for eco_name in ECOSYSTEMS:
                if eco_name.lower() in title.lower():
                    ecosystem = eco_name
                    break

            reports.append({
                "title": title,
                "type": "report",
                "url": self._make_absolute_url(href) if href else "",
                "downloads": downloads,
                "ecosystem": ecosystem,
            })

        return reports

    def get_ecosystems_for_cpv(self, cpv_code: str) -> List[Dict[str, Any]]:
        """
        Find which industrial ecosystems are relevant for a CPV code.
        Used by Tenderator to provide sector context.

        Args:
            cpv_code: CPV code (first 2 digits used)

        Returns:
            List of matching ecosystem summaries
        """
        cpv_category = cpv_code[:2]
        matches = []

        for name, data in ECOSYSTEMS.items():
            if cpv_category in data["cpv"]:
                matches.append({
                    "ecosystem": name,
                    "cpv_categories": data["cpv"],
                    "indicators": [
                        INDICATORS.get(i, {"name": i}).get("name", i)
                        for i in data["indicators"]
                    ],
                })

        return matches

    def get_all_ecosystems(self) -> List[Dict[str, Any]]:
        """Get all 14 industrial ecosystems with their metadata."""
        return [
            {
                "ecosystem": name,
                "cpv_categories": data["cpv"],
                "indicator_count": len(data["indicators"]),
                "indicators": [
                    INDICATORS.get(i, {"name": i}).get("name", i)
                    for i in data["indicators"]
                ],
            }
            for name, data in ECOSYSTEMS.items()
        ]
