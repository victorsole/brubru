"""WAF-bypass browser fetcher for JavaScript-challenge-walled EU pages.

WHY THIS EXISTS
---------------
`eur-lex.europa.eu` (and a few other europa.eu hosts) sit behind a JavaScript
challenge WAF. Any client that cannot execute JavaScript receives
``HTTP 202 Accepted`` with a ZERO-byte body — this includes ``curl``, ``httpx``,
``requests``, ``aiohttp`` and the WebFetch tool. A real browser runs the
challenge script, obtains the clearance cookie, and only THEN receives the page.

This module drives a headless Chromium (via Playwright) that clears the
challenge, waits for the SPA/content to settle, expands EUR-Lex's collapsible
"More on..." accordions, and returns the rendered text + HTML.

WHEN TO USE IT (read this before reaching for it)
-------------------------------------------------
This is a LAST-RESORT fallback, not the primary path. The Publications Office
exposes the SAME data through machine-readable backends that have NO WAF and are
far cheaper than spinning up a browser:

  1. Cellar SPARQL   http://publications.europa.eu/webapi/rdf/sparql   (metadata + relationships)
  2. Cellar REST     http://publications.europa.eu/resource/celex/{CELEX}  (notice + content; send Accept + Accept-Language)
  3. Data dump       https://datadump.publications.europa.eu               (bulk, EU Login)
  4. data.europa.eu  https://data.europa.eu/sparql + /api/hub/search/      (DCAT-AP open data)

Use this fetcher ONLY for EUR-Lex *prose* pages that have no machine-readable
equivalent (help/learning/news explainers) or as an emergency fallback when a
content endpoint is unavailable. For document content and metadata, go through
Cellar — see ``services/api_clients/cellar_sparql_client.py`` and
``services/api_clients/eurlex_client.py``.

DEPENDENCY
----------
Playwright is NOT in Brubru's requirements. Install on demand::

    pip install playwright
    python -m playwright install chromium

If Playwright is missing, ``WafBrowserFetcher`` raises a clear ImportError at
construction time rather than failing deep in a scrape.

CLI
---
    python -m backend.services.scrapers.waf_browser_fetcher <url> [out.txt]
"""

from __future__ import annotations

import concurrent.futures as _cf
import logging
import sys
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Browser User-Agent — a real Chrome string is required; the WAF fingerprints
# obviously-automated agents.
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# EUR-Lex left-nav / toolbar labels that pollute body inner_text. Stripped so
# the caller gets substance, not chrome. Kept conservative — only exact-match
# single-line labels are removed.
_NAV_NOISE = frozenset({
    "back to help main page", "Help", "EUR-Lex content", "What can be found on EUR-Lex",
    "Linguistic coverage", "Identifiers", "Numbering of acts", "Classifications",
    "European Case Law Identifier (ECLI)", "European Legislation Identifier (ELI)",
    "Communitatis Europeae Lex (CELEX)", "Directories of EU law", "Directory of case-law",
    "Experimental features", "Search", "Results list", "My EUR-Lex", "Official Journal",
    "Data reuse", "Search in help", "Export PDF", "Print", "Share", "MENU",
    "Quick search", "Search tips", "How to search", "Advanced search", "Expert search",
    "Predefined RSS alerts", "Browse by EU institutions", "Browse by EuroVoc",
    "Refine your query", "Edit your search", "Customise the results list", "Export results",
    "Create an account", "Preferences", "My items", "My searches", "My email alerts",
    "My RSS alerts", "About the Official Journal", "Series and subseries",
    "Browse the Official Journal", "Official Journal daily view", "Special editions",
    "Verify authenticity", "Reuse EUR-Lex content", "Webservice", "Create permanent links",
    "Text", "Document information", "Permanent link", "Download notice", "Save to My items",
})

_NOISE_PREFIXES = (
    "This site uses cookies", "Accept all", "Accept only", "An official website",
    "How do you know", "Skip to main", "Use quotation marks", "Need more search options",
    "We use analytics cookies", "I refuse analytics", "I accept analytics",
    "For any information on the other cookies", "Access to page content",
    "Direct access to", "<a href",
)

# Everything from this line down is page footer.
_FOOTER_MARKERS = (
    "This site is managed by the Publications Office",
    "Discover more on europa.eu",
)


@dataclass
class FetchResult:
    url: str
    title: str = ""
    nav_status: int | None = None
    text: str = ""
    html: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.text) > 200


def _strip_chrome(text: str) -> str:
    """Remove EUR-Lex nav/cookie/footer chrome and collapse blank runs."""
    out: list[str] = []
    blanks = 0
    for line in text.splitlines():
        s = line.strip()
        if any(s.startswith(m) for m in _FOOTER_MARKERS):
            break
        if s in _NAV_NOISE:
            continue
        if any(s.startswith(p) for p in _NOISE_PREFIXES):
            continue
        if not s:
            blanks += 1
            if blanks > 1:
                continue
        else:
            blanks = 0
        out.append(line.rstrip())
    return "\n".join(out).strip()


# Chromium launch flags for a memory- and process-capped container.
#
# Production evidence (20-23 Aug 2026): `votes_ep` failed 49 of 49 runs, and the
# non-timeout failures carry
#     pthread_create: Resource temporarily unavailable (11)
#     Zygote could not fork: process_type gpu-process
# The container runs out of processes/threads before Chromium finishes starting.
# Every one of these flags removes a process or a shared-memory dependency that
# a headless scrape does not need:
#
#   --no-sandbox              the sandbox needs extra helper processes and buys
#                             nothing here: we render EU government pages, not
#                             untrusted user content, and the container is the
#                             isolation boundary.
#   --disable-dev-shm-usage   Docker gives /dev/shm 64 MB by default; Chromium
#                             falls over on larger pages. Sends it to /tmp.
#   --no-zygote               the zygote is a fork server. It is the thing that
#                             "could not fork" in the logs.
#   --disable-gpu             no GPU exists here; the gpu-process is pure cost
#                             and is named in the fork failure.
#   --disable-extensions,
#   --disable-background-*    fewer background processes and timers.
#
# NOT included: --single-process. It removes the most processes and also breaks
# navigation on JS-heavy sites, which is exactly what this fetcher is for.
_CONTAINER_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--no-zygote",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
]


def _call_bounded(fn, timeout_s: float, what: str):
    """Run a blocking Playwright call with a hard wall-clock bound.

    Playwright bounds `launch()` (30s by default) and every navigation, but
    `sync_playwright().start()` -- which spawns the driver process -- takes no
    timeout at all, and neither `browser.close()` nor `playwright.stop()` can be
    interrupted once the browser is a zombie. In a container where Chromium
    fails to fork (`Zygote could not fork: process_type gpu-process`, observed
    in production on 22-23 Aug 2026) those calls can block for ever.

    A blocked *scraper* is a bad day. A blocked scraper inside a caller that
    releases its concurrency guard in a `finally` is a dead nightly job, because
    the `finally` never runs: that is exactly how the scraper-health detector
    went silent after 21 Aug 2026 and stayed silent.

    On timeout the worker thread is abandoned rather than killed -- Python
    cannot interrupt a blocking C call -- but the CALLER is freed, which is the
    whole point. One leaked thread per incident is cheap; a permanently wedged
    cron is not.
    """
    pool = _cf.ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(fn)
    try:
        return fut.result(timeout=timeout_s)
    except _cf.TimeoutError:
        raise TimeoutError(f"{what} exceeded {timeout_s}s") from None
    finally:
        # NEVER `with ThreadPoolExecutor(...)`: its __exit__ calls
        # shutdown(wait=True), which blocks until the worker finishes -- so the
        # deadline would expire and the caller would still wait for the hang it
        # was supposed to escape. Measured: a 2s bound on a 30s call returned
        # after 30.01s. wait=False is the entire point of this helper.
        pool.shutdown(wait=False)


class WafBrowserFetcher:
    """Headless-Chromium fetcher that clears the EUR-Lex JS-challenge WAF.

    Reuse one instance across many URLs — the browser launches once and the
    challenge clearance cookie is retained for the host within the context::

        with WafBrowserFetcher() as f:
            for url in urls:
                result = f.fetch(url)
                if result.ok:
                    ...
    """

    def __init__(
        self,
        *,
        user_agent: str = _DEFAULT_UA,
        settle_ms: int = 5000,
        networkidle_ms: int = 15000,
        nav_timeout_ms: int = 45000,
        launch_timeout_ms: int = 30000,
        locale: str = "en-US",
        viewport: tuple[int, int] = (1440, 1200),
    ) -> None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on host
            raise ImportError(
                "WafBrowserFetcher needs Playwright. Install it on demand:\n"
                "    pip install playwright\n"
                "    python -m playwright install chromium"
            ) from exc

        self.user_agent = user_agent
        self.settle_ms = settle_ms
        self.networkidle_ms = networkidle_ms
        self.nav_timeout_ms = nav_timeout_ms
        self.launch_timeout_ms = launch_timeout_ms
        self.locale = locale
        self.viewport = {"width": viewport[0], "height": viewport[1]}
        self._pw = None
        self._browser = None
        self._ctx = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "WafBrowserFetcher":
        from playwright.sync_api import sync_playwright

        # NOTE ON WHAT IS AND IS NOT BOUNDED HERE (audited 24 Aug 2026).
        #
        # `launch()` is bounded -- Playwright defaults it to 30s and we now pass
        # it explicitly so the bound is visible and tunable rather than folklore.
        #
        # `sync_playwright().start()` takes no timeout, and neither `close()`
        # nor `stop()` can be interrupted once the browser is a zombie. Those
        # calls CANNOT be bounded from here: Playwright's sync API is
        # thread-affine (greenlet), so running them in a watchdog thread and
        # using the result from the caller raises
        # `greenlet.error: cannot switch to a different thread`. Verified by
        # test, not assumed.
        #
        # The deadline for those therefore belongs at the JOB boundary, where
        # one bound covers every way a run can wedge, browser or not. See
        # `api/cron.py::_run_scraper_health_bg`. A hang here is what silenced
        # the scraper-health detector from 22 Aug 2026 onwards.
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True, timeout=self.launch_timeout_ms, args=_CONTAINER_ARGS)
        self._ctx = self._browser.new_context(
            user_agent=self.user_agent, locale=self.locale, viewport=self.viewport
        )
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._ctx, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._ctx = self._browser = self._pw = None

    # -- fetch -------------------------------------------------------------
    def fetch(
        self,
        url: str,
        *,
        expand_accordions: bool = True,
        strip_chrome: bool = True,
        wait_for_selector: str | None = None,
        wait_for_selector_timeout_ms: int = 8000,
    ) -> FetchResult:
        """Render ``url`` past the WAF and return cleaned text + raw HTML.

        ``wait_for_selector`` lets the caller pin extraction to a site-specific
        content anchor (e.g. ``eui-accordion-item`` on the F&T Portal SPA)
        instead of guessing from ``settle_ms``. If the selector never appears
        within ``wait_for_selector_timeout_ms`` the fetch still returns whatever
        DOM is present — same fail-soft behaviour as before.
        """
        if self._ctx is None:
            raise RuntimeError("Use WafBrowserFetcher as a context manager (`with ...:`).")

        page = self._ctx.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
            status = resp.status if resp else None
            # The first response is the 202 challenge; the wait lets Chromium
            # run it, set the cookie, and reload the real content.
            page.wait_for_timeout(self.settle_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=self.networkidle_ms)
            except Exception:
                pass

            if wait_for_selector:
                try:
                    page.wait_for_selector(
                        wait_for_selector, timeout=wait_for_selector_timeout_ms, state="attached",
                    )
                except Exception:
                    pass

            if expand_accordions:
                # EUR-Lex hides detail behind "More on..." accordions; open them all.
                # F&T Portal (EUI Angular components) uses <eui-accordion-item>
                # with shadow-DOM event handlers — including their header
                # selectors here makes the same pass work for both.
                try:
                    page.eval_on_selector_all(
                        "[aria-expanded='false'], a.toggle, .accordion-toggle, "
                        "[data-toggle='collapse'], .moreLink, "
                        "eui-accordion-item, eui-accordion-item [slot='header'], "
                        ".eui-accordion__header, .eui-accordion-item__header",
                        "els => els.forEach(e => { "
                        "  try { e.click(); } catch (_) {} "
                        "  try { if (typeof e.open === 'function') e.open(); } catch (_) {} "
                        "  try { e.dispatchEvent(new MouseEvent('click', {bubbles: true})); } catch (_) {} "
                        "})",
                    )
                except Exception:
                    pass
                page.wait_for_timeout(1200)
                # F&T Portal lazy-loads accordion body content via XHR after
                # the header click; let those settle before extraction.
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass
                # Force-reveal any still-collapsed panels.
                try:
                    page.eval_on_selector_all(
                        ".collapse, .panel-collapse, [hidden], "
                        "eui-accordion-item:not([expanded])",
                        "els => els.forEach(e => { e.classList.add('in','show'); "
                        "e.style.display='block'; e.removeAttribute('hidden'); "
                        "try { e.setAttribute('expanded', ''); } catch (_) {} })",
                    )
                except Exception:
                    pass
                page.wait_for_timeout(400)

            title = page.title()
            html = page.content()
            raw = page.inner_text("body")
            text = _strip_chrome(raw) if strip_chrome else raw
            return FetchResult(url=url, title=title, nav_status=status, text=text, html=html)
        except Exception as exc:  # pragma: no cover - network dependent
            return FetchResult(url=url, error=f"{type(exc).__name__}: {exc}")
        finally:
            try:
                page.close()
            except Exception:
                pass


def fetch_one(url: str, **kwargs) -> FetchResult:
    """Convenience: launch a browser, fetch a single URL, tear down.

    Constructor knobs (settle_ms, networkidle_ms, nav_timeout_ms, launch_timeout_ms,
    user_agent, locale, viewport) are routed to WafBrowserFetcher; the rest (expand_accordions,
    strip_chrome) go to fetch().
    """
    ctor_keys = {"user_agent", "settle_ms", "networkidle_ms", "nav_timeout_ms",
                 "launch_timeout_ms", "locale", "viewport"}
    ctor_kwargs = {k: v for k, v in kwargs.items() if k in ctor_keys}
    fetch_kwargs = {k: v for k, v in kwargs.items() if k not in ctor_keys}
    with WafBrowserFetcher(**ctor_kwargs) as f:
        return f.fetch(url, **fetch_kwargs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m backend.services.scrapers.waf_browser_fetcher <url> [out.txt]")
        raise SystemExit(2)
    target = sys.argv[1]
    # Optional speed knobs for bulk crawling (subprocess-isolated + externally
    # hard-capped). Defaults stay generous for one-off accuracy.
    import os as _os
    _kw = {}
    if _os.environ.get("BRUBRU_FETCH_SETTLE_MS"):
        _kw["settle_ms"] = int(_os.environ["BRUBRU_FETCH_SETTLE_MS"])
    if _os.environ.get("BRUBRU_FETCH_NETWORKIDLE_MS"):
        _kw["networkidle_ms"] = int(_os.environ["BRUBRU_FETCH_NETWORKIDLE_MS"])
    result = fetch_one(target, **_kw) if _kw else fetch_one(target)
    if not result.ok:
        print(f"[ERROR] {target} -> {result.error or 'empty/blocked'} (status={result.nav_status})")
        raise SystemExit(1)
    body = (
        f"URL: {result.url}\nTITLE: {result.title}\nNAV_STATUS: {result.nav_status}\n"
        f"LEN: {len(result.text)}\n{'=' * 70}\n{result.text}\n"
    )
    if len(sys.argv) >= 3:
        with open(sys.argv[2], "w") as fh:
            fh.write(body)
        print(f"[OK] {target} -> {sys.argv[2]} ({len(result.text)} chars)")
    else:
        print(body)
