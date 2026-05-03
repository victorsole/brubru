"""
Commissioner Agenda Client.

On-demand fetch of a Commissioner's published calendar items from
commission.europa.eu. Discovers the per-commissioner political-leader ID by
scraping the bio page (cached 24h), then queries the faceted calendar URL.

Calendar URL pattern:
  https://commission.europa.eu/about/organisation/college-commissioners/
    calendar-items-president-and-commissioners_en
    ?f%5B0%5D=commissioner_dynamic_commissioner_dynamic%3A
    http%3A//publications.europa.eu/resource/authority/political-leader/COM_XXXXXXXX

Each calendar entry surfaces as <article class="ecl-content-item ecl-content-item--inline">
with a date span and a title.

Created: April 2026
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BIO_BASE = "https://commission.europa.eu/about/organisation/college-commissioners"
CALENDAR_BASE = (
    "https://commission.europa.eu/about/organisation/college-commissioners/"
    "calendar-items-president-and-commissioners_en"
)
# The Commission redesigned the calendar page in spring 2026 — the HTML now
# loads items via JavaScript, breaking the previous server-side scrape. The
# bare RSS feed at /node/33084/rss_en still returns the latest 30 items
# globally, each tagged with the commissioner's political-leader URI in
# <category domain="...">. We use the RSS feed as the canonical source and
# filter per commissioner from the merged list.
RSS_FEED_URL = "https://commission.europa.eu/node/33084/rss_en"
LEADER_AUTHORITY_BASE = (
    "http://publications.europa.eu/resource/authority/political-leader/"
)
USER_AGENT = "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"
BIO_TTL = 24 * 3600
AGENDA_TTL = 1 * 3600

COMMISSIONERS_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "knowledge_base"
    / "institutions"
    / "commissioners.json"
)


def _norm(s: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace and punctuation."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[\s\W_]+", " ", s).strip().lower()
    return s


@dataclass
class CommissionerProfile:
    name: str
    slug: str  # e.g. "raffaele-fitto"
    country: str
    portfolio: str
    bio_url: str
    leader_id: Optional[str] = None  # e.g. "COM_00006A3260A2"


@dataclass
class AgendaItem:
    date: date
    title: str
    location: str = ""
    detail_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "title": self.title,
            "location": self.location,
            "detail_url": self.detail_url,
        }


# ---------- profile registry ----------

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _slug_from_url(url: str) -> str:
    # https://commission.europa.eu/about/.../college-commissioners/raffaele-fitto_en
    m = re.search(r"/college-commissioners/([a-z0-9\-]+)_[a-z]+/?$", url or "")
    if m:
        return m.group(1)
    # Special case: the President page lives at /about/organisation/president_en.
    if url and "/about/organisation/president_en" in url:
        return "president"
    return ""


def _slug_from_name(name: str) -> str:
    """Fallback slug derivation from the human name (accent-insensitive)."""
    s = _strip_accents((name or "").lower()).strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def load_commissioner_profiles() -> List[CommissionerProfile]:
    """Read commissioners.json and flatten president + EVPs + commissioners."""
    if not COMMISSIONERS_JSON.exists():
        logger.warning("[commissioner-agenda] commissioners.json not found at %s", COMMISSIONERS_JSON)
        return []
    data = json.loads(COMMISSIONERS_JSON.read_text(encoding="utf-8"))
    out: List[CommissionerProfile] = []
    college = data.get("college", {})

    def add(record: Dict[str, Any]) -> None:
        name = (record.get("name") or "").strip()
        url = (record.get("url") or "").strip()
        if not name or not url:
            return
        slug = _slug_from_url(url) or _slug_from_name(name)
        out.append(CommissionerProfile(
            name=name,
            slug=slug,
            country=record.get("country") or "",
            portfolio=record.get("portfolio") or record.get("position") or "",
            bio_url=url,
        ))

    pres = college.get("president")
    if isinstance(pres, dict):
        add(pres)
    for r in college.get("executive_vice_presidents") or []:
        if isinstance(r, dict):
            add(r)
    for r in college.get("commissioners") or []:
        if isinstance(r, dict):
            add(r)
    return out


def find_profile(query: str, profiles: Optional[List[CommissionerProfile]] = None) -> Optional[CommissionerProfile]:
    """Resolve a free-text mention (e.g., 'Fitto', 'Raffaele Fitto', 'Sefcovic',
    'raffaele-fitto') to a profile. Accepts the canonical slug too."""
    if profiles is None:
        profiles = load_commissioner_profiles()
    if not query:
        return None
    q = _strip_accents(query.lower()).strip()
    if not q:
        return None
    # exact slug match (canonical input from /commissioners list)
    for p in profiles:
        if (p.slug or "").lower() == q:
            return p
    # exact name match (accent-insensitive)
    for p in profiles:
        if _strip_accents(p.name.lower()) == q:
            return p
    # slug treated as name with hyphens-as-spaces (e.g. "raffaele-fitto" → "raffaele fitto")
    q_dehyphen = q.replace("-", " ")
    if q_dehyphen != q:
        for p in profiles:
            if _strip_accents(p.name.lower()) == q_dehyphen:
                return p
    # surname-only match
    for p in profiles:
        parts = _strip_accents(p.name.lower()).split()
        if parts and parts[-1] == q:
            return p
    # token-set match (any token of q matches a surname)
    tokens = q.split() + q_dehyphen.split()
    for p in profiles:
        surname = _strip_accents(p.name.lower()).split()[-1] if p.name else ""
        if surname and surname in tokens:
            return p
    # substring fallback (only if 4+ chars, to avoid false positives)
    if len(q) >= 4:
        for p in profiles:
            if q in _strip_accents(p.name.lower()) or q_dehyphen in _strip_accents(p.name.lower()):
                return p
    return None


# ---------- client ----------

class CommissionerAgendaClient:
    def __init__(self) -> None:
        self._bio_cache: Dict[str, Tuple[float, Optional[str]]] = {}
        self._agenda_cache: Dict[str, Tuple[float, List[AgendaItem]]] = {}
        self._profiles: Optional[List[CommissionerProfile]] = None

    @property
    def profiles(self) -> List[CommissionerProfile]:
        if self._profiles is None:
            self._profiles = load_commissioner_profiles()
        return self._profiles

    def resolve(self, query: str) -> Optional[CommissionerProfile]:
        return find_profile(query, self.profiles)

    async def _get(self, url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return None
                return r.text
        except httpx.HTTPError as exc:
            logger.warning("[commissioner-agenda] HTTP error %s: %s", url, exc)
            return None

    async def _discover_leader_id(self, profile: CommissionerProfile) -> Optional[str]:
        """Fetch bio page, extract the political-leader authority ID (cached 24h)."""
        if profile.leader_id:
            return profile.leader_id
        cached = self._bio_cache.get(profile.slug)
        if cached and time.time() - cached[0] < BIO_TTL:
            profile.leader_id = cached[1]
            return cached[1]
        html = await self._get(profile.bio_url)
        if not html:
            return None
        m = re.search(r"authority/political-leader/(COM_[0-9A-F]+)", html)
        leader_id = m.group(1) if m else None
        self._bio_cache[profile.slug] = (time.time(), leader_id)
        profile.leader_id = leader_id
        return leader_id

    @staticmethod
    def _build_calendar_url(leader_id: str) -> str:
        # The page expects: f[0]=commissioner_dynamic_commissioner_dynamic:<authority-uri>
        authority_uri = LEADER_AUTHORITY_BASE + leader_id
        # Slashes must stay literal; only colons get encoded by the EC portal's filter URLs.
        return f"{CALENDAR_BASE}?f%5B0%5D=commissioner_dynamic_commissioner_dynamic%3A{quote(authority_uri, safe='/')}"

    @staticmethod
    def _parse_date(text: str) -> Optional[date]:
        # Examples: "21 Apr 2026", "16 Apr 2026"
        text = text.strip()
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _build_rss_url_entries(rss_xml: str) -> List[Tuple[date, str, str]]:
        """Parse the bare RSS feed into a flat list of (date, normalised_title, url).

        Used to enrich HTML-parsed items with detail URLs that the Commission
        no longer renders inline on the calendar page. The RSS <title> has the
        form "YYYY-MM-DD - <event title>" — but the title is truncated at ~90
        chars and many events on the same date share a long common prefix
        ("Executive Vice-President Fitto attends the…"). A list-of-tuples lets
        the lookup do token-set scoring rather than relying on a brittle
        prefix-equality key.
        """
        from xml.etree import ElementTree as ET

        if not rss_xml:
            return []
        try:
            root = ET.fromstring(rss_xml)
        except ET.ParseError:
            return []

        out: List[Tuple[date, str, str]] = []
        for it in root.findall(".//item"):
            title_el = it.find("title")
            link_el = it.find("link")
            if title_el is None or link_el is None:
                continue
            raw = (title_el.text or "").strip()
            link = (link_el.text or "").strip()
            if not raw or not link:
                continue
            m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s*[-–]\s*(.+)$", raw)
            if not m:
                continue
            try:
                event_date = date.fromisoformat(m.group(1))
            except ValueError:
                continue
            out.append((event_date, _norm(m.group(2)), link))
        return out

    @staticmethod
    def _lookup_rss_url(entries: List[Tuple[date, str, str]], item: "AgendaItem") -> str:
        """Pick the RSS URL whose title has the largest token-overlap with the
        HTML item, allowing a ±1 day window on the date.

        The Commission RSS dates are systematically one day BEFORE the HTML
        listing dates (timezone or publication-date drift on their side, hard
        to predict). A strict date match misses every entry, so we widen the
        window to ±1 day and rely on token-overlap to disambiguate.

        Returns "" when no candidate clears 60% Jaccard overlap — better null
        than wrong.
        """
        if not entries or not item.title:
            return ""
        html_tokens = {t for t in _norm(item.title).split() if len(t) > 2}
        if not html_tokens:
            return ""
        best_url = ""
        best_score = 0.0
        for d, rss_title, url in entries:
            day_delta = abs((d - item.date).days)
            if day_delta > 1:
                continue
            rss_tokens = {t for t in rss_title.split() if len(t) > 2}
            if not rss_tokens:
                continue
            overlap = len(html_tokens & rss_tokens)
            denom = max(len(html_tokens), len(rss_tokens))
            score = overlap / denom if denom else 0.0
            if score > best_score:
                best_score = score
                best_url = url
        return best_url if best_score >= 0.6 else ""

    @staticmethod
    def _parse_rss_items(rss_xml: str, leader_id: str) -> List[AgendaItem]:
        """Parse the bare commission calendar RSS and filter to one commissioner.

        The RSS feed is the only working source after the spring 2026 redesign
        (the leader-filtered HTML page is now JS-rendered). Each <item> carries
        the political-leader authority URI in a <category domain="..."> tag,
        which lets us match the requested commissioner without a server-side
        filter. Returns ALL items whose category matches the leader_id.
        """
        from xml.etree import ElementTree as ET

        if not rss_xml or not leader_id:
            return []
        try:
            root = ET.fromstring(rss_xml)
        except ET.ParseError as exc:
            logger.warning("[commissioner-agenda] RSS parse failed: %s", exc)
            return []

        target_uri = f"{LEADER_AUTHORITY_BASE}{leader_id}"
        out: List[AgendaItem] = []
        for it in root.findall(".//item"):
            categories = it.findall("category")
            # Match the political-leader category by domain prefix (the upstream
            # sometimes appends '/0002', '/0004' suffixes — accept any prefix).
            owner_match = False
            for c in categories:
                domain = c.attrib.get("domain", "")
                if domain.startswith(LEADER_AUTHORITY_BASE):
                    if domain == target_uri or domain.startswith(target_uri + "/"):
                        owner_match = True
                        break
            if not owner_match:
                continue

            title_el = it.find("title")
            link_el = it.find("link")
            pub_el = it.find("pubDate")
            raw_title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            pub = (pub_el.text or "").strip() if pub_el is not None else ""

            # Title is "YYYY-MM-DD - <title>". Extract both halves.
            event_date: Optional[date] = None
            display_title = raw_title
            m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s*[-–]\s*(.+)$", raw_title)
            if m:
                try:
                    event_date = date.fromisoformat(m.group(1))
                except ValueError:
                    event_date = None
                display_title = m.group(2).strip()
            if event_date is None and pub:
                # pubDate fallback: "Fri, 01 May 2026 12:58:14 +0200"
                try:
                    event_date = datetime.strptime(pub.split(" +")[0].split(" -")[0], "%a, %d %b %Y %H:%M:%S").date()
                except Exception:  # noqa: BLE001
                    event_date = None
            if event_date is None:
                continue

            out.append(AgendaItem(date=event_date, title=display_title, location="", detail_url=link))
        return out

    @staticmethod
    def _parse_items(html: str) -> List[AgendaItem]:
        soup = BeautifulSoup(html, "html.parser")
        out: List[AgendaItem] = []
        for node in soup.select("article.ecl-content-item--inline"):
            time_el = node.find("time")
            if not time_el:
                continue
            day_el = time_el.find(class_="ecl-date-block__day")
            month_el = time_el.find(class_="ecl-date-block__month")
            year_el = time_el.find(class_="ecl-date-block__year")
            if not (day_el and month_el and year_el):
                continue
            d = CommissionerAgendaClient._parse_date(
                f"{day_el.get_text(strip=True)} {month_el.get_text(strip=True)} {year_el.get_text(strip=True)}"
            )
            if not d:
                continue
            title_el = node.find(class_="ecl-content-block__title")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            location = ""
            loc_el = node.find(class_="wt-icon--location")
            if loc_el:
                # location text is in the sibling label span
                meta_li = loc_el.find_parent("li")
                if meta_li:
                    label = meta_li.find(class_="ecl-content-block__secondary-meta-label")
                    if label:
                        location = re.sub(r"\s+", " ", label.get_text(" ", strip=True)).strip()
            # Spring-2026 redesign: the cards expose <a href> links that point
            # to NEIGHBOURING cards (sibling-card "read more" anchors), not to
            # the event itself. Trusting the inline href produced shifted URLs
            # — every item showed the previous item's detail page. Leave it
            # empty here and let the RSS-merge step populate detail_url with
            # token-set scoring.
            out.append(AgendaItem(date=d, title=title, location=location, detail_url=""))
        return out

    @staticmethod
    def _persist_rss_to_db(rss_xml: str, db) -> int:
        """UPSERT every (leader_id, date, title, url) tuple from the RSS feed
        into commission_calendar_urls. Returns the number of rows touched.

        The Commission's RSS feed is a 30-item global rolling window — each
        agenda call ingests it here so historical detail URLs accumulate even
        after items roll out of the live feed. Idempotent on the unique key
        (leader_id, event_date, title_normalised); revisits bump last_seen_at.
        """
        from xml.etree import ElementTree as ET
        from sqlalchemy import text as _sql

        if not rss_xml or db is None:
            return 0
        try:
            root = ET.fromstring(rss_xml)
        except ET.ParseError:
            return 0

        rows = []
        for it in root.findall(".//item"):
            title_el = it.find("title")
            link_el = it.find("link")
            if title_el is None or link_el is None:
                continue
            raw = (title_el.text or "").strip()
            link = (link_el.text or "").strip()
            if not raw or not link:
                continue
            m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s*[-–]\s*(.+)$", raw)
            if not m:
                continue
            try:
                event_date = date.fromisoformat(m.group(1))
            except ValueError:
                continue
            display_title = m.group(2).strip()
            normalised = _norm(display_title)
            # Pull every leader_id this item is tagged with (some events list
            # multiple commissioners co-hosting).
            for cat in it.findall("category"):
                domain = cat.attrib.get("domain", "")
                if not domain.startswith(LEADER_AUTHORITY_BASE):
                    continue
                leader = domain[len(LEADER_AUTHORITY_BASE):].strip("/").split("/")[0]
                if not leader:
                    continue
                rows.append({
                    "leader_id": leader,
                    "event_date": event_date,
                    "title_normalised": normalised,
                    "title": display_title,
                    "detail_url": link,
                })

        if not rows:
            return 0

        try:
            db.execute(
                _sql("""
                    INSERT INTO commission_calendar_urls
                        (leader_id, event_date, title_normalised, title, detail_url)
                    VALUES (:leader_id, :event_date, :title_normalised, :title, :detail_url)
                    ON CONFLICT (leader_id, event_date, title_normalised)
                    DO UPDATE SET
                        detail_url = EXCLUDED.detail_url,
                        last_seen_at = NOW()
                """),
                rows,
            )
            db.commit()
            return len(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[commissioner-agenda] DB persist failed: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return 0

    @staticmethod
    def _lookup_db_urls(
        items: List["AgendaItem"], leader_id: str, db
    ) -> Dict[Tuple[date, str], str]:
        """Batch-fetch detail URLs from the DB for a list of agenda items.

        Returns a {(date, normalised_title): url} dict. The lookup uses a
        ±1-day window on event_date and the same token-set Jaccard scoring
        as the live RSS path, so older events captured weeks ago still match.
        """
        from sqlalchemy import text as _sql

        if not items or not leader_id or db is None:
            return {}
        dates = sorted({it.date for it in items})
        if not dates:
            return {}
        # Pull every row for this leader within ±1 day of the requested range.
        try:
            rows = db.execute(
                _sql("""
                    SELECT event_date, title_normalised, detail_url
                    FROM commission_calendar_urls
                    WHERE leader_id = :leader_id
                      AND event_date BETWEEN :from_date AND :to_date
                """),
                {
                    "leader_id": leader_id,
                    "from_date": min(dates) - timedelta(days=1),
                    "to_date": max(dates) + timedelta(days=1),
                },
            ).fetchall()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[commissioner-agenda] DB lookup failed: %s", exc)
            return {}

        out: Dict[Tuple[date, str], str] = {}
        for it in items:
            html_tokens = {t for t in _norm(it.title).split() if len(t) > 2}
            if not html_tokens:
                continue
            best_url = ""
            best_score = 0.0
            for r in rows:
                row_date = r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0]))
                if abs((row_date - it.date).days) > 1:
                    continue
                row_tokens = {t for t in (r[1] or "").split() if len(t) > 2}
                if not row_tokens:
                    continue
                overlap = len(html_tokens & row_tokens)
                denom = max(len(html_tokens), len(row_tokens))
                score = overlap / denom if denom else 0.0
                if score > best_score:
                    best_score = score
                    best_url = r[2]
            if best_score >= 0.6 and best_url:
                out[(it.date, _norm(it.title))] = best_url
        return out

    async def fetch_agenda(
        self,
        commissioner_query: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        db=None,
    ) -> Tuple[Optional[CommissionerProfile], List[AgendaItem]]:
        profile = self.resolve(commissioner_query)
        if profile is None:
            return None, []

        leader_id = await self._discover_leader_id(profile)
        if not leader_id:
            logger.info("[commissioner-agenda] no leader_id for %s", profile.name)
            return profile, []

        cache_key = profile.slug
        cached = self._agenda_cache.get(cache_key)
        if cached and time.time() - cached[0] < AGENDA_TTL:
            items = cached[1]
        else:
            # The Commission's spring-2026 redesign STRIPPED per-event detail
            # links from the calendar HTML listing — each card now shows only
            # date + title + location, no <a href>. The bare RSS feed at
            # /node/33084/rss_en still carries per-event URLs but only for the
            # latest 30 items globally. Strategy: parse HTML for the per-
            # commissioner roster, persist current RSS items to DB so URLs
            # accumulate over time, then look up each item's URL from DB
            # (covers older events that have rolled out of live RSS) with a
            # live-RSS fallback for anything not yet persisted.
            url = self._build_calendar_url(leader_id)
            html = await self._get(url)
            items = self._parse_items(html or "")
            rss = await self._get(RSS_FEED_URL)
            self._persist_rss_to_db(rss or "", db)
            db_urls = self._lookup_db_urls(items, leader_id, db)
            entries = self._build_rss_url_entries(rss or "")
            items = [
                AgendaItem(
                    date=it.date,
                    title=it.title,
                    location=it.location,
                    detail_url=(
                        db_urls.get((it.date, _norm(it.title)))
                        or self._lookup_rss_url(entries, it)
                    ),
                )
                for it in items
            ]
            self._agenda_cache[cache_key] = (time.time(), items)

        if date_from or date_to:
            df = date_from or date.min
            dt = date_to or date.max
            items = [it for it in items if df <= it.date <= dt]
        # newest first
        items.sort(key=lambda x: x.date, reverse=True)
        return profile, items


_singleton: Optional[CommissionerAgendaClient] = None


def get_commissioner_agenda_client() -> CommissionerAgendaClient:
    global _singleton
    if _singleton is None:
        _singleton = CommissionerAgendaClient()
    return _singleton
