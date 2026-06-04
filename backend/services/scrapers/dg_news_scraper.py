"""
European Commission DG / agency NEWS scraper (MEUB "News" source).

Parses the EC "What's on" Drupal news component (ECL `ecl-content-item` with an
`ecl-content-item__image`, a `<time datetime>`, a title link and a description),
shared across the DG / agency newsrooms. Image-rich, for a beautiful feed.

NO LLM / NO Anthropic. DG subdomains render to a normal browser-UA fetch (no WAF);
SPA / presscorner pages fall back to the Playwright fetcher and are best-effort.
Source registry: dg_news_sources.py.
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_TAG = re.compile(r"<[^>]+>")

_ARTICLE = re.compile(r'<article\s+class="ecl-content-item.*?</article>', re.S)
_IMG = re.compile(r'ecl-content-item__image"[^>]*\ssrc="([^"]+)"', re.S)
_TIME = re.compile(r'<time[^>]*\sdatetime="(\d{4}-\d{2}-\d{2})', re.S)
_TITLE = re.compile(r'ecl-content-block__title"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DESC = re.compile(r'ecl-content-block__description"[^>]*>\s*(?:<p[^>]*>)?(.*?)(?:</p>|</div>)', re.S)
_META = re.compile(r'ecl-content-block__primary-meta-item">\s*([^<]+?)\s*</li>', re.S)


# Article subdomain -> canonical DG. An article's TRUE department is its home
# subdomain, not the (possibly hub-filter) page that surfaced it — this fixes
# cross-listed duplicates being tagged to the wrong DG.
_SUBDOMAIN_DG = {
    "agriculture.ec.europa.eu": "AGRI", "climate.ec.europa.eu": "CLIMA",
    "digital-strategy.ec.europa.eu": "CNECT", "competition-policy.ec.europa.eu": "COMP",
    "digital-markets-act.ec.europa.eu": "COMP", "defence-industry-space.ec.europa.eu": "DEFIS",
    "eu-space.europa.eu": "DEFIS", "copernicus.eu": "DEFIS", "www.copernicus.eu": "DEFIS",
    "economy-finance.ec.europa.eu": "ECFIN", "employment-social-affairs.ec.europa.eu": "EMPL",
    "energy.ec.europa.eu": "ENER", "enlargement.ec.europa.eu": "ENEST",
    "neighbourhood-enlargement.ec.europa.eu": "ENEST", "environment.ec.europa.eu": "ENV",
    "anti-fraud.ec.europa.eu": "OLAF", "civil-protection-humanitarian-aid.ec.europa.eu": "ECHO",
    "finance.ec.europa.eu": "FISMA", "fpi.ec.europa.eu": "FPI",
    "food.ec.europa.eu": "SANTE", "health.ec.europa.eu": "SANTE",
    "single-market-economy.ec.europa.eu": "GROW", "international-partnerships.ec.europa.eu": "INTPA",
    "joint-research-centre.ec.europa.eu": "JRC", "oceans-and-fisheries.ec.europa.eu": "MARE",
    "north-africa-middle-east-gulf.ec.europa.eu": "MENA", "home-affairs.ec.europa.eu": "HOME",
    "transport.ec.europa.eu": "MOVE", "research-and-innovation.ec.europa.eu": "RTD",
    "projects.research-and-innovation.ec.europa.eu": "RTD", "taxation-customs.ec.europa.eu": "TAXUD",
    "policy.trade.ec.europa.eu": "TRADE", "translation.ec.europa.eu": "DGT",
    "cordis.europa.eu": "RTD",
}


def dg_from_url(url: str) -> Optional[str]:
    """The article's true DG from its own URL (subdomain/path), or None."""
    try:
        p = urlparse(url)
    except Exception:
        return None
    host, path = p.netloc.lower(), p.path.lower()
    if "health-emergency-preparedness-and-response-hera" in path:
        return "HERA"
    if host == "ec.europa.eu":
        if "/eurostat" in path:
            return "ESTAT"
        if "/regional_policy" in path:
            return "REGIO"
        if "/environment" in path:
            return "ENV"
    return _SUBDOMAIN_DG.get(host)


def _canon_url(url: str) -> str:
    """Canonical article identity: scheme://host/path (no query/fragment)."""
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}"
    except Exception:
        return url


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", s or ""))).strip()


def _slug_id(href: str) -> str:
    path = urlparse(href).path.rstrip("/")
    return (path.rsplit("/", 1)[-1] or path)[:200]


def _item_type(meta: Optional[str], default: str) -> str:
    m = (meta or "").lower()
    if "publication" in m or "report" in m or "study" in m or "factsheet" in m:
        return "publication"
    if "story" in m or "explained" in m:
        return "story"
    if "press" in m or "statement" in m or "speech" in m:
        return "press"
    if "news" in m:
        return "news"
    return default or "news"


def fetch_html(url: str, *, spa: bool = False) -> str:
    if not spa:
        try:
            import httpx
            r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": _UA})
            if r.status_code == 200 and len(r.text) > 1500:
                return r.text
            logger.info(f"[DG-NEWS] {url} -> HTTP {r.status_code} len {len(r.text)}; trying WAF browser")
        except Exception as e:
            logger.info(f"[DG-NEWS] httpx failed for {url}: {e}; trying WAF browser")
    try:
        from services.scrapers.waf_browser_fetcher import fetch_one
        return fetch_one(url, expand_accordions=False, strip_chrome=False).html or ""
    except Exception as e:
        logger.warning(f"[DG-NEWS] WAF browser failed for {url}: {e}")
        return ""


def parse_ecl_news(html: str, base_url: str, default_type: str) -> List[Dict]:
    """Parse ECL news cards -> normalised item dicts (with image + date + summary)."""
    out: List[Dict] = []
    seen: set = set()
    for m in _ARTICLE.finditer(html or ""):
        block = m.group(0)
        tm = _TITLE.search(block)
        if not tm:
            continue
        href, title = tm.group(1), _clean(tm.group(2))
        if not title:
            continue
        ext = _slug_id(href)
        if ext in seen:
            continue
        seen.add(ext)
        dm = _TIME.search(block)
        nd = None
        if dm:
            try:
                nd = datetime.strptime(dm.group(1), "%Y-%m-%d").date()
            except ValueError:
                nd = None
        img = _IMG.search(block)
        desc = _DESC.search(block)
        meta = _META.search(block)
        out.append({
            "title": title[:480],
            "summary": (_clean(desc.group(1))[:600] if desc else None),
            "news_date": nd,
            "image_url": _html.unescape(img.group(1)) if img else None,
            "source_url": urljoin(base_url, href),
            "external_id": ext,
            "item_type": _item_type(meta.group(1) if meta else None, default_type),
        })
    return out


def parse_rss(xml_text: str, base_url: str, default_type: str) -> List[Dict]:
    """Parse an RSS 2.0 / Atom feed -> normalised item dicts. The universal path
    for the many EU bodies (Council, ECB, EIB, EP, agencies) that don't use the
    EC ECL component but do publish a feed."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    out: List[Dict] = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except Exception:
        return out
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]  # strip namespaces
    entries = root.findall(".//item") or root.findall(".//entry")
    seen: set = set()
    for e in entries:
        title = (e.findtext("title") or "").strip()
        if not title:
            continue
        link = ""
        le = e.find("link")
        if le is not None:
            link = (le.text or le.get("href") or "").strip()
        if not link:
            for l in e.findall("link"):
                if l.get("href"):
                    link = l.get("href"); break
        if not link:
            continue
        ext = _slug_id(link)
        if ext in seen:
            continue
        seen.add(ext)
        nd = None
        ds = e.findtext("pubDate") or e.findtext("published") or e.findtext("updated") or e.findtext("date") or ""
        if ds:
            try:
                nd = parsedate_to_datetime(ds).date()
            except Exception:
                try:
                    nd = datetime.fromisoformat(ds[:10]).date()
                except Exception:
                    nd = None
        img = None
        enc = e.find("enclosure")
        if enc is not None and enc.get("url"):
            img = enc.get("url")
        if not img:
            mc = e.find("content")
            if mc is not None and mc.get("url"):
                img = mc.get("url")
        out.append({
            "title": title[:480],
            "summary": (_clean(e.findtext("description") or e.findtext("summary") or "")[:600]) or None,
            "news_date": nd,
            "image_url": img,
            "source_url": urljoin(base_url, link),
            "external_id": ext,
            "item_type": default_type,
        })
    return out


def scrape_source(src: Dict) -> List[Dict]:
    """Fetch + parse one news source into tagged item dicts."""
    kind = src.get("kind", "ecl")
    if kind == "rss":
        try:
            import httpx
            r = httpx.get(src["url"], timeout=30, follow_redirects=True, headers={"User-Agent": _UA})
            items = parse_rss(r.text, src["url"], src.get("default_type", "news")) if r.status_code == 200 else []
        except Exception as e:
            logger.info(f"[DG-NEWS] RSS fetch failed {src['url']}: {e}")
            items = []
        for it in items:
            it["institution"] = src.get("institution", "COMMISSION")
            it["commission_dg"] = src.get("dg")
            it["source_key"] = src.get("source_key") or src.get("dg") or src.get("agency") or src.get("institution") or "EU"
            it["entry_key"] = _canon_url(it["source_url"])
        if not items:
            logger.info(f"[DG-NEWS] 0 RSS items from {src['url']}")
        return items

    spa = src.get("default_type") == "press" or "presscorner" in src["url"]
    html = fetch_html(src["url"], spa=spa)
    if not html:
        logger.warning(f"[DG-NEWS] no HTML for {src['url']}")
        return []
    items = parse_ecl_news(html, src["url"], src.get("default_type", "news"))
    reg_dg = src.get("dg")
    agency = src.get("agency")
    for it in items:
        # DG = the article's own subdomain (correct for cross-listed items),
        # falling back to the source registry's DG.
        url_dg = dg_from_url(it["source_url"])
        dg = url_dg or reg_dg
        it["institution"] = src.get("institution", "COMMISSION")
        it["commission_dg"] = dg
        it["source_key"] = dg or agency or "EC"
        # Canonical identity = the article URL -> the SAME article found on
        # multiple source pages dedups to one row.
        it["entry_key"] = _canon_url(it["source_url"])
    if not items:
        logger.info(f"[DG-NEWS] 0 items parsed from {src['url']}")
    return items
