"""
Fetch + parse EP committee draft-agenda doceo documents into body text + HTML.

A committee draft agenda is the official "order of the day" (OJ) for a
committee meeting, e.g.
    https://www.europarl.europa.eu/doceo/document/LIBE-OJ-2026-06-03-1_EN.pdf
The agenda metadata (committee, date, the doc URL) is already stored as an
EUCalendarEvent (source='ep_committee_agenda'); this module fills in the
document BODY.

doceo is JS-WAF-walled to most hosts (a plain request returns HTTP 202 + an
empty body). `fetch_pdf` (urllib + the EP-accepted User-Agent) succeeds from
the Railway host — the very same path that already populated
committee_minutes.full_text (110 rows in production). Body extraction therefore
runs where the API runs (Railway), not from a developer sandbox.

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
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
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
