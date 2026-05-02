"""
Glossary injector — scan a built chat context for EU authority URIs and
return a localised one-line glossary block per URI.

Design constraints (from euvoc.md Phase 1 risks):
  - Only injects when URIs are present (no clutter for unrelated answers).
  - One glossary line per unique URI, not per occurrence.
  - Fallback chain CA -> ES -> EN matches AuthorityLabelCache default.
  - Fail-soft: any DB / lookup error returns None (no glossary), never
    raises into chat.

Public entry points:
    extract_authority_uris(text)              -> list[str]
    build_glossary_block(text, db, lang)      -> Optional[str]
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Sequence

from sqlalchemy.orm import Session

from .authority_label_cache import AuthorityLabelCache

logger = logging.getLogger(__name__)

# Authority URIs we care about share this prefix.
_AUTH_PREFIX = "http://publications.europa.eu/resource/authority/"

# Match `http://publications.europa.eu/resource/authority/{name}/{code}` where
# name + code are word-ish characters. We capture the whole URI.
_AUTH_URI_RE = re.compile(
    r"http://publications\.europa\.eu/resource/authority/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-:.]+"
)

# Cap glossary size — keep the injected block small so it doesn't crowd
# the 32k context budget. Phase 1 numbers: chat queries rarely surface > 10
# unique authority URIs at once.
_MAX_GLOSSARY_ENTRIES = 12


# Cheap language detector — only needs to tell apart Brubru's 6 supported
# languages. Heuristic-only; we don't need fasttext-class accuracy here.
_LANG_SIGNALS = {
    "ca": ("què", "açò", "perquè", "només", "açò", "aquest", "aquesta", "vostè", "ja", "amb", "fins", "està", "qui", "què", "tu ", " ho ", "menjar", "ciutadania", "regulació"),
    "es": ("¿", "qué", "porqué", "porque", "ahora", "está", "tienen", "cómo", "cuál", "ahora", "ciudad", "regulación", "directiva"),
    "fr": ("qu'est", "qu'", "ç", "où", "voici", "voilà", "directive", "règlement", "comment", "pourquoi"),
    "it": ("perché", "come", "ció", "regolamento", "direttiva", "città", "qual", "qualcosa"),
    "nl": ("waarom", "wat is", "richtlijn", "verordening", "hoe ", "wij ", "het ", "dat is"),
    "en": (),  # default
}


def detect_language(text: str) -> str:
    """Return one of {en,fr,es,ca,it,nl}. Defaults to 'en' on no signal."""
    if not text:
        return "en"
    t = text.lower()
    scores = {lang: 0 for lang in _LANG_SIGNALS}
    for lang, signals in _LANG_SIGNALS.items():
        for sig in signals:
            if sig in t:
                scores[lang] += 1
    # Pick the highest-scoring non-zero language; tie-break on canonical
    # priority (CA > ES > FR > IT > NL > EN — minority languages win to
    # honour Brubru's commitment to Catalan + minority EU langs).
    priority = ("ca", "es", "fr", "it", "nl", "en")
    best = max(priority, key=lambda l: (scores[l], -priority.index(l)))
    return best if scores[best] > 0 else "en"


def extract_authority_uris(text: str) -> List[str]:
    """Return de-duplicated authority URIs found in `text` (preserve order)."""
    if not text:
        return []
    seen: List[str] = []
    seen_set = set()
    for match in _AUTH_URI_RE.finditer(text):
        uri = match.group(0)
        if uri not in seen_set:
            seen_set.add(uri)
            seen.append(uri)
            if len(seen) >= _MAX_GLOSSARY_ENTRIES * 2:  # generous safety
                break
    return seen


def build_glossary_block(
    text: str,
    db: Session,
    lang: str = "en",
    *,
    fallback_chain: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """
    Scan `text` for authority URIs, resolve each in `lang`, and return a
    glossary block string ready to splice near the top of the AI context.

    Returns None when:
      - no authority URIs found
      - cache lookup yields no resolutions
      - any error occurs (logged, swallowed)
    """
    try:
        uris = extract_authority_uris(text)
        if not uris:
            return None

        cache = AuthorityLabelCache(db)
        resolved = cache.resolve_batch(uris[:_MAX_GLOSSARY_ENTRIES], lang, fallback_chain=fallback_chain)
        if not resolved:
            return None

        lines = ["=== EU VOCABULARY GLOSSARY ==="]
        lines.append(
            f"Localised labels for the EU authority URIs that appear in the context "
            f"(language: {lang}, fallback chain {list(fallback_chain) if fallback_chain else ['ca','es','en']}):"
        )
        for uri in uris[:_MAX_GLOSSARY_ENTRIES]:
            label = resolved.get(uri)
            if not label:
                continue
            short_id = uri.rsplit("/", 1)[-1]
            short_ds = uri.rsplit("/", 2)[-2]
            lines.append(f"- [{short_ds}/{short_id}] {label}")
        if len(lines) <= 2:
            # Nothing actually resolved.
            return None
        lines.append("")
        lines.append("INSTRUCTIONS:")
        lines.append("- When citing one of these URIs, prefer the localised label above.")
        lines.append("- Do NOT invent a label for any URI not listed here.")
        lines.append("=== END EU VOCABULARY GLOSSARY ===")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        logger.warning("glossary_injector: build failed (%s) — skipping", e)
        return None
