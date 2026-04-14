"""
Legal Text Annotator
====================

Combines the three annotation layers (cross-references, law aliases, defined
terms) into a single `annotate_legal_text(text, defined_terms=None)` helper.

This is what the frontend calls to turn a raw paragraph of EU legal text into
hover-and-click-ready HTML:

- Cross-refs:        <a class="eur-lex-ref" href="EUR-Lex">...</a>
- Aliases:           <a class="eur-lex-ref eur-lex-ref--alias" ...>GDPR</a>
- Defined terms:     <span class="defined-term" title="Article 3(i): ...">online platform</span>

The layering order matters: we annotate citations and aliases first (which
insert new `<a>` tags), then wrap defined terms *only in the text fragments
that lie outside any `<a>` tag*. That way we never wrap a term that happens to
appear inside a citation's visible label.

Usage
-----
>>> from services.parsers.legal_text_annotator import annotate_legal_text
>>> html = annotate_legal_text("An online platform under GDPR Article 5", defined_terms=terms)
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from .cross_reference_resolver import annotate_html as _annotate_citations


# Segments HTML into tag vs non-tag runs so we can apply further text-level
# wrapping only to non-tag segments.
_TAG_SPLIT = re.compile(r"(<[^>]+>)")
_A_OPEN = re.compile(r"<a\b", re.IGNORECASE)
_A_CLOSE = re.compile(r"</a\s*>", re.IGNORECASE)


def _iter_text_outside_anchors(html: str):
    """
    Yield `(text_segment, is_outside_anchor)` tuples so callers can process
    only the text nodes that are not inside an `<a>...</a>` region.

    Everything that is a tag is yielded unchanged with is_outside_anchor=False.
    Plain text inside an anchor is yielded with False.
    Plain text outside anchors is yielded with True.
    """
    depth = 0
    for chunk in _TAG_SPLIT.split(html):
        if not chunk:
            continue
        if chunk.startswith("<") and chunk.endswith(">"):
            if _A_OPEN.match(chunk):
                depth += 1
            elif _A_CLOSE.match(chunk):
                depth = max(0, depth - 1)
            yield chunk, False
        else:
            yield chunk, depth == 0


def _escape_html_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _wrap_defined_terms(text: str, terms_sorted: list[tuple[str, dict[str, Any]]]) -> str:
    """
    Wrap the first occurrence (per pattern) of each defined term in `text`.

    `terms_sorted` is sorted longest-first so multi-word terms win over
    sub-string shorter terms. Matching is case-insensitive but word-boundary
    strict. Each term is wrapped only ONCE per paragraph -- wrapping every
    occurrence of common words would make the page unreadable.
    """
    if not text or not terms_sorted:
        return text
    # Track byte spans that have already been wrapped so subsequent terms do not
    # re-wrap inside an earlier wrap.
    out_chunks: list[str] = []
    cursor = 0
    text_lower = text.lower()
    wrapped_ranges: list[tuple[int, int]] = []

    for term_key, entry in terms_sorted:
        if len(term_key) < 4:
            continue
        pattern = re.compile(r"(?<![\w\-]){re}(?![\w\-])".format(re=re.escape(term_key)), re.IGNORECASE)
        m = pattern.search(text_lower)
        if not m:
            continue
        s, e = m.start(), m.end()
        # Skip if inside an already-wrapped range
        if any(not (e <= rs or s >= re_) for rs, re_ in wrapped_ranges):
            continue
        wrapped_ranges.append((s, e))

    # Now apply wraps in order
    wrapped_ranges.sort()
    for s, e in wrapped_ranges:
        out_chunks.append(text[cursor:s])
        raw = text[s:e]
        # Find which term matches to pull the definition
        for term_key, entry in terms_sorted:
            if term_key.lower() == raw.lower() or raw.lower() == term_key.lower():
                title_text = _build_definition_title(entry)
                article = entry.get("article", "")
                point = entry.get("point") or ""
                data_attrs = (
                    f'data-term="{_escape_html_attr(term_key)}" '
                    f'data-article="{_escape_html_attr(article)}"'
                )
                if point:
                    data_attrs += f' data-point="{_escape_html_attr(point)}"'
                out_chunks.append(
                    f'<span class="defined-term" '
                    f'title="{_escape_html_attr(title_text)}" '
                    f"{data_attrs}>{raw}</span>"
                )
                break
        else:
            out_chunks.append(raw)
        cursor = e
    out_chunks.append(text[cursor:])
    return "".join(out_chunks)


def _build_definition_title(entry: Mapping[str, Any]) -> str:
    article = entry.get("article", "")
    point = entry.get("point") or ""
    definition = entry.get("definition", "")
    ref = f"{article}({point})" if point else article
    if definition and len(definition) > 260:
        definition = definition[:260].rsplit(" ", 1)[0] + "…"
    return f"{ref}: {definition}" if ref else definition


def annotate_legal_text(
    text: str,
    defined_terms: Optional[Mapping[str, Mapping[str, Any]]] = None,
    *,
    include_aliases: bool = True,
) -> str:
    """
    Return HTML with:
    - cross-references to EU legal acts wrapped in <a class="eur-lex-ref">
    - acronyms (GDPR, DSA, ...) wrapped when include_aliases=True
    - defined terms from `defined_terms` wrapped in <span class="defined-term">
      with a native `title` tooltip for progressive disclosure

    Defined-term wrapping is applied only to text outside existing anchors so
    it can never double-wrap inside a citation hyperlink.
    """
    # Layer 1 + 2: citations and aliases (yields annotated HTML)
    annotated = _annotate_citations(text, include_aliases=include_aliases)

    # Layer 3: defined terms, only in non-anchor text
    if not defined_terms:
        return annotated

    # Longest term first so "Very Large Online Platform" beats "Platform"
    terms_sorted = sorted(defined_terms.items(), key=lambda kv: -len(kv[0]))

    out: list[str] = []
    for segment, is_outside in _iter_text_outside_anchors(annotated):
        if is_outside:
            out.append(_wrap_defined_terms(segment, terms_sorted))
        else:
            out.append(segment)
    return "".join(out)


def annotate_many(
    texts: list[str],
    defined_terms: Optional[Mapping[str, Mapping[str, Any]]] = None,
    *,
    include_aliases: bool = True,
) -> list[str]:
    """Vectorised helper so the frontend can annotate all paragraphs in one call."""
    return [annotate_legal_text(t, defined_terms, include_aliases=include_aliases) for t in texts]
