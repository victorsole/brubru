"""
Shared helpers for the /specialised/* backfill scripts.

Reduces boilerplate when adding a new backfill: import the helpers,
provide a universe-fetch + classification function, point at a target
table, and the rest (Cellar body fetch, PDF text extraction, HTML
strip, NUL strip, throttle, idempotent UPSERT, pooler-conn auto-retry)
is handled here.

Usage:
    from _specialised_helpers import (
        fetch_xhtml, fetch_pdf, extract_pdf_text, strip_html_to_text,
        fetch_url_bytes, ChunkedDb, get_env, to_iso,
    )
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote as _urlquote

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"


# ─────────────────────── env / db helpers ────────────────────────────────


def get_env(k: str) -> str:
    if not ENV.exists():
        return os.environ.get(k, "")
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return os.environ.get(k, "")


class ChunkedDb:
    """Postgres connection wrapper that auto-reopens on pooler timeouts."""

    def __init__(self, autocommit: bool = False):
        self._dsn = get_env("DATABASE_URL")
        if not self._dsn:
            print("[FATAL] DATABASE_URL missing", file=sys.stderr)
            sys.exit(1)
        self._autocommit = autocommit
        self.conn = psycopg2.connect(self._dsn, connect_timeout=15)
        self.conn.autocommit = autocommit
        self.cur = self.conn.cursor()

    def execute(self, sql: str, params: dict | tuple | None = None,
                *, retries: int = 2) -> None:
        attempt = 0
        while True:
            try:
                self.cur.execute(sql, params)
                return
            except psycopg2.OperationalError as exc:
                if attempt >= retries:
                    raise
                attempt += 1
                print(f"[warn] reopening pooled conn (attempt {attempt}): {exc!s}", flush=True)
                try:
                    self.cur.close()
                    self.conn.close()
                except Exception:
                    pass
                self.conn = psycopg2.connect(self._dsn, connect_timeout=15)
                self.conn.autocommit = self._autocommit
                self.cur = self.conn.cursor()

    def fetchall(self):
        return self.cur.fetchall()

    def fetchone(self):
        return self.cur.fetchone()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        try:
            self.cur.close()
            self.conn.close()
        except Exception:
            pass


def to_iso(value: Any) -> Optional[str]:
    """Normalise a date-ish value to ISO YYYY-MM-DD or None."""
    if not value:
        return None
    s = str(value).split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


# ─────────────────────── HTTP helpers ────────────────────────────────────


_UA = "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"


def fetch_url_bytes(url: str, *, accept: str = "*/*",
                    accept_language: str = "en", timeout: int = 30,
                    headers: dict | None = None) -> tuple[Optional[bytes], Optional[str], int]:
    """Generic GET. Returns (body, content_type, http_status)."""
    h = {"User-Agent": _UA, "Accept": accept, "Accept-Language": accept_language}
    if headers:
        h.update(headers)
    req = urllib_request.Request(url, headers=h)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            return r.read(), ctype, r.status if hasattr(r, "status") else 200
    except urllib_error.HTTPError as e:
        return None, None, e.code
    except urllib_error.URLError:
        return None, None, 0
    except Exception:
        return None, None, 0


# ─────────────────────── Cellar body fetch ───────────────────────────────


def cellar_url(celex: str) -> str:
    """CELEX-encoded resource URL — parens must be percent-encoded."""
    return f"https://publications.europa.eu/resource/celex/{_urlquote(celex, safe='')}"


def fetch_xhtml(celex: str, timeout: int = 30) -> Optional[str]:
    """Cellar XHTML manifestation (EN). Returns HTML string or None."""
    body, ctype, _ = fetch_url_bytes(
        cellar_url(celex),
        accept="application/xhtml+xml",
        timeout=timeout,
    )
    if not body or not ctype:
        return None
    if "xhtml" in ctype or "html" in ctype:
        return body.decode("utf-8", errors="replace")
    return None


def fetch_pdf(celex: str, timeout: int = 45) -> Optional[bytes]:
    """Cellar PDF resource. Handles 300-multi-choice listing fallback."""
    body, ctype, _ = fetch_url_bytes(
        cellar_url(celex),
        accept="application/pdf",
        timeout=timeout,
    )
    if not body:
        return None
    if ctype and "pdf" in ctype:
        return body
    # Cellar served a multi-choice listing — find DOC_1 PDF.
    try:
        listing = body.decode("utf-8", errors="replace")
    except Exception:
        return None
    m = re.search(r'(https?://publications\.europa\.eu/resource/cellar/[^"\s<>]+DOC_1\.pdf)', listing)
    if not m:
        return None
    body2, ctype2, _ = fetch_url_bytes(m.group(1), accept="application/pdf", timeout=timeout * 2)
    if body2 and ctype2 and "pdf" in ctype2:
        return body2
    return None


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    """pypdf text extraction — handles old EU PDFs with glyph encoding (poorly)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip() or None
    except Exception:
        return None


def strip_html_to_text(html: str) -> str:
    """Conservative HTML → text. Drops scripts/styles/nav, keeps paragraphs."""
    text = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>",
                  " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return text.strip()


def fetch_body_for_celex(celex: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Combined Cellar fetch: returns (body_html, body_text, body_source).

    body_html is None for PDF-sourced rows (we never synthesise HTML
    from extracted PDF text).
    """
    xhtml = fetch_xhtml(celex)
    if xhtml and "<html" in xhtml.lower():
        text = strip_html_to_text(xhtml)
        return xhtml.replace("\x00", "")[:5_000_000], text.replace("\x00", "")[:5_000_000], "xhtml"
    pdf = fetch_pdf(celex)
    if pdf:
        text = extract_pdf_text(pdf)
        if text:
            return None, text.replace("\x00", "")[:5_000_000], "pdf"
    return None, None, None
