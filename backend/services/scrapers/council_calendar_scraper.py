"""
Council of the EU Calendar Scraper.

Scrapes the Council meetings calendar from consilium.europa.eu.

Source: https://www.consilium.europa.eu/en/meetings/calendar/

Created: February 2026
"""

import logging
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup

from services.scrapers.base_scraper import BaseScraper, ScraperError
from knowledge_base.eu_calendar_institutions import COUNCIL_CONFIGURATIONS

logger = logging.getLogger(__name__)

BASE_URL = "https://www.consilium.europa.eu"
CALENDAR_URL = f"{BASE_URL}/en/meetings/calendar/"


def _detect_council_configuration(title: str) -> Optional[str]:
    """Detect Council configuration from meeting title."""
    title_upper = title.upper()

    # Direct matches
    for config_code, config_name in COUNCIL_CONFIGURATIONS.items():
        if config_code in title_upper:
            return config_code
        # Check full name
        name_words = config_name.upper().split()
        if len(name_words) >= 2 and name_words[0] in title_upper:
            return config_code

    # Pattern-based detection
    patterns = {
        r"FOREIGN\s+AFFAIRS": "FAC",
        r"GENERAL\s+AFFAIRS": "GAC",
        r"ECONOMIC\s+AND\s+FINANCIAL": "ECOFIN",
        r"JUSTICE\s+AND\s+HOME": "JHA",
        r"EMPLOYMENT": "EPSCO",
        r"COMPETITIVENESS": "COMPET",
        r"TRANSPORT": "TTE",
        r"TELECOMM": "TTE",
        r"ENERGY": "TTE",
        r"AGRI": "AGRIFISH",
        r"FISH": "AGRIFISH",
        r"ENVIRONMENT": "ENVI",
        r"EDUCATION": "EDUC",
        r"EUROGROUP": "EUROGROUP",
        r"COREPER\s*(I[^I]|1[^0-9])": "COREPER_I",
        r"COREPER\s*(II|2)": "COREPER_II",
    }

    for pattern, config in patterns.items():
        if re.search(pattern, title_upper):
            return config

    return None


def _detect_european_council(title: str) -> bool:
    """Check if meeting is a European Council summit."""
    title_upper = title.upper()
    return "EUROPEAN COUNCIL" in title_upper and "COUNCIL OF" not in title_upper


class CouncilCalendarScraper(BaseScraper):
    """Scrapes Council of the EU meetings calendar."""

    def __init__(self):
        super().__init__(
            base_url=BASE_URL,
            rate_limit=2.0,
        )

    async def scrape_meetings(
        self, months_ahead: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Scrape Council meetings from the calendar page.

        Returns list of event dicts ready for the sync service.
        """
        events = []

        try:
            html = await self.fetch(CALENDAR_URL)
            soup = BeautifulSoup(html, "html.parser")

            # The Council calendar uses various selectors
            meeting_items = soup.select(
                ".council-filters__list-item, "
                ".meeting-item, "
                "[class*='meeting'], "
                ".calendar-list__item"
            )

            if not meeting_items:
                # Fallback: look for any list items with dates
                meeting_items = soup.select("li[data-date], .event-item, article")

            logger.info(f"[INFO] Found {len(meeting_items)} potential Council meeting entries")

            for item in meeting_items:
                try:
                    event = self._parse_meeting_item(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"[WARN] Failed to parse Council meeting item: {e}")
                    continue

        except ScraperError as e:
            logger.error(f"[ERROR] Council calendar scrape failed: {e}")
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error scraping Council calendar: {e}")

        logger.info(f"[OK] Scraped {len(events)} Council meetings")
        return events

    def _parse_meeting_item(self, item) -> Optional[Dict[str, Any]]:
        """Parse a single meeting item from the calendar HTML."""
        # Extract title
        title_el = item.select_one(
            "h3, h4, .meeting-item__title, "
            "[class*='title'], a[class*='link']"
        )
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # Extract date
        date_el = item.select_one(
            "time, [datetime], .meeting-item__date, "
            "[class*='date']"
        )
        meeting_date = None
        if date_el:
            datetime_attr = date_el.get("datetime", "")
            if datetime_attr:
                try:
                    meeting_date = datetime.fromisoformat(
                        datetime_attr.replace("Z", "+00:00")
                    ).date()
                except ValueError:
                    pass
            if not meeting_date:
                date_text = date_el.get_text(strip=True)
                for fmt in ("%d %B %Y", "%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        meeting_date = datetime.strptime(date_text, fmt).date()
                        break
                    except ValueError:
                        continue

        if not meeting_date:
            return None

        # Extract link
        link_el = item.select_one("a[href]")
        source_url = None
        if link_el:
            href = link_el.get("href", "")
            if href.startswith("/"):
                source_url = f"{BASE_URL}{href}"
            elif href.startswith("http"):
                source_url = href

        # Determine institution and event type
        is_european_council = _detect_european_council(title)
        config = _detect_council_configuration(title)

        if is_european_council:
            institution = "EUROPEAN_COUNCIL"
            event_type = "european_council_summit"
        elif config == "EUROGROUP":
            institution = "COUNCIL"
            event_type = "eurogroup"
        else:
            institution = "COUNCIL"
            event_type = "council_meeting"

        # Build external_id
        date_str = meeting_date.isoformat()
        clean_title = re.sub(r"[^a-z0-9]", "_", title.lower())[:40]
        external_id = f"council_{date_str}_{clean_title}"

        return {
            "institution": institution,
            "event_type": event_type,
            "title": title,
            "start_date": meeting_date,
            "all_day": True,
            "status": "confirmed",
            "council_configuration": config,
            "source": "council_calendar",
            "external_id": external_id,
            "source_url": source_url or CALENDAR_URL,
        }
