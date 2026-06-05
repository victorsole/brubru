"""Council of the EU register scraper.

Populates ``council_register_items`` (migration 109) — the backing store for the
eight Council-of-the-EU API endpoints. consilium.europa.eu is one website
serving Council / European Council / Eurogroup; this scraper covers the
*Council of the EU* surfaces.

TWO HARD-WON ACCESS FACTS (proven 5 June 2026):
  1. consilium.europa.eu index pages sit behind a PER-CONTEXT rate-throttle, NOT
     a hard JS-WAF. The first navigation in a fresh browser context returns 200
     with full server-rendered HTML; reusing the context 403s every follow-up.
     => fetch each URL in a FRESH Playwright context.
  2. The document store ``data.consilium.europa.eu/doc/document/<REF>/en/pdf`` is
     NOT walled at all — plain httpx GET returns the PDF. Same for ``/media/*.pdf``
     research papers. => bodies are cheap; no browser needed for PDFs.

Bodies are composed at scrape time from the real inline facts (or the PDF text)
and stored, so the API never scrapes on the request path and the five mandatory
datapoints (public_url, body_txt, body_html, document_date, creation_date) are
always present on every row.

Parsers read rendered ``inner_text`` + anchor hrefs (structure-agnostic) rather
than fragile CSS classes.

Dependency: Playwright (installed on this project) + pypdf + httpx.
"""

from __future__ import annotations

import html as _html
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

BASE = "https://www.consilium.europa.eu"

# Index pages per content_type (the Council-of-the-EU surfaces).
SOURCES = {
    "press_release":    f"{BASE}/en/press/press-releases/",
    "meeting":          f"{BASE}/en/meetings/calendar/?daterange=past&category=meeting",
    "voting_result":    f"{BASE}/en/documents/public-register/votes/",
    "register_doc":     f"{BASE}/en/documents/public-register/latest/",
    "oj_agenda":        f"{BASE}/en/documents/public-register/oj-council/",
    "preparatory_body": f"{BASE}/en/meetings/preparatory-bodies/",
    "research_paper":   f"{BASE}/en/documents-publications/council-research-papers/",
    "treaty_agreement": f"{BASE}/en/documents/treaties-agreements/",
    # --- European Council (folder 2) ---
    "euco_conclusions":  f"{BASE}/en/documents/public-register/euco-conclusions/",
    "euco_meeting":      f"{BASE}/en/meetings/european-council/",
    # --- Eurogroup (folder 3) ---
    "eurogroup_meeting":  f"{BASE}/en/meetings/eurogroup/",
    "eurogroup_document": f"{BASE}/en/eurogroup/eurogroup-documents-register/",
}

# Named-meeting content types -> (allowed URL slug, council_configuration|None).
NAMED_MEETINGS = {
    "euco_meeting":      ("european-council", None),
    "eurogroup_meeting": ("eurogroup", "EUROGROUP"),
}

# Reference content types -> list of (url, title). Each page becomes one row
# whose body is the page's own cleaned text (+ any PDF link). Honest reference
# data — the consilium prose pages have no list/register backing.
REFERENCE_PAGES = {
    "euco_strategic_agenda": [
        (f"{BASE}/en/european-council/strategic-agenda-2024-2029/", "Strategic Agenda 2024-2029"),
    ],
    "euro_summit": [
        (f"{BASE}/en/european-council/euro-summit/", "Euro Summit"),
    ],
    "euco_member": [
        (f"{BASE}/en/european-council/members/", "Members of the European Council"),
    ],
    "euco_about": [
        (f"{BASE}/en/european-council/how-the-european-council-works/", "How the European Council works"),
        (f"{BASE}/en/european-council/president/", "President of the European Council"),
        (f"{BASE}/en/european-council/role-nominations-appointment/", "Role, nominations and appointment"),
        (f"{BASE}/en/european-council/history/", "History of the European Council"),
    ],
    "eurogroup_work_programme": [
        (f"{BASE}/en/eurogroup/work-programme/", "Eurogroup work programme"),
    ],
    "eurogroup_member": [
        (f"{BASE}/en/eurogroup/eurogroup-members/", "Members of the Eurogroup"),
        (f"{BASE}/en/eurogroup/eurogroup-members/eurogroup-inclusive-members/", "Members of the Eurogroup (inclusive format)"),
    ],
    "eurogroup_about": [
        (f"{BASE}/en/eurogroup/how-the-eurogroup-works/", "How the Eurogroup works"),
        (f"{BASE}/en/eurogroup/how-the-eurogroup-works/eurogroup-working-group/", "Eurogroup Working Group"),
        (f"{BASE}/en/eurogroup/transparency/", "Eurogroup transparency"),
        (f"{BASE}/en/eurogroup/history/", "History of the Eurogroup"),
    ],
}

# Council configuration slug -> code (for meeting URLs /en/meetings/{slug}/...).
SLUG_TO_CONFIG = {
    "gac": "GAC", "fac": "FAC", "ecofin": "ECOFIN", "jha": "JHA", "epsco": "EPSCO",
    "compet": "COMPET", "tte": "TTE", "agrifish": "AGRIFISH", "env": "ENVI",
    "eycs": "EYCS", "eurogroup": "EUROGROUP",
}

_DDMMYYYY = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_REF_LINE = re.compile(r"^((?:ST|CM)\s+\d+\s+\d{4}(?:\s+[A-Z]+(?:\s+\d+)?)?)\s*-?\s*([A-Z][A-Za-z .]+)?$")
_INTERINST = re.compile(r"\b(\d{4}/\d{3,4}\([A-Z]{2,4}\))")
_MEETING_HREF = re.compile(r"/en/meetings/([a-z-]+)/(\d{4})/(\d{2})/(\d{2}(?:-\d{2})?)/?$")
_PRESS_HREF = re.compile(r"/en/press/press-releases/(\d{4})/(\d{2})/(\d{2})/([a-z0-9-]+)/?$")
_MPO_HREF = re.compile(r"/en/meetings/mpo/(\d{4})/(\d{1,2})/([^/?#]+)/?$")
_PDF_DOC = re.compile(r"data\.consilium\.europa\.eu/doc/document/([A-Z0-9-]+)/[a-z]{2}/pdf", re.I)


@dataclass
class ScrapedItem:
    content_type: str
    title: str
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = None
    document_ref: Optional[str] = None
    council_configuration: Optional[str] = None
    interinstitutional_ref: Optional[str] = None
    subject_matters: list = field(default_factory=list)
    pdf_url: Optional[str] = None
    policy_areas: list = field(default_factory=list)
    source_url: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def item_key(self) -> str:
        slug = self.document_ref or self.public_url or self.title
        slug = re.sub(r"\s+", "-", (slug or "").strip().lower())[:300]
        return f"{self.content_type}:{slug}"


# --------------------------------------------------------------------------- #
# Fetch helpers                                                               #
# --------------------------------------------------------------------------- #

def _parse_ddmmyyyy(s: str) -> Optional[date]:
    m = _DDMMYYYY.search(s or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def fetch_pdf_text(url: str, *, max_pages: int = 12, timeout: int = 30) -> Optional[str]:
    """Fetch + extract text from an un-walled consilium/media PDF. None on failure."""
    try:
        import httpx
        from pypdf import PdfReader
        import io
    except ImportError as exc:  # pragma: no cover
        logger.warning("[council-register] pdf deps missing: %s", exc)
        return None
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": UA}) as c:
            r = c.get(url)
        if r.status_code != 200 or "pdf" not in r.headers.get("content-type", "").lower():
            return None
        reader = PdfReader(io.BytesIO(r.content))
        out = []
        for pg in reader.pages[:max_pages]:
            try:
                out.append(pg.extract_text() or "")
            except Exception:
                continue
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
        return text or None
    except Exception as exc:
        logger.info("[council-register] pdf fetch failed %s: %s", url, exc)
        return None


class _Fetcher:
    """One browser; a FRESH context per URL (defeats the per-context 403 throttle)."""

    def __init__(self, settle_ms: int = 4000, nav_timeout_ms: int = 45000):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.settle_ms = settle_ms
        self.nav_timeout_ms = nav_timeout_ms

    def close(self):
        for c in (self._browser, self._pw):
            try:
                c.stop() if hasattr(c, "stop") else c.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def get(self, url: str) -> tuple:
        """Return (status, text, anchors) where anchors is list[(text, abs_href)]."""
        ctx = self._browser.new_context(user_agent=UA, locale="en-US",
                                        viewport={"width": 1440, "height": 1200})
        page = ctx.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
            status = resp.status if resp else None
            page.wait_for_timeout(self.settle_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            text = page.inner_text("body")
            try:
                anchors = page.eval_on_selector_all(
                    "main a[href], article a[href], a[href]",
                    "els => els.slice(0,600).map(e => [(e.innerText||'').trim(), e.href])",
                )
            except Exception:
                anchors = []
            return status, text, anchors
        finally:
            try:
                page.close(); ctx.close()
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Body composers                                                              #
# --------------------------------------------------------------------------- #

def _compose_record_body(it: ScrapedItem) -> tuple:
    """(body_txt, body_html) from a register record's real inline facts. Always
    filled — structures the scraped facts, invents nothing."""
    lines = [it.title]
    if it.document_ref:
        lines.append(f"Document: {it.document_ref}")
    if it.council_configuration:
        lines.append(f"Council configuration: {it.council_configuration}")
    if it.document_date:
        lines.append(f"Date: {it.document_date.isoformat()}")
    if it.interinstitutional_ref:
        lines.append(f"Interinstitutional file: {it.interinstitutional_ref}")
    if it.subject_matters:
        lines.append("Subject matters: " + ", ".join(it.subject_matters))
    if it.pdf_url:
        lines.append(f"Full document (PDF): {it.pdf_url}")
    txt = "\n".join(lines)

    parts = [f"<h2>{_html.escape(it.title)}</h2>", "<ul>"]
    if it.document_ref:
        parts.append(f"<li><strong>Document:</strong> {_html.escape(it.document_ref)}</li>")
    if it.council_configuration:
        parts.append(f"<li><strong>Configuration:</strong> {_html.escape(it.council_configuration)}</li>")
    if it.document_date:
        parts.append(f"<li><strong>Date:</strong> {it.document_date.isoformat()}</li>")
    if it.interinstitutional_ref:
        parts.append(f"<li><strong>Interinstitutional file:</strong> {_html.escape(it.interinstitutional_ref)}</li>")
    if it.subject_matters:
        parts.append(f"<li><strong>Subject matters:</strong> {_html.escape(', '.join(it.subject_matters))}</li>")
    parts.append("</ul>")
    if it.pdf_url:
        parts.append(f'<p><a href="{_html.escape(it.pdf_url)}">Full document (PDF)</a></p>')
    html = "<article>" + "".join(parts) + "</article>"
    return txt, html


def _compose_simple_body(title: str, facts: list, url: Optional[str]) -> tuple:
    """(body_txt, body_html) for meeting/prep-body/research rows from facts."""
    lines = [title] + [f"{k}: {v}" for k, v in facts if v]
    if url:
        lines.append(f"More information: {url}")
    txt = "\n".join(lines)
    items = "".join(f"<li><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</li>" for k, v in facts if v)
    parts = [f"<h2>{_html.escape(title)}</h2>"]
    if items:
        parts.append(f"<ul>{items}</ul>")
    if url:
        parts.append(f'<p><a href="{_html.escape(url)}">More information</a></p>')
    return txt, "<article>" + "".join(parts) + "</article>"


# --------------------------------------------------------------------------- #
# Parsers                                                                     #
# --------------------------------------------------------------------------- #

def _pdf_map(anchors) -> dict:
    """ref-token (e.g. 'ST-9727-2026-INIT') -> pdf url, from anchors."""
    out = {}
    for _t, h in anchors:
        m = _PDF_DOC.search(h or "")
        if m:
            out.setdefault(m.group(1).upper(), h)
    return out


def parse_register(text: str, anchors, content_type: str, source_url: str, limit: int) -> list:
    """Parse a public-register list (votes / latest / oj-agendas). Records are
    rendered as text blocks led by a 'ST/CM NNNN YYYY ...' reference line."""
    pdfmap = _pdf_map(anchors)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Find indices of reference lines.
    idx = [i for i, l in enumerate(lines) if _REF_LINE.match(l)]
    out = []
    for n, start in enumerate(idx):
        end = idx[n + 1] if n + 1 < len(idx) else len(lines)
        block = lines[start:end]
        mref = _REF_LINE.match(block[0])
        ref = re.sub(r"\s+", " ", mref.group(1)).strip()
        ref_token = ref.replace(" ", "-").upper()
        # date = first dd/mm/yyyy in the block (the publication date, line after ref)
        doc_date = None
        title = None
        interinst = None
        subjects = []
        for ln in block[1:]:
            if doc_date is None and _DDMMYYYY.fullmatch(ln):
                doc_date = _parse_ddmmyyyy(ln)
                continue
            if ln.startswith("Interinstitutional file"):
                mi = _INTERINST.search(ln)
                if mi:
                    interinst = mi.group(1)
                continue
            if ln.startswith("Subject matters"):
                subjects = [s.strip() for s in re.split(r"[\t:]", ln, 1)[-1].split(",") if s.strip()]
                continue
            if ln.startswith(("Also available", "This document is only", "Originator", "Addressee", "Date of meeting", "Interinstitutional")):
                continue
            if title is None and len(ln) > 12 and not _DDMMYYYY.fullmatch(ln):
                title = ln
        if not title:
            title = ref
        pdf_url = pdfmap.get(ref_token)
        it = ScrapedItem(
            content_type=content_type, title=title[:500], document_ref=ref,
            document_date=doc_date, interinstitutional_ref=interinst,
            subject_matters=subjects, pdf_url=pdf_url,
            public_url=pdf_url or source_url, source_url=source_url,
        )
        it.body_txt, it.body_html = _compose_record_body(it)
        out.append(it)
        if len(out) >= limit:
            break
    return out


def parse_meetings(anchors, source_url: str, limit: int, fetcher=None, enrich: int = 0) -> list:
    """Parse the past-meetings calendar (anchors to /en/meetings/{slug}/{Y}/{M}/{D}/)."""
    seen = set()
    out = []
    for t, h in anchors:
        m = _MEETING_HREF.search(h or "")
        if not m:
            continue
        slug, y, mo, dd = m.group(1), m.group(2), m.group(3), m.group(4)
        if slug not in SLUG_TO_CONFIG:
            continue
        if h in seen or len(t) < 8:
            continue
        seen.add(h)
        day = int(dd.split("-")[0])
        try:
            dt = date(int(y), int(mo), day)
        except ValueError:
            dt = None
        cfg = SLUG_TO_CONFIG[slug]
        it = ScrapedItem(
            content_type="meeting", title=t.replace("\n", " ").strip()[:500],
            public_url=h, document_date=dt, council_configuration=cfg,
            source_url=source_url,
        )
        out.append(it)
        if len(out) >= limit:
            break
    # Enrich the first `enrich` with the detail page "Main results".
    for it in out[:enrich]:
        if fetcher is None:
            break
        results = _fetch_main_results(fetcher, it.public_url)
        if results:
            it.extra["main_results"] = True
            it.body_txt = f"{it.title}\n\n{results}"
            it.body_html = (f"<article><h2>{_html.escape(it.title)}</h2>"
                            + "".join(f"<p>{_html.escape(p)}</p>" for p in results.split('\n') if p.strip())
                            + "</article>")
    for it in out:
        if it.body_txt is None:
            facts = [("Council configuration", it.council_configuration),
                     ("Meeting date", it.document_date.isoformat() if it.document_date else None)]
            it.body_txt, it.body_html = _compose_simple_body(it.title, facts, it.public_url)
    return out


def _fetch_main_results(fetcher, url: str) -> Optional[str]:
    """Extract the 'Main results' narrative from a meeting detail page."""
    try:
        status, text, _a = fetcher.get(url)
    except Exception:
        return None
    if status != 200 or not text:
        return None
    lines = [l.rstrip() for l in text.splitlines()]
    # Slice between 'Main results' and the first of the closing sections.
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().lower() == "main results")
    except StopIteration:
        return None
    stops = {"meeting files", "press releases", "press information", "press contacts",
             "preparatory documents", "outcome documents"}
    body = []
    for l in lines[start + 1:]:
        if l.strip().lower() in stops:
            break
        if l.strip():
            body.append(l.strip())
    out = "\n".join(body).strip()
    return out or None


def parse_press(anchors, source_url: str, limit: int, fetcher=None, enrich: int = 0) -> list:
    seen = set()
    out = []
    for t, h in anchors:
        m = _PRESS_HREF.search(h or "")
        if not m or h in seen or len(t) < 12:
            continue
        seen.add(h)
        y, mo, dd = m.group(1), m.group(2), m.group(3)
        try:
            dt = date(int(y), int(mo), int(dd))
        except ValueError:
            dt = None
        it = ScrapedItem(
            content_type="press_release", title=t.replace("\n", " ").strip()[:500],
            public_url=h, document_date=dt, source_url=source_url,
        )
        out.append(it)
        if len(out) >= limit:
            break
    for it in out[:enrich]:
        if fetcher is None:
            break
        body = _fetch_press_body(fetcher, it.public_url, it.title)
        if body:
            it.body_txt = body
            it.body_html = ("<article>" + "".join(f"<p>{_html.escape(p)}</p>" for p in body.split('\n') if p.strip()) + "</article>")
    for it in out:
        if it.body_txt is None:
            facts = [("Published", it.document_date.isoformat() if it.document_date else None)]
            it.body_txt, it.body_html = _compose_simple_body(it.title, facts, it.public_url)
    return out


def _fetch_press_body(fetcher, url: str, title: Optional[str] = None) -> Optional[str]:
    try:
        status, text, _a = fetcher.get(url)
    except Exception:
        return None
    if status != 200 or not text:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    stops = {"press contacts", "press information", "if you are not a journalist",
             "share this page", "topics", "meetings", "documents and research"}
    # Start the body right AFTER the page's own title line — this drops the
    # global top-nav + breadcrumb + duplicated headline cleanly. Fall back to a
    # nav-label skip list if the title can't be located.
    start = 0
    if title:
        key = title.strip().lower()[:40]
        for i, l in enumerate(lines):
            if l.strip().lower().startswith(key):
                start = i + 1
                break
    nav = ("about the institutions", "topics", "meetings", "news and media",
           "documents and research", "search", "statements and remarks",
           "we use cookies", "visit our cookies", "i accept", "skip to content",
           "european council", "council of the european union", "menu", "home",
           "current language", "en", "highlights", "press releases", "press release")
    body = []
    for l in lines[start:]:
        ll = l.strip().lower()
        if ll in stops:
            break
        if ll in nav:
            continue
        body.append(l)
    out = "\n".join(body[:120]).strip()
    return out if len(out) > 80 else None


def parse_prep_bodies(anchors, source_url: str, limit: int) -> list:
    seen = set()
    out = []
    for t, h in anchors:
        m = _MPO_HREF.search(h or "")
        if not m or h in seen or len(t) < 6:
            continue
        seen.add(h)
        y, mo = m.group(1), m.group(2)
        try:
            dt = date(int(y), int(mo), 1)
        except ValueError:
            dt = None
        it = ScrapedItem(
            content_type="preparatory_body", title=t.replace("\n", " ").strip()[:500],
            public_url=h, document_date=dt, source_url=source_url,
            extra={"month": f"{y}-{mo}"},
        )
        facts = [("Type", "Council preparatory body meeting (COREPER / working party)"),
                 ("Month", f"{y}-{int(mo):02d}")]
        it.body_txt, it.body_html = _compose_simple_body(it.title, facts, it.public_url)
        out.append(it)
        if len(out) >= limit:
            break
    return out


def parse_research(anchors, source_url: str, limit: int, fetch_pdf: int = 0) -> list:
    seen = set()
    out = []
    for t, h in anchors:
        if not h or not h.lower().endswith(".pdf") or "/media/" not in h:
            continue
        if h in seen or len(t) < 10:
            continue
        seen.add(h)
        it = ScrapedItem(
            content_type="research_paper", title=t.replace("\n", " ").strip()[:500],
            public_url=h, pdf_url=h, source_url=source_url,
        )
        out.append(it)
        if len(out) >= limit:
            break
    for it in out[:fetch_pdf]:
        txt = fetch_pdf_text(it.pdf_url)
        if txt:
            # Honest PDF-only: body_txt = extracted text, body_html = None.
            it.body_txt, it.body_html = txt, None
    for it in out:
        if it.body_txt is None:
            facts = [("Source", "Council research paper (ART — Analysis and Research Team)")]
            it.body_txt, it.body_html = _compose_simple_body(it.title, facts, it.public_url)
    return out


def parse_treaties(text: str, source_url: str) -> list:
    """The Treaties & Agreements page is a searchable database with no default
    list. Expose one honest reference row whose body is the page's own
    description + the canonical search URL."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    skip_exact = {"about the institutions", "topics", "meetings", "news and media",
                  "documents and research", "search", "menu", "home", "en",
                  "current language", "toggle navigation", "sections", "documents",
                  "european council", "council of the european union", "skip to content"}
    skip_prefix = ("We use cookies", "Visit our cookies", "I accept")
    body = [l for l in lines
            if l.strip().lower() not in skip_exact
            and not any(l.startswith(p) for p in skip_prefix)][:30]
    desc = "\n".join(body).strip() or "Search the Council's database of treaties and international agreements."
    it = ScrapedItem(
        content_type="treaty_agreement",
        title="EU Treaties and Agreements database (Council of the EU)",
        public_url=source_url, document_date=None, source_url=source_url,
        extra={"reference_entry": True},
    )
    it.body_txt = desc
    it.body_html = "<article><h2>EU Treaties and Agreements database</h2>" + \
        "".join(f"<p>{_html.escape(p)}</p>" for p in desc.split('\n') if p.strip()) + \
        f'<p><a href="{_html.escape(source_url)}">Search the database</a></p></article>'
    return [it]


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_TEXTDATE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.I)


def _parse_textdate(s: str) -> Optional[date]:
    m = _TEXTDATE.search(s or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    except (ValueError, KeyError):
        return None


def parse_pdf_list(anchors, source_url: str, content_type: str, limit: int) -> list:
    """Parse a list whose items are PDF anchors with a dated title (e.g. the
    Eurogroup document register: 'Summing-up letter, Eurogroup, 22 May 2026')."""
    seen = set()
    out = []
    for t, h in anchors:
        if not h or not (h.lower().endswith(".pdf") or "data.consilium" in h):
            continue
        if "/media/" not in h and "data.consilium" not in h:
            continue
        if h in seen:
            continue
        title = (t or "").split("\n")[0].strip()
        if len(title) < 8:
            continue
        seen.add(h)
        it = ScrapedItem(
            content_type=content_type, title=title[:500], public_url=h, pdf_url=h,
            document_date=_parse_textdate(title), source_url=source_url,
        )
        facts = [("Document date", it.document_date.isoformat() if it.document_date else None),
                 ("Type", "Eurogroup document")]
        it.body_txt, it.body_html = _compose_simple_body(it.title, facts, h)
        out.append(it)
        if len(out) >= limit:
            break
    return out


def parse_named_meetings(anchors, source_url: str, content_type: str, slug: str,
                         council_config, limit: int, fetcher=None, enrich: int = 0) -> list:
    """Parse a meetings list for a specific slug (european-council / euro-summit /
    eurogroup). Same shape as parse_meetings but for non-Council-configuration
    institutions; enriches the first `enrich` with the detail 'Main results'."""
    seen = set()
    out = []
    for t, h in anchors:
        m = _MEETING_HREF.search(h or "")
        if not m or m.group(1) != slug:
            continue
        if h in seen or len(t) < 6:
            continue
        seen.add(h)
        y, mo, dd = m.group(2), m.group(3), m.group(4)
        day = int(dd.split("-")[0])
        try:
            dt = date(int(y), int(mo), day)
        except ValueError:
            dt = None
        out.append(ScrapedItem(
            content_type=content_type, title=t.replace("\n", " ").strip()[:500],
            public_url=h, document_date=dt, council_configuration=council_config,
            source_url=source_url,
        ))
        if len(out) >= limit:
            break
    for it in out[:enrich]:
        if fetcher is None:
            break
        results = _fetch_main_results(fetcher, it.public_url)
        if results:
            it.extra["main_results"] = True
            it.body_txt = f"{it.title}\n\n{results}"
            it.body_html = (f"<article><h2>{_html.escape(it.title)}</h2>"
                            + "".join(f"<p>{_html.escape(p)}</p>" for p in results.split('\n') if p.strip())
                            + "</article>")
    for it in out:
        if it.body_txt is None:
            facts = [("Meeting date", it.document_date.isoformat() if it.document_date else None)]
            it.body_txt, it.body_html = _compose_simple_body(it.title, facts, it.public_url)
    return out


_REF_NAV = {"about the institutions", "topics", "meetings", "news and media",
            "documents and research", "search", "menu", "home", "en",
            "current language", "current language,", "toggle navigation", "sections",
            "documents", "european council", "council of the european union",
            "skip to content", "share this page", "highlights"}
_REF_NAV_PREFIX = ("We use cookies", "Visit our cookies", "I accept")


def parse_reference_page(fetcher, url: str, title: str, content_type: str) -> Optional[ScrapedItem]:
    """Fetch one consilium prose page and return a reference row whose body is the
    page's own cleaned text (+ first PDF link). None if the page can't be read."""
    try:
        status, text, anchors = fetcher.get(url)
    except Exception:
        return None
    if status != 200 or not text:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Start after the page's own title where possible; strip global nav.
    start = 0
    key = title.strip().lower()[:30]
    for i, l in enumerate(lines):
        if l.strip().lower().startswith(key):
            start = i + 1
            break
    body = [l for l in lines[start:]
            if l.strip().lower() not in _REF_NAV
            and not any(l.startswith(p) for p in _REF_NAV_PREFIX)][:80]
    desc = "\n".join(body).strip()
    if len(desc) < 40:
        desc = title
    pdf = None
    for _t, h in anchors:
        if h and (h.lower().endswith(".pdf")) and ("/media/" in h or "data.consilium" in h):
            pdf = h
            break
    it = ScrapedItem(
        content_type=content_type, title=title[:500], public_url=url,
        pdf_url=pdf, source_url=url, extra={"reference_entry": True},
    )
    it.body_txt = desc
    it.body_html = ("<article><h2>" + _html.escape(title) + "</h2>"
                    + "".join(f"<p>{_html.escape(p)}</p>" for p in desc.split('\n') if p.strip())
                    + (f'<p><a href="{_html.escape(pdf)}">Document (PDF)</a></p>' if pdf else "")
                    + "</article>")
    return it


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #

def scrape(content_types: list, *, limit: int = 25, enrich: int = 6) -> list:
    """Scrape the requested content_types. Returns list[ScrapedItem] ready to
    upsert. `enrich` = how many meetings/press to deep-fetch for a rich body."""
    items: list = []
    with _Fetcher() as f:
        for ct in content_types:
            # Reference content types: fetch N prose pages, one row each.
            if ct in REFERENCE_PAGES:
                got = []
                for url, title in REFERENCE_PAGES[ct]:
                    row = parse_reference_page(f, url, title, ct)
                    if row:
                        got.append(row)
                logger.info("[council-register] %s -> %d items", ct, len(got))
                items.extend(got)
                continue

            url = SOURCES.get(ct)
            if not url:
                continue
            try:
                status, text, anchors = f.get(url)
            except Exception as exc:
                logger.warning("[council-register] %s fetch error: %s", ct, exc)
                continue
            if status != 200:
                logger.warning("[council-register] %s -> HTTP %s (skipped)", ct, status)
                continue
            if ct in ("voting_result", "register_doc", "oj_agenda", "euco_conclusions"):
                got = parse_register(text, anchors, ct, url, limit)
            elif ct == "eurogroup_document":
                got = parse_pdf_list(anchors, url, ct, limit)
            elif ct == "meeting":
                got = parse_meetings(anchors, url, limit, fetcher=f, enrich=enrich)
            elif ct in NAMED_MEETINGS:
                slug, cfg = NAMED_MEETINGS[ct]
                got = parse_named_meetings(anchors, url, ct, slug, cfg, limit, fetcher=f, enrich=enrich)
            elif ct == "press_release":
                got = parse_press(anchors, url, limit, fetcher=f, enrich=enrich)
            elif ct == "preparatory_body":
                got = parse_prep_bodies(anchors, url, limit)
            elif ct == "research_paper":
                got = parse_research(anchors, url, limit, fetch_pdf=min(enrich, 8))
            elif ct == "treaty_agreement":
                got = parse_treaties(text, url)
            else:
                got = []
            logger.info("[council-register] %s -> %d items", ct, len(got))
            items.extend(got)
    return items


ALL_CONTENT_TYPES = list(SOURCES.keys()) + list(REFERENCE_PAGES.keys())
