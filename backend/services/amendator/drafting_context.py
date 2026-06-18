"""
Drafting context builder for the Amendator AI.

When the user asks the AI to amend Article 5, the model used to receive only
Article 5's own text -- legally isolated, with no sight of the recitals that
motivate it, the defined terms it uses, or the other acts it cites. That is
exactly how an amendment ends up contradicting a definition or breaking a
cross-reference.

This module assembles a compact "DRAFTING CONTEXT" block from capability that
already exists elsewhere in the codebase but was never fed to the amendment
model:

  - definition_store        -> the Article 2 "means ..." definitions
  - recital_article_store    -> TF-IDF recital<->article linkage
  - cross_reference_resolver -> external acts cited in the element text

Everything is fail-safe: when the law is not in `eu_laws`, or its Formex is
unreadable, or no celex is supplied, the builders return an empty string and
the AI simply drafts as before. Both stores cache their result in
`eu_laws.extra_metadata`, so a precomputed law works even where the local
Formex archive is not deployed.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Priority order when budgeting characters: definitions are the most dangerous
# thing to get wrong, then external citations, then motivating recitals.
_DEFAULT_BUDGET = 1800
_MAX_DEFINITIONS = 8
_MAX_RECITALS = 3
_MAX_XREFS = 6

_DEF_TERM_MIN_LEN = 3  # skip 1-2 char "terms" that match noise


def _article_key_from_number(number: Optional[str]) -> Optional[str]:
    """Normalise an article number into the 'Article N' key the stores use."""
    if not number:
        return None
    num = str(number).strip()
    if not num:
        return None
    return num if num.lower().startswith("article") else f"Article {num}"


def build_element_context(
    db: Session,
    celex: Optional[str],
    *,
    article_number: Optional[str] = None,
    element_text: str = "",
    char_budget: int = _DEFAULT_BUDGET,
) -> str:
    """
    Build a DRAFTING CONTEXT block for a single legislative element.

    Includes (in priority order, within the char budget):
      1. definitions of any defined terms that appear in `element_text`
      2. external acts cited in `element_text` (resolved to CELEX)
      3. recitals linked to this article (rationale)

    Returns "" on any failure or when nothing relevant is found.
    """
    if not celex:
        return ""

    sections: list[str] = []
    spent = 0

    # 1. Definitions used in this element ------------------------------------
    try:
        from services.parsers.definition_store import get_or_compute_map as _defs

        def_map = _defs(db, celex) or {}
        if def_map and element_text:
            haystack = element_text.lower()
            hits: list[str] = []
            for term, entry in def_map.items():
                if len(term) < _DEF_TERM_MIN_LEN:
                    continue
                # word-boundary match so "data" does not fire inside "validate"
                if re.search(r"\b" + re.escape(term) + r"\b", haystack):
                    definition = (entry.get("definition") or "").strip()
                    if definition:
                        hits.append(f'  - "{entry.get("term", term)}": {definition}')
                if len(hits) >= _MAX_DEFINITIONS:
                    break
            if hits:
                block = "Defined terms used here (keep usage consistent):\n" + "\n".join(hits)
                if spent + len(block) <= char_budget:
                    sections.append(block)
                    spent += len(block)
    except Exception as exc:  # never block drafting on context enrichment
        logger.debug("drafting_context definitions failed for %s: %s", celex, exc)

    # 2. External cross-references in this element ----------------------------
    try:
        from services.parsers.cross_reference_resolver import resolve_references_json

        refs = resolve_references_json(element_text or "") or []
        seen: set[str] = set()
        lines: list[str] = []
        for ref in refs:
            label = (ref.get("raw") or "").strip()
            celex_ref = (ref.get("celex") or "").strip()
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            lines.append(f"  - {label}" + (f" (CELEX {celex_ref})" if celex_ref else ""))
            if len(lines) >= _MAX_XREFS:
                break
        if lines:
            block = "Acts referenced by this element (do not break these links):\n" + "\n".join(lines)
            if spent + len(block) <= char_budget:
                sections.append(block)
                spent += len(block)
    except Exception as exc:
        logger.debug("drafting_context xrefs failed for %s: %s", celex, exc)

    # 3. Recitals that motivate this article ---------------------------------
    try:
        from services.parsers.recital_article_store import get_or_compute_map as _recmap

        article_key = _article_key_from_number(article_number)
        rec_map = _recmap(db, celex) or {}
        if article_key and rec_map:
            linked = rec_map.get(article_key) or []
            lines = []
            for link in linked[:_MAX_RECITALS]:
                num = link.get("recital_number", "?")
                snippet = (link.get("snippet") or "").strip()
                if snippet:
                    lines.append(f"  - Recital ({num}): {snippet}")
            if lines:
                block = "Recitals motivating this article (rationale):\n" + "\n".join(lines)
                if spent + len(block) <= char_budget:
                    sections.append(block)
                    spent += len(block)
    except Exception as exc:
        logger.debug("drafting_context recitals failed for %s: %s", celex, exc)

    if not sections:
        return ""
    return "DRAFTING CONTEXT (from the loaded law, for accuracy):\n\n" + "\n\n".join(sections)


def build_document_definitions_block(
    db: Session,
    celex: Optional[str],
    *,
    char_budget: int = _DEFAULT_BUDGET,
    max_terms: int = 12,
) -> str:
    """
    Build a document-level defined-terms block for batch suggestions.

    Per-element recital/cross-ref enrichment is too costly to fan out across a
    whole document, but the defined-terms glossary is document-level and the
    single most valuable thing to keep an LLM consistent with. Returns "" when
    the law has no extractable definitions.
    """
    if not celex:
        return ""
    try:
        from services.parsers.definition_store import get_or_compute_map as _defs

        def_map = _defs(db, celex) or {}
    except Exception as exc:
        logger.debug("drafting_context doc definitions failed for %s: %s", celex, exc)
        return ""

    if not def_map:
        return ""

    lines: list[str] = []
    spent = 0
    for term, entry in list(def_map.items())[:max_terms]:
        definition = (entry.get("definition") or "").strip()
        if not definition:
            continue
        line = f'  - "{entry.get("term", term)}": {definition}'
        if spent + len(line) > char_budget:
            break
        lines.append(line)
        spent += len(line)

    if not lines:
        return ""
    return (
        "DEFINED TERMS in this law (keep amendments consistent with these):\n"
        + "\n".join(lines)
    )
