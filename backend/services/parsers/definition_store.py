"""
Persistence helpers for the defined-terms map (Option B of the LegalViz pattern).

Stored under `eu_laws.extra_metadata.defined_terms` — no schema migration.

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
