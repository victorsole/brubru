"""
EP Committees Webstreaming Client

Two discovery paths:
  (1) Committees hub (https://www.europarl.europa.eu/committees/en/meetings/webstreaming)
      -- UPCOMING meetings, no past VOD. Used by /news.
  (2) Multimedia portal day feed (https://multimedia.europarl.europa.eu/_next/data/
      {BUILD_ID}/en/webstreaming.json?view=day&d=YYYY-MM-DD) -- PAST + upcoming items,
      each with a `mediaKey` (e.g. 202604230900COMMITTEESANT) from which a
      deterministic HLS master URL can be built. Used by /transcripts.

HLS master pattern (no WAF, Google-cloud CDN, HTTP 200):
    https://vod-pckgr.media.eup.glcloud.eu/i/,/{YYYY}/{MM}/{DD}/{KEY-DASHED}/
      {KEY-DASHED}_,360p,540p,720p,1080p,.mp4/master.m3u8
  with KEY-DASHED = YYYYMMDD-HHMM-COMMITTEE-CODE (the mediaKey with hyphens inserted).
  The master m3u8 carries multi-language AUDIO tracks (one per interpretation booth:
  floor `qaj/qar/qac`, `LANGUAGE="en"`, `fr`, `es`, `it`, `nl`, ...). Pick the booth.

Created: April 2026
Updated: May 2026 -- day-feed discovery + deterministic HLS URL construction.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

COMMITTEES_BASE = "https://www.europarl.europa.eu"
COMMITTEES_WEBSTREAMING_URL = f"{COMMITTEES_BASE}/committees/en/meetings/webstreaming"
MULTIMEDIA_BASE = "https://multimedia.europarl.europa.eu"
MULTIMEDIA_DAY_PATH = "/en/webstreaming?view=day&d={date}"
HLS_PACKAGER = "https://vod-pckgr.media.eup.glcloud.eu"
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
        use_day_feed: Optional[bool] = None,
    ) -> List[CommitteeMeeting]:
        """Discover committee meetings.

        If `use_day_feed` is True (or auto-detected from a single past `date_from
        == date_to`), use the multimedia-portal day-feed -- gives past meetings
        with deterministic HLS URLs. Otherwise scrape the committees hub for
        upcoming. /news default path stays on the hub for parity.
        Returns meetings newest-first.
        """
        today = date.today()
        if use_day_feed is None:
            # Auto: only switch to day-feed when caller asks for a specific past day
            use_day_feed = bool(
                date_from and date_to and date_from == date_to and date_from < today
            )
        cache_key = f"discover:{committee_code or 'all'}:{date_from}:{date_to}:{'day' if use_day_feed else 'hub'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if use_day_feed:
            df = date_from
            dt = date_to or today
            meetings = await self.discover_via_day_feed(
                date_from=df, date_to=dt, committee_code=committee_code,
            )
        else:
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
            "[EP-multimedia] Discovered %d meetings (%s; committee=%s, range=%s..%s)",
            len(meetings), "day-feed" if use_day_feed else "hub",
            committee_code or "all", date_from, date_to,
        )
        return meetings

    # -- Multimedia portal day-feed path (past meetings + recordings) -----

    async def discover_via_day_feed(
        self,
        date_from: date,
        date_to: date,
        committee_code: Optional[str] = None,
    ) -> List[CommitteeMeeting]:
        """Fetch the Next.js day-feed for each day in range, return committee meetings
        with deterministic HLS master URL populated as video_url. WAF-cleared via
        Playwright; falls back to plain httpx if BUILD_ID can be guessed.
        """
        import asyncio

        meetings = await asyncio.to_thread(
            self._sync_discover_via_day_feed, date_from, date_to, committee_code,
        )
        return meetings

    def _sync_discover_via_day_feed(
        self,
        date_from: date,
        date_to: date,
        committee_code: Optional[str] = None,
    ) -> List[CommitteeMeeting]:
        from playwright.sync_api import sync_playwright

        meetings: List[CommitteeMeeting] = []
        code_upper = committee_code.upper() if committee_code else None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                build_id = self._get_build_id(page)
                if not build_id:
                    logger.warning("[EP-multimedia] Could not extract Next.js BUILD_ID")
                    return []

                day = date_from
                while day <= date_to:
                    items = self._fetch_day_feed_json(page, build_id, day)
                    if items:
                        for item in items:
                            mtg = self._media_item_to_meeting(item, day)
                            if not mtg:
                                continue
                            if code_upper and code_upper != mtg.committee_code:
                                continue
                            meetings.append(mtg)
                    day += timedelta(days=1)
            finally:
                browser.close()

        meetings.sort(key=lambda m: (m.meeting_date, m.start_time or ""), reverse=True)
        return meetings

    def _get_build_id(self, page) -> Optional[str]:
        """Load the SPA, parse __NEXT_DATA__ to extract buildId."""
        try:
            page.goto(MULTIMEDIA_BASE + "/en/webstreaming", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)
            build_id = page.evaluate(
                "() => { const el = document.getElementById('__NEXT_DATA__'); "
                "if (!el) return null; try { return JSON.parse(el.textContent).buildId; } catch (e) { return null; } }"
            )
            if build_id:
                logger.info("[EP-multimedia] BUILD_ID = %s", build_id)
            return build_id
        except Exception as exc:
            logger.warning("[EP-multimedia] BUILD_ID extraction failed: %s", exc)
            return None

    def _fetch_day_feed_json(self, page, build_id: str, day: date) -> List[Dict[str, Any]]:
        """Fetch the Next.js _next/data day-feed JSON and return pageProps.mediaItems."""
        url = (
            f"{MULTIMEDIA_BASE}/_next/data/{build_id}/en/webstreaming.json"
            f"?view=day&d={day.strftime('%Y-%m-%d')}"
        )
        try:
            text = page.evaluate(
                "async (u) => { const r = await fetch(u, {headers:{'Accept':'application/json'}}); "
                "return r.ok ? await r.text() : null; }",
                url,
            )
            if not text:
                return []
            data = json.loads(text)
            return data.get("pageProps", {}).get("mediaItems", []) or []
        except Exception as exc:
            logger.debug("[EP-multimedia] day-feed fetch failed for %s: %s", day, exc)
            return []

    def _media_item_to_meeting(self, item: Dict[str, Any], day: date) -> Optional[CommitteeMeeting]:
        """Convert one mediaItems entry into a CommitteeMeeting with HLS master URL.

        Trusts the mediaKey's own date (YYYYMMDD prefix). If the day-feed returns
        items from another date (the Next.js endpoint sometimes echoes a previous
        day's items when the requested day is empty), we filter by `day` so we
        never fabricate a meeting on a date the item didn't carry itself.
        """
        media_key = item.get("mediaKey") or ""
        if "COMMITTEE" not in media_key:
            return None

        # mediaKey format: YYYYMMDDHHMMCOMMITTEECODE (e.g. 202604230900COMMITTEESANT)
        m = re.match(r"^(\d{8})(\d{4})COMMITTEE([A-Z]+)$", media_key)
        if not m:
            return None
        ymd, hhmm, code = m.groups()
        try:
            item_date = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
        except ValueError:
            return None
        if item_date != day:
            return None  # day-feed echoed an item from another day; reject

        start_time = f"{hhmm[:2]}:{hhmm[2:]}"
        title = item.get("title") or f"{code} committee meeting - {item_date.strftime('%d %B %Y')}"

        # Dashed key derived from the item's OWN date+time, not the requested day.
        key_dashed = f"{ymd}-{hhmm}-COMMITTEE-{code}"
        hls_master = (
            f"{HLS_PACKAGER}/i/,/{ymd[:4]}/{ymd[4:6]}/{ymd[6:]}"
            f"/{key_dashed}/{key_dashed}_,360p,540p,720p,1080p,.mp4/master.m3u8"
        )

        # event_id mirrors the multimedia detail-page slug pattern so it stays unique.
        event_id = f"{code.lower()}-committee-meeting_{key_dashed}_vd"
        multimedia_url = f"{MULTIMEDIA_BASE}/en/webstreaming/{event_id}"

        return CommitteeMeeting(
            event_id=event_id,
            committee_code=code,
            title=title,
            meeting_date=item_date,
            start_time=start_time,
            end_time=None,
            multimedia_url=multimedia_url,
            video_url=hls_master,
            duration_minutes=None,
            is_live=False,
        )

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
