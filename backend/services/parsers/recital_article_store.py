"""
Thin persistence helpers for the recital-article map.

Keeps the computation pure (see `recital_article_linker`) and isolates all
database shape concerns here. Stored under `eu_laws.extra_metadata.recital_article_map`
so no schema migration is needed.

Usage
-----
>>> from services.parsers.recital_article_store import get_or_compute_map
>>> data = get_or_compute_map(db, celex="32016R0679")

`data` is a dict keyed by article key, each value a list of
`{recital_number, score, snippet}` dicts (the JSON form emitted by
`link_recitals_to_articles_json`).
"""

from __future__ import annotations

from typing import Any, Optional
from pathlib import Path

from sqlalchemy import text as sqla_text
from sqlalchemy.orm import Session

from .formex_parser import parse_formex_file
from .recital_article_linker import link_recitals_to_articles_json


# The key under which we persist inside eu_laws.extra_metadata.
METADATA_KEY = "recital_article_map"
VERSION_KEY = "recital_article_map_version"
CURRENT_VERSION = 1


def read_map(db: Session, celex: str) -> Optional[dict[str, Any]]:
    """Return the stored map or None if absent / stale."""
    row = db.execute(
        sqla_text(
            "SELECT extra_metadata FROM eu_laws WHERE celex = :celex LIMIT 1"
        ),
        {"celex": celex},
    ).first()
    if not row or not row[0]:
        return None
    meta = row[0]
    if meta.get(VERSION_KEY) != CURRENT_VERSION:
        return None
    return meta.get(METADATA_KEY)


def write_map(db: Session, celex: str, mapping: dict[str, Any]) -> bool:
    """
    Merge `mapping` into eu_laws.extra_metadata under METADATA_KEY and commit.
    Returns True if a row was updated.
    """
    # jsonb_set is safe for null root; we coalesce to '{}' to handle missing metadata
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
            "mapping": _to_json(mapping),
            "ver": str(CURRENT_VERSION),
        },
    )
    db.commit()
    return result.rowcount > 0


def _to_json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def compute_from_formex(xml_path: str | Path) -> dict[str, Any]:
    """Parse a local Formex XML file and return the JSON-form map."""
    parsed = parse_formex_file(xml_path)
    return link_recitals_to_articles_json(parsed, top_n=3)


def get_or_compute_map(
    db: Session,
    celex: str,
    *,
    top_n: int = 3,
    force_recompute: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Return the recital-article map for `celex`.

    1. If already stored in extra_metadata (and current version), return it.
    2. Otherwise look up `xml_path` on the eu_laws row and parse Formex.
    3. Persist the freshly computed map to extra_metadata.

    Returns None if the law is not present in eu_laws or its Formex is unreadable.
    """
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

    xml_path = row[0]
    # xml_path is stored relative to project root (see CLAUDE.md)
    project_root = Path(__file__).resolve().parents[3]
    candidate = (project_root / xml_path).resolve()
    if not candidate.is_file():
        return None

    try:
        parsed = parse_formex_file(candidate)
    except Exception:
        return None

    mapping = link_recitals_to_articles_json(parsed, top_n=top_n)
    write_map(db, celex, mapping)
    return mapping
