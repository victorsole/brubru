"""Anti-bot escalation fetcher (Phase 1, step 1.3).

requests (browser UA) -> Playwright render, chosen by the anti_bot profile and by
whether plain requests actually yielded content. One entry point: fetch(url, anti_bot).
"""
from __future__ import annotations

import ipaddress
import socket
import time
from urllib.parse import urlparse

import requests

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_CHALLENGE = ("/challenge", "/cdn-cgi", "just a moment", "/sorry", "enable javascript")
# anti_bot values that always require a real browser
_BROWSER = {"playwright", "pow_solve", "tls_relaxed", "cookie_handshake", "js_faceted"}
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal"}


def _is_safe_url(url: str) -> bool:
    """SSRF guard: only allow http(s) to a host that resolves entirely to public IPs.
    Blocks loopback, link-local (incl. cloud metadata 169.254.169.254), private
    (RFC1918), unique-local, reserved, multicast and unspecified ranges. This endpoint
    fetches partner-supplied URLs server-side, so it must never reach internal targets."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS:
        return False
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
                or addr.is_multicast or addr.is_unspecified):
            return False
    return True


def _is_challenge(url: str, text: str) -> bool:
    low = (url + " " + text[:2000]).lower()
    return any(c in low for c in _CHALLENGE)


def _needs_browser(anti_bot) -> bool:
    vals = anti_bot if isinstance(anti_bot, list) else [anti_bot]
    return any(v in _BROWSER for v in vals)


def _get_no_internal_redirects(s, url, *, max_hops=5):
    """GET following redirects manually, re-validating each hop against the SSRF guard
    (a public host can 302 to an internal one). Returns the final Response or None."""
    cur = url
    for _ in range(max_hops):
        if not _is_safe_url(cur):
            return None
        r = s.get(cur, timeout=30, allow_redirects=False)
        if r.is_redirect or r.is_permanent_redirect:
            loc = r.headers.get("location")
            if not loc:
                return r
            cur = requests.compat.urljoin(cur, loc)
            continue
        return r
    return None


def _requests_fetch(url: str, *, cooldown: bool):
    s = requests.Session(); s.headers.update({"User-Agent": _UA})
    for attempt in range(3 if cooldown else 1):
        try:
            r = _get_no_internal_redirects(s, url)
            if r is None:
                return None, "blocked"
        except requests.RequestException:
            return None, "error"
        # requests defaults undeclared text/* to ISO-8859-1, but EU pages are UTF-8;
        # honour the real charset so "Europe’s" doesn't mojibake to "Europeâ€™s".
        if "charset=" not in r.headers.get("content-type", "").lower():
            r.encoding = r.apparent_encoding or "utf-8"
        if r.status_code == 200 and not _is_challenge(r.url, r.text):
            return r.text, "ok"
        if cooldown and (_is_challenge(r.url, r.text)):
            time.sleep(60 * (attempt + 1)); continue
        return None, ("challenge" if _is_challenge(r.url, r.text) else f"http_{r.status_code}")
    return None, "challenged"


def _playwright_fetch(url: str, *, tls_relaxed: bool, wait_ms: int = 3500, settle: bool = True):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            ctx = b.new_context(user_agent=_UA, ignore_https_errors=tls_relaxed)
            pg = ctx.new_page()
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            if not _is_safe_url(pg.url):  # SSRF: navigation may have redirected internal
                b.close()
                return None
            pg.wait_for_timeout(wait_ms)
            # Render-settle: slow AJAX grids (Power Pages / Dynamics data_grid, faceted
            # SPAs) populate seconds after domcontentloaded. Poll body text until it
            # stops growing (settled) or a hard cap, so we don't snapshot a "loading"
            # state and extract 0 items.
            if settle:
                prev, stable = -1, 0
                for i in range(12):  # up to ~18s extra
                    try:
                        cur = pg.evaluate("document.body && document.body.innerText.length || 0")
                        spinner = pg.evaluate(
                            "[...document.querySelectorAll('.loading,.spinner,[class*=loading],"
                            "[class*=spinner]')].some(e=>e.offsetParent!==null)")
                    except Exception:
                        break
                    stable = 0 if cur > prev * 1.02 else stable + 1
                    prev = cur
                    # settle only after a minimum dwell, two stable reads, no visible
                    # spinner -> never snapshots a still-loading AJAX grid (Power Pages).
                    if i >= 3 and stable >= 2 and not spinner:
                        break
                    pg.wait_for_timeout(1500)
            html = pg.content()
            b.close()
            return html
    except Exception:
        return None


def fetch(url: str, anti_bot) -> tuple[str | None, str]:
    """Return (html, how). 'how' in {requests, browser, failed, blocked}."""
    if not _is_safe_url(url):  # SSRF: never fetch internal / non-public targets
        return None, "blocked"
    vals = anti_bot if isinstance(anti_bot, list) else [anti_bot]
    cooldown = "rate_limit_cooldown" in vals
    tls = "tls_relaxed" in vals
    if not _needs_browser(anti_bot):
        html, status = _requests_fetch(url, cooldown=cooldown)
        if html:
            return html, "requests"
    # browser path (either required by profile, or requests failed/empty)
    html = _playwright_fetch(url, tls_relaxed=tls)
    return (html, "browser") if html else (None, "failed")
