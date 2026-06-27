"""Extract engine orchestration (Phase 1): classify -> fetch -> parse -> Items."""
from __future__ import annotations

from . import classifier as _clf
from . import fetcher as _fetch
from . import handlers as _handlers


def classify(url: str, html: str | None = None):
    return _clf.classify(url, html)


def _deep_fill(items, anti_bot, *, limit_fetches: int = 25, body: bool = True, dates: bool = True):
    """Deep-fetch item detail pages to enrich them. body=True replaces the thin listing
    snippet with the real article text (for classification); dates=True recovers the
    publication date when the listing card carried none (many Drupal sites — eige, easa,
    enisa — only show the date on the detail page). Best-effort per item. When body is
    off, only dateless items are fetched, so date-completion stays cheap."""
    from bs4 import BeautifulSoup
    from . import article as _article
    from .handlers import smart_date
    targets = [it for it in items if it.public_url and (body or (dates and not it.document_date))]
    for it in targets[:limit_fetches]:
        try:
            html, _ = _fetch.fetch(it.public_url, anti_bot)
            if not html:
                continue
            if dates and not it.document_date:
                d = smart_date(BeautifulSoup(html, "html.parser"))
                if d:
                    it.document_date = d
            if body:
                body_txt, body_html = _article.extract_body(html, it.public_url)
                if body_txt:
                    it.body_txt, it.body_html = body_txt, body_html
        except Exception:
            continue


def extract(url: str, *, item_type: str = "news", limit: int = 60,
            classify_eurovoc: bool = False, lang: str = "en", deep: bool = False,
            complete_dates: bool = False) -> dict:
    """Run the engine on one URL. Returns a result dict (items + diagnostics).
    classify_eurovoc=True runs the Phase-2 EuroVoc classify step on each item
    (slow: BERT per item; default off for the live endpoint, on for batch writers).
    deep=True first fetches each item's detail page and classifies on the full article
    body instead of the listing snippet (one extra fetch per item; kills mixed-title
    artifacts). deep is only meaningful together with classify_eurovoc."""
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
    # detail-page enrichment: deep (body+dates, for classify) or just date-completion
    if deep:
        _deep_fill(items, anti_bot, body=True, dates=True)
    elif complete_dates:
        _deep_fill(items, anti_bot, body=False, dates=True)
    if classify_eurovoc:
        from services.classify import classify_item
        for it in items:
            it.extras["eurovoc"] = classify_item(it, lang=lang)
    return {"url": url, "platform": platform, "body_code": body, "fetched_via": how,
            "item_count": len(items), "items": items}
