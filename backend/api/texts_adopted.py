"""
Texts Adopted API

FastAPI endpoints for EP Texts Adopted data.

Routes:
- GET /api/texts-adopted/items - List texts with filters
- GET /api/texts-adopted/items/{id} - Get single text
- GET /api/texts-adopted/by-reference/{ta_ref} - Get by TA reference
- GET /api/texts-adopted/tracked - Get user's tracked texts
- POST /api/texts-adopted/track/{id} - Track a text
- DELETE /api/texts-adopted/track/{id} - Untrack a text
- GET /api/texts-adopted/terms - List available terms
- GET /api/texts-adopted/sync/status - Get sync status
- POST /api/texts-adopted/sync - Trigger sync (Blue tier)

Created: February 2026
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from datetime import datetime

from core.database import get_db
from models.user import User
from models.text_adopted import (
    TextAdopted,
    UserTextAdoptedTrack,
    TextTypeEnum,
)
from schemas.texts_adopted_schemas import (
    TextType,
    TextAdoptedSummary,
    TextAdoptedDetailResponse,
    TextAdoptedListResponse,
    TrackTextRequest,
    TrackedTextAdoptedResponse,
    TrackedTextsListResponse,
    ParliamentaryTermInfo,
    TermsListResponse,
    SyncStatusResponse,
    SyncResultResponse,
)
from schemas.scrapers.texts_adopted_schemas import PARLIAMENTARY_TERMS
from .auth import get_current_user

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/texts-adopted", tags=["Texts Adopted"])


# ===== List Items =====

@router.get(
    "/items",
    response_model=TextAdoptedListResponse,
    summary="Get adopted texts",
    description="Get adopted texts with filtering, sorting, and pagination"
)
def get_items(
    text_type: Optional[TextType] = Query(None, description="Filter by text type"),
    parliamentary_term: Optional[int] = Query(None, ge=4, le=10, description="Filter by term"),
    procedure_ref: Optional[str] = Query(None, description="Filter by procedure reference"),
    search: Optional[str] = Query(None, description="Search in title"),
    date_from: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    sort_by: str = Query("adoption_date", description="Sort field: adoption_date, title, ta_reference"),
    sort_desc: bool = Query(True, description="Sort descending"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
) -> TextAdoptedListResponse:
    """Get adopted texts with optional filters."""
    try:
        query = db.query(TextAdopted)
        filters_applied = {}

        if text_type:
            query = query.filter(TextAdopted.text_type == text_type.value)
            filters_applied['text_type'] = text_type.value

        if parliamentary_term:
            query = query.filter(TextAdopted.parliamentary_term == parliamentary_term)
            filters_applied['parliamentary_term'] = parliamentary_term

        if procedure_ref:
            query = query.filter(TextAdopted.procedure_ref == procedure_ref)
            filters_applied['procedure_ref'] = procedure_ref

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    TextAdopted.title.ilike(search_term),
                    TextAdopted.ta_reference.ilike(search_term),
                    TextAdopted.procedure_ref.ilike(search_term)
                )
            )
            filters_applied['search'] = search

        if date_from:
            try:
                from_dt = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(TextAdopted.adoption_date >= from_dt)
                filters_applied['date_from'] = date_from
            except ValueError:
                pass

        if date_to:
            try:
                to_dt = datetime.strptime(date_to, "%Y-%m-%d")
                query = query.filter(TextAdopted.adoption_date <= to_dt)
                filters_applied['date_to'] = date_to
            except ValueError:
                pass

        # Get total count
        total = query.count()

        # Sort — push NULLs to the end so meaningful rows (with adoption_date,
        # title, etc.) lead. Otherwise 18 NULL-adoption_date "Amendments" rows
        # crowd the top of the default list.
        sort_column = getattr(TextAdopted, sort_by, TextAdopted.adoption_date)
        if sort_desc:
            query = query.order_by(sort_column.desc().nullslast())
        else:
            query = query.order_by(sort_column.asc().nullslast())

        # Paginate
        items = query.offset(offset).limit(limit).all()

        # Corpus bounds, computed from the data (D2). A zero result must be
        # readable as "outside what we hold" rather than as "no such text".
        cov = db.query(func.min(TextAdopted.adoption_date),
                       func.max(TextAdopted.adoption_date)).one()

        return TextAdoptedListResponse(
            items=[TextAdoptedSummary.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters_applied if filters_applied else None,
            coverage_from=(cov[0].date() if cov and cov[0] else None),
            coverage_to=(cov[1].date() if cov and cov[1] else None),
            coverage_note=(
                "Earliest and latest adopted text HELD, not the bounds of the "
                "parliamentary term. A query with no results before coverage_from "
                "means the corpus does not reach that far back."
            ),
        )

    except Exception as e:
        logger.exception(f"Failed to get texts adopted: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve texts")


# ===== Get Single Item =====

@router.get(
    "/items/{item_id}",
    response_model=TextAdoptedDetailResponse,
    summary="Get text detail",
    description="Get full details of a specific adopted text"
)
async def get_item(
    item_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TextAdoptedDetailResponse:
    """Get a single adopted text by ID."""
    try:
        item = db.query(TextAdopted).filter(TextAdopted.id == item_id).first()

        if not item:
            raise HTTPException(status_code=404, detail="Text not found")

        response = TextAdoptedDetailResponse.model_validate(item)

        # Check if user is tracking
        if current_user:
            track = db.query(UserTextAdoptedTrack).filter(
                UserTextAdoptedTrack.user_id == current_user.id,
                UserTextAdoptedTrack.text_adopted_id == item_id
            ).first()
            if track:
                response.is_tracked = True
                response.user_notes = track.notes
                response.tracked_since = track.tracked_since

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get text {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve text")


# ===== Get by TA Reference =====

@router.get(
    "/by-reference/{ta_ref:path}",
    response_model=TextAdoptedDetailResponse,
    summary="Get by TA reference",
    description="Get an adopted text by its TA reference"
)
async def get_by_reference(
    ta_ref: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TextAdoptedDetailResponse:
    """Get an adopted text by TA reference."""
    try:
        item = db.query(TextAdopted).filter(
            TextAdopted.ta_reference == ta_ref
        ).first()

        if not item:
            raise HTTPException(status_code=404, detail="Text not found")

        response = TextAdoptedDetailResponse.model_validate(item)

        if current_user:
            track = db.query(UserTextAdoptedTrack).filter(
                UserTextAdoptedTrack.user_id == current_user.id,
                UserTextAdoptedTrack.text_adopted_id == item.id
            ).first()
            if track:
                response.is_tracked = True
                response.user_notes = track.notes
                response.tracked_since = track.tracked_since

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get text by ref {ta_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve text")


# ===== Tracking =====

@router.get(
    "/tracked",
    response_model=TrackedTextsListResponse,
    summary="Get tracked texts",
    description="Get all texts the current user is tracking"
)
def get_tracked_texts(
    archived: bool = Query(False, description="False = active tracks (default); True = archived tracks"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TrackedTextsListResponse:
    """Get user's tracked texts. Active by default; pass archived=true for the archived view."""
    try:
        q = db.query(UserTextAdoptedTrack).filter(
            UserTextAdoptedTrack.user_id == current_user.id
        )
        q = q.filter(UserTextAdoptedTrack.archived_at.isnot(None)) if archived \
            else q.filter(UserTextAdoptedTrack.archived_at.is_(None))
        tracks = q.all()

        items = []
        for track in tracks:
            text_item = db.query(TextAdopted).filter(
                TextAdopted.id == track.text_adopted_id
            ).first()

            if text_item:
                items.append(TrackedTextAdoptedResponse(
                    track_id=str(track.id),
                    archived_at=track.archived_at,
                    text=TextAdoptedSummary.model_validate(text_item),
                    tracked_since=track.tracked_since,
                    notes=track.notes,
                ))

        return TrackedTextsListResponse(items=items, total=len(items))

    except Exception as e:
        logger.exception(f"Failed to get tracked texts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked texts")


@router.post(
    "/track/{item_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Track a text",
    description="Start tracking an adopted text"
)
async def track_text(
    item_id: UUID,
    request: TrackTextRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track an adopted text."""
    try:
        item = db.query(TextAdopted).filter(TextAdopted.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Text not found")

        existing = db.query(UserTextAdoptedTrack).filter(
            UserTextAdoptedTrack.user_id == current_user.id,
            UserTextAdoptedTrack.text_adopted_id == item_id
        ).first()

        if existing:
            return {"message": "Already tracking this text", "id": str(item_id)}

        if request is None:
            request = TrackTextRequest()

        track = UserTextAdoptedTrack(
            user_id=current_user.id,
            text_adopted_id=item_id,
            notes=request.notes,
            tracked_since=datetime.now()
        )
        db.add(track)
        db.commit()

        return {
            "message": "Now tracking text",
            "id": str(item_id),
            "ta_reference": item.ta_reference
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to track text {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track text")


@router.delete(
    "/track/{item_id}",
    summary="Untrack a text",
    description="Stop tracking an adopted text"
)
async def untrack_text(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Untrack an adopted text."""
    try:
        track = db.query(UserTextAdoptedTrack).filter(
            UserTextAdoptedTrack.user_id == current_user.id,
            UserTextAdoptedTrack.text_adopted_id == item_id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this text")

        db.delete(track)
        db.commit()

        return {"message": "Stopped tracking text", "id": str(item_id)}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to untrack text {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to untrack text")


# ===== Terms =====

@router.get(
    "/terms",
    response_model=TermsListResponse,
    summary="Get parliamentary terms",
    description="Get available parliamentary terms with text counts"
)
async def get_terms(
    db: Session = Depends(get_db)
) -> TermsListResponse:
    """Get available parliamentary terms."""
    try:
        # Get counts by term
        term_counts = db.query(
            TextAdopted.parliamentary_term,
            func.count(TextAdopted.id)
        ).group_by(TextAdopted.parliamentary_term).all()
        counts_map = {term: count for term, count in term_counts}

        terms = []
        for term_num, info in sorted(PARLIAMENTARY_TERMS.items(), reverse=True):
            terms.append(ParliamentaryTermInfo(
                term=term_num,
                years=info["years"],
                prefix=info["prefix"],
                text_count=counts_map.get(term_num, 0)
            ))

        return TermsListResponse(terms=terms)

    except Exception as e:
        logger.exception(f"Failed to get terms: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve terms")


# ===== Sync =====

@router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    summary="Get sync status",
    description="Get information about last sync and data statistics"
)
async def get_sync_status(
    db: Session = Depends(get_db)
) -> SyncStatusResponse:
    """Get sync status and statistics."""
    try:
        total = db.query(TextAdopted).count()

        last_item = db.query(TextAdopted).order_by(
            TextAdopted.scraped_at.desc()
        ).first()
        last_sync = last_item.scraped_at if last_item else None

        term_counts = db.query(
            TextAdopted.parliamentary_term,
            func.count(TextAdopted.id)
        ).group_by(TextAdopted.parliamentary_term).all()
        items_by_term = {term: count for term, count in term_counts}

        type_counts = db.query(
            TextAdopted.text_type,
            func.count(TextAdopted.id)
        ).group_by(TextAdopted.text_type).all()
        items_by_type = {str(t.value) if t else 'unknown': count for t, count in type_counts}

        return SyncStatusResponse(
            last_sync=last_sync,
            total_items=total,
            items_by_term=items_by_term,
            items_by_type=items_by_type
        )

    except Exception as e:
        logger.exception(f"Failed to get sync status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync status")


@router.post(
    "/sync",
    response_model=SyncResultResponse,
    summary="Trigger sync (Blue tier)",
    description="Manually trigger a sync of texts adopted data"
)
async def trigger_sync(
    mode: str = Query("rss", description="Sync mode: rss, term"),
    term: Optional[int] = Query(None, ge=4, le=10, description="Term number (for term mode)"),
    max_dates: Optional[int] = Query(None, ge=1, le=500, description="Max dates to scrape"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SyncResultResponse:
    """Trigger a sync (Blue tier only)."""
    try:
        if current_user.subscription_tier not in ['blue', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Blue subscription required to trigger sync"
            )

        from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService
        import time

        start_time = time.time()
        service = TextsAdoptedSyncService(db=db)

        if mode == "rss":
            result = await service.sync_rss(skip_existing=False)
        elif mode == "term":
            if term is None:
                raise HTTPException(status_code=400, detail="Term number required for term mode")
            result = await service.sync_term(
                term=term,
                max_dates=max_dates,
                skip_existing=False
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

        duration = time.time() - start_time

        return SyncResultResponse(
            added=result['added'],
            updated=result['updated'],
            skipped=result['skipped'],
            errors=result['errors'],
            duration_seconds=duration
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to run sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
