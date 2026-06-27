"""Extract engine orchestration (Phase 1): classify -> fetch -> parse -> Items."""
from __future__ import annotations

from . import classifier as _clf
from . import fetcher as _fetch
from . import handlers as _handlers


def classify(url: str, html: str | None = None):
    return _clf.classify(url, html)


def _deep_fill(items, anti_bot, *, limit_fetches: int = 10, body: bool = True, dates: bool = True):
    """Deep-fetch item detail pages to enrich them. body=True replaces the thin listing
    snippet with the real article text (for classification); dates=True recovers the
    publication date when the listing card carried none (many Drupal sites — eige, easa,
    enisa — only show the date on the detail page). Best-effort per item. When body is
    off, only dateless items are fetched, so date-completion stays cheap."""
    from bs4 import BeautifulSoup
    from . import article as _article
    from .handlers import smart_date

    def _real_detail(u: str | None) -> bool:
        # ONLY fetch a real, distinct detail page. A synthetic public_url
        # (`{listing}#{title}`, for JS-span cards with no real link) resolves to the
        # LISTING page, whose content is NOT this item's body — assigning it would be a
        # fabrication. Such items stay body/date-empty (honest), never back-filled wrong.
        return bool(u) and u.startswith(("http://", "https://")) and "#" not in u

    targets = [it for it in items
               if _real_detail(it.public_url) and (body or (dates and not it.document_date))]
    for it in targets[:limit_fetches]:
        try:
            html, _ = _fetch.fetch(it.public_url, anti_bot)
            if not html:
                continue  # fetch failed -> leave fields as-is, do not fabricate
            soup = BeautifulSoup(html, "html.parser")
            if dates and not it.document_date:
                d = smart_date(soup)
                if d:
                    it.document_date = d
            if body:
                body_txt, body_html = _article.extract_body(html, it.public_url)
                if body_txt:  # only assign genuinely-extracted content
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
        _deep_fill(items, anti_bot, body=want_body, dates=want_dates, limit_fetches=min(limit, 60))
    if classify_eurovoc:
        from services.classify import classify_item
        for it in items:
            it.extras["eurovoc"] = classify_item(it, lang=lang)
    return {"url": url, "platform": platform, "body_code": body, "fetched_via": how,
            "item_count": len(items), "items": items}
