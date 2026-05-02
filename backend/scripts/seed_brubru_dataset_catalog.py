#!/usr/bin/env python3
"""
Phase 2 of docs/applications/euvoc.md — seed `brubru_dataset_catalog` with
Brubru's published datasets so the DCAT-AP feed can render them.

Idempotent (UPSERT on dcat_uri). Safe to re-run after schema or content
changes.

Run:
    python3.12 backend/scripts/seed_brubru_dataset_catalog.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed-catalog")

BRUBRU_BASE = "https://brubru.beresol.eu"

# ----------------------------------------------------------------------
# EuroVoc themes used as dcat:theme tags. Real concept IRIs from the live
# EuroVoc 4.23 graph (verified 2026-05-02).
# ----------------------------------------------------------------------
EUROVOC_THEMES = {
    "law":              "http://eurovoc.europa.eu/2462",
    "european_union":   "http://eurovoc.europa.eu/911",
    "regulation":       "http://eurovoc.europa.eu/1646",
    "data_protection":  "http://eurovoc.europa.eu/3028",
    "ai":               "http://eurovoc.europa.eu/8500",
    "translation":      "http://eurovoc.europa.eu/3911",
    "open_data":        "http://eurovoc.europa.eu/c_82c4f1a7",
    "official_journal": "http://eurovoc.europa.eu/233",
}

# CC-BY-4.0 — Brubru's default reuse policy (mirrors the EU PSI reuse policy).
LICENSE_CC_BY_4 = "http://creativecommons.org/licenses/by/4.0/"


def _datasets_to_seed() -> List[Dict[str, Any]]:
    """Hand-curated catalogue rows for Phase 2 seed.

    Every entry maps a real Brubru-owned dataset to a DCAT-AP description.
    """
    return [
        {
            "dcat_uri": f"{BRUBRU_BASE}/datasets/catalan-eu-laws",
            "title": "Catalan translations of EU legislation",
            "description": {
                "en": (
                    "EU legislation translated into Catalan from the Publications "
                    "Office Formex V4 corpus. Updated daily via the /catalan "
                    "skill. Covers in-force regulations, directives, and "
                    "decisions; rendered as plain HTML for human reading."
                ),
                "ca": (
                    "Traducció catalana de la legislació de la UE a partir del "
                    "corpus Formex V4 de l'Oficina de Publicacions. "
                    "Actualitzada cada dia. Inclou reglaments, directives i "
                    "decisions vigents en HTML."
                ),
                "es": (
                    "Traducción al catalán de la legislación de la UE a partir "
                    "del corpus Formex V4 de la Oficina de Publicaciones. "
                    "Actualizada diariamente."
                ),
            },
            "dcat_theme": [
                EUROVOC_THEMES["law"],
                EUROVOC_THEMES["european_union"],
                EUROVOC_THEMES["translation"],
            ],
            "distribution": [
                {
                    "title": "HTML rendering (per-act pages)",
                    "access_url": "https://brubru.beresol.eu/legislacio-ue-catala/",
                    "media_type": "text/html",
                    "format": "HTML",
                },
            ],
            "license": LICENSE_CC_BY_4,
            "accrual_periodicity": "P1D",
        },
        {
            "dcat_uri": f"{BRUBRU_BASE}/datasets/chat-knowledge-guides",
            "title": "Brubru chat knowledge guides",
            "description": {
                "en": (
                    "Curated knowledge guides used by the Brubru chat retrieval "
                    "pipeline. Each guide explains an EU policy file, "
                    "regulation, or institutional process in plain language "
                    "with verified primary-source citations."
                ),
                "ca": (
                    "Guies de coneixement curades que alimenten el chatbot de "
                    "Brubru. Cada guia explica un fitxer normatiu de la UE "
                    "amb citacions verificades."
                ),
            },
            "dcat_theme": [
                EUROVOC_THEMES["law"],
                EUROVOC_THEMES["european_union"],
            ],
            "distribution": [
                {
                    "title": "Public knowledge-guides index (HTML)",
                    "access_url": "https://brubru.beresol.eu/guides/",
                    "media_type": "text/html",
                    "format": "HTML",
                },
                {
                    "title": "v1 API: list knowledge guides",
                    "access_url": "https://brubru.beresol.eu/api/v1/knowledge-guides",
                    "media_type": "application/json",
                    "format": "JSON",
                },
            ],
            "license": LICENSE_CC_BY_4,
            "accrual_periodicity": "P1D",
        },
        {
            "dcat_uri": f"{BRUBRU_BASE}/datasets/eu-laws-tsvector",
            "title": "EU legislation TSVECTOR corpus (eu_laws)",
            "description": {
                "en": (
                    "8,710 distinct adopted EU laws (28,513 OJ publications, "
                    "61,219 translatable XML files). Sourced from LEG_2025-11 "
                    "Publications Office bulk export and the Cellar SPARQL "
                    "delta sync. Indexed via PostgreSQL TSVECTOR for full-text "
                    "search."
                ),
                "ca": (
                    "Corpus TSVECTOR de 8.710 lleis adoptades de la UE — "
                    "exportació massiva LEG_2025-11 + delta SPARQL Cellar — "
                    "indexat per cerca de text complet."
                ),
            },
            "dcat_theme": [
                EUROVOC_THEMES["law"],
                EUROVOC_THEMES["regulation"],
                EUROVOC_THEMES["official_journal"],
            ],
            "distribution": [
                {
                    "title": "v1 API: list / search EU laws",
                    "access_url": "https://brubru.beresol.eu/api/v1/laws",
                    "media_type": "application/json",
                    "format": "JSON",
                },
            ],
            "license": LICENSE_CC_BY_4,
            "accrual_periodicity": "P1D",
        },
        {
            "dcat_uri": f"{BRUBRU_BASE}/datasets/v1-rest-api",
            "title": "Brubru v1 REST API",
            "description": {
                "en": (
                    "Public paid REST surface at /api/v1/*. 120+ endpoints "
                    "covering EU laws, procedures, MEPs, calendar, "
                    "consultations, predictions, and authority-table "
                    "vocabularies. Rate-limited at 60 req/min per API key."
                ),
                "ca": (
                    "API REST pública de Brubru a /api/v1/*. Més de 120 "
                    "punts d'accés sobre legislació UE, procediments, "
                    "diputats, calendari, consultes, prediccions i "
                    "vocabularis. Limitació de 60 sol·licituds/min per clau API."
                ),
            },
            "dcat_theme": [
                EUROVOC_THEMES["open_data"],
                EUROVOC_THEMES["european_union"],
            ],
            "distribution": [
                {
                    "title": "v1 API root",
                    "access_url": "https://brubru.beresol.eu/api/v1/",
                    "media_type": "application/json",
                    "format": "JSON",
                },
                {
                    "title": "OpenAPI documentation",
                    "access_url": "https://brubru.beresol.eu/api/docs",
                    "media_type": "text/html",
                    "format": "HTML",
                },
            ],
            "license": LICENSE_CC_BY_4,
            "accrual_periodicity": "P1D",
        },
        {
            "dcat_uri": f"{BRUBRU_BASE}/datasets/eu-vocabularies",
            "title": "EU authority labels (Brubru cache)",
            "description": {
                "en": (
                    "Local cache of skos:prefLabel + skos:altLabel rows from "
                    "the EU Publications Office authority tables. 18,000+ rows "
                    "across 12 hot NALs (corporate-body, dir-eu-legal-act, "
                    "procedure, notice-type, etc.) in 6 Brubru languages. "
                    "Refreshed nightly from the Cellar SPARQL endpoint."
                ),
                "ca": (
                    "Memòria cau local de skos:prefLabel + skos:altLabel des "
                    "de les taules d'autoritat de l'Oficina de Publicacions UE."
                ),
            },
            "dcat_theme": [
                EUROVOC_THEMES["open_data"],
                EUROVOC_THEMES["european_union"],
            ],
            "distribution": [
                {
                    "title": "v1 API: corporate bodies",
                    "access_url": "https://brubru.beresol.eu/api/v1/vocabularies/corporate-bodies",
                    "media_type": "application/json",
                    "format": "JSON",
                },
                {
                    "title": "v1 API: procedures",
                    "access_url": "https://brubru.beresol.eu/api/v1/vocabularies/procedures",
                    "media_type": "application/json",
                    "format": "JSON",
                },
                {
                    "title": "v1 API: directories",
                    "access_url": "https://brubru.beresol.eu/api/v1/vocabularies/directories",
                    "media_type": "application/json",
                    "format": "JSON",
                },
                {
                    "title": "v1 API: modification types",
                    "access_url": "https://brubru.beresol.eu/api/v1/vocabularies/modification-types",
                    "media_type": "application/json",
                    "format": "JSON",
                },
            ],
            "license": LICENSE_CC_BY_4,
            "accrual_periodicity": "P1D",
        },
        {
            "dcat_uri": f"{BRUBRU_BASE}/datasets/europa-source-registry",
            "title": "europa.eu source registry",
            "description": {
                "en": (
                    "Curated registry of 519 europa.eu sub-portals and feeds "
                    "Brubru tracks for legislative and policy news. Each entry "
                    "carries the source URL, ingestion method (API / RSS / "
                    "HTML / Tavily), and current status."
                ),
            },
            "dcat_theme": [
                EUROVOC_THEMES["european_union"],
                EUROVOC_THEMES["open_data"],
            ],
            "distribution": [
                {
                    "title": "Source registry markdown",
                    "access_url": "https://github.com/Beresol-BV/brubru/tree/main/data/europa_eu",
                    "media_type": "text/markdown",
                    "format": "Markdown",
                },
            ],
            "license": LICENSE_CC_BY_4,
            "accrual_periodicity": "P1W",
        },
    ]


def upsert_row(db, row: Dict[str, Any]) -> None:
    db.execute(
        text(
            """
            INSERT INTO brubru_dataset_catalog
                (dcat_uri, title, description, dcat_theme, distribution,
                 license, accrual_periodicity, last_validated_at)
            VALUES
                (:dcat_uri, :title, CAST(:description AS JSONB),
                 :dcat_theme, CAST(:distribution AS JSONB),
                 :license, :accrual, :validated_at)
            ON CONFLICT (dcat_uri) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                dcat_theme = EXCLUDED.dcat_theme,
                distribution = EXCLUDED.distribution,
                license = EXCLUDED.license,
                accrual_periodicity = EXCLUDED.accrual_periodicity,
                last_validated_at = EXCLUDED.last_validated_at,
                updated_at = NOW()
            """
        ),
        {
            "dcat_uri": row["dcat_uri"],
            "title": row["title"],
            "description": json.dumps(row.get("description") or {}),
            "dcat_theme": row.get("dcat_theme") or [],
            "distribution": json.dumps(row.get("distribution") or []),
            "license": row.get("license"),
            "accrual": row.get("accrual_periodicity"),
            "validated_at": datetime.now(timezone.utc),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = _datasets_to_seed()
    log.info(f"Seeding {len(rows)} catalogue rows (dry_run={args.dry_run})")
    for row in rows:
        log.info(f"  {row['dcat_uri']}")

    if args.dry_run:
        log.info("--dry-run: no DB writes")
        return 0

    db = SessionLocal()
    try:
        for row in rows:
            upsert_row(db, row)
        db.commit()
        result = db.execute(text("SELECT COUNT(*) AS n FROM brubru_dataset_catalog")).first()
        log.info(f"DONE — brubru_dataset_catalog now has {result.n} rows")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
