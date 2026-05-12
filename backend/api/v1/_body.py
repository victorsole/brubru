"""
Shared body-field helpers for /api/v1/* endpoints.

The v1 API exposes textual content via three companion fields on every
content-bearing item:

    has_body : bool            — True iff some text body is present (>500 chars)
    body_html: Optional[str]   — HTML rendering when source is HTML; None for PDF-only
    body_txt: Optional[str]   — Plain-text body, always populated when has_body=True

A deprecated `body` alias is also surfaced (one release) returning whichever
of body_text / body_html is non-null. Clients should migrate to the explicit
pair.

Per Victor's directive (5 May 2026):
- No truncation: full body on both list and detail responses.
- For PDF-sourced rows (Cellar PDFs, RegDel PDFs, etc.) we DO NOT synthesise
  HTML from the extracted text — body_html stays None to honestly represent
  "we never saw HTML upstream, only a PDF binary".
- For HTML-sourced rows we either capture body_html as stored, or compose it
  from canonical structured fields (Stage 1) until a re-scrape pass captures
  the byte-identical upstream body div (Stage 2, deferred).
"""

from __future__ import annotations

import re
from html import escape as _html_escape
from typing import Optional, Tuple


# Default min length for has_body=True. Filters out scrape artifacts
# ("Page not found", boilerplate-only PDFs, etc.). Endpoints expose this
# as a `body_threshold` query parameter so partners can tune it per-call —
# e.g. funding-call summaries are often 200-400 chars and partners may
# want has_body=true on those too.
DEFAULT_HAS_BODY_THRESHOLD = 500


def _strip_html_to_text(html: str) -> str:
    """Conservative HTML → text. Replaces tags with whitespace, collapses runs."""
    if not html:
        return ""
    # Remove <script> + <style> with their contents.
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level tags with newline so paragraphs stay readable.
    html = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", " ", html)
    # HTML entity → char (lightweight; full unescape lives in stdlib).
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;|&apos;", "'", text)
    # Collapse whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return text.strip()


def body_from_pdf_text(
    text: Optional[str],
    threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> Tuple[Optional[str], Optional[str], bool]:
    """For PDF-sourced rows: return (body_html=None, body_txt=text, has_body).

    Honest contract — we never invent HTML from PDF text. If a partner needs
    HTML, they must use the source PDF URL.

    Args:
        text: extracted PDF text or None.
        threshold: minimum char length to set has_body=True. Default 500.
    """
    if text is None:
        return None, None, False
    text = text.strip()
    if not text:
        return None, None, False
    has = len(text) >= threshold
    return None, text, has


def body_from_html(
    html: Optional[str],
    threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> Tuple[Optional[str], Optional[str], bool]:
    """For HTML-sourced rows: return (body_html=html, body_txt=stripped, has_body)."""
    if html is None:
        return None, None, False
    html = html.strip()
    if not html:
        return None, None, False
    text = _strip_html_to_text(html)
    has = len(text) >= threshold
    return html, text, has


def compose_html_from_sections(
    sections: list,
    threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> Tuple[Optional[str], Optional[str], bool]:
    """Stage 1 composer — wrap structured fields as semantic HTML.

    Used by /consultations where we have description, full_description,
    objectives, target_group, outcome_summary as separate columns. Composes
    them into a single article body. NOT byte-identical to the upstream
    HYS page; Stage 2 (deferred) will replace this with a re-scrape capture.

    Args:
        sections: list of (heading, content) tuples. None / empty content
                  is silently skipped — never emits an empty section.
        threshold: minimum char length on the composed body_text to set
                  has_body=True. Default 500.
    """
    parts_html = []
    parts_text = []
    for heading, content in sections:
        if content is None:
            continue
        c = str(content).strip()
        if not c:
            continue
        # Detect if content already contains HTML tags.
        has_tags = bool(re.search(r"<[a-z][^>]*>", c, re.IGNORECASE))
        if has_tags:
            section_html = f"<section><h2>{_html_escape(heading)}</h2>{c}</section>"
            section_text = f"{heading}\n\n{_strip_html_to_text(c)}"
        else:
            # Wrap each paragraph in <p>; preserve line breaks.
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", c) if p.strip()]
            paras_html = "".join(f"<p>{_html_escape(p)}</p>" for p in paragraphs)
            section_html = f"<section><h2>{_html_escape(heading)}</h2>{paras_html}</section>"
            section_text = f"{heading}\n\n{c}"
        parts_html.append(section_html)
        parts_text.append(section_text)

    if not parts_html:
        return None, None, False

    body_html = f"<article>{''.join(parts_html)}</article>"
    body_text = "\n\n".join(parts_text)
    has = len(body_text) >= threshold
    return body_html, body_text, has


def deprecated_body(body_txt: Optional[str], body_html: Optional[str]) -> Optional[str]:
    """One-release back-compat alias. Returns body_txt if present, else body_html.

    Clients must migrate to the explicit body_txt / body_html pair before
    we drop this in the next minor release.
    """
    return body_txt or body_html


# ---------------------------------------------------------------------------
# FastAPI dependency: body_threshold query parameter
# ---------------------------------------------------------------------------
# Endpoints that emit body fields take a `body_threshold` query parameter so
# partners can tune the has_body cutoff per request. Default 500 chars; clamp
# to [0, 100000] to prevent silly values. Use as:
#
#     from ._body import body_threshold_param
#     ...
#     async def list_x(
#         ...,
#         body_threshold: int = Depends(body_threshold_param),
#     ):
#         body_html, body_text, has_body = compose_html_from_sections(
#             [...], threshold=body_threshold,
#         )

from fastapi import Query as _Query


def body_threshold_param(
    body_threshold: int = _Query(
        DEFAULT_HAS_BODY_THRESHOLD,
        ge=0,
        le=100_000,
        description=(
            "Minimum character length of body_text required for has_body=True. "
            "Default 500. Lower it (e.g. 200) if the source data has legitimately "
            "short bodies (funding-call summaries, infringement summaries). Set 0 "
            "to make has_body=True on any non-empty body."
        ),
    ),
) -> int:
    """Reusable FastAPI dependency for the body_threshold query param."""
    return body_threshold
