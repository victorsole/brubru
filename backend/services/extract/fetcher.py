"""Anti-bot escalation fetcher (Phase 1, step 1.3).

requests (browser UA) -> Playwright render, chosen by the anti_bot profile and by
whether plain requests actually yielded content. One entry point: fetch(url, anti_bot).
"""
from __future__ import annotations

import time

import requests

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_CHALLENGE = ("/challenge", "/cdn-cgi", "just a moment", "/sorry", "enable javascript")
# anti_bot values that always require a real browser
_BROWSER = {"playwright", "pow_solve", "tls_relaxed", "cookie_handshake", "js_faceted"}


def _is_challenge(url: str, text: str) -> bool:
    low = (url + " " + text[:2000]).lower()
    return any(c in low for c in _CHALLENGE)


def _needs_browser(anti_bot) -> bool:
    vals = anti_bot if isinstance(anti_bot, list) else [anti_bot]
    return any(v in _BROWSER for v in vals)


def _requests_fetch(url: str, *, cooldown: bool):
    s = requests.Session(); s.headers.update({"User-Agent": _UA})
    for attempt in range(3 if cooldown else 1):
        try:
            r = s.get(url, timeout=30, allow_redirects=True)
        except requests.RequestException:
            return None, "error"
        if r.status_code == 200 and not _is_challenge(r.url, r.text):
            return r.text, "ok"
        if cooldown and (_is_challenge(r.url, r.text)):
            time.sleep(60 * (attempt + 1)); continue
        return None, ("challenge" if _is_challenge(r.url, r.text) else f"http_{r.status_code}")
    return None, "challenged"


def _playwright_fetch(url: str, *, tls_relaxed: bool, wait_ms: int = 3500):
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
            pg.wait_for_timeout(wait_ms)
            html = pg.content()
            b.close()
            return html
    except Exception:
        return None


def fetch(url: str, anti_bot) -> tuple[str | None, str]:
    """Return (html, how). 'how' in {requests, browser, failed}."""
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
