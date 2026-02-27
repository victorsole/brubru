"""
EPRS Publications API

FastAPI endpoints for European Parliament Research Service publications.

EPRS data is chatbot-only -- these endpoints serve the context builder
and admin sync operations. No dedicated user-facing UI.

Routes:
- GET  /api/eprs/publications         - Search publications
- GET  /api/eprs/publications/by-procedure/{ref} - By procedure reference
- GET  /api/eprs/publications/by-celex/{celex}   - By CELEX number
- GET  /api/eprs/stats                - Database statistics
- POST /api/eprs/sync                 - Trigger sync (Blue tier)

Created: February 2026
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc
from datetime import datetime

from core.database import get_db
from models.user import User
from models.eprs_publication import EPRSPublication
from .auth import get_current_user

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eprs", tags=["EPRS Publications"])


@router.get(
    "/publications",
    summary="Search EPRS publications",
    description="Search EPRS publications by query, type, or policy area"
)
async def search_publications(
    search: Optional[str] = Query(None, description="Search in title or summary"),
    publication_type: Optional[str] = Query(None, description="Filter by type: at_a_glance, briefing, in_depth_analysis, study"),
    policy_area: Optional[str] = Query(None, description="Filter by policy area keyword"),
    procedure_ref: Optional[str] = Query(None, description="Filter by procedure reference"),
    celex: Optional[str] = Query(None, description="Filter by CELEX number"),
    has_full_text: Optional[bool] = Query(None, description="Only publications with full text extracted"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search EPRS publications with filters."""
    try:
        query = db.query(EPRSPublication)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    EPRSPublication.title.ilike(search_term),
                    EPRSPublication.summary.ilike(search_term)
                )
            )

        if publication_type:
            query = query.filter(EPRSPublication.publication_type == publication_type)

        if policy_area:
            # Use ANY for array contains
            query = query.filter(
                EPRSPublication.policy_areas.any(policy_area)
            )

        if procedure_ref:
            query = query.filter(
                EPRSPublication.related_procedures.any(procedure_ref)
            )

        if celex:
            query = query.filter(
                EPRSPublication.related_celex_numbers.any(celex)
            )

        if has_full_text is not None:
            query = query.filter(EPRSPublication.has_full_text == has_full_text)

        total = query.count()
        publications = (
            query
            .order_by(desc(EPRSPublication.publication_date))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "publications": [
                _format_publication(pub) for pub in publications
            ]
        }

    except Exception as e:
        logger.error(f"EPRS search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search EPRS publications: {str(e)}"
        )


@router.get(
    "/publications/by-procedure/{procedure_ref:path}",
    summary="Find EPRS publications for a legislative procedure",
    description="Returns EPRS briefings and analyses related to a specific procedure"
)
async def get_by_procedure(
    procedure_ref: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Find EPRS publications for a procedure reference (e.g., 2021/0106(COD))."""
    try:
        publications = (
            db.query(EPRSPublication)
            .filter(EPRSPublication.related_procedures.any(procedure_ref))
            .order_by(desc(EPRSPublication.publication_date))
            .limit(limit)
            .all()
        )

        return {
            "procedure_ref": procedure_ref,
            "total": len(publications),
            "publications": [
                _format_publication(pub) for pub in publications
            ]
        }

    except Exception as e:
        logger.error(f"EPRS by-procedure failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch EPRS publications: {str(e)}"
        )


@router.get(
    "/publications/by-celex/{celex}",
    summary="Find EPRS publications for a CELEX number",
    description="Returns EPRS briefings and analyses related to a specific EU law"
)
async def get_by_celex(
    celex: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Find EPRS publications for a CELEX number (e.g., 32024R1689)."""
    try:
        publications = (
            db.query(EPRSPublication)
            .filter(EPRSPublication.related_celex_numbers.any(celex))
            .order_by(desc(EPRSPublication.publication_date))
            .limit(limit)
            .all()
        )

        return {
            "celex": celex,
            "total": len(publications),
            "publications": [
                _format_publication(pub) for pub in publications
            ]
        }

    except Exception as e:
        logger.error(f"EPRS by-celex failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch EPRS publications: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get EPRS database statistics",
    description="Returns publication counts by type and extraction status"
)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get statistics about indexed EPRS publications."""
    try:
        total = db.query(func.count(EPRSPublication.id)).scalar() or 0
        with_text = db.query(func.count(EPRSPublication.id)).filter(
            EPRSPublication.has_full_text == True
        ).scalar() or 0

        by_type = {}
        type_counts = db.query(
            EPRSPublication.publication_type,
            func.count(EPRSPublication.id)
        ).group_by(EPRSPublication.publication_type).all()
        for pub_type, count in type_counts:
            by_type[pub_type] = count

        return {
            "total": total,
            "with_full_text": with_text,
            "without_full_text": total - with_text,
            "by_type": by_type,
        }

    except Exception as e:
        logger.error(f"EPRS stats failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get EPRS stats: {str(e)}"
        )


@router.post(
    "/sync",
    summary="Trigger EPRS sync",
    description="Sync EPRS publications from RSS feeds. Professional plan only."
)
async def trigger_sync(
    days: int = Query(14, ge=1, le=90, description="Days to look back"),
    enrich: bool = Query(False, description="Enable PDF extraction (slower)"),
    limit: int = Query(200, ge=1, le=500, description="Max publications per type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger EPRS publication sync. Blue tier only."""
    # Check tier
    if current_user.subscription_tier not in ('blue', 'admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EPRS sync requires Professional plan"
        )

    try:
        from services.scrapers.eprs_sync_service import EPRSSyncService

        sync = EPRSSyncService(
            db=db,
            enable_pdf_extraction=enrich
        )

        if enrich:
            result = await sync.sync_with_enrichment(
                days=days,
                limit=min(limit, 50),  # Limit enriched sync
                verbose=False
            )
        else:
            result = await sync.sync_all(
                days=days,
                limit=limit,
                skip_existing=True,
                verbose=False
            )

        return {
            "success": True,
            "message": "EPRS sync completed",
            **{k: v for k, v in result.items() if k != 'error_details'},
        }

    except Exception as e:
        logger.error(f"EPRS sync failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"EPRS sync failed: {str(e)}"
        )


def _format_publication(pub: EPRSPublication) -> dict:
    """Format EPRSPublication model to API response dict."""
    return {
        "id": str(pub.id),
        "publication_id": pub.publication_id,
        "title": pub.title,
        "publication_type": pub.publication_type,
        "html_url": pub.html_url,
        "pdf_url": pub.pdf_url,
        "authors": pub.authors or [],
        "publication_date": pub.publication_date.isoformat() if pub.publication_date else None,
        "summary": pub.summary,
        "word_count": pub.word_count,
        "page_count": pub.page_count,
        "policy_areas": pub.policy_areas or [],
        "committees": pub.committees or [],
        "related_celex_numbers": pub.related_celex_numbers or [],
        "related_procedures": pub.related_procedures or [],
        "categories": pub.categories or [],
        "extraction_quality": pub.extraction_quality,
        "has_full_text": pub.has_full_text,
        "first_seen": pub.first_seen.isoformat() if pub.first_seen else None,
    }
