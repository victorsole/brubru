"""Read a news item's publication date from the item's OWN page.

Two callers, one chain
----------------------
`scripts/backfill_news_document_dates.py` built and proved this chain on 10 September
2026, repairing rows already stored. On 11 September the question moved upstream --
stop new rows arriving undated -- and the news writers need the identical chain for
the few items per run that a listing leaves undated. A second copy in the writers
would drift from the one the backfill proved, so the chain lives here and both
import it ([[feedback_one_source_of_truth_per_fact]]). A date the sweep can read is
then a date a new row gets, and the other way round.

The chain, in order
-------------------
1. **Press Corner items: the documents API `eventDate`.** The detail page
   (`/presscorner/detail/en/ip_26_1801`) is a JavaScript shell with no date in its
   static HTML; the API behind it is the publisher's own JSON. Verified 11 Sep 2026
   for every kind stored in eu_news_items (ip, statement, speech, mex, qanda, inf,
   ac), and the Reform task force's listing dates agreed with it on 10 of 10 items.
   A miss falls through to the page rather than ending the attempt.
2. **The page**, fetched plain, then with a real TLS fingerprint, then in a browser
   when the plain fetch hits a wall -- and `extract_item_date` on what came back.
3. **The rendered page**, when the page arrived but carried no date. The ECA renders
   its date client-side: 157KB of static HTML with no carrier, and a rendered page
   that opens with `<time class="date" datetime="09/09/2026">`.

What it never does
------------------
Return a date the publisher did not state for THAT item: never the sitemap
`<lastmod>` (a modification date), never the ingest time, never a year or month read
out of the URL path. `(None, <reason>)` is a correct, honest answer, and the reason
says which failure it was so a caller can report it rather than guess
([[feedback_backfill_no_hallucination]]).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from services.scrapers.economy_common import extract_item_date, http_get, parse_listing_date

# WAF / rate-limit statuses. A 403 is a wall, a 429 is us going too fast, and a
# 503 is either. None of the three means "this page has no date".
_WALL_STATUSES = {403, 406, 429, 503}

# Case-insensitive: one stored URL spells it `IP_26_1637`. The fragment (`#11` on a
# MEX daily news item) is ignored by construction.
_PRESSCORNER_DETAIL = re.compile(r"/presscorner/detail/[a-z]{2}/([a-z]+)_(\d{2})_(\d+)", re.I)
_PRESSCORNER_API = ("https://ec.europa.eu/commission/presscorner/api/documents"
                    "?reference={ref}&language=en")

# Provenances that are NOT a date. Callers that tally outcomes need this list, and
# it belongs next to the code that produces the strings.
MISS_PROVENANCES = ("no_url", "pdf_not_read", "fetch_failed", "no_carrier")


def _in_bounds(dt: datetime) -> bool:
    today = datetime.now(timezone.utc)
    return datetime(1990, 1, 1, tzinfo=timezone.utc) <= dt <= today + timedelta(days=1)


def presscorner_reference(url: str) -> Optional[str]:
    """`IP/26/1801` for a Press Corner detail URL, else None."""
    m = _PRESSCORNER_DETAIL.search(url or "")
    if not m:
        return None
    return f"{m.group(1).upper()}/{m.group(2)}/{m.group(3)}"


def presscorner_event_date(url: str) -> Optional[datetime]:
    """The Press Corner API's `eventDate` for a detail URL, or None."""
    ref = presscorner_reference(url)
    if not ref:
        return None
    r = http_get(_PRESSCORNER_API.format(ref=ref))
    if r is None or getattr(r, "status_code", None) != 200:
        return None
    try:
        ev = (json.loads(r.text) or {}).get("eventDate")
        dt = datetime.strptime(str(ev)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None
    return dt if _in_bounds(dt) else None


# ---------------------------------------------------------------------------
# Site rules: where four publishers print an item's date in a form no generic
# carrier reads (11 September 2026). Each was found on the rendered page and checked
# against an INDEPENDENT carrier -- the item's own listing card -- before being
# trusted. Each refuses rather than guesses when its page is ambiguous.
# ---------------------------------------------------------------------------
_DMY_DOTS = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_DMY_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_NAMED_DATE = r"(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})"


def _ymd(y, m, d) -> Optional[datetime]:
    """A real calendar date, NOT yet bounds-checked: see _one."""
    try:
        return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
    except ValueError:
        return None


def _one(found: set) -> Optional[datetime]:
    """The single distinct date, bounds-checked only AFTER the count.

    The order matters. An EUIPO page reading "09/09/2026 ... apply by 30/09/2026"
    holds two dates; bounds-checking first silently dropped the future deadline and
    left one "unambiguous" date. A future deadline beside the real date is exactly
    the ambiguity these rules exist to refuse (caught by a test, 11 Sep 2026)."""
    found.discard(None)
    if len(found) != 1:
        return None
    dt = next(iter(found))
    return dt if _in_bounds(dt) else None


def _eeas_date(soup, html: str = "", url: str = "") -> Optional[datetime]:
    """EEAS prints `<div class="node__meta">01.06.2026 | Press and information team`.

    The page's OWN meta sits in the main card beside the <h1> (or at page level on
    a campaign page). Related items -- "more stories", "related content" -- carry
    node__meta too, inside a Views listing, and the first node__meta on a campaign
    page belongs to one of THEM: it read 10 March for a campaign the listing dates
    4 March. So metas inside a Views listing are skipped, and the rule answers only
    when the page's own metas hold exactly one date. Agreed with the filter-page card
    on 9 of 9 comparable pages once related metas are excluded.
    """
    found = set()
    for meta in soup.select(".node__meta"):
        if meta.find_parent(class_=("related-grid", "view-content", "views-element-container")):
            continue
        for d, m, y in _DMY_DOTS.findall(meta.get_text(" ", strip=True)):
            found.add(_ymd(y, m, d))
    return _one(found)


def _ombudsman_date(soup, html: str = "", url: str = "") -> Optional[datetime]:
    """The Ombudsman's document block reads
    `News | - | Date | Thursday | 20 August 2026 | Case | ... | Opened on | ...`.
    Only the date after the `Date` label is the document's; `Opened on` and
    `Decision on` belong to the case. Matched the listing card on 4 of 4."""
    found = set()
    for blk in soup.select(".article-information"):
        txt = blk.get_text(" | ", strip=True)
        for raw in re.findall(r"(?:^|\|)\s*Date\s*\|\s*(?:[A-Za-z]+\s*\|\s*)?" + _NAMED_DATE, txt):
            dt = parse_listing_date(raw)
            found.add(dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt)
    return _one(found)


def _storyblok_first_published(html: str, url: str) -> Optional[datetime]:
    """`first_published_at` of the Storyblok story whose `full_slug` IS this page.

    EUIPO's page payload embeds several stories (the page's own, plus layout stories
    whose first_published_at is 2023-05-24 on every page), so the value is read only
    from the object whose full_slug equals the URL path, looking FORWARD from that key:
    Storyblok serialises first_published_at after full_slug, and looking backwards
    reaches the previous story. Matched the listing card on 3 of 3 (11 Sep 2026)."""
    slug = urlparse((url or "").strip()).path.strip("/")
    if not slug or not html:
        return None
    txt = html.replace('\\"', '"')
    found = set()
    for m in re.finditer(r'"full_slug"\s*:\s*"' + re.escape(slug) + r'/?"', txt):
        for y, mo, d in re.findall(r'"first_published_at"\s*:\s*"(\d{4})-(\d{2})-(\d{2})T',
                                   txt[m.end(): m.end() + 2000])[:1]:
            found.add(_ymd(y, mo, d))
    return _one(found)


def _euipo_date(soup, html: str = "", url: str = "") -> Optional[datetime]:
    """EUIPO shows one `01/06/2026` in a styling span with a hashed class name.

    Day-first is proven, not assumed: `29/07/2026` cannot be month-first, and on 3 of
    3 items the value matched the listing card's "July 29, 2026". Taken when the
    visible text (scripts removed) holds exactly one such date.

    When it holds several (a webinar page lists every session; a guidelines notice
    cites earlier editions), the page's own Storyblok story answers instead. On the 4
    undated pages that show dates, its first_published_at was the first date shown on
    every one."""
    found = {_ymd(y, m, d) for d, m, y in _DMY_SLASH.findall(soup.get_text(" ", strip=True))}
    dt = _one(found)
    if dt is not None:
        return dt
    return _storyblok_first_published(html, url)


def _echa_date(soup, html: str = "", url: str = "") -> Optional[datetime]:
    """ECHA news opens with a dateline, `Helsinki, 11 May 2026 –`. Other dates in the
    body are deadlines (one release cites 14 February 2028), so only the dateline is
    read, and only when there is exactly one."""
    art = soup.select_one(".single-news-article") or soup
    text = art.get_text(" ", strip=True).replace("\xa0", " ")
    found = set()
    for raw in re.findall(r"Helsinki,\s*" + _NAMED_DATE, text):
        dt = parse_listing_date(raw)
        found.add(dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt)
    return _one(found)


def _enisa_date(soup, html: str = "", url: str = "") -> Optional[datetime]:
    """ENISA's own byline: `<p class="events-metadata"><span class="type">Press
    Release</span> <span class="date">Aug 06,2026</span>`.

    The page ALSO lists related publications, each with a `<time datetime>` inside
    `.publications-item`, and those come first in the markup. The generic first-<time>
    carrier stored 16 February 2023 for a release of 6 August 2026 and was wrong on 6 of
    8 pages checked against the listing card on 11 Sep 2026; this byline matched 8 of 8.
    """
    found = set()
    for e in soup.select(".events-metadata .date"):
        dt = parse_listing_date(e.get_text(" ", strip=True))
        found.add(dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt)
    return _one(found)


_HOST_RULES = (
    ("enisa.europa.eu", _enisa_date, "enisa_events_metadata"),
    ("eeas.europa.eu", _eeas_date, "eeas_node_meta"),
    ("ombudsman.europa.eu", _ombudsman_date, "ombudsman_date_label"),
    ("euipo.europa.eu", _euipo_date, "euipo_sole_page_date"),
    ("echa.europa.eu", _echa_date, "echa_helsinki_dateline"),
)


def _rule_for(url: str):
    host = (urlparse((url or "").strip()).hostname or "").lower()
    for suffix, rule, name in _HOST_RULES:
        if host == suffix or host.endswith("." + suffix):
            return rule, name
    return None


def host_item_date(url: str, html: str) -> Tuple[Optional[datetime], Optional[str]]:
    """(datetime, carrier) from a site rule for this URL's host, or (None, None)."""
    found = _rule_for(url)
    if found is None or not html:
        return None, None
    rule, name = found
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    # The raw html and url travel too: a machine-readable carrier can live inside
    # <script> (EUIPO's Storyblok payload), which the soup has just removed.
    dt = rule(soup, html, url)
    return (dt, name) if dt is not None else (None, None)


def _date_from_page(url: str, html: str):
    """A site with a rule is answered by its rule ALONE; every other site by the
    generic carriers.

    Authoritative, not first-then-fallback: on these sites the generic carriers are
    exactly what reads the WRONG element. Falling back on ENISA would take a related
    publication's <time> (2023 for an August 2026 release) the moment the byline was
    missing -- the refusal is worth more than that date.
    """
    if _rule_for(url) is not None:
        return host_item_date(url, html)
    return extract_item_date(html)


def cffi_get(url: str) -> Optional[str]:
    """EUDA sits behind a WAF that 403s a plain requests UA, so its own scraper uses
    a curl_cffi Chrome TLS fingerprint. Reuse that rather than re-tuning headers,
    per feedback_waf_walled_use_playwright."""
    from curl_cffi import requests as creq
    s = creq.Session(impersonate="chrome131")
    try:
        r = s.get(url, timeout=40)
        return r.text if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


_WAF_MODULE = None


def _waf_module():
    """waf_browser_fetcher, imported by file path and registered in sys.modules, as
    the backfill always did: importing it as a package module runs
    services/scrapers/__init__.py, which imports every scraper in the package."""
    global _WAF_MODULE
    if _WAF_MODULE is None:
        import importlib.util
        import pathlib
        f = pathlib.Path(__file__).resolve().parents[1] / "scrapers/waf_browser_fetcher.py"
        spec = importlib.util.spec_from_file_location("waf_browser_fetcher", f)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["waf_browser_fetcher"] = mod
        spec.loader.exec_module(mod)
        _WAF_MODULE = mod
    return _WAF_MODULE


class LazyBrowser:
    """One headless browser for a whole sweep: opened only when a page needs
    rendering, reused, and restarted every `restart_every` pages.

    Why: on 11 Sep 2026 the eu_news_items backfill called the resolver without a
    browser, so every page needing rendering launched a fresh Chromium through
    fetch_one. EEAS throttling sends many rows down that path; on an 8GB machine
    already holding the user's own Chrome (2.6GB), the OS killed the run before its
    first commit. One reused browser is how every long run that day survived; the
    periodic restart caps what a long-lived browser accumulates.

    Quacks like WafBrowserFetcher for browser_get: only `.fetch()` is used.
    """

    def __init__(self, restart_every: int = 40, **browser_kwargs):
        self.restart_every = restart_every
        self.browser_kwargs = browser_kwargs
        self._browser = None
        self._pages = 0
        self.launches = 0

    def fetch(self, url: str, **kwargs):
        if self._browser is not None and self._pages >= self.restart_every:
            self.close()
        if self._browser is None:
            self._browser = _waf_module().WafBrowserFetcher(**self.browser_kwargs).__enter__()
            self._pages = 0
            self.launches += 1
        self._pages += 1
        return self._browser.fetch(url, **kwargs)

    def close(self) -> None:
        if self._browser is not None:
            try:
                self._browser.__exit__(None, None, None)
            finally:
                self._browser = None


def browser_get(url: str, fetcher=None) -> Optional[str]:
    """Rendered HTML. Uses the caller's open WafBrowserFetcher when given one (the
    bespoke and EP writers already hold a browser for the whole run; launching a
    second Chromium per item would be the fan-out an 8GB machine cannot take),
    otherwise a one-shot browser.

    `.html` is `page.content()`, the full DOM with <head>: `strip_chrome` only
    cleans the separate text extraction, so meta and JSON-LD carriers survive."""
    try:
        if fetcher is not None:
            res = fetcher.fetch(url, expand_accordions=False, strip_chrome=False)
        else:
            res = _waf_module().fetch_one(url)
        return (res.html or "") or None
    except Exception:  # noqa: BLE001
        return None


def escalating_get(url: str, fetcher=None, render: bool = True) -> Optional[str]:
    """Plain GET, then a real TLS fingerprint, then a real browser.

    Added 10 September 2026 after the first eu_news_items sweep reported
    `fetch_failed` on 360 of 589 rows and the number was taken at face value for
    about a minute. Sampling the failures showed THREE different things wearing
    one label:

      * HTTP 200 with a full page (EIT, EEAS, CNECT) -- the page was fine and the
        sweep had simply outrun the host. That is the rate limiter being measured,
        not the site (feedback_paced_regression_measures_the_model).
      * HTTP 403 (EUIPO, ECHA) -- a WAF. Use a browser, never tune headers
        (feedback_waf_walled_use_playwright).
      * HTTP 429 (EEAS) -- explicitly us, going too fast.

    So a wall or an empty 200 escalates instead of being recorded as an absent
    date. An empty result is not absence; it is usually the instrument
    (feedback_empty_result_is_a_broken_instrument).
    """
    r = http_get(url)
    if r is not None and getattr(r, "status_code", 0) not in _WALL_STATUSES:
        ctype = (r.headers.get("content-type") or "").lower()
        if ("html" in ctype or "xml" in ctype) and len(r.text) > 2000:
            return r.text
        # a 200 with nothing parseable is also a wall
    try:
        html = cffi_get(url)
        if html and len(html) > 2000:
            return html
    except Exception:  # noqa: BLE001
        pass
    if not render:
        return None
    return browser_get(url, fetcher=fetcher)


def resolve_item_date(url: str, *, fetcher=None, render: bool = True) -> Tuple[Optional[datetime], str]:
    """(publication datetime, provenance) for one news item, or (None, reason).

    `reason` is one of MISS_PROVENANCES. `fetcher` is an open WafBrowserFetcher to
    reuse for any rendering; without one a one-shot browser is launched.

    `render=False` never opens a browser. For server-rendered sites whose date is in
    the static HTML (EEAS), rendering adds nothing but memory: on 11 Sep 2026 the OS
    killed an EEAS sweep a minute in, on an 8GB machine shared with the user's own
    Chrome, VS Code and other sessions. A page that needed the browser then reads as
    `fetch_failed` / `no_carrier`, and a later run with rendering can pick it up.
    """
    # Stored URLs can carry whitespace: ENISA's listing writes `href="/news/slug "`.
    url = (url or "").strip()
    if not url:
        return None, "no_url"
    if presscorner_reference(url):
        dt = presscorner_event_date(url)
        if dt is not None:
            return dt, "presscorner_api"
    if url.lower().split("#", 1)[0].split("?", 1)[0].endswith(".pdf"):
        # A PDF is not HTML: extract_item_date on its bytes would be reading noise,
        # and rendering it twice would cost two browser loads to learn nothing.
        return None, "pdf_not_read"
    html = escalating_get(url, fetcher=fetcher, render=render)
    if html is None:
        return None, "fetch_failed"
    dt, carrier = _date_from_page(url, html)
    if dt is not None:
        return dt, carrier
    # ESCALATE ON EXTRACTION FAILURE, not only on fetch failure (10 September 2026).
    # `escalating_get` decides "wall" from the status and the size, so a 200 serving
    # a full shell looked healthy and the browser was never tried. The test has to
    # be "did we get the thing we came for", not "did the request look fine".
    rendered = browser_get(url, fetcher=fetcher) if render else None
    if rendered:
        dt, carrier = _date_from_page(url, rendered)
        if dt is not None:
            return dt, f"{carrier}_rendered"
    return None, "no_carrier"
