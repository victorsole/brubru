"""
Brussels lobbies — org-type classification + per-org news detection.

Powers the proprietary "Brussels lobbies" product (/api/v2/proprietary/
brussels-lobbies). Two pure-ish helpers:

  classify(registration_category)  -> (org_type, eutr_section, for_profit)
  detect_and_fetch(website_url)    -> NewsResult (source kind, feed url, items)

News detection is multi-signal, most-reliable-first:
  1. RSS / Atom autodiscovery (<link rel="alternate">) + a few common feed paths.
  2. sitemap.xml — recent <lastmod> on news-like URLs.
  3. Validated path probe (/news, /press, ...) WITH a soft-404 guard (many sites
     return HTTP 200 for every path, so we compare against a known-bogus path).

Only RSS/Atom/sitemap yield dated items; an html-only news section is recorded as
"active" with a feed/index URL but no machine-readable items (item extraction
from arbitrary HTML is unreliable and left to a later pass).

No Anthropic / Claude API (non-chat code). Stdlib + requests + feedparser + bs4.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
_TIMEOUT = 12

# ─────────────────────── Classification ──────────────────────────────────
# registration_category (raw EUTR value) -> (org_type, eutr_section, for_profit)

_CATEGORY_MAP: dict[str, tuple[str, str, Optional[bool]]] = {
    "Professional consultancies":                    ("consultancy",       "I",   True),
    "Law firms":                                     ("law_firm",          "I",   True),
    "Self-employed individuals":                     ("self_employed",     "I",   True),
    "Self-employed consultants":                     ("self_employed",     "I",   True),
    "Companies & groups":                            ("company",           "II",  True),
    "Trade and business associations":               ("trade_association", "II",  False),
    "Trade unions and professional associations":    ("trade_union",       "II",  False),
    "Other organisations, public or mixed entities": ("public_authority",  "VI",  None),
    "Non-governmental organisations, platforms and networks and similar":
                                                     ("ngo",               "III", False),
    "Think tanks and research institutions":         ("think_tank",        "IV",  False),
    "Academic institutions":                         ("academic",          "IV",  False),
    "Organisations representing churches and religious communities":
                                                     ("religious",         "V",   False),
    "Associations and networks of public authorities":
                                                     ("public_authority",  "VI",  False),
    "Entities, offices or networks established by third countries":
                                                     ("third_country",     "VI",  None),
}

# European-ish HQ countries — a company HQ'd OUTSIDE this set is flagged
# is_global_corp (its website newsroom is likely global PR, not EU affairs).
_EUROPEAN_COUNTRIES = {
    "AUSTRIA", "BELGIUM", "BULGARIA", "CROATIA", "CYPRUS", "CZECH REPUBLIC", "CZECHIA",
    "DENMARK", "ESTONIA", "FINLAND", "FRANCE", "GERMANY", "GREECE", "HUNGARY",
    "IRELAND", "ITALY", "LATVIA", "LITHUANIA", "LUXEMBOURG", "MALTA", "NETHERLANDS",
    "POLAND", "PORTUGAL", "ROMANIA", "SLOVAKIA", "SLOVENIA", "SPAIN", "SWEDEN",
    "ICELAND", "LIECHTENSTEIN", "NORWAY", "SWITZERLAND", "UNITED KINGDOM",
}


def normalise_category(raw: Optional[str]) -> Optional[str]:
    """Repair the legacy &-dropped variant so old + new rows classify alike."""
    if not raw:
        return raw
    # "Companies  groups" (double space where & was) -> "Companies & groups"
    return re.sub(r"\bCompanies\s{2,}groups\b", "Companies & groups", raw).strip()


def classify(registration_category: Optional[str]) -> tuple[str, Optional[str], Optional[bool]]:
    cat = normalise_category(registration_category)
    if cat and cat in _CATEGORY_MAP:
        return _CATEGORY_MAP[cat]
    return ("other", None, None)


def is_global_corp(org_type: str, head_office_country: Optional[str]) -> bool:
    if org_type != "company":
        return False
    c = (head_office_country or "").strip().upper()
    return bool(c) and c not in _EUROPEAN_COUNTRIES


# ─────────────────────── News detection ──────────────────────────────────

@dataclass
class NewsItem:
    guid: str
    url: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    published_at: Optional[datetime]


def _is_future(dt: Optional[datetime]) -> bool:
    """True if dt is meaningfully in the future. Big corporate sitemaps + RSS
    sometimes carry financial-calendar / upcoming-event dates (e.g. an AGM in
    November); those are not 'published news' and must not lead order=recent.
    A 2-day skew tolerates timezone / clock drift."""
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - now).total_seconds() > 2 * 86400


def _drop_future(items: list["NewsItem"]) -> list["NewsItem"]:
    return [i for i in items if not _is_future(i.published_at)]


@dataclass
class NewsResult:
    status: str = "none"          # active | none | error | blocked
    source_kind: Optional[str] = None  # rss | atom | sitemap | html
    feed_url: Optional[str] = None
    items: list[NewsItem] = field(default_factory=list)

    @property
    def last_item_date(self) -> Optional[datetime]:
        dates = [i.published_at for i in self.items if i.published_at]
        return max(dates) if dates else None


_COMMON_FEED_PATHS = ["/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml",
                      "/en/rss.xml", "/?feed=rss2", "/index.xml", "/atom.xml",
                      "/news/feed", "/news/rss", "/blog/feed"]
_NEWS_PATHS = ["/news", "/news/", "/press", "/press-releases", "/media",
               "/newsroom", "/blog", "/news-events", "/publications",
               "/media-centre", "/press-room", "/en/news", "/actualites",
               "/noticias", "/nieuws", "/aktuelles", "/latest", "/updates"]
_NEWS_URL_HINT = re.compile(r"/(news|press|media|blog|actualit|noticia|nieuws|aktuell|article|publicat)", re.I)


def _norm_url(url: str) -> Optional[str]:
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _get(session: requests.Session, url: str, **kw):
    return session.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True, **kw)


def _parse_published(entry) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None) or entry.get(key) if hasattr(entry, "get") else getattr(entry, key, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _feed_items(feed_url: str, content: bytes | str, max_items: int) -> list[NewsItem]:
    parsed = feedparser.parse(content)
    items: list[NewsItem] = []
    for e in parsed.entries[:max_items]:
        link = e.get("link")
        guid = e.get("id") or e.get("guid") or link
        if not guid:
            continue
        summary = e.get("summary") or e.get("description")
        if summary:
            summary = BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)[:1000]
        items.append(NewsItem(
            guid=guid, url=link, title=(e.get("title") or "").strip() or None,
            summary=summary, published_at=_parse_published(e),
        ))
    return items


def _discover_feeds(base: str, home_html: str) -> list[str]:
    feeds: list[str] = []
    try:
        soup = BeautifulSoup(home_html, "html.parser")
        for ln in soup.find_all("link", rel=lambda v: v and "alternate" in v):
            typ = (ln.get("type") or "").lower()
            href = ln.get("href")
            if href and ("rss" in typ or "atom" in typ or "xml" in typ):
                feeds.append(urljoin(base + "/", href))
    except Exception:
        pass
    return feeds


def detect_and_fetch(website_url: Optional[str], max_items: int = 20) -> NewsResult:
    """Detect a news source for one org and return recent items where machine-readable."""
    url = _norm_url(website_url or "")
    if not url:
        return NewsResult(status="none")
    base = _base(url)
    session = requests.Session()

    # 1) homepage + RSS/Atom autodiscovery
    home_html = ""
    try:
        r = _get(session, url)
        if r.status_code in (401, 403, 429):
            return NewsResult(status="blocked")
        if r.status_code < 400 and r.text:
            home_html = r.text
    except requests.RequestException:
        # try base if the stored URL was a deep path
        try:
            r = _get(session, base)
            if r.status_code in (401, 403, 429):
                return NewsResult(status="blocked")
            home_html = r.text if r.status_code < 400 else ""
        except requests.RequestException:
            return NewsResult(status="error")

    candidate_feeds = _discover_feeds(base, home_html)
    candidate_feeds += [base + p for p in _COMMON_FEED_PATHS]
    seen = set()
    for fu in candidate_feeds:
        if fu in seen:
            continue
        seen.add(fu)
        if "comment" in fu.lower():   # WordPress comments feed — not org news
            continue
        try:
            fr = _get(session, fu)
        except requests.RequestException:
            continue
        if fr.status_code >= 400 or not fr.content:
            continue
        ctype = (fr.headers.get("content-type") or "").lower()
        body = fr.content
        # quick sniff: must look like a feed
        head = body[:600].lstrip().lower()
        if not (b"<rss" in head or b"<feed" in head or b"<?xml" in head or "xml" in ctype):
            continue
        items = _drop_future(_feed_items(fu, body, max_items))
        if items:
            kind = "atom" if b"<feed" in head else "rss"
            return NewsResult(status="active", source_kind=kind, feed_url=fu, items=items)

    # 2) sitemap.xml — recent lastmod on news-like URLs
    try:
        sm = _get(session, base + "/sitemap.xml")
        if sm.status_code < 400 and b"<urlset" in sm.content[:2000] or b"<sitemapindex" in sm.content[:2000]:
            items = _drop_future(_sitemap_items(session, base, sm.content, max_items))
            if items:
                return NewsResult(status="active", source_kind="sitemap",
                                  feed_url=base + "/sitemap.xml", items=items)
    except requests.RequestException:
        pass

    # 3) validated path probe with soft-404 guard
    news_url = _probe_news_path(session, base)
    if news_url:
        return NewsResult(status="active", source_kind="html", feed_url=news_url, items=[])

    return NewsResult(status="none")


def _sitemap_items(session: requests.Session, base: str, content: bytes, max_items: int) -> list[NewsItem]:
    try:
        soup = BeautifulSoup(content, "xml")
    except Exception:
        return []
    # sitemap index -> follow the first news-like child sitemap
    if soup.find("sitemapindex"):
        for sm in soup.find_all("loc")[:10]:
            loc = sm.get_text(strip=True)
            if _NEWS_URL_HINT.search(loc):
                try:
                    child = _get(session, loc)
                    if child.status_code < 400:
                        return _sitemap_items(session, base, child.content, max_items)
                except requests.RequestException:
                    continue
        return []
    rows: list[tuple[Optional[datetime], str]] = []
    for u in soup.find_all("url"):
        loc_el = u.find("loc")
        if not loc_el:
            continue
        loc = loc_el.get_text(strip=True)
        if not _NEWS_URL_HINT.search(loc):
            continue
        lm = u.find("lastmod")
        dt = None
        if lm:
            dt = _parse_iso(lm.get_text(strip=True))
        rows.append((dt, loc))
    rows.sort(key=lambda r: (r[0] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    items = []
    for dt, loc in rows[:max_items]:
        items.append(NewsItem(guid=loc, url=loc, title=_slug_title(loc), summary=None, published_at=dt))
    return items


def _probe_news_path(session: requests.Session, base: str) -> Optional[str]:
    # soft-404 baseline
    bogus_len = -1
    try:
        b = _get(session, base + "/brubru-nonexistent-probe-9z9z")
        if b.status_code == 200:
            bogus_len = len(b.content or b"")
    except requests.RequestException:
        pass
    for p in _NEWS_PATHS:
        try:
            r = _get(session, base + p)
        except requests.RequestException:
            continue
        if r.status_code != 200:
            continue
        ctype = (r.headers.get("content-type") or "").lower()
        if "html" not in ctype:
            continue
        n = len(r.content or b"")
        if n < 1500:
            continue
        # soft-404 guard: if the site returns 200 for everything, the bogus page
        # has similar length -> reject unless this page is materially larger.
        if bogus_len >= 0 and abs(n - bogus_len) < max(800, int(bogus_len * 0.1)):
            continue
        return base + p
    return None


_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    m = _ISO_RE.match(s.strip())
    if not m:
        return None
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
    except ValueError:
        return None


def _slug_title(url: str) -> Optional[str]:
    seg = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not seg:
        return None
    seg = re.sub(r"\.(html?|php|aspx?)$", "", seg)
    seg = seg.replace("-", " ").replace("_", " ").strip()
    return seg[:200].title() if seg else None
