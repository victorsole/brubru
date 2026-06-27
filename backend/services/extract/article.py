"""Article-body extraction for deep classify (Phase 2 hardening).

The listing handlers give a title + a short card snippet. Classifying that thin text
makes the embedder grasp at proper nouns / acronyms in the title ("FIRST by FMD" ->
"first stage of EMU"). Deep-fetch instead pulls each item's detail page and extracts
the main article text, so the classifier sees the real content. Opt-in (one extra
fetch per item) and best-effort: on any failure the item keeps its listing snippet.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Where EU detail pages keep the body, roughly best-first across the 8 platforms.
_BODY_SELECTORS = [
    "article .ecl-content-block__description", ".ecl-paragraph", "article",
    "[role=main] .field--name-body", ".node__content .field--name-body",
    ".field--name-body", ".wysiwyg", ".node__content", "main [property='text']",
    "main article", "[role=main]", "main", "#main-content", ".main-content", ".content",
]
_STRIP = "nav, header, footer, aside, script, style, form, noscript, .menu, .navbar, " \
         ".breadcrumb, .cookie, .ecl-site-header, .ecl-site-footer, .related, .share, " \
         ".social, [role=navigation], [role=banner], [role=contentinfo]"
_WS = re.compile(r"\s+")


def _txt(el) -> str:
    return _WS.sub(" ", el.get_text(" ", strip=True)).strip()


def extract_body(html: str, url: str = "", *, max_chars: int = 6000) -> tuple[str, str]:
    """Return (body_txt, body_html) for a detail page. body_txt is the cleaned main
    article text (capped); body_html is the chosen container's inner HTML. ('','') if
    nothing substantial is found."""
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select(_STRIP):
        el.decompose()
    best, best_len = None, 0
    for sel in _BODY_SELECTORS:
        for cand in soup.select(sel):
            n = len(_txt(cand))
            if n > best_len:
                best, best_len = cand, n
        if best_len >= 400:  # a confident hit at a high-priority selector: stop early
            break
    # Fallback: stitch the substantial paragraphs together.
    if best_len < 200:
        paras = [p for p in (soup.select("p") or []) if len(_txt(p)) >= 50]
        if paras:
            txt = _WS.sub(" ", " ".join(_txt(p) for p in paras)).strip()
            return txt[:max_chars], "".join(str(p) for p in paras)[:max_chars * 3]
    if not best or best_len < 80:
        return "", ""
    return _txt(best)[:max_chars], best.decode()[:max_chars * 3]
