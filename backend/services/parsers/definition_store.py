"""
Persistence helpers for the defined-terms map (Option B of the LegalViz pattern).

Stored under `eu_laws.extra_metadata.defined_terms` — no schema migration.

Two versions (15 September 2026)
--------------------------------
`defined_terms` is parsed from the act's ORIGINAL Formex text and never refreshed, so a
definition added by an amendment never appeared (the AI Act: 65 terms, no "SME" or
"small mid-cap enterprise", both in consolidated version 02024R1689-20260727).
`get_defined_terms(version="latest")` reads the latest CONSOLIDATED text from Cellar
instead and caches it PER CONSOLIDATED VERSION under
`extra_metadata.defined_terms_consolidated.<consolidated CELEX>`, so a new consolidation
is a new cache entry, never a stale hit. Every result says which text it came from.

Shape
-----
    {
      "information society service": {
        "term": "information society service",
        "definition": "a 'service' as defined in Article 1(1), point (b), of Directive (EU) 2015/1535",
        "article": "Article 3",
        "point": "a"
      },
      ...
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text as sqla_text
from sqlalchemy.orm import Session

from .definition_extractor import extract_definitions_map
from .formex_parser import parse_formex_file

METADATA_KEY = "defined_terms"
VERSION_KEY = "defined_terms_version"
CURRENT_VERSION = 1


def read_map(db: Session, celex: str) -> Optional[dict[str, Any]]:
    row = db.execute(
        sqla_text("SELECT extra_metadata FROM eu_laws WHERE celex = :celex LIMIT 1"),
        {"celex": celex},
    ).first()
    if not row or not row[0]:
        return None
    meta = row[0]
    if meta.get(VERSION_KEY) != CURRENT_VERSION:
        return None
    return meta.get(METADATA_KEY)


def write_map(db: Session, celex: str, mapping: dict[str, Any]) -> bool:
    import json

    result = db.execute(
        sqla_text(
            """
            UPDATE eu_laws
               SET extra_metadata = jsonb_set(
                       jsonb_set(
                           COALESCE(extra_metadata, '{}'::jsonb),
                           ARRAY[:map_key],
                           CAST(:mapping AS jsonb),
                           true
                       ),
                       ARRAY[:ver_key],
                       CAST(:ver AS jsonb),
                       true
                   ),
                   updated_at = NOW()
             WHERE celex = :celex
            """
        ),
        {
            "celex": celex,
            "map_key": METADATA_KEY,
            "ver_key": VERSION_KEY,
            "mapping": json.dumps(mapping, ensure_ascii=False),
            "ver": str(CURRENT_VERSION),
        },
    )
    db.commit()
    return result.rowcount > 0


def get_or_compute_map(
    db: Session,
    celex: str,
    *,
    force_recompute: bool = False,
) -> Optional[dict[str, Any]]:
    if not force_recompute:
        cached = read_map(db, celex)
        if cached is not None:
            return cached

    row = db.execute(
        sqla_text("SELECT xml_path FROM eu_laws WHERE celex = :celex LIMIT 1"),
        {"celex": celex},
    ).first()
    if not row or not row[0]:
        return None

    project_root = Path(__file__).resolve().parents[3]
    candidate = (project_root / row[0]).resolve()
    if not candidate.is_file():
        return None

    try:
        parsed = parse_formex_file(candidate)
    except Exception:
        return None

    mapping = extract_definitions_map(parsed)
    write_map(db, celex, mapping)
    return mapping


# ---------------------------------------------------------------------------
# Versioned access: latest consolidated text or the original act
# ---------------------------------------------------------------------------
CONSOLIDATED_KEY = "defined_terms_consolidated"
# Bump when the XHTML parse or the extractor changes what a consolidated entry holds.
CONSOLIDATED_PARSER_VERSION = 2  # 2: point-by-point parsing (GDPR 23 -> 26, AI Act 69 -> 72)
_LATEST_TTL_SECONDS = 6 * 3600
_latest_cache: dict[str, tuple[float, Optional[dict[str, Any]]]] = {}

CELLAR_CELEX = "https://publications.europa.eu/resource/celex/{celex}"
EURLEX_CELEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def latest_consolidated_version(celex: str) -> Optional[dict[str, Any]]:
    """{consolidatedCelex, date} of the newest consolidation OF this act, or None.
    Cached in-process for six hours: consolidations appear a few times a year."""
    import asyncio
    import time

    key = celex.upper()
    hit = _latest_cache.get(key)
    if hit and time.monotonic() - hit[0] < _LATEST_TTL_SECONDS:
        return hit[1]

    async def _lookup():
        from services.api_clients.cellar_sparql_client import CellarSPARQLClient
        async with CellarSPARQLClient() as client:
            return await client.get_consolidated_versions(key)

    try:
        rows = asyncio.run(_lookup())
    except Exception:
        return None  # a failed lookup is not cached: the next request retries
    latest = rows[0] if rows else None
    _latest_cache[key] = (time.monotonic(), latest)
    return latest


def fetch_consolidated_xhtml(consolidated_celex: str) -> Optional[str]:
    import httpx

    try:
        r = httpx.get(CELLAR_CELEX.format(celex=consolidated_celex), timeout=90, follow_redirects=True,
                      headers={"Accept": "application/xhtml+xml", "Accept-Language": "en"})
    except Exception:
        return None
    if r.status_code != 200 or "xhtml" not in r.headers.get("content-type", ""):
        return None
    return r.text


def _read_consolidated(db: Session, celex: str, consolidated_celex: str) -> Optional[dict[str, Any]]:
    row = db.execute(
        sqla_text("SELECT extra_metadata #> ARRAY[:k, :c] FROM eu_laws WHERE celex = :celex LIMIT 1"),
        {"k": CONSOLIDATED_KEY, "c": consolidated_celex, "celex": celex},
    ).first()
    entry = row[0] if row else None
    if not entry or entry.get("parser_version") != CONSOLIDATED_PARSER_VERSION:
        return None
    return entry


def _write_consolidated(db: Session, celex: str, consolidated_celex: str, entry: dict[str, Any]) -> None:
    import json

    db.execute(
        sqla_text(
            """
            UPDATE eu_laws
               SET extra_metadata = jsonb_set(
                       jsonb_set(COALESCE(extra_metadata, '{}'::jsonb), ARRAY[:k],
                                 COALESCE(extra_metadata -> :k, '{}'::jsonb), true),
                       ARRAY[:k, :c], CAST(:entry AS jsonb), true)
             WHERE celex = :celex
            """
        ),
        {"k": CONSOLIDATED_KEY, "c": consolidated_celex, "celex": celex,
         "entry": json.dumps(entry, ensure_ascii=False)},
    )
    db.commit()


def get_defined_terms(
    db: Session,
    celex: str,
    *,
    version: str = "latest",
    force_recompute: bool = False,
) -> Optional[dict[str, Any]]:
    """The defined terms of `celex` with the text they came from, or None when the act
    is unknown.

    Returns {terms, version_requested, version_used, source_celex, version_date,
    source_url, fallback_reason}. `version="latest"` reads the newest consolidated text;
    when the act has no consolidation (never amended) or that text cannot be read, it
    answers from the original text and names the reason in `fallback_reason` rather
    than failing or pretending.
    """
    from datetime import datetime, timezone

    celex = celex.upper()
    version = (version or "latest").lower()

    def _original(reason: Optional[str]) -> Optional[dict[str, Any]]:
        terms = get_or_compute_map(db, celex, force_recompute=force_recompute)
        if terms is None:
            return None
        return {"terms": terms, "version_requested": version, "version_used": "original",
                "source_celex": celex, "version_date": None,
                "source_url": EURLEX_CELEX.format(celex=celex), "fallback_reason": reason}

    if version == "original":
        return _original(None)

    latest = latest_consolidated_version(celex)
    if not latest or not latest.get("consolidatedCelex"):
        return _original("no_consolidated_version")
    cons = latest["consolidatedCelex"]

    entry = None if force_recompute else _read_consolidated(db, celex, cons)
    if entry is None:
        xhtml = fetch_consolidated_xhtml(cons)
        if not xhtml:
            return _original("consolidated_text_unavailable")
        from .consolidated_xhtml import parse_consolidated_law

        terms = extract_definitions_map(parse_consolidated_law(xhtml))
        if not terms:
            # An empty parse of a law whose original defines terms is our failure, not
            # the law's: answer from the original and say so; do not cache it.
            original = _original("consolidated_parse_empty")
            if original is not None and original["terms"]:
                return original
        entry = {"terms": terms, "version_date": latest.get("date"),
                 "parser_version": CONSOLIDATED_PARSER_VERSION,
                 "computed_at": datetime.now(timezone.utc).isoformat()}
        exists = db.execute(sqla_text("SELECT 1 FROM eu_laws WHERE celex = :c"), {"c": celex}).first()
        if exists:
            _write_consolidated(db, celex, cons, entry)
    return {"terms": entry["terms"], "version_requested": version, "version_used": "latest",
            "source_celex": cons, "version_date": entry.get("version_date"),
            "source_url": EURLEX_CELEX.format(celex=cons), "fallback_reason": None,
            "computed_at": entry.get("computed_at")}
