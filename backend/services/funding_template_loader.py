"""
One loader for the funding templates behind Tender Docs, with locale fallback.

Three routers each had their own copy of "open knowledge_base/funding_templates/
<id>.json and cache it", which is why adding a language meant touching three
files and why none of them ever got one. Brubru speaks six languages (EN, FR,
NL, ES, CA, IT) and every section title, evaluation criterion and AI prompt seed
in these 19 templates is English, so a French user sees a French interface
wrapped around an English document.

Layout, following the sibling-file option from the i18n handoff:

    funding_templates/
      eic-accelerator-stage-1.json        <- EN source of truth
      eic-accelerator-stage-1.fr.json     <- overlay, partial is fine
      eic-accelerator-stage-1.ca.json

An overlay does not have to be complete. It is deep-merged over the English
document, so a file carrying only `name` and the section labels yields
translated headings with English prompt seeds rather than an error or a blank.
That matters because the bodies are ~13,000 strings and will land in batches:
each batch improves the page instead of being invisible until the last one.

Lists merge by index and only when the lengths match, because a translation is
generated from the English structure and a length mismatch means the overlay is
stale. Silently zipping a stale overlay onto the wrong sections would attach the
wrong prompts to the wrong criterion, which is worse than showing English.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "funding_templates"

# Brubru's six. Never 23.
SUPPORTED_LANGS = ("en", "es", "ca", "fr", "it", "nl")
DEFAULT_LANG = "en"

# (template_id, lang) -> merged document
_CACHE: Dict[tuple[str, str], Dict[str, Any]] = {}


def normalise_lang(lang: Optional[str]) -> str:
    """A supported language code, defaulting to English."""
    if not lang:
        return DEFAULT_LANG
    code = str(lang).strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LANGS else DEFAULT_LANG


def _deep_merge(base: Any, overlay: Any, path: str = "") -> Any:
    """Overlay translated values onto the English document."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, value in overlay.items():
            merged[key] = _deep_merge(base.get(key), value, f"{path}.{key}")
        return merged

    if isinstance(base, list) and isinstance(overlay, list):
        if len(base) != len(overlay):
            logger.warning(
                "funding template overlay length mismatch at %s (en=%d, overlay=%d); "
                "keeping English for this list",
                path or "<root>", len(base), len(overlay),
            )
            return base
        return [_deep_merge(b, o, f"{path}[{i}]") for i, (b, o) in enumerate(zip(base, overlay))]

    # A blank string in an overlay means "not translated yet", not "erase this".
    if isinstance(overlay, str) and not overlay.strip():
        return base

    return overlay if overlay is not None else base


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open() as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as exc:
        logger.warning("funding template %s unreadable: %s", path.name, exc)
        return None


def available_locales(template_id: str) -> List[str]:
    """Languages this template actually ships, English always first."""
    found = [DEFAULT_LANG]
    for lang in SUPPORTED_LANGS:
        if lang == DEFAULT_LANG:
            continue
        if (TEMPLATES_DIR / f"{template_id}.{lang}.json").exists():
            found.append(lang)
    return found


def load_template(template_id: str, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The template in `lang`, falling back to English key by key.

    Returns None when the English source does not exist, so callers can raise
    their own 404 with their own wording.
    """
    code = normalise_lang(lang)
    cached = _CACHE.get((template_id, code))
    if cached is not None:
        return cached

    base = _read(TEMPLATES_DIR / f"{template_id}.json")
    if base is None:
        return None

    document = base
    if code != DEFAULT_LANG:
        overlay = _read(TEMPLATES_DIR / f"{template_id}.{code}.json")
        if overlay:
            document = _deep_merge(base, overlay, template_id)

    document = dict(document)
    document["lang"] = code
    document["available_locales"] = available_locales(template_id)
    # Honest about what the user is actually reading, so the UI can say so
    # rather than implying a full translation exists.
    document["is_translated"] = code != DEFAULT_LANG and code in document["available_locales"]

    _CACHE[(template_id, code)] = document
    return document


def load_all(lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every template, in `lang`. Overlay files are not templates themselves."""
    out: List[Dict[str, Any]] = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        # "eic-accelerator-stage-1.fr" has two dots: it is an overlay, skip it.
        if "." in path.stem:
            continue
        document = load_template(path.stem, lang)
        if document:
            out.append(document)
    return out


def clear_cache() -> None:
    """Drop the in-process cache. Used by tests."""
    _CACHE.clear()
