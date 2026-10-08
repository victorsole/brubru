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
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

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


# ---------------------------------------------------------------------------
# The next cut-off a template's applicant can still aim for.
#
# Why (8 Oct 2026): three places showed `cut_offs_2026_cet[0]` as the "next"
# deadline, so in October the EIC Accelerator templates offered 7 January and
# 4 March 2026 and STEP offered 11 February 2026; a new draft was pre-filled with
# a date already past and its card counted down to "overdue". The Accelerator
# short proposal also carried the FULL-proposal batches, although short
# proposals are batched on the first Tuesday of every month at 17:00 Brussels
# time (EIC Work Programme 2026, Section V).
# ---------------------------------------------------------------------------

_BRUSSELS = ZoneInfo("Europe/Brussels")


def _first_tuesday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(1 - first.weekday()) % 7)


def _parse_iso(value: str) -> Optional[datetime]:
    """An ISO date or datetime as an aware datetime; a bare date means 17:00 Brussels."""
    try:
        if len(value) == 10:
            d = date.fromisoformat(value)
            return datetime.combine(d, time(17, 0), tzinfo=_BRUSSELS)
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_BRUSSELS)
    except (TypeError, ValueError):
        return None


def next_deadline(template: Dict[str, Any], now: Optional[datetime] = None) -> Optional[str]:
    """The next cut-off still ahead of `now`, as the template states it.

    Order: a monthly rule (`cutoff_rule: first_tuesday_monthly`, bounded by
    `submission_end_date`), then the earliest future entry of `cut_offs_2026_cet`,
    then the earliest future single deadline. A call whose dates are all past
    returns its last known date, so a closed call still shows when it closed;
    a past date is never returned while a future one exists.
    """
    now = (now or datetime.now(_BRUSSELS)).astimezone(_BRUSSELS)

    if template.get("cutoff_rule") == "first_tuesday_monthly":
        hh, mm = (int(x) for x in str(template.get("cutoff_time_brussels") or "17:00").split(":"))
        end_raw = template.get("submission_end_date")
        end = _parse_iso(end_raw) if end_raw else None
        year, month = now.year, now.month
        for _ in range(3):
            cut = datetime.combine(_first_tuesday(year, month), time(hh, mm), tzinfo=_BRUSSELS)
            if cut > now:
                if end is not None and cut.date() > end.date():
                    return end_raw
                return cut.isoformat()
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return end_raw

    listed = [s for s in (template.get("cut_offs_2026_cet") or []) if isinstance(s, str)]
    parsed = [(s, _parse_iso(s)) for s in listed]
    future = sorted((p, s) for s, p in parsed if p is not None and p > now)
    if future:
        return future[0][1]

    singles = [template.get(k) for k in ("deadline_2026_cet", "deadline_2027_cet", "deadline_2027_indicative_cet")]
    singles = [s for s in singles if isinstance(s, str)]
    future_singles = sorted((p, s) for s in singles for p in [_parse_iso(s)] if p is not None and p > now)
    if future_singles:
        return future_singles[0][1]

    past = sorted((p, s) for s in listed + singles for p in [_parse_iso(s)] if p is not None)
    return past[-1][1] if past else None
