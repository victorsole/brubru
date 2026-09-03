"""
euagenda.eu scraper -- third-party Brussels events aggregator.

Scrapes the public events listing at https://euagenda.eu/events and the
per-event detail pages. Extracted events are upserted by
`eu_calendar_sync_service.py` into `eu_calendar_events` with
institution=THIRD_PARTY and source='euagenda'.

Listing page anatomy (verified 22 April 2026):
  <div class="event-box card ..."> containing:
    <a href="/events/YYYY/MM/DD/slug-of-event">...</a>
    plain-text lines: BOOSTED? | title | subtitle | country/lang | date | organiser

Detail page anatomy:
  <h1>Title</h1>
  <h2>Subtitle</h2>
  <h3>When</h3>  "27 May 2026 @ 09:00 am"  "29 May 2026 @ 01:15 pm"
  <h3>Where</h3>  "Online Webinar" or physical address
  <h3>Organised by</h3>  "Academy of European Law"
  <meta property="og:image">
  (no JSON-LD at 22 April 2026; may appear later)

Scraping rules: public pages only, no login, no behind-paywall. Rate-limited
via BaseScraper coordinator.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from services.scrapers.base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Data class for a scraped event (pre-DB, post-HTML)
# --------------------------------------------------------------------------

@dataclass
class ScrapedEuAgendaEvent:
    """One event scraped from euagenda.eu, ready for sync upsert."""
    external_id: str                  # e.g. "euagenda:2026-05-27-eu-savings-and-investments-union..."
    source_url: str                   # https://euagenda.eu/events/2026/05/27/slug
    title: str
    subtitle: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    all_day: bool = False
    venue: Optional[str] = None       # "Online Webinar" / physical address
    organiser: Optional[str] = None
    description: Optional[str] = None
    event_type: str = "agency_event"  # inferred below: conference/webinar/roundtable/training/workshop/agency_event
    country: Optional[str] = None     # "Belgium", "Online", etc.
    language: Optional[str] = None    # "en", "fr", etc.
    image_url: Optional[str] = None
    policy_areas: List[str] = field(default_factory=list)
    raw_date_line: Optional[str] = None  # for debugging


# --------------------------------------------------------------------------
# euagenda topic badges that appear as the FIRST line of a listing card and are
# NOT the event name (calendar audit, 3 September 2026). In --no-details mode the
# title was taken as card_lines[0] with only the "BOOSTED" marker skipped, so
# 126 rows landed in My EU Calendar titled "Agriculture", "Energy", "Regions"...
# Two genuinely different events on 5 May 2026 were BOTH stored as "Agriculture",
# which also made them look like duplicates to any (title, date) grouping.
_EUAGENDA_TOPIC_BADGES = {
    "agriculture", "aviation", "cities", "climate", "digital", "employment",
    "energy", "environment", "home affairs", "regions", "renewable energy",
    "science", "trade", "health", "transport", "justice", "security",
    "economy", "finance", "research", "innovation", "education", "culture",
    "defence", "migration", "enlargement", "budget", "fisheries", "maritime",
    "consumers", "competition", "taxation", "social", "development",
}


def _title_from_slug(slug: str) -> str:
    """Humanise a euagenda URL slug into a readable event title."""
    if not slug:
        return ""
    words = [w for w in slug.replace("_", "-").split("-") if w]
    if not words:
        return ""
    small = {"a", "an", "the", "of", "for", "and", "to", "in", "on", "from", "with", "at", "by"}
    # A slug lower-cases acronyms, and "Eu Rural Innovation Forum" reads wrong
    # in a calendar. Restore the ones that actually occur in EU event names.
    acronyms = {
        "eu", "ec", "ep", "eeas", "ecb", "eib", "eea", "efsa", "ema", "esma",
        "eba", "eiopa", "enisa", "eppo", "olaf", "jrc", "cor", "eesc", "ecj",
        "cjeu", "nato", "un", "oecd", "wto", "ilo", "who", "ai", "ict", "sme",
        "smes", "co2", "esg", "gdpr", "dsa", "dma", "cbam", "espr", "ets",
        "mff", "cap", "rrf", "stem", "r&d", "hpc", "5g", "6g",
    }
    def _cap(w: str, first: bool) -> str:
        if w.lower() in acronyms:
            return w.upper()
        if not first and w in small:
            return w
        return w.capitalize()
    out = [_cap(words[0], True)]
    out += [_cap(w, False) for w in words[1:]]
    joined = " ".join(out)
    # A slug flattens the possessive: "europe-s-twin-transition" came back as
    # "Europe S Twin Transition". Re-attach a lone "s" to the word before it.
    joined = re.sub(r"\b(\w+) [Ss]\b", r"\1's", joined)
    return joined


def _best_card_title(title_preview: str, slug: str) -> str:
    """Prefer the slug-derived title when the card's first line is a topic badge.

    A badge is short and is the whole line, so a length test alone would eat
    legitimately short event names; the badge set is checked explicitly and the
    slug is only used when it actually yields something longer.
    """
    preview = (title_preview or "").strip()
    if preview and preview.lower() not in _EUAGENDA_TOPIC_BADGES:
        return preview
    from_slug = _title_from_slug(slug)
    if from_slug and len(from_slug) > len(preview):
        return from_slug
    return preview


# Event type inference from title / subtitle
# --------------------------------------------------------------------------

EVENT_TYPE_KEYWORDS = [
    (r"\bwebinar\b|\bonline\s+(course|seminar|session)\b", "webinar"),
    (r"\bconference\b|\bcongress\b|\bsummit\b|\bsymposium\b", "conference"),
    (r"\broundtable\b|\bround[\s-]?table\b", "roundtable"),
    (r"\btraining\b|\bcourse\b|\bacademy\b|\bbootcamp\b", "training"),
    (r"\bworkshop\b|\bseminar\b", "workshop"),
]


def _infer_event_type(title: str, subtitle: str = "", venue: str = "") -> str:
    blob = f"{title} {subtitle} {venue}".lower()
    for pattern, etype in EVENT_TYPE_KEYWORDS:
        if re.search(pattern, blob):
            return etype
    return "agency_event"  # safe default, existing enum value


# --------------------------------------------------------------------------
# Date parsing (handles "27 May 2026 @ 09:00 am" and "Jun 29, 2026" formats)
# --------------------------------------------------------------------------

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

# "27 May 2026 @ 09:00 am" or "27 May 2026 @ 09:00" or "27 May 2026"
_DATE_TIME_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*(?:@|at)?\s*(\d{1,2})?(?::(\d{2}))?\s*(am|pm)?",
    re.IGNORECASE,
)


def _parse_datetime_line(line: str) -> Tuple[Optional[date], Optional[time]]:
    """Parse lines like '27 May 2026 @ 09:00 am' into (date, time)."""
    if not line:
        return None, None
    m = _DATE_TIME_RE.search(line)
    if not m:
        return None, None
    day, mon_str, year = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
    month = _MONTH_MAP.get(mon_str)
    if not month:
        return None, None
    try:
        d = date(year, month, day)
    except ValueError:
        return None, None
    hour = m.group(4)
    minute = m.group(5)
    ampm = (m.group(6) or "").lower()
    if hour is None:
        return d, None
    hh = int(hour)
    mm = int(minute) if minute else 0
    if ampm == "pm" and hh < 12:
        hh += 12
    if ampm == "am" and hh == 12:
        hh = 0
    try:
        t = time(hh, mm)
    except ValueError:
        return d, None
    return d, t


# --------------------------------------------------------------------------
# URL parsing (listing cards include /events/YYYY/MM/DD/slug -- good fallback)
# --------------------------------------------------------------------------

_DETAIL_URL_RE = re.compile(r"^/events/(\d{4})/(\d{1,2})/(\d{1,2})/([\w-]+)$")


def _parse_detail_url(href: str) -> Tuple[Optional[date], Optional[str], str]:
    """Extract (date, slug, absolute_url) from a /events/YYYY/MM/DD/slug path."""
    if not href:
        return None, None, ""
    m = _DETAIL_URL_RE.match(href.strip())
    if not m:
        return None, None, href
    y, mm, dd, slug = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    try:
        d = date(y, mm, dd)
    except ValueError:
        d = None
    abs_url = f"https://euagenda.eu{href}"
    return d, slug, abs_url


# --------------------------------------------------------------------------
# Scraper
# --------------------------------------------------------------------------

class EuAgendaScraper(BaseScraper):
    """Scraper for https://euagenda.eu/events."""

    LISTING_URL = "https://euagenda.eu/events"
    POLICY_URLS = {  # map euagenda policy sectors to Brubru policy_areas tags
        "energy": "energy",
        "environment": "environment",
        "digital": "digital",
        "health": "public_health",
        "economy": "economy",
        "science": "research",
        "trade": "trade",
        "security": "security_defence",
        "justice": "justice",
        "agriculture": "agriculture",
        "transport": "transport",
        "culture": "culture",
    }

    def __init__(self):
        super().__init__(
            base_url="https://euagenda.eu",
            name="euagenda",
            rate_limit_delay=2.0,  # polite: 2s between requests
            cache_ttl=3600,
            timeout=30,
            max_retries=3,
        )

    # ------------------------------------------------------------------
    # Listing page
    # ------------------------------------------------------------------

    async def scrape_listing(
        self,
        policy_area: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """Fetch the events listing page and extract event card metadata.

        Returns a list of dicts with keys:
          detail_url, start_date (best-effort from URL), title_preview,
          raw_text, country_lang.
        """
        url = f"{self.base_url}/events"
        if policy_area and policy_area in self.POLICY_URLS:
            url = f"{self.base_url}/events/{policy_area}"

        try:
            html = await self._fetch(url, use_cache=False)
        except ScraperError as exc:
            logger.error("euagenda: listing fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_=re.compile(r"\bevent-box\b"))
        logger.info("euagenda: found %d event cards on %s", len(cards), url)

        results: List[Dict] = []
        for card in cards[:limit]:
            # First anchor pointing to /events/YYYY/MM/DD/slug
            detail_link = None
            for a in card.find_all("a", href=True):
                href = a["href"]
                if _DETAIL_URL_RE.match(href):
                    detail_link = href
                    break
            if not detail_link:
                continue
            parsed_date, slug, abs_url = _parse_detail_url(detail_link)

            # Card text for preview
            card_text = card.get_text("\n", strip=True)
            card_lines = [ln for ln in card_text.split("\n") if ln.strip()]
            # Skip BOOSTED marker if present
            if card_lines and card_lines[0].strip().upper() == "BOOSTED":
                card_lines = card_lines[1:]
            title_preview = card_lines[0] if card_lines else ""
            subtitle_preview = card_lines[1] if len(card_lines) > 1 else ""
            country_lang = card_lines[2] if len(card_lines) > 2 else ""
            date_preview = card_lines[3] if len(card_lines) > 3 else ""
            organiser_preview = card_lines[4] if len(card_lines) > 4 else ""

            results.append({
                "detail_url": abs_url,
                "slug": slug,
                "start_date_from_url": parsed_date,
                "title_preview": title_preview,
                "subtitle_preview": subtitle_preview,
                "country_lang_preview": country_lang,
                "date_preview": date_preview,
                "organiser_preview": organiser_preview,
            })
        return results

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------

    async def scrape_detail(self, detail_url: str) -> Optional[ScrapedEuAgendaEvent]:
        """Fetch one event detail page and return a ScrapedEuAgendaEvent."""
        try:
            html = await self._fetch(detail_url, use_cache=True)
        except ScraperError as exc:
            logger.warning("euagenda: detail fetch failed %s: %s", detail_url, exc)
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Strip script/style so get_text is clean
        for s in soup(["script", "style", "noscript"]):
            s.decompose()

        # Title + subtitle
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title or title.lower().startswith(("404 not found", "oops")):
            logger.info("euagenda: detail page 404 or empty for %s", detail_url)
            return None
        h2 = soup.find("h2")
        subtitle = h2.get_text(strip=True) if h2 else None

        # Walk h3 labels: When, Where, Organised by.
        # Detail pages occasionally render the "Where" block inside a malformed
        # <meta> tag that also nests the subsequent h3 — so we can't rely on
        # next_sibling alone. Extract text, then truncate at the next known
        # label marker.
        def _value_after(h3_tag) -> List[str]:
            """Collect text from all siblings following an h3 up to the next heading,
            then truncate at downstream label bleed-through.
            """
            parts: List[str] = []
            sib = h3_tag.find_next_sibling()
            while sib is not None:
                if hasattr(sib, "name") and sib.name and re.match(r"^h[1-6]$", sib.name):
                    break
                txt = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                if txt:
                    parts.append(txt)
                sib = sib.find_next_sibling() if hasattr(sib, "find_next_sibling") else None
            raw = "\n".join(parts)
            # Truncate at any subsequent label that bled into these siblings
            for stop in ("Organised by", "Organized by", "Organiser", "Organizer",
                         "Register to attend", "Share this event",
                         "Other events by", "Contact ", "Subscribe "):
                idx = raw.find(stop)
                if idx > 0:
                    raw = raw[:idx].strip()
                    break
            if not raw:
                return []
            lines = [ln.strip() for ln in re.split(r"\n|\s{2,}|\s*\|\s*", raw) if ln.strip()]
            return lines or [raw]

        when_lines: List[str] = []
        where_lines: List[str] = []
        organiser: Optional[str] = None
        for h3 in soup.find_all("h3"):
            label = h3.get_text(strip=True).lower().rstrip(":")
            if label == "when":
                when_lines = _value_after(h3)
            elif label == "where":
                where_lines = _value_after(h3)
            elif label in ("organised by", "organized by", "organiser", "organizer"):
                lines = _value_after(h3)
                if lines:
                    # Organiser name is the first line; drop phone/email/URL noise
                    first = lines[0]
                    # Strip trailing contact noise
                    first = re.sub(r"\s*(\+?\d[\d\s\-()]{6,}|https?://\S+|\[email[^\]]*\]|\S+@\S+).*$", "", first).strip()
                    organiser = first or lines[0]

        # Parse When lines -> (start, end) datetime
        start_date = start_time = end_date = end_time = None
        raw_date_line = " | ".join(when_lines)
        if when_lines:
            sd, st = _parse_datetime_line(when_lines[0])
            start_date, start_time = sd, st
            if len(when_lines) > 1:
                ed, et = _parse_datetime_line(when_lines[1])
                end_date, end_time = ed, et

        # Venue
        venue = where_lines[0] if where_lines else None

        # Description: first paragraph after h2 or first substantive text block
        desc_parts: List[str] = []
        article = soup.find("article") or soup.find("main") or soup.body
        if article:
            for p in article.find_all("p"):
                txt = p.get_text(" ", strip=True)
                if txt and len(txt) > 40:
                    desc_parts.append(txt)
                if len(desc_parts) >= 3:
                    break
        description = "\n\n".join(desc_parts) if desc_parts else None

        # og:image
        og_img = soup.find("meta", attrs={"property": "og:image"})
        image_url = og_img.get("content") if og_img else None

        # External id from URL slug
        m = _DETAIL_URL_RE.match(detail_url.replace("https://euagenda.eu", ""))
        if m:
            external_id = f"euagenda:{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}-{m.group(4)}"
        else:
            external_id = f"euagenda:{detail_url}"

        # Infer event type
        event_type = _infer_event_type(title, subtitle or "", venue or "")

        # all_day when both start/end are date-only (no time parsed)
        all_day = bool(start_date) and start_time is None

        return ScrapedEuAgendaEvent(
            external_id=external_id,
            source_url=detail_url,
            title=title,
            subtitle=subtitle,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            all_day=all_day,
            venue=venue,
            organiser=organiser,
            description=description,
            event_type=event_type,
            image_url=image_url,
            raw_date_line=raw_date_line,
        )

    # ------------------------------------------------------------------
    # Top-level orchestration
    # ------------------------------------------------------------------

    async def scrape_upcoming(
        self,
        max_events: int = 200,
        include_details: bool = True,
    ) -> List[ScrapedEuAgendaEvent]:
        """Scrape the main listing and optionally enrich with detail pages.

        Args:
            max_events: cap on number of events to process (listing returns ~150).
            include_details: if True, fetch each detail page (slower, richer).
                             if False, return listing-only events with best-effort
                             fields from the URL + card text.
        """
        cards = await self.scrape_listing(limit=max_events)
        if not cards:
            return []

        events: List[ScrapedEuAgendaEvent] = []
        for i, card in enumerate(cards):
            if include_details:
                ev = await self.scrape_detail(card["detail_url"])
                if ev is None:
                    continue
                # Fallback: if detail page didn't give start_date, use URL date
                if ev.start_date is None and card.get("start_date_from_url"):
                    ev.start_date = card["start_date_from_url"]
                    ev.all_day = True
                events.append(ev)
            else:
                # Minimal path: fabricate from card only
                m = _DETAIL_URL_RE.match(
                    card["detail_url"].replace("https://euagenda.eu", "")
                )
                if m:
                    external_id = (
                        f"euagenda:{m.group(1)}-{int(m.group(2)):02d}-"
                        f"{int(m.group(3)):02d}-{m.group(4)}"
                    )
                else:
                    external_id = f"euagenda:{card['detail_url']}"
                title = _best_card_title(card["title_preview"], card["slug"]) or card["slug"] or "(untitled event)"
                events.append(ScrapedEuAgendaEvent(
                    external_id=external_id,
                    source_url=card["detail_url"],
                    title=title,
                    subtitle=card.get("subtitle_preview"),
                    start_date=card.get("start_date_from_url"),
                    all_day=True,
                    organiser=card.get("organiser_preview") or None,
                    event_type=_infer_event_type(title, card.get("subtitle_preview") or ""),
                ))
        logger.info("euagenda: scraped %d events (include_details=%s)", len(events), include_details)
        return events

    # ------------------------------------------------------------------
    # BaseScraper abstract methods (not meaningful for an events-only scraper)
    # ------------------------------------------------------------------

    async def search(self, query: str, **kwargs) -> List[Dict]:  # pragma: no cover
        """Not used; euagenda is an events aggregator without a search API surface."""
        return []

    async def get_document(self, document_id: str) -> Dict:  # pragma: no cover
        """Map document_id to a detail_url and return the scraped event as a dict."""
        if document_id.startswith("http"):
            url = document_id
        else:
            url = f"{self.base_url}/events/{document_id}"
        ev = await self.scrape_detail(url)
        return ev.__dict__ if ev else {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict]:  # pragma: no cover
        """Return the most recent events from the listing (newest first heuristic)."""
        cards = await self.scrape_listing(limit=limit)
        return cards[:limit]
