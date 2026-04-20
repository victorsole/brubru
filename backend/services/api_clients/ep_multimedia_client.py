"""
EP Committees Webstreaming Client

Canonical source: https://www.europarl.europa.eu/committees/en/meetings/webstreaming
(the committees hub page), with detail pages hosted on
multimedia.europarl.europa.eu.

Discovery happens from the committees hub (live-stream schedule + "Video
recordings" archive). Transcription is on-demand only.

Selectors (verified 19 April 2026):
  Card:       div.es_document-header
  Link:       h3.es_document-title a[href*="multimedia.europarl"]
  Date/time:  span.es_agenda-date  (e.g. "20-04-2026 14:30 - 17:30")
  Committee:  a.es_badge-committee (text == committee code, may repeat for joint meetings)

Detail URL pattern:
  https://multimedia.europarl.europa.eu/en/{slug}-committee-meeting_YYYYMMDD-HHMM-COMMITTEE-{CODE(S)}_vd

Created: April 2026
Updated: April 2026 — switched to committees hub scraping (was multimedia centre)
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

COMMITTEES_BASE = "https://www.europarl.europa.eu"
COMMITTEES_WEBSTREAMING_URL = f"{COMMITTEES_BASE}/committees/en/meetings/webstreaming"
MULTIMEDIA_BASE = "https://multimedia.europarl.europa.eu"
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
        max_pages: int = 1,
    ) -> List[CommitteeMeeting]:
        """Discover committee meetings from the EP committees hub webstreaming page.

        Scrapes both live-stream schedule (upcoming) and the "Video recordings"
        archive (past meetings). Returns meetings newest-first.
        """
        cache_key = f"discover:{committee_code or 'all'}:{date_from}:{date_to}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        html = await self._fetch_html(COMMITTEES_WEBSTREAMING_URL)
        if not html:
            logger.warning("[EP-committees-ws] Failed to fetch hub page")
            return []

        meetings = self._parse_committees_hub_page(html)

        if committee_code:
            code_upper = committee_code.upper()
            meetings = [m for m in meetings if code_upper in m.committee_code.upper().split("-")]

        if date_from:
            meetings = [m for m in meetings if m.meeting_date >= date_from]
        if date_to:
            meetings = [m for m in meetings if m.meeting_date <= date_to]

        self._cache_put(cache_key, meetings)
        logger.info(
            "[EP-committees-ws] Discovered %d meetings (filter committee=%s, range=%s..%s)",
            len(meetings), committee_code or "all", date_from, date_to,
        )
        return meetings

    def _parse_committees_hub_page(self, html: str) -> List[CommitteeMeeting]:
        """Parse the committees hub webstreaming page into CommitteeMeeting objects.

        Target DOM (verified April 2026):
            div.es_document-header
              h3.es_document-title > a[href*="multimedia.europarl"]
              span.es_agenda-date  "DD-MM-YYYY HH:MM - HH:MM"
              a.es_badge-committee (1+ per card, e.g. joint IMCO-JURI-PETI)
        """
        soup = BeautifulSoup(html, "lxml")
        meetings: List[CommitteeMeeting] = []

        for card in soup.select("div.es_document-header"):
            meeting = self._parse_hub_card(card)
            if meeting:
                meetings.append(meeting)

        return meetings

    def _parse_hub_card(self, card) -> Optional[CommitteeMeeting]:
        """Extract a CommitteeMeeting from a committees-hub card."""
        try:
            link = card.select_one('h3.es_document-title a[href*="multimedia.europarl"]')
            if not link:
                return None
            multimedia_url = link.get("href", "").strip()
            if not multimedia_url:
                return None

            # event_id from URL: "libe-committee-meeting_20260420-1500-COMMITTEE-LIBE_vd"
            event_id = multimedia_url.rstrip("/").split("/")[-1]

            # Date/time: "20-04-2026 14:30 - 17:30"
            date_el = card.select_one("span.es_agenda-date")
            if not date_el:
                return None
            dt_text = date_el.get_text(" ", strip=True)
            dt_match = re.match(
                r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})",
                dt_text,
            )
            if not dt_match:
                return None
            d_, m_, y_, start_time, end_time = dt_match.groups()
            meeting_date = date(int(y_), int(m_), int(d_))

            # Committee badges (one per code, multiple for joint meetings)
            badges = card.select("a.es_badge-committee")
            codes = [b.get_text(strip=True).upper() for b in badges if b.get_text(strip=True)]
            if not codes:
                # Fallback: extract from URL
                url_code_match = re.search(r"COMMITTEE-([A-Z-]+)_vd", multimedia_url)
                if url_code_match:
                    codes = url_code_match.group(1).split("-")
            if not codes:
                return None

            # committee_code column is VARCHAR(10) — use primary code only.
            # Joint meetings preserve all codes in the title (e.g. "IMCO-JURI-PETI ...").
            full_code_str = "-".join(codes)
            committee_code = codes[0]  # primary for filtering

            title = (
                f"{full_code_str} Committee Meeting - {meeting_date.strftime('%d %B %Y')}"
                if len(codes) > 1
                else f"{committee_code} Committee Meeting - {meeting_date.strftime('%d %B %Y')}"
            )

            # Duration
            duration = None
            try:
                s = datetime.strptime(start_time, "%H:%M")
                e = datetime.strptime(end_time, "%H:%M")
                duration = int((e - s).total_seconds() / 60)
            except ValueError:
                pass

            # Live if today and not yet ended
            today = date.today()
            is_live = meeting_date == today

            return CommitteeMeeting(
                event_id=event_id,
                committee_code=committee_code,
                title=title,
                meeting_date=meeting_date,
                start_time=start_time,
                end_time=end_time,
                multimedia_url=multimedia_url,
                duration_minutes=duration,
                is_live=is_live,
            )
        except Exception as exc:
            logger.debug("[EP-committees-ws] Failed to parse card: %s", exc)
            return None

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
