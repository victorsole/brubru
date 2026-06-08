"""
Shared primitives for the economy & finance scrapers (ECB, the EU financial
institutions, ESM). Each body's module (economy_ecb.py, economy_eba.py, ...)
imports these and adds its own source map + extraction strategy.

No LLM is used anywhere in economy ingestion.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 BrubruBot/1.0"
_TIMEOUT = 30
_BODY_CAP = 800_000  # chars; working-paper PDFs can be large


@dataclass
class Item:
    body_code: str
    item_type: str            # news | publication | event | legal
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
    r = http_get(url)
    if r is None:
        return None, None, "unreachable"
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/pdf" in ctype or url.lower().endswith(".pdf"):
        return extract_pdf(r.content), f'<p>PDF document: <a href="{url}">{url}</a></p>', "pdf"
    if "html" not in ctype and "xml" not in ctype:
        # Office docs (.docx/.xlsx), archives, images, etc. — do not parse as HTML.
        kind = (ctype.split(";")[0].split("/")[-1] or "file")[:20] or "file"
        return None, f'<p>Document: <a href="{url}">{url}</a></p>', kind
    body_txt, body_html = extract_html(r.text)
    return body_txt, body_html, "html"


# --- date parsing ----------------------------------------------------------
# Handles: 11/06/2026 ; "8 June 2026" / "8 JUNE 2026" ; "8 Dec 2026" ;
# ranges "11/06/2026 - 12/06/2026" and "18-19 Nov 2026" (-> the start day).
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_NUM_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_NAME_DATE_RE = re.compile(r"\b(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b")


def parse_listing_date(text: str) -> datetime | None:
    text = text or ""
    m = _NUM_DATE_RE.search(text)                # 11/06/2026 (ranges -> first match = start)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
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
