"""
Council of the EU Calendar Scraper.

Scrapes the Council meetings calendar from consilium.europa.eu.

Source: https://www.consilium.europa.eu/en/meetings/calendar/

Created: February 2026
"""

import logging
import re
from urllib.parse import urlparse
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup

from services.scrapers.base_scraper import BaseScraper, ScraperError
from knowledge_base.eu_calendar_institutions import COUNCIL_CONFIGURATIONS

logger = logging.getLogger(__name__)

BASE_URL = "https://www.consilium.europa.eu"
# The ministerial configurations and summits, one RSS feed each (the feed without
# ?cat answers 404). Coreper, committees and working parties are left out, as
# the HTML calendar path never carried them either.
RSS_CATEGORIES = ("agri", "compet", "ecofin", "envi", "epsco", "euco", "eurog",
                  "euros", "eycs", "fac", "gac", "is", "jha", "tte")
RSS_USER_AGENT = "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"
CALENDAR_URL = f"{BASE_URL}/en/meetings/calendar/"

# consilium.europa.eu encodes the configuration in the meeting URL path
# (/en/meetings/<slug>/<yyyy>/<mm>/<dd>[-dd]/). Map the slug to the Council
# configuration code used elsewhere in Brubru.
_SLUG_TO_CONFIG = {
    "gac": "GAC", "fac": "FAC", "ecofin": "ECOFIN", "jha": "JHA",
    "epsco": "EPSCO", "compet": "COMPET", "tte": "TTE", "agrifish": "AGRIFISH",
    "env": "ENVI", "envi": "ENVI", "eycs": "EYCS", "educ": "EDUC",
    "eurogroup": "EUROGROUP",
}


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
        # consilium.europa.eu sits behind a WAF that 403s aiohttp requests, so
        # scrape_meetings() renders the page with the headless-Chromium
        # WafBrowserFetcher rather than the BaseScraper aiohttp path.
        super().__init__(
            base_url=BASE_URL,
            name="Council Calendar",
            rate_limit_delay=2.0,
        )

    # BaseScraper is an ABC with three abstract methods (search / get_document /
    # get_latest_updates) aimed at document databases. This scraper only lists
    # meetings via scrape_meetings(), but the abstract methods still need
    # concrete implementations or the class cannot be instantiated at all (the
    # bug that silently killed the live Council calendar sync). These are sync
    # stubs — scrape_meetings uses the WAF browser fetcher (sync Chromium), so
    # the whole scraper is deliberately synchronous.
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Not applicable: the Council calendar scraper only lists meetings."""
        return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Not applicable: the Council calendar scraper only lists meetings."""
        raise NotImplementedError("CouncilCalendarScraper does not fetch documents")

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Not applicable here; use scrape_meetings() for the calendar."""
        return []

    def scrape_meetings(self, months_ahead: int = 6) -> List[Dict[str, Any]]:
        """
        Scrape upcoming Council + European Council meetings from the calendar.

        Renders the WAF-protected consilium calendar with headless Chromium and
        parses the ``gsc-excerpt-list`` structure. SYNCHRONOUS: the WAF fetcher
        uses sync Playwright and must not run inside an asyncio loop.

        Returns a list of event dicts ready for EUCalendarSyncService._upsert_event.
        """
        from services.scrapers.waf_browser_fetcher import fetch_one

        events: List[Dict[str, Any]] = []
        seen: set[str] = set()

        # RSS first (24 Sep 2026). consilium blocks the Railway address for its
        # HTML pages, so council_calendar failed every run in production while
        # the same code worked from a laptop, and the fix of 23 Sep needed a
        # paid Scrape.do call Railway had no key for. The Council publishes a
        # meetings feed per configuration (/en/rss/meetings.ashx?cat=...), plain
        # XML that its press-release feed already proves reachable from Railway.
        # Same event dicts, same external_ids as the HTML path.
        # The feeds are not complete on their own: each holds its 50 items
        # reaching years back, and the informal health ministers' meeting of
        # 30 Sep 2026 was on the HTML calendar but in no feed. So RSS is merged
        # with the free HTML render whenever that gets through (it does from a
        # laptop, not from Railway); the paid fallback runs only if both fail.
        rss = self._fetch_rss_meetings(months_ahead)
        for event in rss:
            seen.add(event["external_id"])
            events.append(event)

        html = ""
        try:
            result = fetch_one(
                CALENDAR_URL, expand_accordions=False, strip_chrome=False
            )
            if getattr(result, "ok", False):
                html = getattr(result, "html", "") or ""
            else:
                logger.warning(
                    f"[WARN] Council calendar browser fetch blocked/empty "
                    f"(status={getattr(result, 'nav_status', None)})"
                )
        except Exception as e:
            logger.warning(f"[WARN] Council calendar render failed: {e}")

        # Scrape.do fallback (23 Sep 2026). consilium blocks the Railway address
        # by IP reputation, so in production this fetch returned nothing from 24
        # July and every Council meeting after that was missing from My EU
        # Calendar (the Competitiveness Council of 24 Sep among them) while the
        # same code worked from a laptop. A plain Scrape.do call (1 credit) returns
        # the full list. Used only when the free fetch produced no meeting list.
        if "gsc-excerpt-list__item" not in html:
            if events:
                self.last_fetch_tier = "rss"
                logger.info(f"[OK] Council calendar from RSS only: {len(events)} meetings")
                return events
            try:
                html = self._fetch_scrapedo(CALENDAR_URL)
                self.last_fetch_tier = "scrapedo"
            except Exception as e:
                logger.error(f"[ERROR] Council calendar Scrape.do fallback failed: {e}")
                return events
        else:
            self.last_fetch_tier = "rss+browser" if events else "browser"

        soup = BeautifulSoup(html, "html.parser")
        groups = soup.select(".gsc-excerpt-list__item")
        logger.info(f"[INFO] Found {len(groups)} Council calendar date groups")

        cutoff = date.today() + timedelta(days=int(months_ahead * 31))

        for group in groups:
            date_el = group.select_one(".gsc-excerpt-list__item-date")
            group_date = _parse_long_date(date_el.get_text(strip=True)) if date_el else None
            for item in group.select(".gsc-excerpt-item"):
                try:
                    event = self._parse_excerpt(item, group_date)
                except Exception as e:
                    logger.warning(f"[WARN] Failed to parse Council meeting item: {e}")
                    continue
                if not event:
                    continue
                if event["external_id"] in seen:
                    continue
                if event["start_date"] and event["start_date"] > cutoff:
                    continue
                seen.add(event["external_id"])
                events.append(event)

        logger.info(f"[OK] Scraped {len(events)} Council meetings")
        return events

    def _fetch_rss_meetings(self, months_ahead: int = 6) -> List[Dict[str, Any]]:
        """Meetings from the Council's per-configuration RSS feeds.

        Returns [] if no feed answered, so the caller falls back to the HTML
        path. A feed that fails is logged by name, never silently dropped.
        """
        import xml.etree.ElementTree as ET

        import requests

        today = date.today()
        window_start = today - timedelta(days=14)
        cutoff = today + timedelta(days=int(months_ahead * 31))
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        answered = 0
        for cat in RSS_CATEGORIES:
            url = f"{BASE_URL}/en/rss/meetings.ashx?cat={cat}"
            try:
                r = requests.get(url, timeout=20, headers={"User-Agent": RSS_USER_AGENT})
                if r.status_code != 200 or b"<rss" not in r.content[:400]:
                    logger.warning(f"[WARN] Council RSS {cat}: HTTP {r.status_code}, not a feed")
                    continue
                root = ET.fromstring(r.content)
            except Exception as e:  # noqa: BLE001 -- one feed must not stop the rest
                logger.warning(f"[WARN] Council RSS {cat} failed: {type(e).__name__}: {e}")
                continue
            answered += 1
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                event = _event_from(title, link, "euco" if cat in ("euco", "euros") else "")
                if not event or event["external_id"] in seen:
                    continue
                if not (window_start <= event["start_date"] <= cutoff):
                    continue
                seen.add(event["external_id"])
                out.append(event)
        logger.info(f"[INFO] Council RSS: {answered}/{len(RSS_CATEGORIES)} feeds answered, {len(out)} meetings in window")
        return out if answered else []

    def _parse_excerpt(self, item, group_date: Optional[date]) -> Optional[Dict[str, Any]]:
        """Parse one ``gsc-excerpt-item`` (a single meeting) into an event dict."""
        title_el = item.select_one(".gsc-excerpt-item__title")
        if not title_el:
            return None
        link_el = item.select_one(".gsc-excerpt-item__link")
        href = link_el.get("href", "") if link_el else ""
        theme = (item.get("data-theme") or "").lower()  # 'ceu' = Council, 'euco' = European Council
        return _event_from(title_el.get_text(strip=True), href, theme, group_date)


def _event_from(title: str, href: str, theme: str = "",
                group_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """One meeting as an event dict, from its title and meeting URL.

    Shared by the HTML calendar and the RSS feeds so both produce the SAME
    external_id for the same meeting: an absolute RSS link is reduced to its
    path first, or every meeting would be stored twice.
    """
    title = (title or "").strip()
    if not title or len(title) < 3:
        return None
    if href.startswith("http"):
        href = urlparse(href).path
    source_url = f"{BASE_URL}{href}" if href.startswith("/") else (href or CALENDAR_URL)

    # The URL carries the true date range + configuration slug:
    #   /en/meetings/<slug>/<yyyy>/<mm>/<dd>[-<dd>]/
    start_date, end_date, slug = group_date, None, None
    m = re.search(r"/meetings/([a-z0-9\-]+)/(\d{4})/(\d{2})/(\d{2})(?:-(\d{2}))?", href)
    if m:
        slug = m.group(1)
        year, month, day1 = int(m.group(2)), int(m.group(3)), int(m.group(4))
        try:
            start_date = date(year, month, day1)
            if m.group(5):
                end_date = date(year, month, int(m.group(5)))
                # "30-01" spans a month boundary: the end is in the NEXT
                # month. Read literally it put the end before the start
                # (EPSCO 30 Sep - 1 Oct 2026 ended on 1 September).
                if end_date < start_date:
                    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
                    end_date = date(ny, nm, int(m.group(5)))
        except ValueError:
            pass
    if not start_date:
        return None

    # Institution / event type / configuration
    is_euco = theme == "euco" or _detect_european_council(title)
    config = _SLUG_TO_CONFIG.get(slug) if slug else None
    if not config:
        config = _detect_council_configuration(title)

    if is_euco:
        institution, event_type = "EUROPEAN_COUNCIL", "european_council_summit"
    elif config == "EUROGROUP" or "eurogroup" in title.lower():
        institution, event_type, config = "COUNCIL", "eurogroup", "EUROGROUP"
    elif "informal" in title.lower():
        institution, event_type = "COUNCIL", "informal_meeting"
    else:
        institution, event_type = "COUNCIL", "council_meeting"

    # Stable external_id from the meeting URL so the same multi-day meeting
    # (listed under each of its days) collapses to one event.
    key = href.strip("/").replace("/", "_")
    if not key:
        key = f"{start_date.isoformat()}_{re.sub(r'[^a-z0-9]+', '_', title.lower())[:40]}"
    external_id = f"council_{key}"

    return {
        "institution": institution,
        "event_type": event_type,
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "all_day": True,
        "status": "scheduled",
        "council_configuration": config,
        "source": "council_calendar",
        "external_id": external_id,
        "source_url": source_url,
    }


def _parse_long_date(text: str) -> Optional[date]:
    """Parse consilium's ``24 July 2026`` heading into a date."""
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None
