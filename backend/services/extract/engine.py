"""Extract engine orchestration (Phase 1): classify -> fetch -> parse -> Items."""
from __future__ import annotations

import hashlib
import re

from . import classifier as _clf
from . import fetcher as _fetch
from . import handlers as _handlers


def classify(url: str, html: str | None = None):
    return _clf.classify(url, html)


_ERR_PAGE = re.compile(
    r"page (you requested |that you requested )?(could not be|cannot be|can't be|was not|not) found"
    r"|page not found|404 not found|error 404|\b404\b.{0,20}\bnot found\b"
    r"|this page (does not exist|isn'?t available)|requested url was not found", re.I)


def _reg_domain(host: str) -> str:
    parts = (host or "").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else (host or "")


def _deep_fill(items, anti_bot, *, limit_fetches: int = 10, body: bool = True, dates: bool = True,
               site_url: str = ""):
    """Deep-fetch item detail pages to fill body_txt/body_html + complete document_date.
    Anti-hallucination is enforced HERE, not just in validation — a back-fill must come
    from the item's OWN, real detail page or it is left empty (honest):
      * synthetic URL (`{listing}#{title}`) -> skip (would resolve to the listing).
      * OFF-SITE url (e.g. youtube.com) -> skip (not this body's detail page).
      * SOFT-404 / error page -> skip (don't assign 'page not found' as the body/date).
      * DUPLICATE body across items -> skip (a shared/wrong page fetched for several items).
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse
    from . import article as _article
    from .handlers import smart_date

    site_reg = _reg_domain(urlparse(site_url).hostname or "")

    def _real_detail(u: str | None) -> bool:
        if not u or not u.startswith(("http://", "https://")) or "#" in u:
            return False
        host = urlparse(u).hostname or ""
        return _reg_domain(host) == site_reg if site_reg else False  # same EU site only

    seen_body: set[str] = set()
    targets = [it for it in items
               if _real_detail(it.public_url) and (body or (dates and not it.document_date))]
    for it in targets[:limit_fetches]:
        try:
            html, _ = _fetch.fetch(it.public_url, anti_bot)
            if not html:
                continue  # fetch failed -> leave fields as-is, do not fabricate
            soup = BeautifulSoup(html, "html.parser")
            head = soup.get_text(" ", strip=True)[:400]
            if _ERR_PAGE.search(head):
                continue  # soft-404 / error page -> never assign its content as the item
            if dates and not it.document_date:
                d = smart_date(soup)
                if d:
                    it.document_date = d
            if body:
                body_txt, body_html = _article.extract_body(html, it.public_url)
                if body_txt:
                    h = hashlib.md5(body_txt[:400].encode("utf-8", "ignore")).hexdigest()
                    if h not in seen_body:  # not a duplicate of another item's body
                        seen_body.add(h)
                        it.body_txt, it.body_html = body_txt, body_html
        except Exception:
            continue


def extract(url: str, *, item_type: str = "news", limit: int = 60,
            classify_eurovoc: bool = False, lang: str = "en", deep: bool = False,
            complete_dates: bool = False, shallow: bool = False) -> dict:
    """Run the engine on one URL. Returns a result dict (items + diagnostics).

    CONTRACT: by default (shallow=False) the engine populates the full Item contract —
    it fetches each item's detail page to fill body_txt/body_html and complete
    document_date when the listing lacks it (capped at _deep_fill's limit). So canonical
    Items carry all 5 target datapoints, not just public_url.
    shallow=True skips the per-item detail fetches (fast, listing-only; body/date stay
    best-effort) — for the cost-bounded live path. deep/complete_dates force the
    detail-fetch on even when shallow (back-compat aliases).
    classify_eurovoc=True runs the Phase-2 EuroVoc classify step on each item."""
    platform, anti_bot, body = _clf.classify(url)
    html, how = _fetch.fetch(url, anti_bot)
    if not html:
        return {"url": url, "platform": platform, "body_code": body, "fetched_via": how,
                "item_count": 0, "items": [], "error": "fetch_failed"}
    # confirm platform from the actual HTML when the domain guess was generic
    if body not in _clf._OVERRIDES:
        platform, _, _ = _clf.classify(url, html)
    items = _handlers.parse(platform, html, url, body_code=body, item_type=item_type, limit=limit)
    # escalate once: a non-browser fetch that yielded nothing -> render and retry
    if not items and how == "requests":
        html2, how2 = _fetch.fetch(url, "playwright")
        if html2:
            platform2, _, _ = _clf.classify(url, html2)
            items = _handlers.parse(platform2, html2, url, body_code=body, item_type=item_type, limit=limit)
            if items:
                platform, how = platform2, how2
    # a browser fetch that yielded nothing on a JS grid (Power Pages / SPA) often just
    # lost the render race -> one fresh browser retry.
    if not items and how == "browser" and platform in ("dynamics", "spa"):
        html3, _ = _fetch.fetch(url, "playwright")
        if html3:
            items = _handlers.parse(platform, html3, url, body_code=body, item_type=item_type, limit=limit)
    # Contract enrichment from detail pages: fill body_txt/body_html + complete dates,
    # so Items carry the full 5-datapoint contract. On by default; shallow skips it.
    want_body = deep or not shallow
    want_dates = deep or complete_dates or not shallow
    if items and (want_body or want_dates):
        # fill ALL returned items (budget scales with the requested limit, capped at 60),
        # so the contract holds for every item, not just the first few.
        _deep_fill(items, anti_bot, body=want_body, dates=want_dates,
                   limit_fetches=min(limit, 60), site_url=url)
    if classify_eurovoc:
        from services.classify import classify_item
        for it in items:
            it.extras["eurovoc"] = classify_item(it, lang=lang)
    return {"url": url, "platform": platform, "body_code": body, "fetched_via": how,
            "item_count": len(items), "items": items}
