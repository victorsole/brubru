"""
Shared primitives for the economy & finance scrapers (ECB, the EU financial
institutions, ESM). Each body's module (economy_ecb.py, economy_eba.py, ...)
imports these and adds its own source map + extraction strategy.

No LLM is used anywhere in economy ingestion.
"""
from __future__ import annotations

import io
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 BrubruBot/1.0"
_TIMEOUT = 30
_BODY_CAP = 800_000  # chars; working-paper PDFs can be large


@dataclass
class Item:
    # CANONICAL item shape. The 5 "target" datapoints (public_url, body_txt, body_html,
    # document_date, creation_date) are BEST-EFFORT, not guaranteed: creation_date is
    # always set; public_url is always non-empty (extract handlers fall back to a
    # synthetic guid); body_txt/body_html are populated only on the deep/detail-fetch
    # path; document_date is best-effort. Type does not enforce this — see
    # extract_engine_plan.md Contract A (relaxed to match reality).
    body_code: str
    item_type: str            # canonical, caller-supplied page-level hint:
                              # news | event | publication | topic | consultation | tender | legal
    title: str
    public_url: str
    summary: str | None = None
    body_txt: str | None = None
    body_html: str | None = None
    document_date: datetime | None = None
    creation_date: datetime | None = None
    source_kind: str | None = None
    guid: str | None = None
    extras: dict = field(default_factory=dict)


_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # C0 controls except \t \n \r


def intentionally_empty(reason: str):
    """Mark an ingestor that returns [] BY DESIGN, so the health detector can
    tell intentional silence from a regression.

    Without this, `_classify` sees `parse_count == 0` with historical rows and
    reports BROKEN "regression" -- correctly, on the evidence available to it,
    and permanently wrong. That is exactly what happened to
    `edps/press_release` and `edps/publication`: they were deliberately
    switched to `return []` on 17 Aug 2026 (EDPS merged press-releases and
    publications into one press-news feed), the detector shipped two days
    later, and it alerted every night on a state somebody had just created on
    purpose. `consecutive_fails` could never reset, because the condition was
    permanent by design.

    The marker lives on the FUNCTION, next to the `return []`, rather than in a
    registry somewhere else, so the two cannot drift: re-enabling the scraper
    and deleting the marker are the same edit.

    Usage::

        @intentionally_empty("upstream merged this feed into `news`, Aug 2026")
        def ingest_x(*, fetch_bodies: bool = True, **_) -> list[Item]:
            return []
    """
    def deco(fn):
        fn.intentionally_empty = reason
        return fn
    return deco


def clean(s: str | None) -> str | None:
    """Strip NUL + other C0 control chars Postgres TEXT rejects (PDF extraction emits them)."""
    if not s:
        return s
    return _CTRL_RE.sub("", s)


def norm_url(url: str) -> str:
    """Collapse doubled slashes after the host (some feeds emit ecb.europa.eu//press/...)."""
    if not url:
        return url
    url = url.strip()
    m = re.match(r"^(https?://[^/]+)(/.*)$", url)
    if not m:
        return url
    return m.group(1) + re.sub(r"/{2,}", "/", m.group(2))


def http_get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return r
    except requests.RequestException:
        return None
    return None


def to_dt(struct) -> datetime | None:
    if not struct:
        return None
    try:
        return datetime(*struct[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def extract_html(html: str) -> tuple[str | None, str | None]:
    """(body_txt, body_html) from a server-rendered detail page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    node = soup.find("main") or soup.find("article") or soup.body or soup
    body_html = clean(str(node)[:_BODY_CAP])
    body_txt = clean(node.get_text("\n", strip=True)[:_BODY_CAP])
    return (body_txt or None), (body_html or None)


def extract_pdf(content: bytes) -> str | None:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        parts, total = [], 0
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
            total += len(t)
            if total > _BODY_CAP:
                break
        return clean("\n".join(parts).strip()[:_BODY_CAP]) or None
    except Exception:
        return None


def fetch_detail(url: str) -> tuple[str | None, str | None, str]:
    """Return (body_txt, body_html, source_kind) for one item URL.

    HTML -> parsed; PDF -> text-extracted; any other type (Office docs, zip,
    images) -> a link wrapper, never fed to the HTML parser as binary.
    """
    body_txt, body_html, kind, _dt, _carrier = fetch_detail_dated(url)
    return body_txt, body_html, kind


def fetch_detail_dated(url: str):
    """fetch_detail plus the publication date, from the SAME single fetch.

    Returns (body_txt, body_html, source_kind, document_date, date_carrier).

    Needed because `extract_html` decomposes <script> and reads from
    <main>/<article>/<body>, so the JSON-LD block and the <head> <meta> tags -- the
    two carriers the EIB and EU-Rail publish their dates in -- are gone by the time
    body_html exists. Extracting the date here means one request, not two, on
    scrapers that already fetch every item page.
    """
    r = http_get(url)
    if r is None:
        return None, None, "unreachable", None, None
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/pdf" in ctype or url.lower().endswith(".pdf"):
        return (extract_pdf(r.content),
                f'<p>PDF document: <a href="{url}">{url}</a></p>', "pdf", None, None)
    if "html" not in ctype and "xml" not in ctype:
        # Office docs (.docx/.xlsx), archives, images, etc. — do not parse as HTML.
        kind = (ctype.split(";")[0].split("/")[-1] or "file")[:20] or "file"
        return None, f'<p>Document: <a href="{url}">{url}</a></p>', kind, None, None
    body_txt, body_html = extract_html(r.text)
    doc_dt, carrier = extract_item_date(r.text)
    return body_txt, body_html, "html", doc_dt, carrier


# --- date parsing ----------------------------------------------------------
# Handles: 11/06/2026 ; 29.05.2026 ; "8 June 2026" / "8 JUNE 2026" ; "8 Dec 2026" ;
# ordinals "2nd June 2026" ; ranges "11/06/2026 - 12/06/2026" and "18-19 Nov 2026"
# (-> the start day).
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_NUM_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DOT_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_ORDINAL_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_NAME_DATE_RE = re.compile(r"\b(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b")


def _iso_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_listing_date(text: str) -> datetime | None:
    text = _ORDINAL_RE.sub(r"\1", text or "")    # "2nd June 2026" -> "2 June 2026"
    m = _NUM_DATE_RE.search(text)                # 11/06/2026 (ranges -> first match = start)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    m = _DOT_DATE_RE.search(text)                # 29.05.2026 (day.month.year)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    m = _US_NAME_DATE_RE.search(text)            # Jun. 22, 2026 / June 22, 2026
    if m:
        month = _MONTHS.get(m.group(1).lower().rstrip("."))
        if month:
            try:
                return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)
            except ValueError:
                return None
    m = _NAME_DATE_RE.search(text)               # 8 June 2026 / 8 Dec 2026 / 18-19 Nov 2026
    if m:
        month = _MONTHS.get(m.group(2).lower().rstrip("."))
        if not month:
            return None
        try:
            return datetime(int(m.group(3)), month, int(m.group(1)), tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


# --- is this "body" actually an error page? ---------------------------------
#
# Why (measured 8 September 2026)
# -------------------------------
# `extract_html` will happily turn a 404 page into a body_txt, and nothing
# downstream can tell the difference: the row satisfies "body_txt is not null",
# passes every five-datapoint check, and feeds chat and RAG as though it were the
# article. The Ombudsman scraper stored 4 such rows whose entire body was
#
#     "You have a complaint against an EU institution or body? ... Oops!
#      404 Not Found  Sorry, an error has occured. Requested page not found!"
#
# plus 2 whose body was unrendered template placeholders
# (`![template_principal_interactiveguide]`). A non-empty body is not a valid body,
# and passing a coverage check on junk is worse than failing it honestly.
#
# Deliberately conservative: it matches explicit error/placeholder signatures and a
# hard length floor, NOT "short" in general. Plenty of legitimate agency notices are
# two sentences long, and suppressing those would trade a false positive for a false
# negative. Returns a reason string so a caller can log WHY, never a bare bool.

# STRONG signatures: phrases and markup that effectively never appear in EU-body
# prose, so they are decisive at any body length.
_ERROR_BODY_STRONG = (
    ("404_not_found", re.compile(r"\b404\s+not\s+found\b", re.I)),
    ("page_not_found", re.compile(r"requested page not found", re.I)),
    ("error_occurred", re.compile(r"an error has occ?ur+ed", re.I)),
    ("unrendered_template", re.compile(r"!\[template[_.]")),
    # WordPress page-builder shortcodes leaking into the text. rail-research.europa.eu
    # serves some posts' content.rendered as raw Divi markup
    # (`[et_pb_section fb_built="1" _builder_version="4.16"]...`), which as body_txt is
    # markup noise, not prose. Measured 8 September 2026.
    ("page_builder_shortcode", re.compile(r"\[(?:et_pb_|vc_|fusion_)\w+", re.I)),
)

# WEAK signatures: real error-page wording that ALSO occurs in legitimate prose, so
# they only count on a body too short to be an article.
#
# Why this split exists (measured 8 September 2026)
# ------------------------------------------------
# The first version treated "access denied" as decisive and threw away 2,612 chars of
# a genuine Ombudsman article -- "Ombudsman asks Commission to deal urgently with
# systemic delays in processing public access to documents requests" -- because it
# quoted the idiom *"access delayed is access denied"*. Access-to-documents complaints
# are the Ombudsman's single most characteristic subject, so that guard would have
# silently suppressed exactly the content the body is known for.
#
# An error page is defined by having NO CONTENT; the phrase only tells you why. So a
# weak signature is decisive below _WEAK_MAX_CHARS and ignored above it.
_ERROR_BODY_WEAK = (
    ("access_denied", re.compile(r"\b(?:403\s+forbidden|access denied)\b", re.I)),
    ("page_not_found_loose", re.compile(r"page (?:could )?not be found", re.I)),
    ("server_error", re.compile(r"\b(?:500|502|503)\s+(?:internal server error|bad gateway|service unavailable)\b", re.I)),
    ("js_required", re.compile(r"(?:requires|enable)\s+javascript", re.I)),
)

_BODY_MIN_CHARS = 40
# A real error page is short. The ones measured: 404 panel 203 chars, template
# placeholders 130, chrome-only 109. Real articles ran 1,714 to 8,305.
_WEAK_MAX_CHARS = 600


def error_body_reason(body_txt: str | None) -> str | None:
    """Why this body must not be stored, or None if it looks like real content."""
    if body_txt is None:
        return None                      # absent is a different state from invalid
    txt = body_txt.strip()
    if not txt:
        return "empty"
    for name, rx in _ERROR_BODY_STRONG:
        if rx.search(txt):
            return name
    if len(txt) < _WEAK_MAX_CHARS:
        for name, rx in _ERROR_BODY_WEAK:
            if rx.search(txt):
                return name
    if len(txt) < _BODY_MIN_CHARS:
        return "below_min_chars"
    return None


# --- publication date, read off the ITEM'S OWN page -------------------------
#
# Why this exists (measured 8 September 2026)
# -------------------------------------------
# 1,761 of 12,509 news rows in economy_items carry no document_date, across 17
# bodies, and for five of them the FETCHER IS ALIVE -- recent creation_date, every
# row undated. Those are not dead scrapers; they never extracted the date. The
# worst case hardcoded it: euda_content.py passed `document_date=None` for 978 rows.
#
# The three carriers below cover the live sites checked on that date:
#   euda  <time datetime="2026-06-30T11:50:03+01:00">      4/4 pages
#   rail  <meta property="article:published_time">         2/2 pages
#   eib   JSON-LD "datePublished"                           3/4 pages
#
# What this must never do
# -----------------------
# Read the date the publisher states for THAT item, on THAT item's page, or return
# None. Specifically NOT the sitemap <lastmod> (a modification date is a different
# fact), NOT the ingest time, and NOT a date inferred from the URL. Returning None
# is correct and honest; `/api/v2/news/all` coalesces to creation_date for FILTERING
# and still reports document_date as null so the caller knows it is unknown.
# See feedback_backfill_no_hallucination.

# Month-first, as SESAR JU renders it: "Jun. 22, 2026".
_US_NAME_DATE_RE = re.compile(r"\b([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),\s*(\d{4})\b")

_ITEM_DATE_CARRIERS = (
    ("time_datetime",
     re.compile(r"<time[^>]*\sdatetime=[\"']([^\"']+)[\"']", re.I)),
    ("og_published",
     re.compile(r"property=[\"']article:published_time[\"'][^>]*content=[\"']([^\"']+)[\"']", re.I)),
    ("og_published_rev",
     re.compile(r"content=[\"']([^\"']+)[\"'][^>]*property=[\"']article:published_time[\"']", re.I)),
    ("jsonld_datePublished",
     re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.I)),
    # LAST on purpose: a class-named element is weaker evidence than a machine-readable
    # meta tag, so this only fires when none of the above matched. Two agencies publish
    # their date ONLY this way and nowhere else -- SESAR JU in
    # `<div class="published-date">Jun. 22, 2026</div>` (18 rows undated) and the EIF in
    # `<span class="eif-inner-date">4 Sept 2026</span>` (37 rows undated).
    #
    # Matches any class ending in `-date` or named exactly `date`, so a third site does
    # not need a fourth entry here -- minus the suffixes that mean something OTHER than
    # publication. That exclusion is the important half: these pages are full of dates
    # that are not the publication date. The SESAR Innovation Days item carries
    # "21 September 2026" twice as the EVENT date, which is why this reads the matched
    # element's own text and never the page.
    # Loose here, precise in Python: the regex only requires "date" somewhere in the
    # class attribute (which keeps the candidate list short), and extract_item_date
    # then checks the individual class TOKENS. Trying to express "a class token that
    # is `date` or ends in -date, anywhere in a multi-class attribute" as one regex
    # produced a pattern that silently missed both `class="date"` and
    # `class="field eif-inner-date field__item"`.
    ("date_class",
     re.compile(r'class=["\']([^"\']*date[^"\']*)["\'][^>]*>\s*([^<]{4,40})<', re.I)),
)

# Class suffixes that end in -date but do not mean "published on". Checked against the
# matched class attribute before the value is trusted.
# Publication-date classes that do NOT end in "-date" and so fail the generic
# shape test above. Added 10 September 2026: EIT publishes its date inside
# `<div class="metadata"> ... <div class="date-place">17/12/2025</div>`, which is
# a byline element, not body prose -- verified by reading the surrounding HTML,
# not inferred from the text containing a date.
#
# The DD/MM order was DERIVED, not assumed: across 14 EIT pages the first field
# ranged 3-29 and the second never exceeded 12. `01/04/2026` alone would have
# been ambiguous and was not parsed on its own.
#
# This is an ALLOWLIST on purpose. Relaxing the shape test to `startswith("date")`
# would have re-admitted every event and deadline class the blocklist below exists
# to keep out.
_PUBLICATION_DATE_CLASSES = ("date-place",)

_NON_PUBLICATION_DATE_CLASSES = (
    "event-date", "deadline-date", "expiry-date", "end-date", "start-date",
    "update-date", "updated-date", "modified-date", "closing-date", "due-date",
)

_LOOSE_YMD_RE = re.compile(
    r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2})(?::(\d{2}))?)?")


def _normalise_dt_string(s: str) -> str:
    """Zero-pad a loose ISO-ish Y-M-D so fromisoformat will take it.

    The EIB publishes `"datePublished": "2026-09-7 02:30"` -- single-digit day and a
    space separator. datetime.fromisoformat rejects that outright, so every EIB news
    row lost its date silently. Verified 8 Sep 2026.
    """
    m = _LOOSE_YMD_RE.match(s or "")
    if not m:
        return (s or "").strip()
    y, mo, d, hh, mm, ss = m.groups()
    out = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    if hh is not None:
        out += f"T{int(hh):02d}:{mm}:{ss or '00'}"
    return out + (s[m.end():].strip() if hh is not None else "")


def extract_item_date(html: str, *, today: datetime | None = None):
    """Return (datetime, carrier_name) from an item page, or (None, None).

    Tries each carrier in order and takes the FIRST that parses to a sane date.
    Sanity bounds are deliberate: a future publication date is not a publication
    date, and `/api/v2/news/latest` already had to stop a scraped deadline setting
    the corpus freshness anchor to 2031 and making `stale` False for ever.
    """
    if not html:
        return None, None
    today = today or datetime.now(timezone.utc)
    floor = datetime(1990, 1, 1, tzinfo=timezone.utc)
    ceiling = today + timedelta(days=1)          # tz slop only, not a real window
    for name, rx in _ITEM_DATE_CARRIERS:
        for raw in rx.findall(html)[:12]:
            if name == "date_class":
                # (class_attr, text). Skip classes that end in -date but mean
                # something other than "published on"; an event or deadline date is
                # often in the past and would be stored as a publication date without
                # anything looking wrong.
                cls, raw = raw
                tokens = [t.lower() for t in cls.split()]
                if any(bad in t for t in tokens for bad in _NON_PUBLICATION_DATE_CLASSES):
                    continue
                if not any(t == "date" or t.endswith("-date") or t in _PUBLICATION_DATE_CLASSES
                           for t in tokens):
                    continue
            dt = _iso_dt(_normalise_dt_string(raw)) or parse_listing_date(raw)
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if floor <= dt <= ceiling:
                return dt, name
    return None, None


# --- generic EU ECL (Europa Component Library) listing scraper --------------
# Many europa.eu bodies (EIOPA, AMLA, EPPO, Commission DGs) render listings as
# .ecl-content-item cards with a <time datetime> date, a standalone title link
# and a description. Server-rendered + ?page=N paginated.


def _parse_ecl_cards(html: str, base: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for ci in soup.select(".ecl-content-item"):
        a = ci.select_one(".ecl-content-block__title a[href]") or ci.select_one("a[href]")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else base + href)
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        t = ci.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if (t and t.get("datetime")) else None
        if doc_dt is None:
            # ECL date-block component (events): day / month / year split spans.
            db = ci.select_one(".ecl-date-block")
            if db:
                day = db.select_one(".ecl-date-block__day")
                mon = db.select_one(".ecl-date-block__month")
                yr = db.select_one(".ecl-date-block__year")
                mon_txt = (mon.get("title") or mon.get_text(strip=True)) if mon else ""
                if day and mon_txt and yr:
                    doc_dt = parse_listing_date(
                        f"{day.get_text(strip=True)} {mon_txt} {yr.get_text(strip=True)}")
        if doc_dt is None:
            meta = ci.select_one(".ecl-content-block__primary-meta-item time") or t
            doc_dt = parse_listing_date(meta.get_text(" ", strip=True)) if meta else None
        desc = ci.select_one(".ecl-content-block__description")
        summary = clean(desc.get_text(" ", strip=True)[:1000]) if desc else None
        out.append((url, title, doc_dt, summary))
    return out


def scrape_ecl_listing(body_code: str, item_type: str, listing_urls, base: str,
                       *, fetch_bodies: bool = True, max_pages: int = 6):
    """Page through ECL .ecl-content-item listings and build Items."""
    items = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        for page in range(max_pages):
            sep = "&" if "?" in listing else "?"
            url = listing if page == 0 else f"{listing}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = _parse_ecl_cards(r.text, base)
            if not rows:
                break
            new = 0
            for url_i, title, doc_dt, summary in rows:
                if url_i in seen:
                    continue
                seen.add(url_i)
                new += 1
                items.append(Item(body_code=body_code, item_type=item_type, title=title,
                                  public_url=url_i, summary=summary, document_date=doc_dt,
                                  creation_date=now, source_kind="html", guid=url_i))
            if new == 0:
                break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


# --- generic EU ECL file-library scraper -----------------------------------
# ECL document libraries (AMLA, and other europa.eu bodies) render each document
# as an .ecl-file card: a title in .ecl-file__title, type + date in
# .ecl-file__detail-meta-item spans, and a /document/download/<uuid> PDF link.
# Server-rendered + ?page=N paginated.
def _parse_ecl_file_cards(html: str, base: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for f in soup.select(".ecl-file"):
        a = f.select_one("a[href]")
        title_el = f.select_one(".ecl-file__title")
        if not a or not a.get("href") or not title_el:
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else base + href)
        title = clean(title_el.get_text(" ", strip=True))
        if not title:
            continue
        doc_dt = None
        metas = f.select(".ecl-file__detail-meta-item")
        for m in metas:                       # the date meta is the one that parses
            d = parse_listing_date(m.get_text(" ", strip=True))
            if d:
                doc_dt = d
                break
        out.append((url, title, doc_dt))
    return out


def scrape_ecl_file_listing(body_code: str, item_type: str, listing_urls, base: str,
                            *, fetch_bodies: bool = True, max_pages: int = 8):
    """Page through ECL .ecl-file document libraries and build Items (PDFs)."""
    items = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        for page in range(max_pages):
            sep = "&" if "?" in listing else "?"
            url = listing if page == 0 else f"{listing}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = _parse_ecl_file_cards(r.text, base)
            if not rows:
                break
            new = 0
            for url_i, title, doc_dt in rows:
                if url_i in seen:
                    continue
                seen.add(url_i)
                new += 1
                items.append(Item(body_code=body_code, item_type=item_type, title=title,
                                  public_url=url_i, document_date=doc_dt, creation_date=now,
                                  source_kind="pdf", guid=url_i))
            if new == 0:
                break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            it.source_kind = kind if kind in ("pdf", "html") else it.source_kind
    return items


# --- generic curated-page "topics" snapshotter -----------------------------
# Snapshot a curated list of stable reference / thematic landing pages as topic
# Items: title from the page h1 (or <title>, else the slug) and the body via
# extract_html. Reference pages carry no publication date, so document_date is
# left null. Used across single-body agency folders for their "topics" resource.
def snapshot_topics(body_code: str, base: str, paths, *, fetch_bodies: bool = True,
                    title_max: int = 300, pace: float = 0.3, retries: int = 2,
                    prefer_title: bool = False):
    # prefer_title=True reads the title from <title> before the page h1 — for sites
    # whose h1 is a fixed banner/slogan repeated on every page (e.g. CdT).
    items = []
    now = datetime.now(timezone.utc)
    for path in paths:
        url = base + path if path.startswith("/") else path
        # ec.europa.eu subdomains rate-limit bursts: pace requests and retry the
        # transient blocks (None) a couple of times before giving up on a page.
        r = http_get(url)
        attempt = 0
        while r is None and attempt < retries:
            attempt += 1
            time.sleep(1.5 * attempt)
            r = http_get(url)
        time.sleep(pace)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        title_tag = soup.title.get_text(strip=True) if soup.title else ""
        if prefer_title and title_tag:
            title = clean(title_tag.split(" | ")[0].split(" - ")[0])
        elif h1 and len(h1.get_text(strip=True)) > 2:
            title = clean(h1.get_text(" ", strip=True))
        elif title_tag:
            title = clean(title_tag.split(" | ")[0].split(" - ")[0])
        else:
            title = clean(url.rstrip("/").rsplit("/", 1)[-1].replace("_en", "").replace("-", " ").title())
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        items.append(Item(body_code=body_code, item_type="topic", title=(title or url)[:title_max],
                          public_url=norm_url(url), creation_date=now, source_kind="html",
                          guid=norm_url(url), body_txt=body_txt, body_html=body_html))
    return items


# --- generic ECB/ESRB date-indexed <dl> listing scraper --------------------
# ECB-CMS bodies (ECB, ESRB) render listings as <dt>(date) + <dd>(title+link).
# Some index pages are server-rendered; others inject the <dl> client-side
# (use_playwright=True). parse_dl_cards handles either rendered HTML.
def parse_dl_cards(html: str, base: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for dd in soup.find_all("dd"):
        a = dd.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else base + href)
        if "/shared/" in url:
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        dt_node = dd.find_previous_sibling("dt")
        doc_dt = parse_listing_date(dt_node.get_text(" ", strip=True)) if dt_node else None
        out.append((url, title, doc_dt))
    return out


def scrape_dl_listing(body_code: str, item_type: str, pages, base: str, *,
                      use_playwright: bool = False, fetch_bodies: bool = True,
                      settle_ms: int = 6000):
    items = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)

    def _collect(html: str):
        for url, title, doc_dt in parse_dl_cards(html or "", base):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code=body_code, item_type=item_type, title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))

    if use_playwright:
        from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
        with WafBrowserFetcher(settle_ms=settle_ms) as f:
            for page in pages:
                res = f.fetch(page, strip_chrome=False)
                _collect(res.html)
    else:
        for page in pages:
            r = http_get(page)
            if r is not None:
                _collect(r.text)

    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


# --- generic .xlsx dataset ingestor ----------------------------------------
# Many EU agencies publish a register/database as a downloadable .xlsx whose rows
# are entities (medicines, shortages, varieties, ...). Each row IS the content,
# so no per-row HTTP fetch. Header is auto-detected (the row with the most cells).
def _xlsx_date(val):
    from datetime import date as _date
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc)
    if isinstance(val, _date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    return parse_listing_date(str(val)) if val else None


def ingest_xlsx_dataset(xlsx_url, body_code, item_type, *,
                        title_cols, url_cols=(), date_cols=(), max_body_cols=40,
                        sheet=None, record_url=None, timeout=180):
    """Build Items from a downloadable .xlsx register.

    title_cols / url_cols / date_cols are ordered lists of header substrings;
    the first match (that is non-empty for the row, for the title) wins.

    sheet      : worksheet name to read (default: the active sheet).
    record_url : canonical dataset URL; when a row has no own URL, the item's
                 public_url is synthesised as ``{record_url}#row=<n>`` so the
                 (body_code, item_type, public_url) UNIQUE constraint holds.
    """
    import io
    try:
        from openpyxl import load_workbook
    except ImportError:
        return []
    try:
        resp = requests.get(xlsx_url, headers={"User-Agent": _UA}, timeout=timeout,
                            allow_redirects=True)
        if resp.status_code != 200:
            return []
    except requests.RequestException:
        return []
    wb = load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
    ws = wb[sheet] if (sheet and sheet in wb.sheetnames) else wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    scan = min(15, len(rows))
    hdr_idx = max(range(scan), key=lambda i: sum(1 for c in rows[i] if c is not None))
    header = [str(c).replace("\n", " ").strip() if c is not None else "" for c in rows[hdr_idx]]

    def cols_for(cands):
        out = []
        for cand in cands:
            for i, h in enumerate(header):
                if cand.lower() in h.lower() and i not in out:
                    out.append(i)
        return out

    title_idxs = cols_for(title_cols)
    url_idxs = cols_for(url_cols)
    date_idxs = cols_for(list(date_cols) + ["date"])
    now = datetime.now(timezone.utc)
    items, seen = [], set()
    for rownum, row in enumerate(rows[hdr_idx + 1:]):
        title = None
        for ti in title_idxs:
            if ti < len(row) and row[ti] not in (None, ""):
                title = clean(str(row[ti]).strip())
                if title:
                    break
        if not title:
            # fallback: first non-empty text cell whose header is not a url/date
            for i, h in enumerate(header):
                if i < len(row) and isinstance(row[i], str) and row[i].strip() \
                        and "url" not in h.lower() and "date" not in h.lower():
                    title = clean(row[i].strip())
                    if title:
                        break
        if not title:
            continue
        url = None
        for ui in url_idxs:
            if ui < len(row) and row[ui]:
                url = str(row[ui]).strip()
                break
        if not url and record_url:
            # no per-row URL: synthesise a unique one so the UNIQUE constraint holds
            url = f"{record_url}#row={rownum + 1}"
        guid = url or f"{item_type}:{title}:{rownum}"
        if guid in seen:
            continue
        seen.add(guid)
        doc_dt = None
        for di in date_idxs:
            if di < len(row):
                doc_dt = _xlsx_date(row[di])
                if doc_dt:
                    break
        lines = []
        for i, h in enumerate(header[:max_body_cols]):
            if h and i < len(row) and row[i] not in (None, "") and "url" not in h.lower():
                lines.append(f"{h}: {str(row[i]).strip()}")
        body_txt = clean("\n".join(lines)) or None
        body_html = clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>") if lines else None
        summary = clean(" | ".join(lines[:4])) if lines else None
        items.append(Item(body_code=body_code, item_type=item_type, title=title,
                          public_url=norm_url(url) if url else None,
                          summary=summary, body_txt=body_txt, body_html=body_html,
                          document_date=doc_dt, creation_date=now,
                          source_kind="dataset", guid=guid))
    return items

# --- Multilingual dateline parsing -------------------------------------------
# Press-release PDFs open with a dateline -- "22 May 2014, Barcelona",
# "Barcelone, le 22 mai 2014", "Barcelona, 17 de marc de 2014" -- which is the
# publisher's own statement of the publication date and the only date carrier some
# bodies expose. f4e publishes 157 press releases as PDFs with no date anywhere in
# the listing markup, no <time>, and no date in the link text.
#
# Six languages, matching what Brubru supports (EN, FR, ES, CA, IT, NL) plus DE,
# because F4E publishes German copies too. Accent-folded so "marc"/"marc" and
# "Marz"/"Marz" both resolve.
_DATELINE_MONTHS: dict[str, int] = {}
for _i, _names in enumerate((
    ("january", "januar", "janvier", "enero", "gener", "gennaio", "januari", "jan"),
    ("february", "februar", "fevrier", "febrero", "febrer", "febbraio", "februari", "feb"),
    ("march", "marz", "mars", "marzo", "marc", "maart", "mar"),
    ("april", "avril", "abril", "aprile", "apr"),
    ("may", "mai", "mayo", "maig", "maggio", "mei"),
    ("june", "juni", "juin", "junio", "juny", "giugno", "jun"),
    ("july", "juli", "juillet", "julio", "juliol", "luglio", "jul"),
    ("august", "aout", "agosto", "agost", "augustus", "aug"),
    ("september", "septembre", "septiembre", "setembre", "settembre", "sep", "sept"),
    ("october", "oktober", "octobre", "octubre", "ottobre", "oct", "okt"),
    ("november", "novembre", "noviembre", "novembre", "nov"),
    ("december", "dezember", "decembre", "diciembre", "desembre", "dicembre", "december", "dec", "dez"),
), start=1):
    for _n in _names:
        _DATELINE_MONTHS[_n] = _i

# "22 May 2014" / "le 22 mai 2014" / "17 de marc de 2014" / "22. Mai 2014"
_DATELINE = re.compile(
    r"\b(\d{1,2})\s*\.?\s*(?:de\s+|d'|dei\s+)?"
    r"([A-Za-z\u00C0-\u024F]{3,12})\.?"
    r"\s*(?:de\s+|del\s+|dell'|)\s*(\d{4})\b",
    re.I | re.U,
)


def _fold(t: str) -> str:
    """Strip accents so month tables need one spelling per language, not four."""
    return "".join(c for c in unicodedata.normalize("NFKD", t)
                   if not unicodedata.combining(c)).lower()


def extract_dateline_date(text: str, *, window: int = 400) -> Optional[datetime]:
    """First plausible day-precision date in the opening `window` chars of `text`.

    Scoped to the opening deliberately: a press release states its own date at the
    top, while the body may quote other years ("the 2035 target", "since 1998") and
    a whole-document scan would pick those up. Returns None rather than a guess --
    an undated row is honest, a wrong date is not (feedback_backfill_no_hallucination).
    """
    if not text:
        return None
    head = text[:window]
    for m in _DATELINE.finditer(head):
        day, name, year = m.group(1), _fold(m.group(2)), m.group(3)
        month = _DATELINE_MONTHS.get(name)
        if not month:
            continue
        try:
            dt = datetime(int(year), month, int(day), tzinfo=timezone.utc)
        except ValueError:
            continue
        # Same guards as extract_item_date: no future news, nothing pre-1990.
        if dt > datetime.now(timezone.utc) + timedelta(days=1):
            continue
        if dt.year < 1990:
            continue
        return dt
    return None


# Eight-digit date runs in a filename: Press_release_20070628_english.pdf,
# Press_release_TB06_ES_070420151200.pdf. Language-independent, which is why it
# backs up the dateline parser rather than the reverse -- F4E publishes copies in
# Finnish and other languages whose month names no table here covers.
# F4E appends a 4-digit time to most filenames -- `..._070420151200.pdf` is
# 07/04/2015 + 1200 -- so an 8-digit run is frequently EMBEDDED in a 12-digit one.
# An `(?<!\d)(\d{8})(?!\d)` pattern therefore matched none of them: 17 of the 21
# f4e rows still undated after the first pass failed for exactly this reason.
# Longest-first, so the 12-digit form is tried before its 8-digit prefix.
_URL_RUNS = re.compile(r"(?<!\d)(\d{12}|\d{8})(?!\d)")
_URL_FORMATS = {12: ("%d%m%Y%H%M", "%Y%m%d%H%M"), 8: ("%Y%m%d", "%d%m%Y")}


def extract_url_date(url: str, *, prefer: Optional[datetime] = None) -> Optional[datetime]:
    """A date embedded in the URL/filename, read as YYYYMMDD then DDMMYYYY.

    `prefer` is a partial date already read from the document itself (typically a
    dateline missing its year). When given, the interpretation landing closest to it
    wins, which resolves the genuinely ambiguous filenames -- one F4E release is
    published at `..._240320151200_080420151200.pdf`, carrying two date runs.

    Returns None when nothing parses to a plausible date. A filename is weaker
    evidence than the document's own dateline, so it is only ever a fallback.
    """
    if not url:
        return None
    now = datetime.now(timezone.utc)
    cands: list[datetime] = []
    for run in _URL_RUNS.findall(url):
        for fmt in _URL_FORMATS[len(run)]:
            try:
                dt = datetime.strptime(run, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if dt.year < 1990 or dt > now + timedelta(days=1):
                continue
            cands.append(dt)
    if not cands:
        return None
    if prefer is not None:
        # Closest to the document's own partial date, so a two-date filename cannot
        # pick the wrong run. Compare DAY-OF-YEAR, not absolute days: a yearless
        # dateline is anchored to an assumed year, and measuring against that let
        # the year dominate -- for `..._240320151200_080420151200.pdf` with a
        # "26 March" dateline it chose 8 April over 24 March.
        def _md_gap(d: datetime) -> int:
            same_year = prefer.replace(year=d.year)
            return abs((d - same_year).days)
        return min(cands, key=_md_gap)
    return min(cands)


def extract_dateline_or_url_date(text: str, url: str) -> tuple[Optional[datetime], str]:
    """(date, provenance). The document's own dateline first, the filename second.

    Provenance is returned rather than inferred later so a consumer can tell a date
    the publisher printed on the page from one read off a filename.
    """
    d = extract_dateline_date(text)
    if d is not None:
        # Cross-validate against the filename when it also carries one. A large
        # disagreement means one of the two is a misparse; keep the dateline (the
        # document's own statement) and say so.
        u = extract_url_date(url, prefer=d)
        if u is not None and abs((u - d).days) > 120:
            return d, "dateline_url_disagree"
        return d, "dateline"
    # No usable dateline: try day+month without a year, then the filename alone.
    m = re.search(r"\b(\d{1,2})\s*\.?\s*(?:de\s+|d')?([A-Za-z\u00C0-\u024F]{3,12})\b",
                  (text or "")[:200])
    partial = None
    if m and _DATELINE_MONTHS.get(_fold(m.group(2))):
        # The year here is a placeholder only: extract_url_date compares month/day.
        partial = datetime(2000, _DATELINE_MONTHS[_fold(m.group(2))],
                           min(int(m.group(1)), 28), tzinfo=timezone.utc)
    u = extract_url_date(url, prefer=partial)
    if u is not None:
        if partial is not None:
            # Best of both: the DAY AND MONTH the document prints, the YEAR only
            # the filename knows. Taking the filename wholesale lost two days on
            # the F4E/DAHER release -- filename 24 March, dateline "26 March".
            try:
                return (datetime(u.year, partial.month, partial.day,
                                 tzinfo=timezone.utc), "dateline_day_url_year")
            except ValueError:
                pass
        return u, "url_filename"
    return None, "none"


# --- last resort: the ONLY date on the page ---------------------------------
# Deliberately NOT part of _ITEM_DATE_CARRIERS. A date in running text is not
# self-describing -- the SESAR Innovation Days page carries an EVENT date twice in
# its body, and a page-wide scan would have stored that as the publication date. So
# this is opt-in per body, for pages that expose no carrier at all.
#
# The safety is the refusal, not the match: it answers only when the whole page
# contains exactly ONE distinct date. Two dates mean the page is ambiguous and it
# declines; zero means there is nothing to find. Measured across chips-ju and satcen
# item pages on 9 Sep 2026: 5 of 6 carried exactly one, the sixth carried none.
_TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\s+\d{4})\b", re.I)


def sole_text_date(html: str, *, today: datetime | None = None):
    """(datetime, "sole_text_date") when the page's text holds exactly one date.

    Returns (None, None) when there are none, when there are two or more, or when the
    one found fails the same sanity bounds every other carrier applies.
    """
    if not html:
        return None, None
    text_only = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    found = {m.group(1) for m in _TEXT_DATE_RE.finditer(text_only)}
    if len(found) != 1:
        return None, None
    dt = parse_listing_date(found.pop())
    if dt is None:
        return None, None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    today = today or datetime.now(timezone.utc)
    if not (datetime(1990, 1, 1, tzinfo=timezone.utc) <= dt <= today + timedelta(days=1)):
        return None, None
    return dt, "sole_text_date"


# --- EDPS / EDPB press-release dateline -------------------------------------------
# EDPS press releases print their official date in a fixed template block, just
# before the "Background information" boilerplate:
#
#     PRESS RELEASE  EDPS/2025/10  Brussels, 24 October 2025
#
# and joint EDPB-EDPS releases open with "Brussels, 12 March 2026 -". The opening
# lines are NOT the date: the Entry/Exit System release opens "entered into operation
# on 12 October 2025" and is dated 24 October; the UN Convention release opens "On
# 4 September 2025, the EDPS issued an Opinion" and is dated 9 September. So this
# anchors on the Brussels token, never on position.
#
# PDF extraction splits glyphs -- "Brusse ls", "1 2 March", "202 5" -- so the token is
# matched space-tolerantly and the 40 characters after it are read with ALL
# whitespace removed. Verified against the raw text on 11 Sep 2026: "1 2 March 2026"
# is day 12 (not a page number fused onto "2"), and a plain contiguous date scan
# truncated it to 2 March.
#
# Two refusals make that safe:
#   * more than one distinct Brussels date -> refuse, the document is ambiguous;
#   * the date must fall in the Drupal upload-folder month (/system/files/YYYY-MM/),
#     which the CMS stamps at upload and the text cannot influence. All 18 resolved
#     EDPS rows passed it; a fused digit that moved the day across a month boundary,
#     or a wrong year, is refused rather than stored.
# Joint EDPB-EDPS releases sometimes print NO year ("Brussels, 21 January -"). The day
# and month are then taken from the document and the year from the upload folder, but
# only when the dateline MONTH equals the folder month -- otherwise a "28 December"
# release uploaded in January would be stored a year out. Verified on 11 Sep 2026
# against the EDPB's own pages: 21 January 2026 and 11 February 2026, both matching.
#
# Deliberately NOT a resolver on the EDPB page's article-date metadata. For the NIS2 /
# Cybersecurity Act release that field reads 19 May 2026 while the release text on the
# same EDPB page, the EDPS PDF and the March upload folder all say 19 March 2026. The
# document's printed dateline outranks a CMS field that can record a later edit.
_BRUSSELS_TOKEN_RE = re.compile(r"B\s*r\s*u\s*s\s*s\s*e\s*l\s*s\s*,?", re.I)
_STRIPPED_DAY_MONTH_YEAR_RE = re.compile(r"^(\d{1,2})([A-Za-z]{3,9})(\d{4})")
_UPLOAD_FOLDER_MONTH_RE = re.compile(r"/system/files/(\d{4})-(\d{2})/")
# Day + an explicit month NAME with no year after it. Month names are spelled out
# (longest first) rather than [A-Za-z]{3,9}, because the stripped tail runs straight
# into the next word -- "21January-TheEuropean" -- and a greedy letter class would
# swallow "JanuaryTh".
_STRIPPED_DAY_MONTH_ONLY_RE = re.compile(
    r"^(\d{1,2})(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")", re.I)


def extract_brussels_dateline(text: str, url: str = "") -> tuple[Optional[datetime], str]:
    """(date, provenance) from a `Brussels, <day> <Month> <year>` dateline.

    Provenance on success is `brussels_dateline` (the document printed day, month and
    year) or `brussels_dateline_day_folder_year` (yearless dateline, year from the
    upload folder, months agreeing). On refusal it names the reason -- `none`,
    `brussels_dateline_multi`, `brussels_dateline_out_of_bounds`,
    `brussels_dateline_folder_mismatch`, `brussels_dateline_yearless_month_mismatch`
    or `brussels_dateline_yearless_unanchored` -- so a backfill can count why rows
    stayed undated instead of reporting a bare miss.
    """
    if not text:
        return None, "none"
    found: set[datetime] = set()
    yearless: set[tuple[int, int]] = set()          # (month, day)
    for m in _BRUSSELS_TOKEN_RE.finditer(text):
        tail = re.sub(r"\s+", "", text[m.end():m.end() + 40])
        d = _STRIPPED_DAY_MONTH_YEAR_RE.match(tail)
        if d and _MONTHS.get(d.group(2).lower()):
            try:
                found.add(datetime(int(d.group(3)), _MONTHS[d.group(2).lower()],
                                   int(d.group(1)), tzinfo=timezone.utc))
            except ValueError:
                pass
            continue
        y = _STRIPPED_DAY_MONTH_ONLY_RE.match(tail)
        if y:
            yearless.add((_MONTHS[y.group(2).lower()], int(y.group(1))))
    if len(found) > 1:
        return None, "brussels_dateline_multi"
    folder = _UPLOAD_FOLDER_MONTH_RE.search(url or "")
    if found:
        dt, prov = found.pop(), "brussels_dateline"
    elif len(yearless) == 1 and folder:
        month, day = yearless.pop()
        if month != int(folder.group(2)):
            return None, "brussels_dateline_yearless_month_mismatch"
        try:
            dt = datetime(int(folder.group(1)), month, day, tzinfo=timezone.utc)
        except ValueError:
            return None, "none"
        prov = "brussels_dateline_day_folder_year"
    elif yearless:
        # Several yearless datelines, or one with no upload folder to anchor a year.
        return None, "brussels_dateline_yearless_unanchored"
    else:
        return None, "none"
    if dt.year < 1990 or dt > datetime.now(timezone.utc) + timedelta(days=1):
        return None, "brussels_dateline_out_of_bounds"
    if folder and (dt.year, dt.month) != (int(folder.group(1)), int(folder.group(2))):
        return None, "brussels_dateline_folder_mismatch"
    return dt, prov
