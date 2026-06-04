"""
Bespoke per-site EVENT scraper for My EU Calendar — the all-EU bodies whose event
pages are neither the EC ECL "What's on" component (handled by dg_events_scraper)
nor a clean RSS. Date-first: an event with no date is not a calendar entry, so we
only emit events that carry a usable date AND are upcoming.

Two extractors:
  * parse_council() — the Council future-meetings page encodes BOTH the
    configuration and the date in the URL (/en/meetings/<config>/YYYY/MM/DD-DD/),
    so we read them straight from the path. Cleanest source.
  * parse_generic() — for the bodies, a per-source `link_re` selects event-detail
    anchors and each is paired with its NEAREST date (a <time datetime> first,
    else a date-text). Title from the anchor text, slug fallback.

NO LLM / NO Anthropic. Link/date signatures discovered 1 Jun 2026 by harvesting
each rendered DOM. Bodies whose pages are JS shells or only-past-events (CJEU,
EUIPO, AMLA, EUAA, ECA, ECDC, EMSA, Eurojust, CPVO, Ombudsman, EIB, ENISA, EDPS,
ECHA) are NOT wired yet — see docs/new_format/meub_linking_anchor_inventory.md.
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse, unquote

logger = logging.getLogger(__name__)

_TAG = re.compile(r"<[^>]+>")
_MON = {m[:3].lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"]) if i}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", s or ""))).strip()


def _slug_title(path: str) -> str:
    seg = [x for x in path.rstrip("/").split("/") if x][-1]
    seg = seg[:-3] if seg.endswith("_en") else seg
    seg = re.sub(r"^\d{4,}[_-]?", "", seg)
    t = re.sub(r"\s+", " ", unquote(seg).replace("-", " ").replace("_", " ")).strip()
    return (t[:1].upper() + t[1:]) if t else ""


def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})", s)
    if m and m[2][:3].lower() in _MON:
        try:
            return date(int(m[3]), _MON[m[2][:3].lower()], int(m[1]))
        except ValueError:
            return None
    m = re.match(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------
# Council configurations that mean the European Council (summits), not a Council
# configuration meeting.
_EUCO = {"euco", "european-council", "special-european-council", "international-summit"}
# URL config slug -> canonical COUNCIL_CONFIGURATIONS key (so the dropdown filter matches)
_CFG_ALIAS = {"eycs": "EDUC", "env": "ENVI", "envir": "ENVI", "agri": "AGRIFISH"}

BESPOKE_EVENT_SOURCES: List[Dict] = [
    {"institution": "COUNCIL", "kind": "council", "source": "council_future_meetings",
     "url": "https://www.consilium.europa.eu/en/meetings/future-meetings/"},
    {"institution": "COR", "source": "bespoke_events:COR", "event_type": "conference",
     "url": "https://www.cor.europa.eu/en/plenaries-events/upcoming-events",
     "link_re": r"^/en/plenaries-events/[a-z0-9][a-z0-9-]{6,}$",
     "exclude": {"/en/plenaries-events/flagship-events", "/en/plenaries-events/awards",
                 "/en/plenaries-events/upcoming-events", "/en/plenaries-events/past-events"}},
    {"institution": "EMA", "source": "bespoke_events:EMA", "event_type": "agency_event",
     "url": "https://www.ema.europa.eu/en/events/upcoming-events",
     "link_re": r"^/en/events/[a-z0-9][a-z0-9-]{6,}$"},
    {"institution": "CEPOL", "source": "bespoke_events:CEPOL", "event_type": "webinar",
     "url": "https://www.cepol.europa.eu/training-education/webinars",
     "link_re": r"/training-education/\d{3,}-\d{4}-web"},
    {"institution": "EU_OSHA", "source": "bespoke_events:EU_OSHA", "event_type": "agency_event",
     "url": "https://osha.europa.eu/en/oshevents",
     "link_re": r"^/en/oshevents/[a-z0-9][a-z0-9-]{6,}$"},
    {"institution": "EIT", "source": "bespoke_events:EIT", "event_type": "conference",
     "url": "https://www.eit.europa.eu/news-events/events",
     "link_re": r"^/news-events/events/[a-z0-9][a-z0-9-]{6,}$",
     "exclude": {"/news-events/events/past"}},
    {"institution": "FRA", "source": "bespoke_events:FRA", "event_type": "conference",
     "url": "https://fra.europa.eu/en/news-and-events/upcoming-events",
     "link_re": r"^/en/event/\d{4}/[a-z0-9-]{6,}$"},
    {"institution": "EUROFOUND", "source": "bespoke_events:EUROFOUND", "event_type": "conference",
     "url": "https://www.eurofound.europa.eu/en/news-and-events/all-events?contentType=upcoming",
     "link_re": r"^/en/news-and-events/events/[a-z0-9][a-z0-9-]{6,}$"},
    {"institution": "EEAS", "source": "bespoke_events:EEAS", "event_type": "conference",
     "url": "https://www.eeas.europa.eu/filter-page/events_en",
     "link_re": r"^(?:/delegations/[^/]+|/eeas)/(?:[^/-]+-){3,}[^/]*_en$"},
    # --- EP think-tank (EPRS) + political-group events (1 Jun 2026) ---
    # institution=EP, organiser tag distinguishes the host. EPRS encodes the
    # date+time at the start of the anchor text; group sites vary (see per-source).
    {"institution": "EP", "source": "bespoke_events:EPRS", "event_type": "conference",
     "organiser": "EPRS (European Parliamentary Research Service)",
     "url": "https://www.europarl.europa.eu/thinktank/en/events/upcoming-events",
     "link_re": r"^/thinktank/en/events/details/[a-z-]+/\w+",
     "title_date_re": r"^(\d{2})-(\d{2})-(\d{4})\s+[\d:]*\s*"},
    {"institution": "EP", "source": "bespoke_events:GROUP_SD", "event_type": "conference",
     "organiser": "S&D Group", "url": "https://www.socialistsanddemocrats.eu/latest?type=event",
     "link_re": r"^/events/[a-z0-9][a-z0-9-]{8,}$"},
    {"institution": "EP", "source": "bespoke_events:GROUP_RENEW", "event_type": "conference",
     "organiser": "Renew Europe", "url": "https://www.reneweuropegroup.eu/events",
     "link_re": r"^/events/\d{4}-\d{2}-\d{2}/[a-z0-9-]+$",
     "date_in_path": r"/events/(\d{4})-(\d{2})-(\d{2})/"},
    {"institution": "EP", "source": "bespoke_events:GROUP_GREENS", "event_type": "conference",
     "organiser": "Greens/EFA", "url": "https://www.greens-efa.eu/en/get-involved/our-events",
     "link_re": r"^/en/article/event/[a-z0-9][a-z0-9-]{5,}$"},
    {"institution": "EP", "source": "bespoke_events:GROUP_ECR", "event_type": "conference",
     "organiser": "ECR Group", "url": "https://ecrgroup.eu/events",
     "link_re": r"^/event/[a-z0-9_]{8,}$"},
    {"institution": "EP", "source": "bespoke_events:EP_DELEGATIONS", "kind": "ep_agenda",
     "url": "https://www.europarl.europa.eu/delegations/en/calendar"},
]

_A = re.compile(r'<a\b[^>]*href="([^"#?]+)"[^>]*>(.*?)</a>', re.S)
_TIME = re.compile(r'<time[^>]*datetime="([^"]+)"')
_DTXT = re.compile(
    r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+20\d{2}'
    r'|20\d{2}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]20\d{2})\b')
_COUNCIL = re.compile(r'^/en/meetings/([a-z-]+)/(\d{4})/(\d{2})/(\d{2})(?:-\d{2})?/?$')
_WINDOW = 1800


def _collect_dates(html: str):
    """Positions + parsed dates: <time datetime> preferred, date-text fallback."""
    out = []
    for m in _TIME.finditer(html):
        d = _parse_date(m.group(1))
        if d:
            out.append((m.start(), d))
    if len(out) < 3:
        for m in _DTXT.finditer(html):
            d = _parse_date(m.group(1))
            if d:
                out.append((m.start(), d))
    return out


def parse_generic(html: str, cfg: Dict, today: date) -> List[Dict]:
    base = f"https://{urlparse(cfg['url']).netloc}"
    link_re = re.compile(cfg["link_re"])
    exclude = set(cfg.get("exclude") or [])
    # Date strategy: (a) date encoded in the href path; (b) date prefixing the
    # anchor text; else (c) nearest date elsewhere on the page.
    path_date_re = re.compile(cfg["date_in_path"]) if cfg.get("date_in_path") else None
    title_date_re = re.compile(cfg["title_date_re"]) if cfg.get("title_date_re") else None
    organiser = cfg.get("organiser")
    dates = _collect_dates(html or "") if not path_date_re else []
    out: List[Dict] = []
    seen: set = set()
    for m in _A.finditer(html or ""):
        href, inner = m.group(1), m.group(2)
        path = urlparse(href).path
        if path.rstrip("/") in exclude or not link_re.search(path):
            continue
        title = _clean(inner)
        start = None
        # (b) date at the start of the anchor text (e.g. EPRS "02-06-2026 15:00 …")
        if title_date_re:
            tm = title_date_re.match(title)
            if tm:
                g = tm.groups()
                try:
                    start = date(int(g[2]), int(g[1]), int(g[0]))
                except (ValueError, IndexError):
                    start = None
                title = title[tm.end():].strip(" -–—:|")
        # (a) date in the href path (e.g. Renew /events/2026-05-18/…)
        if not start and path_date_re:
            pm = path_date_re.search(path)
            if pm:
                try:
                    start = date(int(pm.group(1)), int(pm.group(2)), int(pm.group(3)))
                except (ValueError, IndexError):
                    start = None
        if len(title) < 12:
            title = _slug_title(path)
        if len(title) < 12:
            continue
        # (c) nearest date elsewhere on the page
        if not start:
            apos = m.start()
            bestd = _WINDOW
            for dpos, d in dates:
                dist = abs(dpos - apos)
                if dist < bestd:
                    bestd = dist
                    start = d
        if not start or start < today:
            continue
        url = href if href.startswith("http") else urljoin(base, href)
        key = urlparse(url).path.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title[:480], "start_date": start, "all_day": True,
            "institution": cfg["institution"], "event_type": cfg.get("event_type", "conference"),
            "source": cfg["source"], "external_id": key.rsplit("/", 1)[-1] or key,
            "source_url": url, "organiser": organiser,
        })
    return out


def parse_council(html: str, cfg: Dict, today: date) -> List[Dict]:
    base = "https://www.consilium.europa.eu"
    out: List[Dict] = []
    seen: set = set()
    for m in _A.finditer(html or ""):
        href, inner = m.group(1), m.group(2)
        path = urlparse(href).path
        cm = _COUNCIL.match(path)
        if not cm:
            continue
        config, y, mo, d = cm.group(1), int(cm.group(2)), int(cm.group(3)), int(cm.group(4))
        try:
            start = date(y, mo, d)
        except ValueError:
            continue
        if start < today:
            continue
        title = _clean(inner)
        if len(title) < 12:
            continue
        key = path.strip("/")
        if key in seen:
            continue
        seen.add(key)
        is_euco = config in _EUCO
        low = title.lower()
        if is_euco:
            inst, etype, conf = "EUROPEAN_COUNCIL", "european_council_summit", None
        elif config == "eurogroup":
            inst, etype, conf = "COUNCIL", "eurogroup", "EUROGROUP"
        elif "informal" in low:
            inst, etype, conf = "COUNCIL", "informal_meeting", _CFG_ALIAS.get(config, config.upper())
        else:
            inst, etype, conf = "COUNCIL", "council_meeting", _CFG_ALIAS.get(config, config.upper())
        out.append({
            "title": title[:480], "start_date": start, "all_day": True,
            "institution": inst, "event_type": etype, "council_configuration": conf,
            "source": cfg["source"], "external_id": key,
            "source_url": urljoin(base, href),
            # cross-source dedup key (Council already has a council_calendar source)
            "_dedup": ("start_date", "council_configuration") if not is_euco else ("start_date", "event_type"),
        })
    return out


_AGENDA_TIME = re.compile(r'<time[^>]*datetime="[^"]*"[^>]*>([^<]*)</time>')
_AGENDA_VENUE = re.compile(r'class="small">\s*([^<]+?)\s*</span>')
_AGENDA_COL8 = re.compile(r'col-lg-8.*?<p>(.*?)</p>', re.S)
_AGENDA_DISP = re.compile(r'(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2}))?')


def parse_ep_agenda(html: str, cfg: Dict, today: date) -> List[Dict]:
    """EP es_agenda component (delegations calendar): one event per
    `es_agenda-meeting-more-info` block — <time> date+local-time, span.small venue,
    col-lg-8 title. Tagged ep_committee_code='DELE' so it filters as 'Delegations'."""
    out: List[Dict] = []
    seen: set = set()
    limit = cfg.get("limit", 80)
    for block in html.split("es_agenda-meeting-more-info")[1:]:
        if len(out) >= limit:
            break
        block = block[:1600]
        tm = _AGENDA_TIME.search(block)
        if not tm:
            continue
        dm = _AGENDA_DISP.search(_clean(tm.group(1)))
        if not dm:
            continue
        try:
            start = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
        except ValueError:
            continue
        if start < today:
            continue
        col8 = _AGENDA_COL8.search(block)
        kind_txt = _clean(col8.group(1)) if col8 else ""
        # The aggregate delegations calendar names only the meeting TYPE per row
        # (e.g. "Ordinary meeting"), not which delegation — make the label clear.
        if not kind_txt:
            kind_txt = "meeting"
        title = kind_txt if "delegation" in kind_txt.lower() else f"Delegation — {kind_txt}"
        venue_m = _AGENDA_VENUE.search(block)
        venue = _clean(venue_m.group(1)) if venue_m else None
        st_time = f"{dm.group(4)}:{dm.group(5)}:00" if dm.group(4) else None
        key = f"dele-{start.isoformat()}-{st_time or ''}-{re.sub(r'[^a-z0-9]+', '-', (venue or kind_txt).lower())[:40]}"
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title[:480], "start_date": start, "all_day": st_time is None,
            "start_time": st_time, "venue": venue,
            "institution": "EP", "event_type": "committee_meeting",
            "ep_committee_code": "DELE", "organiser": "EP Delegation",
            "source": cfg["source"], "external_id": key, "source_url": cfg["url"],
        })
    return out


def scrape_event_source(cfg: Dict, fetcher, today: Optional[date] = None) -> List[Dict]:
    today = today or date.today()
    try:
        res = fetcher.fetch(cfg["url"], expand_accordions=False, strip_chrome=False)
        html = res.html or ""
    except Exception as e:
        logger.warning(f"[BESPOKE-EVENTS] fetch failed {cfg['url']}: {e}")
        return []
    kind = cfg.get("kind")
    if kind == "council":
        events = parse_council(html, cfg, today)
    elif kind == "ep_agenda":
        events = parse_ep_agenda(html, cfg, today)
    else:
        events = parse_generic(html, cfg, today)
    if not events:
        logger.info(f"[BESPOKE-EVENTS] 0 upcoming {cfg['institution']} {cfg['url']}")
    return events
