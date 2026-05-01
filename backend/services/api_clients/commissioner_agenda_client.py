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
from datetime import date, datetime
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
            # Prefer the title's own link; fall back to any href in the article;
            # reject anchors and javascript: links.
            def _clean(h: str) -> str:
                if not h or h.startswith(("#", "javascript:", "mailto:")):
                    return ""
                if h.startswith("/"):
                    return "https://commission.europa.eu" + h
                return h

            href = ""
            if title_el:
                a_in_title = title_el.find("a", href=True) or title_el.find_parent("a", href=True)
                if a_in_title:
                    href = _clean(a_in_title.get("href", ""))
            if not href:
                for a in node.find_all("a", href=True):
                    candidate = _clean(a.get("href", ""))
                    if candidate:
                        href = candidate
                        break
            out.append(AgendaItem(date=d, title=title, location=location, detail_url=href))
        return out

    async def fetch_agenda(
        self,
        commissioner_query: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
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
            url = self._build_calendar_url(leader_id)
            html = await self._get(url)
            items = self._parse_items(html or "")
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
