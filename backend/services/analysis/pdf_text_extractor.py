"""
PDF text extraction for the legislative-journey analysis.

The eMeeting documents (draft report, amendments, compromise amendments, voting
list) live on www.europarl.europa.eu/meetdocs/... That host IS WAF-walled now
(25 Sep 2026: HTTP 202, 0 bytes, text/html, from this Mac and from Railway alike),
so a direct GET is tried first and Scrape.do is the fallback at the wall. A
document is recognised by its %PDF magic bytes, never by the status code. Each
meetdocs PDF is immutable once published, so extracted text is cached in
``emeeting_doc_text_cache`` keyed by URL and reused. Only text extracted from a
real PDF is cached: 1,017 of 2,120 cache rows held the WAF's empty body.
"""

import io
import logging
import os
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BrubruBot/1.0)"}
_MAX_BYTES = 30_000_000           # do not download more than ~30 MB
_PER_DOC_CHAR_CAP = 150_000       # full-text, but bounded; flag if we truncate


def _extract_pdf(raw: bytes) -> tuple[str, int]:
    """Return (text, page_count) from raw PDF bytes. Best-effort, never raises."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts), len(reader.pages)
    except Exception as exc:
        logger.warning("[journey] pdf extract failed: %s", exc)
        return "", 0


def _fetch_pdf_bytes(pdf_url: str) -> Optional[bytes]:
    """The PDF's bytes, direct first and through Scrape.do at a wall.

    Returns None when neither route yields a PDF (a genuine 404 means the
    document is listed in eMeeting but not yet published on meetdocs).
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=40.0, headers=_HEADERS) as client:
            resp = client.get(pdf_url)
        if resp.status_code == 200 and resp.content[:4] == b"%PDF":
            return resp.content[:_MAX_BYTES]
        direct = f"HTTP {resp.status_code}, {len(resp.content)} bytes"
    except Exception as exc:  # noqa: BLE001
        direct = f"{type(exc).__name__}: {exc}"

    key = os.environ.get("SCRAPEDO_API_KEY")
    if not key:
        logger.warning("[journey] %s walled (%s) and SCRAPEDO_API_KEY unset", pdf_url, direct)
        return None
    try:
        with httpx.Client(timeout=150.0) as client:
            resp = client.get("https://api.scrape.do/",
                              params={"token": key, "url": pdf_url})
        if resp.status_code == 200 and resp.content[:4] == b"%PDF":
            return resp.content[:_MAX_BYTES]
        logger.warning("[journey] no PDF for %s: direct %s; Scrape.do HTTP %s",
                       pdf_url, direct, resp.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[journey] Scrape.do failed for %s (direct %s): %s", pdf_url, direct, exc)
    return None


def get_pdf_text(db: Session, pdf_url: str) -> Optional[dict]:
    """Extracted text for a meetdocs PDF, cached by URL.

    Returns ``{text, char_count, page_count, truncated}`` or None if the document
    could not be fetched/parsed. Writes through to ``emeeting_doc_text_cache``.
    """
    if not pdf_url:
        return None

    # Cache hit.
    try:
        row = db.execute(text(
            "SELECT text, char_count, page_count, truncated FROM emeeting_doc_text_cache WHERE pdf_url = :u"
        ), {"u": pdf_url}).mappings().first()
        if row and (row["char_count"] or 0) > 0:
            return dict(row)
    except Exception:
        db.rollback()

    # Fetch + extract.
    raw = _fetch_pdf_bytes(pdf_url)
    if raw is None:
        return None

    body, pages = _extract_pdf(raw)
    body = (body or "").strip()
    truncated = False
    if len(body) > _PER_DOC_CHAR_CAP:
        body = body[:_PER_DOC_CHAR_CAP]
        truncated = True
    char_count = len(body)

    # Write through (best-effort; a failed cache write must not fail extraction).
    # An empty extraction from a real PDF (a scanned image) is not cached either,
    # so a better extractor later is not blocked by a stored nothing.
    if char_count == 0:
        return None
    try:
        db.execute(text(
            """
            INSERT INTO emeeting_doc_text_cache (pdf_url, text, char_count, page_count, truncated)
            VALUES (:u, :t, :c, :p, :tr)
            ON CONFLICT (pdf_url) DO UPDATE SET
                text = EXCLUDED.text, char_count = EXCLUDED.char_count,
                page_count = EXCLUDED.page_count, truncated = EXCLUDED.truncated,
                extracted_at = NOW()
            """
        ), {"u": pdf_url, "t": body, "c": char_count, "p": pages, "tr": truncated})
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("[journey] cache write failed for %s: %s", pdf_url, exc)

    if char_count == 0:
        return None
    return {"text": body, "char_count": char_count, "page_count": pages, "truncated": truncated}
