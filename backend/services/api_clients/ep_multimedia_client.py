"""
EP Multimedia Centre Client

Discovers and fetches committee meeting recordings from the European
Parliament's Multimedia Centre (multimedia.europarl.europa.eu).

The Multimedia Centre streams all committee meetings live and keeps
recorded archives. This client scrapes the listing pages and individual
meeting pages to extract video URLs for audio download and transcription.

URL patterns:
  Listings:  https://multimedia.europarl.europa.eu/en/webstreaming
  Committee: https://multimedia.europarl.europa.eu/en/webstreaming?committee={CODE}
  Meeting:   https://multimedia.europarl.europa.eu/en/webstreaming/{EVENT_ID}

Created: April 2026
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MULTIMEDIA_BASE = "https://multimedia.europarl.europa.eu"
WEBSTREAMING_URL = f"{MULTIMEDIA_BASE}/en/webstreaming"
USER_AGENT = "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"
CACHE_TTL = 3600  # 1 hour


@dataclass
class AgendaItem:
    number: int
    title: str
    procedure_refs: List[str] = field(default_factory=list)
    start_time: Optional[str] = None  # HH:MM


@dataclass
class CommitteeMeeting:
    event_id: str
    committee_code: str
    title: str
    meeting_date: date
    start_time: Optional[str] = None      # "09:00"
    end_time: Optional[str] = None        # "12:30"
    multimedia_url: str = ""
    video_url: Optional[str] = None       # Direct mp4/m3u8 URL
    agenda_items: List[AgendaItem] = field(default_factory=list)
    duration_minutes: Optional[int] = None
    is_live: bool = False


class EPMultimediaClient:
    """Client to discover and fetch EP committee meeting recordings."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout
        self._cache: Dict[str, tuple] = {}  # key -> (timestamp, value)

    def _cache_get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, val = entry
        if time.time() - ts > CACHE_TTL:
            self._cache.pop(key, None)
            return None
        return val

    def _cache_put(self, key: str, val: Any) -> None:
        self._cache[key] = (time.time(), val)

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch a page and return HTML text, or None on error."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPError as exc:
            logger.warning("[EP-multimedia] Failed to fetch %s: %s", url, exc)
            return None

    async def discover_meetings(
        self,
        committee_code: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        max_pages: int = 2,
    ) -> List[CommitteeMeeting]:
        """Discover committee meetings from the webstreaming listing page.

        Returns recorded (not live) meetings, newest first.
        """
        cache_key = f"discover:{committee_code or 'all'}:{date_from}:{date_to}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        meetings: List[CommitteeMeeting] = []

        for page in range(max_pages):
            url = f"{WEBSTREAMING_URL}?tab=recorded"
            if committee_code:
                url += f"&committee={committee_code.upper()}"
            if page > 0:
                url += f"&page={page}"

            html = await self._fetch_html(url)
            if not html:
                break

            page_meetings = self._parse_listing_page(html)
            if not page_meetings:
                break

            meetings.extend(page_meetings)
            logger.info("[EP-multimedia] Page %d: %d meetings", page, len(page_meetings))

        # Filter by date range
        if date_from:
            meetings = [m for m in meetings if m.meeting_date >= date_from]
        if date_to:
            meetings = [m for m in meetings if m.meeting_date <= date_to]

        self._cache_put(cache_key, meetings)
        logger.info("[EP-multimedia] Discovered %d meetings for %s", len(meetings), committee_code or "all")
        return meetings

    def _parse_listing_page(self, html: str) -> List[CommitteeMeeting]:
        """Parse the webstreaming listing page into CommitteeMeeting objects."""
        soup = BeautifulSoup(html, "lxml")
        meetings: List[CommitteeMeeting] = []

        # The listing page shows meeting cards with committee code, date, times
        # Structure varies; we look for common patterns in the EP multimedia HTML
        for card in soup.select("[class*='event'], [class*='meeting'], [class*='card']"):
            meeting = self._parse_meeting_card(card)
            if meeting:
                meetings.append(meeting)

        # Fallback: parse from text content if structured selectors fail
        if not meetings:
            meetings = self._parse_listing_fallback(soup)

        return meetings

    def _parse_meeting_card(self, card) -> Optional[CommitteeMeeting]:
        """Extract meeting data from a single card element."""
        try:
            # Extract committee code from badge or text
            committee_code = None
            for el in card.select("[class*='badge'], [class*='committee'], strong, span"):
                text = el.get_text(strip=True).upper()
                if len(text) <= 6 and text.isalpha():
                    committee_code = text
                    break

            if not committee_code:
                return None

            # Extract date
            meeting_date = None
            date_text = card.get_text()
            date_match = re.search(r"(\d{2})-(\d{2})-(\d{4})", date_text)
            if date_match:
                d, m, y = date_match.groups()
                meeting_date = date(int(y), int(m), int(d))

            if not meeting_date:
                return None

            # Extract times
            time_match = re.search(r"(\d{2}:\d{2})\s*[-/]\s*(\d{2}:\d{2})", date_text)
            start_time = time_match.group(1) if time_match else None
            end_time = time_match.group(2) if time_match else None

            # Extract link (event ID)
            link = card.find("a", href=True)
            event_id = ""
            multimedia_url = ""
            if link:
                href = link["href"]
                multimedia_url = href if href.startswith("http") else f"{MULTIMEDIA_BASE}{href}"
                # Event ID is typically the last path segment
                event_id = href.rstrip("/").split("/")[-1]

            # Title
            title_el = card.find(["h3", "h4", "h5", "a"])
            title = title_el.get_text(strip=True) if title_el else f"Committee Meeting {committee_code}"

            # Duration
            duration = None
            if start_time and end_time:
                try:
                    s = datetime.strptime(start_time, "%H:%M")
                    e = datetime.strptime(end_time, "%H:%M")
                    duration = int((e - s).total_seconds() / 60)
                except ValueError:
                    pass

            return CommitteeMeeting(
                event_id=event_id,
                committee_code=committee_code,
                title=title,
                meeting_date=meeting_date,
                start_time=start_time,
                end_time=end_time,
                multimedia_url=multimedia_url,
                duration_minutes=duration,
            )
        except Exception as exc:
            logger.debug("[EP-multimedia] Failed to parse card: %s", exc)
            return None

    def _parse_listing_fallback(self, soup: BeautifulSoup) -> List[CommitteeMeeting]:
        """Fallback parser using text patterns when structured selectors fail."""
        meetings: List[CommitteeMeeting] = []
        text = soup.get_text()

        # Pattern: "16-04-2026 09:00 - 12:30ENVI" or "16-04-2026 09:00 - 11:30FISC"
        pattern = re.compile(
            r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})([A-Z]{3,6})"
        )
        for match in pattern.finditer(text):
            d, m, y, start, end, code = match.groups()
            try:
                meeting_date = date(int(y), int(m), int(d))
            except ValueError:
                continue

            meetings.append(CommitteeMeeting(
                event_id=f"{code.lower()}-{y}{m}{d}",
                committee_code=code,
                title=f"Committee Meeting {code}",
                meeting_date=meeting_date,
                start_time=start,
                end_time=end,
                multimedia_url=f"{WEBSTREAMING_URL}?committee={code}",
            ))

        return meetings

    async def get_meeting_details(self, multimedia_url: str) -> Optional[Dict[str, Any]]:
        """Fetch a meeting detail page and extract video URL and agenda."""
        cache_key = f"detail:{multimedia_url}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        html = await self._fetch_html(multimedia_url)
        if not html:
            return None

        details = self._parse_meeting_detail(html, multimedia_url)
        if details:
            self._cache_put(cache_key, details)
        return details

    def _parse_meeting_detail(self, html: str, source_url: str) -> Optional[Dict[str, Any]]:
        """Extract video URL and agenda from a meeting detail page."""
        soup = BeautifulSoup(html, "lxml")
        result: Dict[str, Any] = {"source_url": source_url, "video_url": None, "agenda_items": []}

        # Video URL: look in <video>, <source>, data attributes, or script tags
        video_el = soup.find("video")
        if video_el:
            source_el = video_el.find("source")
            if source_el and source_el.get("src"):
                result["video_url"] = source_el["src"]
            elif video_el.get("src"):
                result["video_url"] = video_el["src"]

        # Fallback: search for .mp4 or .m3u8 in script tags or data attributes
        if not result["video_url"]:
            for script in soup.find_all("script"):
                text = script.string or ""
                mp4_match = re.search(r'(https?://[^\s"\']+\.mp4)', text)
                m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8)', text)
                if mp4_match:
                    result["video_url"] = mp4_match.group(1)
                    break
                if m3u8_match:
                    result["video_url"] = m3u8_match.group(1)
                    break

        # Fallback: data attributes
        if not result["video_url"]:
            for el in soup.select("[data-video-url], [data-src], [data-media]"):
                for attr in ("data-video-url", "data-src", "data-media"):
                    val = el.get(attr, "")
                    if val and (".mp4" in val or ".m3u8" in val or "mediaserver" in val):
                        result["video_url"] = val
                        break

        # Agenda items: look for numbered list items or structured agenda sections
        agenda_items: List[AgendaItem] = []
        for i, li in enumerate(soup.select("[class*='agenda'] li, [class*='chapter'] li, ol li"), 1):
            text = li.get_text(strip=True)
            if len(text) > 10:
                # Extract procedure references
                proc_refs = re.findall(r"\d{4}/\d{4}\s*\([A-Z]{2,4}\)", text)
                agenda_items.append(AgendaItem(number=i, title=text[:200], procedure_refs=proc_refs))

        result["agenda_items"] = agenda_items
        return result

    async def download_audio_url(self, video_url: str) -> Optional[str]:
        """Verify a video URL is reachable. Returns the URL if valid, None otherwise.

        Actual audio extraction (ffmpeg) is done by the transcription service,
        not this client. This just validates the URL is accessible.
        """
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.head(video_url, follow_redirects=True)
                if resp.status_code < 400:
                    content_type = resp.headers.get("content-type", "")
                    logger.info("[EP-multimedia] Video URL valid: %s (%s)", video_url, content_type)
                    return video_url
                logger.warning("[EP-multimedia] Video URL returned %d: %s", resp.status_code, video_url)
                return None
        except httpx.HTTPError as exc:
            logger.warning("[EP-multimedia] Video URL check failed: %s", exc)
            return None


# Module-level singleton
_client: Optional[EPMultimediaClient] = None


def get_ep_multimedia_client() -> EPMultimediaClient:
    global _client
    if _client is None:
        _client = EPMultimediaClient()
    return _client
