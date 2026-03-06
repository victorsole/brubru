"""
TBT - Technical Barriers to Trade Scraper

Scrapes WTO TBT notifications and EU comments from the EC TBT portal.
TBT notifications signal potential trade barriers that could affect
cross-border procurement and market access.

Source: https://technical-barriers-trade.ec.europa.eu

Integration with Tenderator:
- Flags cross-border procurement risks for tenders in affected sectors
- Alerts users bidding in countries with active TBT notifications
- Tracks EU notifications that may change procurement requirements
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Product area to CPV mapping
TBT_PRODUCT_CPV_MAP = {
    "chemicals": ["24"],
    "chemical precursor": ["24"],
    "pharmaceutical": ["33"],
    "medical device": ["33"],
    "food": ["15"],
    "agriculture": ["03", "16"],
    "automotive": ["34"],
    "vehicle": ["34"],
    "emissions": ["34", "90"],
    "energy": ["09", "31"],
    "ecodesign": ["31", "39"],
    "space heater": ["39"],
    "electrical": ["31"],
    "electronic": ["32"],
    "telecom": ["32"],
    "construction": ["44", "45"],
    "textile": ["19"],
    "cosmetic": ["33"],
    "pesticide": ["24"],
    "biocid": ["24"],
    "biotech": ["33"],
    "gmo": ["03"],
    "carcinogen": ["24"],
    "machinery": ["42", "43"],
    "plastic": ["19", "44"],
    "packaging": ["44"],
    "toy": ["37"],
    "transport": ["34"],
    "maritime": ["34"],
    "aviation": ["34"],
    "it service": ["72"],
    "software": ["48"],
    "cyber": ["72"],
    "ai": ["72"],
    "data": ["72"],
}


class TBTScraper(BaseScraper):
    """
    Scraper for TBT (Technical Barriers to Trade) notifications.

    Monitors EU and third-country TBT notifications that may affect
    procurement requirements or cross-border market access.
    """

    BASE_URL = "https://technical-barriers-trade.ec.europa.eu"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            name="TBT",
            rate_limit_delay=3.0,
            cache_ttl=3600,
        )

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search TBT notifications."""
        return await self.search_notifications(query=query, **kwargs)

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get a specific TBT notification by ID."""
        return await self.get_notification(int(document_id))

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest EU TBT notifications."""
        return await self.get_latest_eu_notifications(limit=limit)

    async def get_latest_eu_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Scrape the latest EU TBT notifications.

        Returns:
            List of EU TBT notification records
        """
        url = f"{self.BASE_URL}/en/notifications/latest/EU/{limit}"
        try:
            content = await self._fetch(url)
            soup = self._parse_html(content)
            return self._parse_notification_list(soup, is_eu=True)
        except Exception as e:
            logger.error(f"Failed to fetch latest EU TBT notifications: {e}")
            return []

    async def search_notifications(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        number: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search TBT notifications.

        Args:
            query: Free-text search
            country: Country name or ISO code
            number: Specific notification ID
            limit: Max results

        Returns:
            List of TBT notification records
        """
        params = {}
        if country:
            params["country"] = country
        if number:
            params["number"] = str(number)

        url = f"{self.BASE_URL}/en/search/results"
        try:
            content = await self._fetch(url, params=params)
            soup = self._parse_html(content)
            results = self._parse_notification_list(soup)

            if query:
                query_lower = query.lower()
                results = [r for r in results if query_lower in r.get("title", "").lower()]

            return results[:limit]
        except Exception as e:
            logger.error(f"Failed to search TBT notifications: {e}")
            return []

    async def get_notification(self, notification_id: int) -> Dict[str, Any]:
        """
        Get detailed info for a TBT notification.

        Args:
            notification_id: TBT notification ID (e.g., 38810)

        Returns:
            Detailed notification record
        """
        url = f"{self.BASE_URL}/en/notification/{notification_id}"
        try:
            content = await self._fetch(url)
            soup = self._parse_html(content)
            return self._parse_notification_detail(soup, notification_id)
        except Exception as e:
            logger.error(f"Failed to fetch TBT notification {notification_id}: {e}")
            return {}

    def _parse_notification_list(self, soup, is_eu: bool = False) -> List[Dict[str, Any]]:
        """Parse TBT notifications from list page."""
        results = []

        # Find notification links
        links = soup.find_all("a", href=re.compile(r"/notification/\d+"))
        seen_ids = set()

        for link in links:
            try:
                href = link.get("href", "")
                id_match = re.search(r"/notification/(\d+)", href)
                if not id_match:
                    continue

                notif_id = int(id_match.group(1))
                if notif_id in seen_ids:
                    continue
                seen_ids.add(notif_id)

                # Get context from parent element
                parent = link.find_parent(["tr", "div", "li", "article", "td"])
                container = parent.find_parent(["tr", "div"]) if parent else None
                context_el = container or parent

                title = ""
                country = ""
                date_str = ""

                if context_el:
                    # Try to get structured data from table
                    cells = context_el.find_all("td") if context_el.name == "tr" else []
                    if len(cells) >= 3:
                        country = cells[0].get_text(strip=True) if cells else ""
                        date_str = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        title = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    else:
                        # Get all text and try to parse
                        full_text = context_el.get_text(separator="|", strip=True)
                        parts = [p.strip() for p in full_text.split("|") if p.strip()]
                        for part in parts:
                            date_match = re.match(r"\d{2}/\d{2}/\d{4}", part)
                            if date_match:
                                date_str = date_match.group()
                            elif len(part) > 20:
                                title = part
                            elif not country:
                                country = part

                if not title:
                    title = link.get_text(strip=True)

                notification_date = None
                if date_str:
                    try:
                        notification_date = datetime.strptime(date_str, "%d/%m/%Y")
                    except ValueError:
                        pass

                # Map to CPV codes
                cpv_codes = self._map_to_cpv(title)

                results.append({
                    "notification_id": notif_id,
                    "title": title,
                    "country": country if country else ("European Union" if is_eu else ""),
                    "is_eu_notification": is_eu or country in ("European Union", "EU"),
                    "notification_date": notification_date.isoformat() if notification_date else None,
                    "cpv_mapping": cpv_codes,
                    "product_area": self._extract_product_area(title),
                    "source_url": f"{self.BASE_URL}/en/notification/{notif_id}",
                    "status": "notified",
                })

            except Exception as e:
                logger.debug(f"Failed to parse TBT link: {e}")

        logger.info(f"[OK] TBT: parsed {len(results)} notifications")
        return results

    def _parse_notification_detail(self, soup, notification_id: int) -> Dict[str, Any]:
        """Parse a TBT notification detail page."""
        result = {
            "notification_id": notification_id,
            "source_url": f"{self.BASE_URL}/en/notification/{notification_id}",
        }

        # Extract fields from detail page
        for element in soup.find_all(["dl", "div", "table"]):
            for label_el in element.find_all(["dt", "label", "strong", "th"]):
                label = label_el.get_text(strip=True).lower()
                value_el = label_el.find_next(["dd", "span", "p", "div", "td"])
                if not value_el:
                    continue
                value = value_el.get_text(strip=True)

                if "title" in label or "subject" in label:
                    result["title"] = value
                elif "member" in label or "country" in label or "notifying" in label:
                    result["country"] = value
                    result["is_eu_notification"] = value in ("European Union", "EU")
                elif "date" in label and "notification" in label:
                    try:
                        result["notification_date"] = datetime.strptime(value, "%d/%m/%Y").isoformat()
                    except ValueError:
                        result["notification_date"] = value
                elif "deadline" in label or "comment" in label and "date" in label:
                    try:
                        result["comment_deadline"] = datetime.strptime(value, "%d/%m/%Y").isoformat()
                    except ValueError:
                        pass
                elif "product" in label and "description" in label:
                    result["product_description"] = value
                elif "description" in label or "content" in label:
                    result["description"] = value
                elif "objective" in label:
                    result["objective"] = value
                elif "symbol" in label:
                    result["symbol"] = value
                elif "hs" in label or "harmonized" in label:
                    result["hs_codes"] = [c.strip() for c in value.split(",") if c.strip()]
                elif "ics" in label:
                    result["ics_codes"] = [c.strip() for c in value.split(",") if c.strip()]

        # Map to CPV
        text = " ".join([
            result.get("title", ""),
            result.get("description", ""),
            result.get("product_description", ""),
        ])
        result["cpv_mapping"] = self._map_to_cpv(text)
        result["product_area"] = self._extract_product_area(text)

        return result

    def _map_to_cpv(self, text: str) -> List[str]:
        """Map text to CPV code categories."""
        if not text:
            return []

        text_lower = text.lower()
        cpv_codes = set()

        for keyword, codes in TBT_PRODUCT_CPV_MAP.items():
            if keyword in text_lower:
                cpv_codes.update(codes)

        return list(cpv_codes)

    def _extract_product_area(self, text: str) -> str:
        """Extract primary product area from text."""
        if not text:
            return ""

        text_lower = text.lower()
        # Return first matching area
        area_priority = [
            ("medical device", "Medical Devices"),
            ("pharmaceutical", "Pharmaceuticals"),
            ("chemical", "Chemicals"),
            ("automotive", "Automotive"),
            ("vehicle", "Automotive"),
            ("emission", "Environment/Emissions"),
            ("ecodesign", "Energy Efficiency"),
            ("energy", "Energy"),
            ("food", "Food & Agriculture"),
            ("construction", "Construction"),
            ("telecom", "Telecommunications"),
            ("electronic", "Electronics"),
            ("textile", "Textiles"),
            ("machinery", "Machinery"),
            ("biotech", "Biotechnology"),
            ("cosmetic", "Cosmetics"),
            ("transport", "Transport"),
        ]

        for keyword, area in area_priority:
            if keyword in text_lower:
                return area

        return "General"

    async def get_eu_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get EU-originated TBT notifications."""
        return await self.get_latest_eu_notifications(limit=limit)

    async def get_notifications_affecting_sector(self, cpv_code: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Find TBT notifications affecting a CPV sector.
        Used by Tenderator to flag cross-border risks.

        Args:
            cpv_code: CPV code (first 2 digits used for matching)
            limit: Max results

        Returns:
            Relevant TBT notifications
        """
        all_notifs = await self.get_latest_eu_notifications(limit=50)
        cpv_category = cpv_code[:2]

        relevant = [
            n for n in all_notifs
            if cpv_category in (n.get("cpv_mapping") or [])
        ]

        logger.info(f"[OK] TBT: {len(relevant)} notifications affecting CPV {cpv_category}")
        return relevant[:limit]
