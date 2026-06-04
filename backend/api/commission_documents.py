"""
Commission Documents API

FastAPI endpoints for EC Register of Commission Documents.

Routes:
- GET /api/commission-documents/items - List documents with filters
- GET /api/commission-documents/items/{id} - Get single document
- GET /api/commission-documents/tracked - Get user's tracked documents
- POST /api/commission-documents/track/{id} - Track a document
- DELETE /api/commission-documents/track/{id} - Untrack a document
- POST /api/commission-documents/sync - Trigger sync (Blue tier)

Created: February 2026
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID
from datetime import datetime

from core.database import get_db
from models.user import User
from models.commission_document import (
    CommissionDocument,
    UserCommissionDocTrack,
)
from schemas.commission_document_schemas import (
    CommissionDocType,
    CommissionDocumentSummary,
    CommissionDocDetailResponse,
    CommissionDocListResponse,
    TrackCommissionDocRequest,
    TrackedCommissionDocResponse,
    TrackedCommissionDocsListResponse,
    SyncResultResponse,
)
from .auth import get_current_user
from services.tracking.pi_committee_crosswalk import dgs_for_interests
from services.tracking.tracked_files_seeder import _interest_list

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/commission-documents", tags=["Commission Documents"])


@router.get(
    "/my-dgs",
    summary="Commission departments matching my policy interests",
    description=(
        "Returns the Commission Directorate-General codes that match the signed-in "
        "user's Policy Interests, so the Commission Documents view can pre-select "
        "them. Empty list for anonymous users or users with no mappable interests."
    ),
)
async def get_my_dgs(
    current_user: Optional[User] = Depends(get_current_user),
) -> dict:
    """Resolve the user's Policy Interests to Commission DG codes."""
    if not current_user:
        return {"dgs": [], "interests": []}
    interests = _interest_list(current_user)
    return {"dgs": sorted(dgs_for_interests(interests)), "interests": interests}


# ===== List Items =====

@router.get(
    "/items",
    response_model=CommissionDocListResponse,
    summary="Get Commission documents",
    description="Get Commission documents with filtering, sorting, and pagination"
)
async def get_items(
    doc_type: Optional[CommissionDocType] = Query(None, description="Filter by document type"),
    dg: Optional[str] = Query(None, description="Filter by responsible DG"),
    search: Optional[str] = Query(None, description="Search in title or reference"),
    date_from: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    sort_by: str = Query("publication_date", description="Sort field"),
    sort_desc: bool = Query(True, description="Sort descending"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
) -> CommissionDocListResponse:
    """Get Commission documents with optional filters."""
    try:
        query = db.query(CommissionDocument)
        filters_applied = {}

        if doc_type:
            query = query.filter(CommissionDocument.doc_type == doc_type.value)
            filters_applied['doc_type'] = doc_type.value

        if dg:
            query = query.filter(CommissionDocument.dg_responsible == dg)
            filters_applied['dg'] = dg

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CommissionDocument.title.ilike(search_term),
                    CommissionDocument.reference.ilike(search_term),
                    CommissionDocument.procedure_ref.ilike(search_term)
                )
            )
            filters_applied['search'] = search

        if date_from:
            try:
                from_dt = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(CommissionDocument.publication_date >= from_dt)
                filters_applied['date_from'] = date_from
            except ValueError:
                pass

        if date_to:
            try:
                to_dt = datetime.strptime(date_to, "%Y-%m-%d")
                query = query.filter(CommissionDocument.publication_date <= to_dt)
                filters_applied['date_to'] = date_to
            except ValueError:
                pass

        # Get total count
        total = query.count()

        # Sort
        sort_column = getattr(CommissionDocument, sort_by, CommissionDocument.publication_date)
        if sort_desc:
            query = query.order_by(sort_column.desc().nullslast())
        else:
            query = query.order_by(sort_column.asc().nullsfirst())

        # Paginate
        items = query.offset(offset).limit(limit).all()

        return CommissionDocListResponse(
            items=[CommissionDocumentSummary.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters_applied if filters_applied else None
        )

    except Exception as e:
        logger.exception(f"Failed to get Commission documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")


# ===== Get Single Item =====

@router.get(
    "/items/{item_id}",
    response_model=CommissionDocDetailResponse,
    summary="Get document detail",
    description="Get full details of a specific Commission document"
)
async def get_item(
    item_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CommissionDocDetailResponse:
    """Get a single Commission document by ID."""
    try:
        item = db.query(CommissionDocument).filter(CommissionDocument.id == item_id).first()

        if not item:
            raise HTTPException(status_code=404, detail="Document not found")

        response = CommissionDocDetailResponse.model_validate(item)

        # Check if user is tracking
        if current_user:
            track = db.query(UserCommissionDocTrack).filter(
                UserCommissionDocTrack.user_id == current_user.id,
                UserCommissionDocTrack.commission_document_id == item_id
            ).first()
            if track:
                response.is_tracked = True
                response.user_notes = track.notes
                response.tracked_since = track.tracked_since

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get document {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")


# ===== Tracking =====

@router.get(
    "/tracked",
    response_model=TrackedCommissionDocsListResponse,
    summary="Get tracked documents",
    description="Get all Commission documents the current user is tracking"
)
async def get_tracked_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TrackedCommissionDocsListResponse:
    """Get user's tracked Commission documents."""
    try:
        tracks = db.query(UserCommissionDocTrack).filter(
            UserCommissionDocTrack.user_id == current_user.id
        ).all()

        items = []
        for track in tracks:
            doc = db.query(CommissionDocument).filter(
                CommissionDocument.id == track.commission_document_id
            ).first()

            if doc:
                items.append(TrackedCommissionDocResponse(
                    document=CommissionDocumentSummary.model_validate(doc),
                    tracked_since=track.tracked_since,
                    notes=track.notes,
                    notify_on_new_documents=track.notify_on_new_documents,
                ))

        return TrackedCommissionDocsListResponse(items=items, total=len(items))

    except Exception as e:
        logger.exception(f"Failed to get tracked documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked documents")


@router.post(
    "/track/{item_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Track a document",
    description="Start tracking a Commission document"
)
async def track_document(
    item_id: UUID,
    request: TrackCommissionDocRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track a Commission document."""
    try:
        item = db.query(CommissionDocument).filter(CommissionDocument.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Document not found")

        existing = db.query(UserCommissionDocTrack).filter(
            UserCommissionDocTrack.user_id == current_user.id,
            UserCommissionDocTrack.commission_document_id == item_id
        ).first()

        if existing:
            return {"message": "Already tracking this document", "id": str(item_id)}

        if request is None:
            request = TrackCommissionDocRequest()

        track = UserCommissionDocTrack(
            user_id=current_user.id,
            commission_document_id=item_id,
            notes=request.notes,
            notify_on_new_documents=request.notify_on_new_documents,
            tracked_since=datetime.now()
        )
        db.add(track)
        db.commit()

        return {
            "message": "Now tracking document",
            "id": str(item_id),
            "reference": item.reference
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to track document {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track document")


@router.delete(
    "/track/{item_id}",
    summary="Untrack a document",
    description="Stop tracking a Commission document"
)
async def untrack_document(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Untrack a Commission document."""
    try:
        track = db.query(UserCommissionDocTrack).filter(
            UserCommissionDocTrack.user_id == current_user.id,
            UserCommissionDocTrack.commission_document_id == item_id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this document")

        db.delete(track)
        db.commit()

        return {"message": "Stopped tracking document", "id": str(item_id)}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to untrack document {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to untrack document")


# ===== Sync =====

@router.post(
    "/sync",
    response_model=SyncResultResponse,
    summary="Trigger sync (Blue tier)",
    description="Manually trigger a sync of Commission documents"
)
async def trigger_sync(
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    force: bool = Query(False, description="Update existing items"),
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

        from services.scrapers.commission_doc_sync_service import CommissionDocSyncService
        import time

        start_time = time.time()
        service = CommissionDocSyncService(db=db)
        result = await service.sync_all(days=days, skip_existing=not force)
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


# ===== Enrichment =====

@router.post(
    "/enrich",
    summary="Enrich documents from RegDoc API (Blue tier)",
    description="Fill in missing titles and DG info from the live RegDoc API"
)
async def trigger_enrichment(
    limit: int = Query(50, ge=1, le=500, description="Max documents to enrich"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger enrichment of existing documents from RegDoc API."""
    try:
        if current_user.subscription_tier not in ['blue', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Blue subscription required to trigger enrichment"
            )

        from services.scrapers.commission_doc_sync_service import CommissionDocSyncService
        import time

        start_time = time.time()
        service = CommissionDocSyncService(db=db)
        result = await service.enrich_documents(limit=limit)
        duration = time.time() - start_time

        return {
            "enriched": result['enriched'],
            "skipped": result['skipped'],
            "errors": result['errors'],
            "duration_seconds": round(duration, 2)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to run enrichment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")
