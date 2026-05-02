"""
DCAT-AP self-catalogue endpoints.

Phase 2 of docs/applications/euvoc.md. Brubru publishes its own datasets
in DCAT-AP-compliant Turtle / RDF/XML / JSON-LD so data.europa.eu (and
any other DCAT-AP harvester) can pick them up.

Public, anonymous, no rate limit — this is a harvester surface.

    GET /api/datasets.ttl
    GET /api/datasets.rdf
    GET /api/datasets.json
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from services.vocabularies.dcat_ap_serializer import serialize, catalog_uri

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["datasets-dcat-ap"])


def _load_rows(db: Session) -> List[Dict[str, Any]]:
    rs = db.execute(
        text(
            """
            SELECT id, dcat_uri, title, description, dcat_theme, distribution,
                   license, accrual_periodicity, last_validated_at,
                   created_at, updated_at
            FROM brubru_dataset_catalog
            ORDER BY dcat_uri
            """
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "dcat_uri": r.dcat_uri,
            "title": r.title,
            "description": r.description,
            "dcat_theme": list(r.dcat_theme or []),
            "distribution": r.distribution,
            "license": r.license,
            "accrual_periodicity": r.accrual_periodicity,
            "last_validated_at": r.last_validated_at,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rs
    ]


@router.get(
    "/datasets.ttl",
    response_class=Response,
    summary="Brubru DCAT-AP self-catalogue (Turtle)",
    description=(
        "DCAT-AP-compliant description of every dataset Brubru publishes. "
        "Designed for harvest by data.europa.eu and any DCAT-AP-compatible "
        "data portal. Catalogue IRI: " + catalog_uri()
    ),
)
async def datasets_ttl(db: Session = Depends(get_db)) -> Response:
    rows = _load_rows(db)
    payload = serialize(rows, format="turtle")
    return Response(content=payload, media_type="text/turtle; charset=utf-8")


@router.get(
    "/datasets.rdf",
    response_class=Response,
    summary="Brubru DCAT-AP self-catalogue (RDF/XML)",
)
async def datasets_rdf(db: Session = Depends(get_db)) -> Response:
    rows = _load_rows(db)
    payload = serialize(rows, format="xml")
    return Response(content=payload, media_type="application/rdf+xml; charset=utf-8")


@router.get(
    "/datasets.json",
    response_class=Response,
    summary="Brubru DCAT-AP self-catalogue (JSON-LD)",
)
async def datasets_jsonld(db: Session = Depends(get_db)) -> Response:
    rows = _load_rows(db)
    payload = serialize(rows, format="json-ld")
    return Response(content=payload, media_type="application/ld+json; charset=utf-8")
