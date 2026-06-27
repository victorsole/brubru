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

# A content item must have a real headline. Nav links, calls-to-action and bare
# section labels ("Registration", "Themes in focus", "Subscribe to ... News") are not
# items: when they slip through they get classified into nonsense ("registration of
# voters", "jurisdiction ratione materiae"). Filter them by title at every item-build
# site. Kept deliberately tight so real headlines are never dropped.
_JUNK_TITLE_EXACT = {
    "registration", "register", "register now", "register here", "read more", "read all",
    "see all", "see more", "view all", "view more", "show more", "load more", "more",
    "themes in focus", "latest news", "all news", "news", "events", "event", "publications",
    "documents", "newsletter", "subscribe", "sign up", "log in", "login", "search", "menu",
    "home", "back to top", "previous", "next", "find out more", "learn more", "discover more",
    "press releases", "press release", "media", "overview", "contact", "contact us", "share",
}
_JUNK_TITLE_RE = re.compile(
    r"^(read|see|view|show|load|find out|learn|discover|explore)\s+(more|all|here)\b"
    r"|registrations?\s+(are\s+)?(now\s+)?open"
    r"|register\s+(now|here|today)"
    r"|\bsubscribe\b|\bnewsletter\b|\bback to\b"
    r"|^refine your search|^search page$|^send a question|^publications office of the e"
    r"|^go to\b|^filter by\b", re.I)


def _is_junk_title(title: str) -> bool:
    t = (title or "").strip().lower().rstrip(".:")
    if t in _JUNK_TITLE_EXACT:
        return True
    return bool(_JUNK_TITLE_RE.search(t))


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
        if _NOISE.search(href) or _NOISE.search(title) or _is_junk_title(title):
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


def _card_title(card) -> str | None:
    """Pick the card's title. Prefer a real heading (12-200 chars, not junk/publisher),
    else the card's main link text, else the longest paragraph. This handles both the
    common case (title in <h2>) and Power Pages cards (publisher in <h5>, title in <p>)."""
    for h in card.select("h1, h2, h3, h4, h5"):
        t = clean(h.get_text(" ", strip=True))
        if t and 12 <= len(t) <= 200 and not _is_junk_title(t):
            return t
    a = next((x for x in card.select("a[href]")
              if not x.get("href", "").startswith(("#", "javascript:", "mailto:"))), None)
    if a:
        t = clean(a.get_text(" ", strip=True))
        if t and 8 <= len(t) <= 200 and not _is_junk_title(t):
            return t
    cands = [clean(p.get_text(" ", strip=True)) for p in card.select("p, .title, strong, span")]
    cands = [c for c in cands if c and 12 <= len(c) <= 200 and not _is_junk_title(c)]
    return max(cands, key=len) if cands else None


def _card_to_item(card, base_url, body_code, platform, item_type, *, permissive=False) -> Item | None:
    """Build an Item from a card. Strict (default): a real anchor href is required, so
    generic `article`/`.card` chrome (language menus, "About us") is not mistaken for an
    item. Permissive (only for explicit item-class cards like .publication-item): allow
    a heading/paragraph title with no anchor, for JS-gated Power Pages grids."""
    title = _card_title(card)
    if not title:
        return None
    a = next((x for x in card.select("a[href]")
              if not x.get("href", "").startswith(("#", "javascript:", "mailto:"))), None)
    href = a["href"] if a else ""
    if not href and not permissive:
        return None
    url = href if href.startswith("http") else (norm_url(_join(base_url, href)) if href else "")
    return Item(body_code=body_code, item_type=item_type, title=title[:300],
                public_url=url, summary=clean(card.get_text(" ", strip=True))[:300],
                document_date=smart_date(card), creation_date=datetime.now(timezone.utc),
                source_kind=platform, guid=url or f"{base_url}#{title[:80]}")


_CTA = re.compile(r"^(click here|read more|read the|read it|download|view|see more|see all|"
                  r"learn more|find out more|discover|more info|access)\b", re.I)


def _cta_cards(soup, base_url, body_code, platform, item_type, limit):
    """Cards whose title sits in a heading and whose link is a CTA ('Click here',
    'Read more', 'Download') — the Power Pages / Dynamics data-grid shape, and many EU
    portals. Climb from each CTA link to the card container and take its longest
    non-junk heading as the title."""
    body = BeautifulSoup(str(soup), "html.parser")
    for tag in body.select("nav, header, footer, aside, .menu, .navbar, .ecl-site-header, .ecl-site-footer"):
        tag.decompose()
    out, seen = [], set()
    for a in body.select("a[href]"):
        if not _CTA.match(clean(a.get_text(" ", strip=True))):
            continue
        href = a.get("href", "")
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        card = a
        for _ in range(4):  # climb to a container that carries a heading
            card = card.find_parent(["div", "article", "li", "section"]) or card
            if card.find(["h2", "h3", "h4", "h5"]):
                break
        heads = [clean(h.get_text(" ", strip=True)) for h in card.find_all(["h2", "h3", "h4", "h5"])]
        heads = [h for h in heads if h and len(h) >= 8 and not _is_junk_title(h)]
        if not heads:
            continue
        title = max(heads, key=len)
        url = href if href.startswith("http") else norm_url(_join(base_url, href))
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(Item(body_code=body_code, item_type=item_type, title=title[:300],
                        public_url=url, summary=clean(card.get_text(" ", strip=True))[:300],
                        document_date=smart_date(card), creation_date=datetime.now(timezone.utc),
                        source_kind=platform, guid=url))
        if len(out) >= limit:
            break
    return out


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
        # Explicit item-class cards first, extracted permissively (handles JS-gated
        # Power Pages grids where the title is a <p> and the link is a JS span).
        item_cards = soup.select(".publication-item, .news-item, .event-item, .card-item")
        permissive = bool(item_cards)
        cards = (item_cards or soup.select("article") or soup.select(".card")
                 or soup.select(".views-row") or soup.select("li.search-result, .result, .teaser"))
        if not cards:  # last resort: anchors to listing-like detail pages
            cards = [a.parent or a for a in soup.select("a[href]")
                     if _LIST_HREF.search(a.get("href", "")) and len(a.get_text(strip=True)) >= 12]
        out = []
        for c in cards:
            it = _card_to_item(c, base_url, body_code, platform, item_type, permissive=permissive)
            if it:
                out.append(it)
            if len(out) >= limit:
                break
        out = _dedup(out)
        if len(out) < 2:
            out = _dedup(out + _cta_cards(soup, base_url, body_code, platform, item_type, limit))
        if len(out) < 2:
            out = _dedup(out + _content_anchors(soup, base_url, body_code, platform, item_type, limit))
        return out[:limit]
    out = []
    for c in cards:
        it = _card_to_item(c, base_url, body_code, platform, item_type)
        if it:
            out.append(it)
        if len(out) >= limit:
            break
    out = _dedup(out)
    # Fallback 1: heading + CTA-link cards (Power Pages / Dynamics data-grid, portals).
    if len(out) < 2:
        out = _dedup(out + _cta_cards(soup, base_url, body_code, platform, item_type, limit))
    # Fallback 2: robust content-anchor scan for anything still missed.
    if len(out) < 2:
        out = _dedup(out + _content_anchors(soup, base_url, body_code, platform, item_type, limit))
    return out[:limit]
