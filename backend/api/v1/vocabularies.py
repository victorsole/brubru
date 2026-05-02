"""
/api/v1/vocabularies/* — public surface over the local NAL cache.

Phase 1 of docs/applications/euvoc.md. Exposes 4 of the 12 hot NALs as
paginated, language-aware lookups. Reads from `eu_authority_labels` (filled
nightly by scripts/sync_eu_authority_labels.py).

Endpoints:
    GET /api/v1/vocabularies/corporate-bodies
    GET /api/v1/vocabularies/procedures
    GET /api/v1/vocabularies/directories
    GET /api/v1/vocabularies/modification-types
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vocabularies", tags=["v1-vocabularies"])

# Map endpoint slug -> source dataset URI in the cache.
_DATASET_URIS = {
    "corporate-bodies": "http://publications.europa.eu/resource/dataset/corporate-body",
    "procedures": "http://publications.europa.eu/resource/dataset/procedure",
    "directories": "http://publications.europa.eu/resource/dataset/dir-eu-legal-act",
    "modification-types": "http://publications.europa.eu/resource/dataset/modification-type",
}

_BRUBRU_LANGS = {"en", "fr", "es", "ca", "it", "nl"}


class VocabularyConcept(BaseModel):
    uri: str
    pref_label: str
    alt_labels: list[str] = Field(default_factory=list)
    lang: str
    source_dataset_uri: str


def _list_concepts(
    db: Session,
    dataset_uri: str,
    *,
    lang: str,
    q: Optional[str],
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Return (rows, total) for the requested NAL slice."""
    where = "source_dataset_uri = :ds AND lang = :lang"
    params = {"ds": dataset_uri, "lang": lang}
    if q:
        # Match pref_label substring OR alt_labels exact (acronym-friendly).
        where += " AND (LOWER(pref_label) LIKE :ql OR :q = ANY(alt_labels))"
        params["q"] = q
        params["ql"] = f"%{q.lower()}%"

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM eu_authority_labels WHERE {where}"),
        params,
    ).first()
    total = int(total_row.n) if total_row else 0

    rows = db.execute(
        text(
            f"""
            SELECT uri, pref_label, alt_labels, lang, source_dataset_uri
            FROM eu_authority_labels
            WHERE {where}
            ORDER BY pref_label
            LIMIT :lim OFFSET :off
            """
        ),
        {**params, "lim": limit, "off": offset},
    ).all()

    return [
        {
            "uri": r.uri,
            "pref_label": r.pref_label,
            "alt_labels": list(r.alt_labels or []),
            "lang": r.lang,
            "source_dataset_uri": r.source_dataset_uri,
        }
        for r in rows
    ], total


def _build_endpoint(slug: str, summary: str, description: str):
    dataset_uri = _DATASET_URIS[slug]

    @router.get(
        f"/{slug}",
        response_model=PaginatedResponse[VocabularyConcept],
        summary=summary,
        description=description,
    )
    async def _handler(
        request: Request,
        q: Optional[str] = Query(None, description="Search term (matches pref_label substring + alt_labels)"),
        lang: str = Query("en", description="Brubru language code (en|fr|es|ca|it|nl)"),
        limit: int = Query(50, ge=1, le=200),
        page: int = Query(1, ge=1),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> PaginatedResponse[VocabularyConcept]:
        lang = lang.lower()
        if lang not in _BRUBRU_LANGS:
            lang = "en"
        offset = (page - 1) * limit
        rows, total = _list_concepts(db, dataset_uri, lang=lang, q=q, limit=limit, offset=offset)
        items = [VocabularyConcept(**r) for r in rows]
        return build_envelope(items=items, total=total, page=page, limit=limit, coverage_complete=True)

    _handler.__name__ = f"list_{slug.replace('-', '_')}"
    return _handler


# Register the 4 endpoints.
list_corporate_bodies = _build_endpoint(
    "corporate-bodies",
    "EU corporate bodies (institutions, agencies, DGs)",
    "Lookups for the corporate-body authority list. ~1,958 concepts. "
    "Covers EP, Council, Commission, agencies, DGs, joint undertakings.",
)
list_procedures = _build_endpoint(
    "procedures",
    "Inter-institutional procedure types",
    "COD / CNS / APP / CONS and other OEIL-tagged procedure types. ~17 concepts.",
)
list_directories = _build_endpoint(
    "directories",
    "Directory of EU legal acts",
    "Subject classification of EU legislation. ~475 concepts.",
)
list_modification_types = _build_endpoint(
    "modification-types",
    "Legal-act modification types",
    "Labels for amends/repeals/corrects/consolidates relationships. ~6 concepts.",
)
