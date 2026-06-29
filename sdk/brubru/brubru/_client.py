"""The Brubru API client: one key, the whole EU institutional data estate.

    import brubru
    bru = brubru.Client(api_key="brubru_live_...")
    res = bru.extract("https://cinea.ec.europa.eu/news_en", classify=True)
    posts = bru.social.posts(entity_type="commissioner", platform="x")
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

import requests

from ._errors import BrubruError, error_for_status
from ._models import ExtractResult, Page
from .social import Social

__all__ = ["Client"]

# The API is served by the backend host. The brand domain (brubru.beresol.eu)
# serves the marketing site + the static docs, and falls back to the SPA for
# unknown paths, so it does NOT answer /api/v2/* with JSON. Point the client at
# the backend. Override base_url once a dedicated API domain / proxy is in place.
DEFAULT_BASE_URL = "https://brubru-production.up.railway.app"


class Client:
    """Thin, synchronous client over the Brubru v2 REST API.

    Args:
        api_key: your ``brubru_live_...`` key. Sent as the ``X-API-Key`` header.
        base_url: API host. Defaults to the public ``brubru.beresol.eu``.
        timeout: per-request timeout in seconds (extract can be slow: it fetches
            and renders a live page, so the default is generous).
        session: an optional ``requests.Session`` (for connection pooling / mocks).
    """

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL,
                 timeout: float = 60.0, session: Optional[requests.Session] = None):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({
            "X-API-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "brubru-python/0.1.0",
        })
        self.social = Social(self)

    # ---- low-level ------------------------------------------------------- #
    def get(self, path: str, **params: Any) -> Any:
        """GET an arbitrary v2 path (e.g. ``/api/v2/legislative/eur-lex/laws``).
        ``params`` with a value of None are dropped. Returns decoded JSON; raises
        a typed BrubruError on any non-2xx response."""
        if not path.startswith("/"):
            path = "/" + path
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._session.get(self.base_url + path, params=clean, timeout=self.timeout)
        return self._handle(resp)

    @staticmethod
    def _handle(resp: requests.Response) -> Any:
        try:
            payload = resp.json()
        except ValueError:
            payload = resp.text
        if not resp.ok:
            raise error_for_status(resp.status_code, payload)
        # A 2xx that is not JSON means base_url points at the wrong host (e.g. the
        # brand domain's SPA fallback returns 200 text/html). Fail loudly rather
        # than hand back HTML that downstream parsing would choke on.
        if not isinstance(payload, (dict, list)):
            ct = resp.headers.get("Content-Type", "?")
            raise BrubruError(
                f"expected JSON from {resp.url} but got {ct}. Check base_url points "
                f"at the Brubru API host (default {DEFAULT_BASE_URL}).",
                status=resp.status_code, payload=payload)
        return payload

    def get_page(self, path: str, item_cls, **params: Any) -> Page:
        """GET a paginated endpoint and wrap the envelope as a Page of item_cls."""
        return Page.from_envelope(self.get(path, **params), item_cls)

    def iter_paginated(self, path: str, item_cls, *, max_items: Optional[int] = None,
                       **params: Any) -> Iterator[Any]:
        """Stream items across every page of a paginated endpoint. Stops at
        ``max_items`` if given. Page size honours a ``limit`` param if passed."""
        page = max(1, int(params.pop("page", 1) or 1))
        yielded = 0
        while True:
            env = self.get(path, page=page, **params)
            p = Page.from_envelope(env, item_cls)
            for item in p.items:
                yield item
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            if not p.has_more or not p.next_page:
                return
            page = p.next_page

    # ---- extract --------------------------------------------------------- #
    def extract(self, url: str, *, item_type: str = "news", limit: int = 30,
                classify: bool = False, shallow: bool = False, lang: str = "en") -> ExtractResult:
        """Extract structured items from any EU institutional URL.

        Detects the platform, fetches it through the right anti-bot path and
        returns 5-datapoint items. ``classify=True`` also tags each item with
        EuroVoc descriptors. ``shallow=True`` is fast listing-only (no bodies).
        """
        data = self.get("/api/v2/extract", url=url, item_type=item_type, limit=limit,
                         classify=str(classify).lower(), shallow=str(shallow).lower(), lang=lang)
        return ExtractResult.from_dict(data)

    def health(self) -> Dict[str, Any]:
        """Public health check (no key needed server-side)."""
        return self.get("/health")

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
