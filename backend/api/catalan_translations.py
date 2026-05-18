"""
Catalan Translations API

Public endpoints for the Catalan EU legislation translation catalogue.
No authentication required -- this is a public resource.

Routes:
- GET  /api/catalan-translations              - List/search translations (paginated)
- GET  /api/catalan-translations/categories    - Category summary with counts
- GET  /api/catalan-translations/stats         - Overall statistics
- GET  /api/catalan-translations/{celex}       - Single translation metadata

Created: March 2026
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from core.database import get_db
from models.catalan_translation import CatalanTranslation

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalan-translations", tags=["Catalan Translations"])


@router.get(
    "",
    summary="List Catalan translations",
    description="Search and paginate the catalogue of translated EU legislation in Catalan"
)
async def list_translations(
    search: Optional[str] = Query(None, description="Search in titles and CELEX"),
    category: Optional[str] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """List translations with optional search, category, and subcategory filter."""
    query = db.query(CatalanTranslation)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                CatalanTranslation.title_ca.ilike(term),
                CatalanTranslation.title_en.ilike(term),
                CatalanTranslation.short_name.ilike(term),
                CatalanTranslation.celex.ilike(term),
            )
        )

    if category:
        query = query.filter(CatalanTranslation.category == category)

    if subcategory:
        query = query.filter(CatalanTranslation.subcategory == subcategory)

    if doc_type:
        query = query.filter(CatalanTranslation.doc_type == doc_type)

    total = query.count()
    items = (
        query
        .order_by(CatalanTranslation.articles_count.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        'total': total,
        'offset': offset,
        'limit': limit,
        'items': [t.to_catalogue_dict() for t in items],
    }


@router.get(
    "/categories",
    summary="Category summary",
    description="Returns each category with its translation count"
)
async def get_categories(db: Session = Depends(get_db)):
    """Get categories with counts for the landing page."""
    rows = (
        db.query(
            CatalanTranslation.category,
            func.count(CatalanTranslation.id).label('count'),
            func.sum(CatalanTranslation.articles_count).label('total_articles'),
        )
        .group_by(CatalanTranslation.category)
        .order_by(func.count(CatalanTranslation.id).desc())
        .all()
    )

    return {
        'categories': [
            {
                'category': row.category,
                'count': row.count,
                'total_articles': row.total_articles or 0,
            }
            for row in rows
        ]
    }


@router.get(
    "/subcategories",
    summary="Subcategory summary",
    description="Returns each subcategory with its translation count, optionally filtered by category"
)
async def get_subcategories(
    category: Optional[str] = Query(None, description="Filter subcategories by parent category"),
    db: Session = Depends(get_db),
):
    """Get subcategories with counts."""
    query = db.query(
        CatalanTranslation.subcategory,
        CatalanTranslation.category,
        func.count(CatalanTranslation.id).label('count'),
    ).filter(CatalanTranslation.subcategory.isnot(None))

    if category:
        query = query.filter(CatalanTranslation.category == category)

    rows = (
        query
        .group_by(CatalanTranslation.subcategory, CatalanTranslation.category)
        .order_by(func.count(CatalanTranslation.id).desc())
        .all()
    )

    return {
        'subcategories': [
            {'subcategory': row.subcategory, 'category': row.category, 'count': row.count}
            for row in rows
        ]
    }


@router.get(
    "/stats",
    summary="Translation statistics",
    description="Overall statistics for the Catalan translation project"
)
async def get_stats(db: Session = Depends(get_db)):
    """Get overall translation statistics."""
    total = db.query(func.count(CatalanTranslation.id)).scalar() or 0
    total_main = (
        db.query(func.count(CatalanTranslation.id))
        .filter(CatalanTranslation.file_type == 'main')
        .scalar()
        or 0
    )
    total_annex = (
        db.query(func.count(CatalanTranslation.id))
        .filter(CatalanTranslation.file_type == 'annex')
        .scalar()
        or 0
    )
    total_articles = db.query(func.sum(CatalanTranslation.articles_count)).scalar() or 0
    total_recitals = db.query(func.sum(CatalanTranslation.recitals_count)).scalar() or 0
    total_size = db.query(func.sum(CatalanTranslation.html_size_bytes)).scalar() or 0
    categories = db.query(func.count(func.distinct(CatalanTranslation.category))).scalar() or 0

    return {
        'total_translations': total,
        'total_main': total_main,
        'total_annex': total_annex,
        'total_articles': total_articles,
        'total_recitals': total_recitals,
        'total_size_mb': round(total_size / (1024 * 1024), 1),
        'categories': categories,
        'target': 28513,
    }


@router.get(
    "/{celex}",
    summary="Get translation metadata",
    description="Returns metadata for a single translated act by CELEX number"
)
async def get_translation(celex: str, db: Session = Depends(get_db)):
    """Get a single translation by CELEX."""
    translation = (
        db.query(CatalanTranslation)
        .filter(CatalanTranslation.celex == celex)
        .first()
    )
    if not translation:
        raise HTTPException(status_code=404, detail=f"Translation {celex} not found")

    return translation.to_dict()
