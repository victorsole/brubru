"""
TRIS - Technical Regulation Information System Scraper

Scrapes notifications of draft national technical regulations under
Directive (EU) 2015/1535 (the transparency procedure, ex 98/34/EC).

When an EU member state drafts a new technical regulation, it must
notify the Commission via TRIS. Other member states can comment,
and the Commission can issue detailed opinions or block adoption.

Source: https://technical-regulation-information-system.ec.europa.eu

Integration with Tenderator:
- Alerts users when new national regulations may affect their tender sectors
- Maps regulations to CPV codes for sector-based notifications
- Tracks standstill periods that may delay procurement timelines
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from services.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Country code mapping for TRIS
TRIS_COUNTRY_MAP = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czech Republic": "CZ", "Czechia": "CZ",
    "Denmark": "DK", "Estonia": "EE", "Finland": "FI", "France": "FR",
    "Germany": "DE", "Greece": "GR", "Hungary": "HU", "Ireland": "IE",
    "Italy": "IT", "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU",
    "Malta": "MT", "Netherlands": "NL", "Poland": "PL", "Portugal": "PT",
    "Romania": "RO", "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES",
    "Sweden": "SE", "Norway": "NO", "Iceland": "IS", "Liechtenstein": "LI",
    "Switzerland": "CH", "Turkey": "TR",
}

# Sector-to-CPV mapping for technical regulations
SECTOR_CPV_MAP = {
    "construction": ["44", "45"],
    "building": ["44", "45"],
    "food": ["15"],
    "transport": ["34"],
    "vehicle": ["34"],
    "railway": ["34"],
    "automotive": ["34"],
    "electrical": ["31"],
    "electronic": ["32"],
    "telecom": ["32"],
    "medical": ["33"],
    "pharmaceutical": ["33"],
    "chemical": ["24"],
    "textile": ["19"],
    "machinery": ["42", "43"],
    "energy": ["09", "31"],
    "gas": ["09", "42"],
    "fire": ["35"],
    "safety": ["35"],
    "environmental": ["90"],
    "waste": ["90"],
    "water": ["41", "65"],
    "agricultural": ["03", "16"],
    "mining": ["43"],
    "packaging": ["44"],
    "cosmetic": ["33"],
    "tobacco": ["15"],
    "alcohol": ["15"],
    "weapon": ["35"],
    "explosive": ["35"],
    "lift": ["42", "45"],
    "elevator": ["42", "45"],
    "pressure": ["42"],
    "measuring": ["38"],
    "weighing": ["38"],
    "toy": ["37"],
    "pyrotechnic": ["35"],
    "marine": ["34"],
    "aeronautic": ["34"],
}


class TRISScraper(BaseScraper):
    """
    Scraper for TRIS technical regulation notifications.

    Scrapes the TRIS website for new and recent notifications.
    Each notification represents a draft national technical regulation
    that must undergo a 3-month EU standstill period.
    """

    BASE_URL = "https://technical-regulation-information-system.ec.europa.eu"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            name="TRIS",
            rate_limit_delay=3.0,  # Conservative - EC website
            cache_ttl=3600,  # 1h cache
        )

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search technical regulation notifications."""
        return await self.search_notifications(query=query, **kwargs)

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get a specific notification by number."""
        return await self.get_notification(int(document_id))

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get notifications from the last 7 days."""
        return await self.get_recent_notifications(days=7)

    async def get_recent_notifications(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetch recent notifications by enumerating recent notification IDs.

        TRIS is a SPA - the list page doesn't contain data in the initial HTML.
        Instead, we enumerate recent notification IDs (descending from latest known)
        and fetch each detail page individually.

        Args:
            days: Approximate look-back period (controls how many IDs to try)

        Returns:
            List of notification records
        """
        # Estimate how many notifications to try based on days
        # TRIS gets ~3-5 notifications per day across all EU/EEA countries
        max_attempts = min(days * 5, 50)

        # Start from a known recent ID and work backwards
        # As of March 2026, notification ~27736 is current
        start_id = 27740  # Slightly above latest known

        results = []
        consecutive_failures = 0

        for offset in range(max_attempts):
            notif_id = start_id - offset

            if consecutive_failures >= 10:
                logger.info(f"TRIS: Stopping enumeration after {consecutive_failures} consecutive failures")
                break

            try:
                detail = await self.get_notification(notif_id)
                if detail and detail.get("reference"):
                    results.append(detail)
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception:
                consecutive_failures += 1

        logger.info(f"[OK] TRIS: fetched {len(results)} notifications via enumeration")
        return results

    async def search_notifications(
        self,
        query: Optional[str] = None,
        year: Optional[int] = None,
        country: Optional[str] = None,
        number: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search TRIS notifications by year, country, or number.

        Args:
            query: Free-text search (searches title)
            year: Notification year (2001-2026)
            country: Country code (ISO alpha-2) or full name
            number: Specific notification number
            limit: Max results

        Returns:
            List of notification records
        """
        params = {}
        if year:
            params["year"] = str(year)
        if country:
            # TRIS uses full country names
            if len(country) == 2:
                for name, code in TRIS_COUNTRY_MAP.items():
                    if code == country.upper():
                        params["country"] = name
                        break
            else:
                params["country"] = country

        url = f"{self.BASE_URL}/en/search"
        try:
            content = await self._fetch(url, params=params)
            soup = self._parse_html(content)
            results = self._parse_notification_list(soup)

            # Filter by query if provided
            if query:
                query_lower = query.lower()
                results = [r for r in results if query_lower in r.get("title", "").lower()]

            return results[:limit]
        except Exception as e:
            logger.error(f"Failed to search TRIS notifications: {e}")
            return []

    async def get_notification(self, notification_number: int) -> Dict[str, Any]:
        """
        Get detailed information for a specific notification.

        Args:
            notification_number: TRIS notification number (e.g., 27736)

        Returns:
            Detailed notification record
        """
        url = f"{self.BASE_URL}/en/notification/{notification_number}"
        try:
            content = await self._fetch(url)
            soup = self._parse_html(content)
            return self._parse_notification_detail(soup, notification_number)
        except Exception as e:
            logger.error(f"Failed to fetch TRIS notification {notification_number}: {e}")
            return {}

    def _parse_notification_list(self, soup) -> List[Dict[str, Any]]:
        """Parse a list of notifications from TRIS HTML."""
        results = []

        # TRIS lists notifications in tables or card layouts
        rows = soup.select("table tbody tr, .notification-item, .tris-notification")

        for row in rows:
            try:
                notification = self._extract_notification_from_row(row)
                if notification:
                    results.append(notification)
            except Exception as e:
                logger.debug(f"Failed to parse TRIS row: {e}")
                continue

        # Also try to find notifications in links
        if not results:
            links = soup.find_all("a", href=re.compile(r"/notification/\d+"))
            for link in links:
                try:
                    href = link.get("href", "")
                    number_match = re.search(r"/notification/(\d+)", href)
                    if number_match:
                        number = int(number_match.group(1))
                        # Get surrounding text for title
                        parent = link.find_parent(["tr", "div", "li", "article"])
                        title = ""
                        if parent:
                            title = parent.get_text(separator=" ", strip=True)
                        else:
                            title = link.get_text(strip=True)

                        # Try to extract country and date
                        country = ""
                        date_str = ""
                        if parent:
                            text = parent.get_text(separator="|", strip=True)
                            parts = text.split("|")
                            for part in parts:
                                part = part.strip()
                                # Check if it's a country
                                if part in TRIS_COUNTRY_MAP:
                                    country = part
                                # Check if it's a date
                                date_match = re.match(r"\d{2}/\d{2}/\d{4}", part)
                                if date_match:
                                    date_str = date_match.group()

                        country_code = TRIS_COUNTRY_MAP.get(country, "")
                        notification_date = None
                        if date_str:
                            try:
                                notification_date = datetime.strptime(date_str, "%d/%m/%Y")
                            except ValueError:
                                pass

                        # Map to CPV
                        cpv_codes = self._map_title_to_cpv(title)

                        results.append({
                            "notification_number": number,
                            "reference": f"{datetime.now().year}/{number}/{country_code}" if country_code else str(number),
                            "title": title,
                            "country": country_code,
                            "country_name": country,
                            "notification_date": notification_date.isoformat() if notification_date else None,
                            "standstill_end_date": (notification_date + timedelta(days=90)).isoformat() if notification_date else None,
                            "status": "notified",
                            "cpv_mapping": cpv_codes,
                            "source_url": f"{self.BASE_URL}/en/notification/{number}",
                        })
                except Exception as e:
                    logger.debug(f"Failed to parse TRIS link: {e}")

        logger.info(f"[OK] TRIS: parsed {len(results)} notifications")
        return results

    def _extract_notification_from_row(self, row) -> Optional[Dict[str, Any]]:
        """Extract a notification from a table row or card element."""
        cols = row.find_all("td") if row.name == "tr" else []

        if len(cols) >= 3:
            number_text = cols[0].get_text(strip=True)
            number_match = re.search(r"(\d+)", number_text)
            if not number_match:
                return None

            number = int(number_match.group(1))
            country_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            title = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            date_text = cols[3].get_text(strip=True) if len(cols) > 3 else ""

            country_code = TRIS_COUNTRY_MAP.get(country_text, country_text[:2] if len(country_text) >= 2 else "")

            notification_date = None
            if date_text:
                try:
                    notification_date = datetime.strptime(date_text, "%d/%m/%Y")
                except ValueError:
                    pass

            cpv_codes = self._map_title_to_cpv(title)

            return {
                "notification_number": number,
                "reference": f"{datetime.now().year}/{number}/{country_code}",
                "title": title,
                "country": country_code,
                "country_name": country_text,
                "notification_date": notification_date.isoformat() if notification_date else None,
                "standstill_end_date": (notification_date + timedelta(days=90)).isoformat() if notification_date else None,
                "status": "notified",
                "cpv_mapping": cpv_codes,
                "source_url": f"{self.BASE_URL}/en/notification/{number}",
            }

        return None

    def _parse_notification_detail(self, soup, notification_number: int) -> Dict[str, Any]:
        """
        Parse a notification detail page.

        TRIS uses the Europa Component Library (ECL) grid layout:
        labels in ecl-col-3 divs, values in sibling ecl-col-9 divs.
        """
        result = {
            "notification_number": notification_number,
            "source_url": f"{self.BASE_URL}/en/notification/{notification_number}",
        }

        # ECL grid pattern: label in ecl-col-3, value in next sibling ecl-col
        for label_div in soup.find_all("div", class_=re.compile(r"ecl-col-3")):
            label = label_div.get_text(strip=True).rstrip(":").lower()
            value_div = label_div.find_next_sibling("div", class_=re.compile(r"ecl-col"))
            if not value_div:
                continue
            value = value_div.get_text(strip=True)
            if not value:
                continue

            if "notification number" in label:
                result["reference"] = value
                # Parse "2026/0111/DK (Denmark)" -> country code + name
                ref_match = re.match(r"(\d{4}/\d+)/(\w{2})\s*\(([^)]+)\)", value)
                if ref_match:
                    result["reference"] = f"{ref_match.group(1)}/{ref_match.group(2)}"
                    result["country"] = ref_match.group(2)
                    result["country_name"] = ref_match.group(3)
            elif "date received" in label:
                try:
                    result["notification_date"] = datetime.strptime(value, "%d/%m/%Y").isoformat()
                except ValueError:
                    result["notification_date"] = value
            elif "standstill" in label:
                try:
                    result["standstill_end_date"] = datetime.strptime(value, "%d/%m/%Y").isoformat()
                except ValueError:
                    result["standstill_end_date"] = value
            elif "title" in label or "subject" in label:
                result["title"] = value
            elif "sector" in label or "product" in label:
                result["product_sector"] = value
            elif "description" in label or "content" in label:
                result["description"] = value
            elif "legislation" in label or "directive" in label:
                result.setdefault("related_eu_legislation", []).append(value)
            elif "opinion" in label:
                result["has_detailed_opinion"] = "yes" in value.lower()
            elif "comment" in label:
                result["has_comments"] = "yes" in value.lower()

        # Fallback: extract title from page heading if not found in grid
        if "title" not in result:
            # Try h1/h2 headings
            for heading in soup.find_all(["h1", "h2"]):
                text = heading.get_text(strip=True)
                if text and "notification" not in text.lower() and "tris" not in text.lower() and len(text) > 10:
                    result["title"] = text
                    break

        # If still no title, use the reference as a fallback
        if "title" not in result and "reference" in result:
            result["title"] = f"TRIS Notification {result['reference']}"

        # Determine status based on standstill date
        if result.get("standstill_end_date"):
            try:
                standstill_end = datetime.fromisoformat(result["standstill_end_date"])
                if standstill_end > datetime.utcnow():
                    result["status"] = "standstill"
                else:
                    result["status"] = "adopted"
            except (ValueError, TypeError):
                result["status"] = "notified"
        else:
            result["status"] = "notified"

        # Map to CPV
        text_for_cpv = " ".join([
            result.get("title", ""),
            result.get("description", ""),
            result.get("product_sector", ""),
        ])
        result["cpv_mapping"] = self._map_title_to_cpv(text_for_cpv)

        return result

    def _map_title_to_cpv(self, text: str) -> List[str]:
        """Map notification title/description to CPV codes."""
        if not text:
            return []

        text_lower = text.lower()
        cpv_codes = set()

        for keyword, codes in SECTOR_CPV_MAP.items():
            if keyword in text_lower:
                cpv_codes.update(codes)

        return list(cpv_codes)

    async def get_notifications_for_country(self, country_code: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all notifications for a specific country."""
        return await self.search_notifications(country=country_code, year=year or datetime.now().year)

    async def get_notifications_affecting_sector(self, cpv_code: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find recent technical regulation notifications that affect a CPV sector.
        Used by Tenderator to alert users about regulatory changes.

        Args:
            cpv_code: CPV code (first 2 digits used for matching)
            days: Look back period in days

        Returns:
            List of relevant notifications
        """
        recent = await self.get_recent_notifications(days=days)
        cpv_category = cpv_code[:2]

        relevant = [
            n for n in recent
            if cpv_category in (n.get("cpv_mapping") or [])
        ]

        logger.info(f"[OK] TRIS: {len(relevant)} notifications affecting CPV {cpv_category} "
                     f"out of {len(recent)} recent notifications")
        return relevant
