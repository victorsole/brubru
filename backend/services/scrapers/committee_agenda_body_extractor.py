"""
Fetch + parse EP committee draft-agenda doceo documents into body text + HTML.

A committee draft agenda is the official "order of the day" (OJ) for a
committee meeting, e.g.
    https://www.europarl.europa.eu/doceo/document/LIBE-OJ-2026-06-03-1_EN.pdf
The agenda metadata (committee, date, the doc URL) is already stored as an
EUCalendarEvent (source='ep_committee_agenda'); this module fills in the
document BODY.

doceo is JS-WAF-walled (a plain request returns HTTP 202 + an empty body).
`fetch_pdf` (urllib + an EP-accepted User-Agent) was assumed to succeed from the
Railway host. Measured on 28 Aug 2026, it does not: **0 of 226 agendas had ever
been cached**, in production included, so every agenda has served
`body_txt: null` since the endpoint shipped. A 202 with zero bytes raises
nothing, so the failure was invisible.

The fix is the house rule for a WAF: use a real browser, never tune headers.
`AgendaPdfBrowser` clears the challenge once, then pulls each PDF through the
browser context (which carries the WAF cookie and Chromium's TLS fingerprint).
The same URL that returns 202/0 bytes to urllib returns a 186KB PDF this way.

Chromium is far too heavy for the request path, which fetches one body PER ROW,
so it is NOT used there: `ensure_agenda_body` keeps its cheap urllib attempt and
the cache, and `scripts/backfill_committee_agenda_bodies.py` (warm cron tier)
fills the cache with the browser out of band.

The extracted body is cached on EUCalendarEvent.related_documents (JSONB) so
each agenda PDF is fetched at most once. body_html is composed from the real
extracted text (one <p> per paragraph) per Victor's directive that draft
agendas carry both body_txt and body_html (1 June 2026).
"""

from __future__ import annotations

import html as _html
import io
import logging
import re
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

CACHE_TXT = "agenda_body_txt"
CACHE_HTML = "agenda_body_html"
CACHE_AT = "agenda_body_extracted_at"


def _compose_agenda_html(text: str) -> Optional[str]:
    """Compose body_html from the real extracted agenda text — one <p> per
    paragraph (blank-line separated), falling back to one <p> per non-empty
    line. Same text as body_txt, structured; nothing is invented."""
    if not text or not text.strip():
        return None
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not paras:
        return None
    return "<article>" + "".join(f"<p>{_html.escape(p)}</p>" for p in paras) + "</article>"


def extract_agenda_body(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch the doceo agenda PDF and return (body_txt, body_html).

    Returns (None, None) when the fetch yields no bytes (WAF wall / 404) or the
    PDF has no extractable text. Never raises for an empty fetch — the caller
    degrades gracefully.
    """
    from scripts.extract_committee_minutes_pdfs import fetch_pdf

    data = fetch_pdf(url)
    if not data:
        return None, None
    return pdf_bytes_to_body(data)


class AgendaPdfBrowser:
    """One Chromium for a whole batch of agenda PDFs.

    Opening a browser per document would be absurd (each launch costs seconds
    and ~200MB), so the challenge is cleared once on the doceo root and every
    subsequent PDF is pulled through the same context.
    """

    _WARMUP = "https://www.europarl.europa.eu/doceo/"

    def __init__(self, settle_ms: int = 9000, timeout_ms: int = 60000):
        self.settle_ms = settle_ms
        self.timeout_ms = timeout_ms
        self._pw = self._browser = self._ctx = None

    def __enter__(self) -> "AgendaPdfBrowser":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._ctx = self._browser.new_context()
        page = self._ctx.new_page()
        try:
            page.goto(self._WARMUP, wait_until="domcontentloaded",
                      timeout=self.timeout_ms)
            # The first response IS the 202 challenge; this wait lets Chromium
            # run it and set the cookie the PDF requests then reuse.
            page.wait_for_timeout(self.settle_ms)
        finally:
            page.close()
        return self

    def __exit__(self, *exc) -> None:
        for obj, meth in ((self._ctx, "close"), (self._browser, "close"),
                          (self._pw, "stop")):
            try:
                if obj is not None:
                    getattr(obj, meth)()
            except Exception:  # noqa: BLE001
                pass

    def get(self, url: str) -> Optional[bytes]:
        """Return the PDF bytes, or None. Verifies the %PDF magic: the WAF
        answers with an HTML challenge under a 200, which pypdf would then
        reject with a confusing parse error rather than an honest miss."""
        resp = self._ctx.request.get(url, timeout=self.timeout_ms)
        if resp.status != 200:
            logger.warning("[WARN] agenda PDF %s -> HTTP %s", url, resp.status)
            return None
        data = resp.body()
        if not data or data[:4] != b"%PDF":
            logger.warning("[WARN] agenda PDF %s -> %d bytes, not a PDF (WAF page?)",
                           url, len(data or b""))
            return None
        return data


def pdf_bytes_to_body(data: bytes) -> Tuple[Optional[str], Optional[str]]:
    """Shared PDF -> (body_txt, body_html) step."""
    from pypdf import PdfReader

    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages).strip()
    if not text:
        return None, None
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, _compose_agenda_html(text)


def cached_agenda_body(event) -> Tuple[Optional[str], Optional[str]]:
    """Read the cached (body_txt, body_html) off the event, or (None, None)."""
    rd = event.related_documents or {}
    return rd.get(CACHE_TXT), rd.get(CACHE_HTML)


def ensure_agenda_body(db, event) -> Tuple[Optional[str], Optional[str]]:
    """Return (body_txt, body_html) for an agenda event, fetching + caching on a
    cache miss. Degrades to the cached value (or (None, None)) when the live
    fetch is WAF-blocked or fails — never raises into the request path."""
    txt, html = cached_agenda_body(event)
    if txt:
        return txt, html
    url = event.agenda_url or event.source_url
    if not url:
        return None, None
    try:
        txt, html = extract_agenda_body(url)
    except Exception as exc:  # noqa: BLE001 — body is best-effort; metadata still serves
        logger.warning("[WARN] agenda body fetch failed for %s: %s", url, exc)
        return None, None
    if txt:
        rd = dict(event.related_documents or {})
        rd[CACHE_TXT] = txt
        rd[CACHE_HTML] = html
        rd[CACHE_AT] = datetime.utcnow().isoformat()
        event.related_documents = rd
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    return txt, html
