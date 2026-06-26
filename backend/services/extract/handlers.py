"""Per-platform parsers (Phase 1, step 1.1): listing HTML -> list[Item].

Each handler turns a listing page into 5-datapoint Items (title, public_url, date,
summary). ECL is the precise case; Drupal covers the .teaser/.card/.views-row
variants; a generic card/anchor parser backstops the JS-rendered platforms after
the browser fetch. The shared smart-date resolver (step 1.4) dates each card.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_DMY = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(20\d{2})\b", re.I)
_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_LIST_HREF = re.compile(r"/(news|events?|publications?|press|media|consultations?)/", re.I)
_NOISE = re.compile(r"(cookie|privacy|accessibility|sitemap|/login|sign[- ]?in|subscribe|"
                    r"newsletter|accept|skip to|legal[- ]notice|data protection|institutions-law)", re.I)


def _content_anchors(soup, base_url, body_code, platform, item_type, limit):
    """Robust fallback for rendered/heterogeneous pages: title-like anchors (>=18
    chars) outside the nav/header/footer/aside chrome, deduped by href, noise
    filtered. Catches content links the platform card selectors miss (jcms detail
    paths, hot-topics, etc.)."""
    body = BeautifulSoup(str(soup), "html.parser")
    for tag in body.select("nav, header, footer, aside, .cookie, .navbar, .menu"):
        tag.decompose()
    out, seen = [], set()
    for a in body.select("a[href]"):
        href = a.get("href", "")
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 18 or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        if _NOISE.search(href) or _NOISE.search(title):
            continue
        url = href if href.startswith("http") else norm_url(_join(base_url, href))
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        card = a.find_parent(["article", "li", "div"]) or a
        out.append(Item(body_code=body_code, item_type=item_type, title=title[:300],
                        public_url=url, summary=clean(card.get_text(" ", strip=True))[:300],
                        document_date=smart_date(card), creation_date=datetime.now(timezone.utc),
                        source_kind=platform, guid=url))
        if len(out) >= limit:
            break
    return out


# ---- shared smart-date (1.4) ------------------------------------------------ #
def smart_date(el) -> datetime | None:
    # JSON-LD startDate/datePublished anywhere under the element
    for s in el.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k in ("startDate", "datePublished"):
                    if o.get(k):
                        m = _ISO.search(str(o[k]))
                        if m:
                            return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    # a <time datetime>
    t = el.find("time")
    if t and t.get("datetime"):
        m = _ISO.search(t["datetime"])
        if m:
            return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
    # visible DMY / ISO in the card text
    txt = el.get_text(" ", strip=True)
    m = _DMY.search(txt)
    if m:
        try:
            return datetime(int(m[3]), _MONTHS[m[2].lower()], int(m[1]), tzinfo=timezone.utc)
        except ValueError:
            pass
    m = _ISO.search(txt)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _card_to_item(card, base_url, body_code, platform, item_type) -> Item | None:
    a = next((x for x in card.select("a[href]")
              if x.get_text(strip=True) and len(x.get_text(strip=True)) >= 10
              and not x.get("href", "").startswith(("#", "javascript:", "mailto:"))), None)
    if not a:
        return None
    href = a["href"]
    url = href if href.startswith("http") else norm_url(_join(base_url, href))
    title = clean(a.get_text(" ", strip=True))
    if not title or len(title) < 8:
        return None
    return Item(body_code=body_code, item_type=item_type, title=title[:300],
                public_url=url, summary=clean(card.get_text(" ", strip=True))[:300],
                document_date=smart_date(card), creation_date=datetime.now(timezone.utc),
                source_kind=platform, guid=url)


def _join(base, href):
    from urllib.parse import urljoin
    return urljoin(base, href)


def _dedup(items):
    seen, out = set(), []
    for it in items:
        k = (it.public_url or "").rstrip("/").lower()
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        out.append(it)
    return out


# ---- platform handlers ------------------------------------------------------ #
def parse(platform, html, base_url, *, body_code="extract", item_type="news", limit=60):
    soup = BeautifulSoup(html, "html.parser")
    if platform == "ecl":
        cards = soup.select(".ecl-content-item")
    elif platform == "drupal":
        cards = (soup.select(".group-content") or soup.select(".views-row")
                 or soup.select(".teaser") or soup.select(".card") or soup.select("article.node"))
    elif platform == "wordpress":
        cards = soup.select("article") or [a.parent for a in soup.select("a[href*='/news/'], a[href*='/publications']")]
    else:  # jcms, sharepoint, dynamics, spa, bespoke (post-render): generic
        cards = (soup.select("article") or soup.select(".card") or soup.select(".views-row")
                 or soup.select("li.search-result, .result, .news-item, .event-item"))
        if not cards:  # last resort: anchors to listing-like detail pages
            cards = [a.parent or a for a in soup.select("a[href]")
                     if _LIST_HREF.search(a.get("href", "")) and len(a.get_text(strip=True)) >= 12]
    out = []
    for c in cards:
        it = _card_to_item(c, base_url, body_code, platform, item_type)
        if it:
            out.append(it)
        if len(out) >= limit:
            break
    out = _dedup(out)
    # Fallback: platform selectors found little -> robust content-anchor scan.
    if len(out) < 2:
        out = _dedup(out + _content_anchors(soup, base_url, body_code, platform, item_type, limit))
    return out[:limit]
