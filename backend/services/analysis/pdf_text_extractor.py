"""
PDF text extraction for the legislative-journey analysis.

The eMeeting documents (draft report, amendments, compromise amendments, voting
list) live on www.europarl.europa.eu/meetdocs/... That host IS WAF-walled now
(25 Sep 2026: HTTP 202, 0 bytes, text/html, from this Mac and from Railway alike),
so a direct GET is tried first, then Scrape.do, then a headless browser that
clears the WAF (28 Sep 2026: the Scrape.do plan is 1,000 requests a month and ran
out, and for three days nothing was extracted). A
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


def _direct(pdf_url: str) -> tuple[Optional[bytes], str]:
    try:
        with httpx.Client(follow_redirects=True, timeout=40.0, headers=_HEADERS) as client:
            resp = client.get(pdf_url)
        if resp.status_code == 200 and resp.content[:4] == b"%PDF":
            return resp.content[:_MAX_BYTES], "direct"
        if resp.status_code == 404:
            return None, "HTTP 404"
        return None, f"HTTP {resp.status_code}, {len(resp.content)} bytes"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _via_scrapedo(pdf_url: str) -> tuple[Optional[bytes], str]:
    from services.scrapers import scrapedo_quota

    key = os.environ.get("SCRAPEDO_API_KEY")
    if not key:
        return None, "Scrape.do: no key"
    if scrapedo_quota.is_exhausted():
        return None, "Scrape.do: monthly quota spent"
    try:
        with httpx.Client(timeout=150.0) as client:
            resp = client.get("https://api.scrape.do/",
                              params={"token": key, "url": pdf_url})
    except Exception as exc:  # noqa: BLE001
        return None, f"Scrape.do: {type(exc).__name__}"
    if resp.status_code == 200 and resp.content[:4] == b"%PDF":
        return resp.content[:_MAX_BYTES], "scrapedo"
    if scrapedo_quota.note(resp.status_code, resp.content[:400]):
        return None, "Scrape.do: monthly quota spent"
    return None, f"Scrape.do: HTTP {resp.status_code}"


def _via_browser(urls: list[str]) -> dict[str, tuple[Optional[bytes], str]]:
    """The free fallback: a headless browser clears the WAF, then GETs each PDF.

    One browser for the whole list, so a backfill pays the ~8 s start-up once.
    """
    try:
        from services.scrapers.waf_browser_fetcher import fetch_bytes_isolated
        got = fetch_bytes_isolated(urls, timeout_s=90 + 60 * len(urls))
    except Exception as exc:  # noqa: BLE001  no Playwright, or Chromium wedged
        return {u: (None, f"browser: {type(exc).__name__}") for u in urls}
    out: dict[str, tuple[Optional[bytes], str]] = {}
    for u in urls:
        status, body, err = got.get(u, (None, b"", "not attempted"))
        if body[:4] == b"%PDF":
            out[u] = (body[:_MAX_BYTES], "browser")
        else:
            out[u] = (None, f"browser: {err or f'HTTP {status}, {len(body)} bytes, not a PDF'}")
    return out


def fetch_pdf_bytes_many(pdf_urls: list[str]) -> dict[str, tuple[Optional[bytes], str]]:
    """``{url: (bytes or None, route or reason)}`` for several meetdocs PDFs.

    Order, per document: direct (free, fails at the WAF), Scrape.do (paid, skipped
    for the rest of the process once its monthly quota is known to be spent), then
    ONE headless browser for everything still missing. A genuine 404 is a document
    listed in eMeeting but not yet published, and is not retried anywhere.
    """
    out: dict[str, tuple[Optional[bytes], str]] = {}
    pending: list[str] = []
    for u in pdf_urls:
        raw, why = _direct(u)
        if raw is None and why != "HTTP 404":
            paid, why2 = _via_scrapedo(u)
            if paid is not None:
                raw, why = paid, why2
            else:
                why = f"{why}; {why2}"
        out[u] = (raw, why)
        if raw is None and not why.startswith("HTTP 404"):
            pending.append(u)
    if pending:
        for u, (raw, why) in _via_browser(pending).items():
            out[u] = (raw, why if raw is not None else f"{out[u][1]}; {why}")
    for u, (raw, why) in out.items():
        if raw is None:
            logger.warning("[journey] no PDF for %s: %s", u, why)
    return out


def _fetch_pdf_bytes(pdf_url: str) -> Optional[bytes]:
    """The PDF's bytes: direct, then Scrape.do, then a headless browser.

    Returns None when no route yields a PDF (a genuine 404 means the document is
    listed in eMeeting but not yet published on meetdocs).
    """
    return fetch_pdf_bytes_many([pdf_url])[pdf_url][0]


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
    return _extract_and_store(db, pdf_url, raw)


def _extract_and_store(db: Session, pdf_url: str, raw: bytes) -> Optional[dict]:
    """Extract text from real PDF bytes and write it through to the cache."""
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
    return {"text": body, "char_count": char_count, "page_count": pages, "truncated": truncated}


def extract_many(db: Session, pdf_urls: list[str]) -> dict[str, str]:
    """Fill the cache for several PDFs with ONE browser; ``{url: outcome}``.

    Outcome is ``cached`` (already held), ``<route>:<chars>`` (direct, scrapedo
    or browser, and how much text), or the reason nothing was stored. Meant for
    backfills; the on-demand path stays ``get_pdf_text``.
    """
    out: dict[str, str] = {}
    held = set()
    if pdf_urls:
        try:
            held = {r[0] for r in db.execute(text(
                "SELECT pdf_url FROM emeeting_doc_text_cache "
                "WHERE pdf_url = ANY(:u) AND coalesce(char_count, 0) > 0"),
                {"u": list(pdf_urls)})}
        except Exception:
            db.rollback()
    todo = [u for u in pdf_urls if u and u not in held]
    out.update({u: "cached" for u in held})
    for u, (raw, why) in fetch_pdf_bytes_many(todo).items():
        if raw is None:
            out[u] = why
            continue
        got = _extract_and_store(db, u, raw)
        out[u] = f"{why}:{got['char_count']}" if got else f"{why}: no text (image-only PDF?)"
    return out
