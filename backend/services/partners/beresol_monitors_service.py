"""
Beresol Monitors service (MEUB 4.2 - Beresol Monitors tab).

Wraps the Beresol Monitor API (https://beresol.eu/api/v1): a key-protected set of
JSON policy-intelligence digests. The index lists the available monitors; each
monitor feed carries a human-readable digest (sanitised body_html + body_txt),
the public dashboard URL and the scrape date.

No Anthropic. Bearer auth via settings.BERESOL_API_KEY. Third-party HTML is
sanitised to a small tag/attribute allowlist before it reaches the client.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Dict, Optional, Tuple

from core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 12
_TTL = 6 * 3600  # upstream refreshes ~daily; a 6h cache is plenty
_cache: Dict[str, Tuple[float, dict]] = {}


def _base() -> str:
    return (settings.BERESOL_API_BASE or "https://beresol.eu/api/v1").rstrip("/")


def _key() -> Optional[str]:
    k = settings.BERESOL_API_KEY
    return k.strip() if k else None


def has_key() -> bool:
    return bool(_key())


def _get(path: str) -> dict:
    """GET <base><path> with Bearer auth. Raises on HTTP / transport error."""
    req = urllib.request.Request(
        f"{_base()}{path}",
        headers={
            "Authorization": f"Bearer {_key()}",
            "Accept": "application/json",
            "User-Agent": "Brubru/1.0 (+https://brubru.beresol.eu)",
        },
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _cached(path: str) -> dict:
    now = time.time()
    hit = _cache.get(path)
    if hit and hit[0] > now:
        return hit[1]
    data = _get(path)
    _cache[path] = (now + _TTL, data)
    return data


# ----------------------------------------------------------------- sanitiser
_ALLOWED_TAGS = {
    "article", "section", "header", "footer", "div", "span", "p", "br", "hr",
    "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "b", "em", "i", "u",
    "a", "table", "thead", "tbody", "tr", "th", "td", "caption", "small", "sup",
    "sub", "blockquote", "code", "figure", "figcaption", "dl", "dt", "dd",
}
_GLOBAL_ATTRS = {"class", "data-monitor"}
_TAG_ATTRS = {"a": {"href", "title", "target", "rel"}}
_VOID = {"br", "hr"}


def _esc_attr(v: str) -> str:
    return (v or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_text(v: str) -> str:
    return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def _clean_attrs(self, tag: str, attrs) -> str:
        allowed = _GLOBAL_ATTRS | _TAG_ATTRS.get(tag, set())
        pairs = []
        for k, v in attrs:
            k = (k or "").lower()
            if k.startswith("on") or k not in allowed:
                continue
            v = v or ""
            if k == "href" and not v.startswith(("http://", "https://", "#", "/")):
                continue
            pairs.append((k, v))
        if tag == "a":
            d = dict(pairs)
            d["target"] = "_blank"
            d["rel"] = "noopener noreferrer"
            pairs = list(d.items())
        return "".join(f' {k}="{_esc_attr(v)}"' for k, v in pairs)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in _ALLOWED_TAGS:
            return
        self.out.append(f"<{tag}{self._clean_attrs(tag, attrs)}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in _ALLOWED_TAGS:
            self.out.append(f"<{tag}{self._clean_attrs(tag, attrs)}>" if tag not in _VOID else f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _ALLOWED_TAGS and tag not in _VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(_esc_text(data))


def sanitize_html(html: str) -> str:
    if not html:
        return ""
    p = _Sanitizer()
    try:
        p.feed(html)
        p.close()
    except Exception as e:  # never let malformed upstream HTML break the response
        logger.warning("[beresol] html sanitise failed: %s", e)
        return ""
    return "".join(p.out)


# ----------------------------------------------------------------- public API
def list_monitors() -> dict:
    """The monitor index: name, description, scrape date, and the monitor list."""
    idx = _cached("/")
    mons = idx.get("monitors", []) or []
    return {
        "name": idx.get("name"),
        "description": idx.get("description"),
        "created_date": idx.get("created_date"),
        "monitors": [
            {
                "monitor": m.get("monitor"),
                "title": m.get("title"),
                "description": m.get("description"),
                "public_url": m.get("public_url"),
            }
            for m in mons
        ],
    }


def get_monitor(slug: str) -> Optional[dict]:
    """One monitor's digest (sanitised). Returns None if the monitor is unknown (404)."""
    try:
        d = _cached(f"/{slug}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return {
        "monitor": d.get("monitor"),
        "title": d.get("title"),
        "public_url": d.get("public_url"),
        "created_date": d.get("created_date"),
        "body_html": sanitize_html(d.get("body_html") or ""),
        "body_txt": d.get("body_txt") or "",
    }
