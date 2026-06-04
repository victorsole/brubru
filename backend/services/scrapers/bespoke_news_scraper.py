"""
Bespoke per-site news scraper (MEUB "News") — the holdout EU bodies that have no
RSS and don't use the EC ECL component. Each is a distinct JS-rendered CMS, so we
render with Playwright and extract items by a per-site **news-detail link rule**
(the URL signature that distinguishes real articles from nav). Date is taken from
the URL where the site encodes it.

NO LLM / NO Anthropic. Link rules discovered 1 Jun 2026 by harvesting each site's
rendered DOM. Many sites wrap the article link around an image (empty anchor text),
so the title resolver falls back: anchor text -> aria-label/title attr -> img alt
-> slug-derived headline. CJEU press releases are dated PDFs on the jcms query page
(rich anchor titles); EEAS surfaces its delegation press releases (HQ items AJAX-load
and are not captured). EDPS, EUAA, CdT use the slug/attr fallback.
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date
from typing import Dict, List
from urllib.parse import urljoin, urlparse, unquote

from services.scrapers.dg_news_scraper import _clean, _canon_url, _slug_id

logger = logging.getLogger(__name__)


def _base(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _attr(name: str, attrs: str):
    m = re.search(name + r'="([^"]*)"', attrs)
    return m.group(1) if m else None


def _slug_title(path: str) -> str:
    """Derive a readable headline from the URL slug (sentence case).

    Used when the article anchor wraps only an image / icon and the real
    title lives in a sibling heading node that we don't have a handle on.
    """
    seg = [x for x in path.rstrip("/").split("/") if x][-1]
    seg = seg[:-3] if seg.endswith("_en") else seg
    seg = re.sub(r"^\d{4,}[_-]?", "", seg)            # strip leading id/date
    text = unquote(seg).replace("-", " ").replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return (text[:1].upper() + text[1:]) if text else ""


def _resolve_title(attrs: str, inner: str, path: str) -> str | None:
    """Title resolution: anchor text -> aria-label/title attr -> img alt -> slug."""
    t = _clean(_html.unescape(inner))
    if 15 <= len(t) <= 220:
        return t
    for a in ("aria-label", "title"):
        v = _attr(a, attrs)
        if v:
            v = _clean(v)
            if 15 <= len(v) <= 220:
                return v
    alt = re.search(r'alt="([^"]{15,220})"', inner)
    if alt:
        return _clean(alt.group(1))
    st = _slug_title(path)
    return st if len(st) >= 12 else None


# Per-site config: institution, source_key, url (news page), link_re (matched
# against the href PATH), optional date_re (groups -> y[,m[,d]]), item_type.
BESPOKE_SOURCES: List[Dict] = [
    {"institution": "COUNCIL", "url": "https://www.consilium.europa.eu/en/press/press-releases/",
     "link_re": r"/en/press/press-releases/\d{4}/\d{2}/\d{2}/[^/]+", "date_re": r"/press-releases/(\d{4})/(\d{2})/(\d{2})/", "type": "press"},
    {"institution": "ECA", "url": "https://www.eca.europa.eu/en/all-news",
     "link_re": r"/en/news/[A-Za-z0-9][A-Za-z0-9_-]{4,}", "date_re": r"NEWS(\d{4})[_-](\d{2})", "type": "news"},
    {"institution": "EIB", "url": "https://www.eib.org/en/press/all/index.htm",
     "link_re": r"/en/press/(?:all|news)/[a-z0-9][a-z0-9-]{8,}", "type": "press"},
    {"institution": "COR", "url": "https://www.cor.europa.eu/en/news",
     "link_re": r"/en/news/(?:stories/)?[a-z0-9][a-z0-9-]{8,}", "type": "news"},
    {"institution": "OMBUDSMAN", "url": "https://www.ombudsman.europa.eu/en/news-documents",
     "link_re": r"/en/news-document/en/\d+", "type": "news"},
    {"institution": "ECHA", "url": "https://echa.europa.eu/news",
     "link_re": r"/-/[a-z][a-z0-9-]{15,}", "type": "news"},
    {"institution": "ENISA", "url": "https://www.enisa.europa.eu/news",
     "link_re": r"/news/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "EUIPO", "url": "https://www.euipo.europa.eu/en/news-and-events",
     "link_re": r"/en/news/(?:podcasts/)?[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "EUAA", "url": "https://www.euaa.europa.eu/news-events/press-releases",
     "link_re": r"/news-events/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "EUROJUST", "url": "https://www.eurojust.europa.eu/media-and-events/press-releases-and-news",
     "link_re": r"/news/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "FRA", "url": "https://fra.europa.eu/en/news-and-events/news",
     "link_re": r"/en/news/\d{4}/[a-z0-9-]{5,}", "date_re": r"/news/(\d{4})/", "type": "news"},
    {"institution": "EU-OSHA", "source_key": "OSHA", "url": "https://osha.europa.eu/en/oshnews",
     "link_re": r"/en/oshnews/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "ACER", "url": "https://www.acer.europa.eu/news-and-events/news",
     "link_re": r"/news/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "ECDC", "url": "https://www.ecdc.europa.eu/en/news-events",
     "link_re": r"/en/news-events/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "CEPOL", "url": "https://www.cepol.europa.eu/newsroom/news/news",
     "link_re": r"/newsroom/news/[a-z][a-z0-9-]{9,}", "type": "news"},
    {"institution": "EIT", "url": "https://www.eit.europa.eu/news-events/news",
     "link_re": r"/news-events/news/[a-z][a-z0-9-]{5,}", "type": "news"},
    {"institution": "CPVO", "url": "https://cpvo.europa.eu/en/news-and-events/news",
     "link_re": r"/en/news-and-events/news/[a-z][a-z0-9-]{5,}", "type": "news"},
    {"institution": "CDT", "url": "https://cdt.europa.eu/en/news",
     "link_re": r"^/en/news/[a-z0-9][a-z0-9-]{5,}$", "type": "news"},
    # --- added 1 Jun 2026: image-wrapped-anchor sites (title via slug fallback) ---
    {"institution": "EDPS", "url": "https://www.edps.europa.eu/press-publications/press-news/press-releases_en",
     "link_re": r"^/press-publications/press-news/press-releases/\d{4}/[a-z0-9-]{8,}",
     "date_re": r"/press-releases/(\d{4})/", "type": "press"},
    {"institution": "EUAA", "url": "https://www.euaa.europa.eu/news-events/press-releases",
     "link_re": r"^/news-events/[a-z][a-z0-9-]{9,}$",
     "exclude": ["/news-events/press-releases", "/news-events/news", "/news-events/events"], "type": "news"},
    # EEAS is handled by a dedicated card parser (see EEAS_SOURCES / scrape_eeas)
    # because its filter pages are card aggregators with real titles, not a single
    # link signature.
    # CJEU: the jcms query page lists every press release as a dated PDF with a
    # rich anchor title; newest-first, so cap to keep the archive from flooding.
    {"institution": "CJEU", "url": "https://curia.europa.eu/jcms/jcms/Jo2_7052/en/?jsp=jcore/query.jsp",
     "link_re": r"(?:^|/)upload/docs/application/pdf/\d{4}-\d{2}/cp\d+en\.pdf$",
     "date_re": r"/pdf/(\d{4})-(\d{2})/", "type": "press", "limit": 60},
]

_A = re.compile(r'<a\b([^>]*)\bhref="([^"#?]+)"([^>]*)>(.*?)</a>', re.S)


def parse_bespoke(html: str, cfg: Dict) -> List[Dict]:
    # Relative hrefs resolve against a page's <base href> if present (CJEU sets
    # <base href=".../site/">), otherwise against the page URL.
    bm = re.search(r'<base[^>]+href="([^"]+)"', html or "", re.I)
    resolve_base = bm.group(1) if bm else cfg["url"]
    link_re = re.compile(cfg["link_re"])
    date_re = re.compile(cfg["date_re"]) if cfg.get("date_re") else None
    exclude = set(cfg.get("exclude") or [])
    limit = cfg.get("limit")
    out: List[Dict] = []
    seen: set = set()
    for m in _A.finditer(html or ""):
        if limit and len(out) >= limit:
            break
        pre, href, post, inner = m.group(1), m.group(2), m.group(3), m.group(4)
        attrs = pre + post
        path = urlparse(href).path
        if path.rstrip("/") in exclude:
            continue
        if not link_re.search(path):
            continue
        title = _resolve_title(attrs, inner, path)
        if not title:
            continue
        url = href if href.startswith("http") else urljoin(resolve_base, href)
        key = _canon_url(url)
        if key in seen:
            continue
        seen.add(key)
        nd = None
        if date_re:
            dm = date_re.search(url)
            if dm:
                g = dm.groups()
                try:
                    if len(g) >= 3:
                        nd = date(int(g[0]), int(g[1]), int(g[2]))
                    elif len(g) == 2:
                        nd = date(int(g[0]), int(g[1]), 1)
                    elif len(g) == 1:
                        nd = date(int(g[0]), 1, 1)
                except ValueError:
                    nd = None
        out.append({
            "title": title[:480], "summary": None, "news_date": nd, "image_url": None,
            "source_url": url, "external_id": _slug_id(url), "item_type": cfg.get("type", "news"),
            "institution": cfg["institution"], "commission_dg": None,
            "source_key": cfg.get("source_key") or cfg["institution"],
            "entry_key": key,
        })
    return out


def scrape_bespoke(cfg: Dict, fetcher) -> List[Dict]:
    try:
        res = fetcher.fetch(cfg["url"], expand_accordions=False, strip_chrome=False)
    except Exception as e:
        logger.warning(f"[BESPOKE-NEWS] fetch failed {cfg['url']}: {e}")
        return []
    items = parse_bespoke(res.html or "", cfg)
    if not items:
        logger.info(f"[BESPOKE-NEWS] 0 items {cfg['institution']} {cfg['url']}")
    return items


# ---------------------------------------------------------------------------
# EEAS (European External Action Service)
#
# EEAS filter pages are server-rendered "card" aggregators: each result card
# carries the REAL title (h5 card-title) and links to wherever the item lives
# (HQ /eeas/<slug>_en, /delegations/<country>/..., mission pages, or EXTERNAL
# Commission/Council pages). We keep EEAS-internal links only — external ones
# are already covered by the Commission/Council scrapers — and take the title
# from the card so we don't fall back to slugs. One parser, run across every
# EEAS category the user curated (press releases, statements, speeches, op-eds,
# reports, publications, campaigns, stories).
# ---------------------------------------------------------------------------

EEAS_SOURCES: List[Dict] = [
    {"type": "press",       "url": "https://www.eeas.europa.eu/filter-page/press-material_en?f%5B0%5D=pm_category%3APress%20release"},
    {"type": "statement",   "url": "https://www.eeas.europa.eu/filter-page/press-material_en?f%5B0%5D=pm_category%3AStatement/Declaration"},
    {"type": "speech",      "url": "https://www.eeas.europa.eu/filter-page/press-material_en?f%5B0%5D=pm_category%3ASpeech/Remark"},
    {"type": "oped",        "url": "https://www.eeas.europa.eu/filter-page/press-material_en?f%5B0%5D=pm_category%3AOp-ed"},
    {"type": "report",      "url": "https://www.eeas.europa.eu/filter-page/publications_en?f%5B0%5D=publication_type%3AReport"},
    {"type": "publication", "url": "https://www.eeas.europa.eu/filter-page/publications_en?f%5B0%5D=publication_type%3AMiscellaneous"},
    {"type": "publication", "url": "https://www.eeas.europa.eu/filter-page/publications_en"},
    {"type": "campaign",    "url": "https://www.eeas.europa.eu/eeas/campaigns_en"},
    {"type": "news",        "url": "https://www.eeas.europa.eu/search_en?fulltext=&created=&created_1=&f%5B0%5D=ct%3Astory"},
]

_EEAS_CARD = re.compile(r'<div class="card\b.*?(?=<div class="card\b|<footer|</main)', re.S)
_EEAS_TITLE = re.compile(r'card-title[^"]*"[^>]*>\s*<a[^>]*href="([^"#?]+)"[^>]*>(.*?)</a>', re.S)
_EEAS_HOST = "eeas.europa.eu"
_EEAS_LIMIT = 50


def _eeas_internal(href: str) -> bool:
    """Keep EEAS-internal links; drop external Commission/Council mirrors."""
    if href.startswith("http"):
        return _EEAS_HOST in urlparse(href).netloc
    return href.startswith("/") and not href.startswith("//")


def parse_eeas_cards(html: str, src: Dict) -> List[Dict]:
    out: List[Dict] = []
    seen: set = set()
    item_type = src.get("type", "news")
    for block in _EEAS_CARD.finditer(html or ""):
        if len(out) >= _EEAS_LIMIT:
            break
        tm = _EEAS_TITLE.search(block.group(0))
        if not tm:
            continue
        href = tm.group(1)
        if not _eeas_internal(href):
            continue
        title = _clean(_html.unescape(tm.group(2)))
        if not (15 <= len(title) <= 300):
            continue
        url = href if href.startswith("http") else urljoin("https://www.eeas.europa.eu/", href)
        key = _canon_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title[:480], "summary": None, "news_date": None, "image_url": None,
            "source_url": url, "external_id": _slug_id(url), "item_type": item_type,
            "institution": "EEAS", "commission_dg": None, "source_key": "EEAS",
            "entry_key": key,
        })
    return out


def scrape_eeas(fetcher) -> List[Dict]:
    """Scrape every curated EEAS filter page; dedup across them by canonical URL."""
    items: List[Dict] = []
    seen: set = set()
    for src in EEAS_SOURCES:
        try:
            res = fetcher.fetch(src["url"], expand_accordions=False, strip_chrome=False)
        except Exception as e:
            logger.warning(f"[EEAS-NEWS] fetch failed {src['url']}: {e}")
            continue
        for it in parse_eeas_cards(res.html or "", src):
            if it["entry_key"] in seen:
                continue
            seen.add(it["entry_key"])
            items.append(it)
    if not items:
        logger.info("[EEAS-NEWS] 0 items across all EEAS sources")
    return items
