"""
Committee Work API

FastAPI endpoints for EP Committee Work In Progress data.

Routes:
- GET /api/committee-work/items - List work items with filters
- GET /api/committee-work/items/{id} - Get single item
- GET /api/committee-work/committees - List all committees
- GET /api/committee-work/tracked - Get user's tracked items
- POST /api/committee-work/track/{id} - Track a work item
- DELETE /api/committee-work/track/{id} - Untrack a work item
- PATCH /api/committee-work/track/{id} - Update tracking preferences
- POST /api/committee-work/sync - Trigger sync (Blue tier only)

Created: January 2026
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from uuid import UUID
from datetime import datetime

from core.database import get_db
from models.user import User
from models.committee_work import (
    CommitteeWorkItem,
    UserCommitteeWorkTrack,
    ProcedureTypeEnum,
    CommitteeRoleEnum,
    CommitteeWorkStatusEnum,
)
from schemas.committee_work_schemas import (
    CommitteeWorkItemResponse,
    CommitteeWorkItemSummary,
    CommitteeWorkListResponse,
    CommitteeWorkDetailResponse,
    TrackWorkItemRequest,
    UpdateTrackingRequest,
    TrackedWorkItemResponse,
    TrackedWorkItemsListResponse,
    CommitteeInfo,
    CommitteesListResponse,
    SyncStatusResponse,
    SyncResultResponse,
    ProcedureType,
    CommitteeRole,
    CommitteeWorkStatus,
)
from knowledge_base.ep_committees import EP_COMMITTEES, EP_COMMITTEE_CODES
from services.tracking.pi_committee_crosswalk import committees_for_interests
from services.tracking.tracked_files_seeder import _interest_list
from .auth import get_current_user

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/committee-work", tags=["Committee Work"])


# ===== List Work Items =====

@router.get(
    "/items",
    response_model=CommitteeWorkListResponse,
    summary="Get committee work items",
    description="Get work items with filtering, sorting, and pagination"
)
def get_work_items(
    committee_code: Optional[str] = Query(None, description="Filter by committee code"),
    procedure_type: Optional[ProcedureType] = Query(None, description="Filter by procedure type"),
    status: Optional[CommitteeWorkStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title"),
    min_relevance: Optional[int] = Query(None, ge=0, le=100, description="Minimum relevance score"),
    has_rapporteur: Optional[bool] = Query(None, description="Filter by rapporteur assigned"),
    sort_by: str = Query("last_updated", description="Sort field: last_updated, relevance_score, title"),
    sort_desc: bool = Query(True, description="Sort descending"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
) -> CommitteeWorkListResponse:
    """Get committee work items with optional filters."""
    try:
        query = db.query(CommitteeWorkItem)

        # Apply filters
        filters_applied = {}

        if committee_code:
            query = query.filter(CommitteeWorkItem.committee_code == committee_code.upper())
            filters_applied['committee_code'] = committee_code.upper()

        if procedure_type:
            query = query.filter(CommitteeWorkItem.procedure_type == procedure_type.value)
            filters_applied['procedure_type'] = procedure_type.value

        if status:
            query = query.filter(CommitteeWorkItem.status == status.value)
            filters_applied['status'] = status.value

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CommitteeWorkItem.title.ilike(search_term),
                    CommitteeWorkItem.procedure_ref.ilike(search_term)
                )
            )
            filters_applied['search'] = search

        if min_relevance is not None:
            query = query.filter(CommitteeWorkItem.relevance_score >= min_relevance)
            filters_applied['min_relevance'] = min_relevance

        if has_rapporteur is not None:
            if has_rapporteur:
                query = query.filter(CommitteeWorkItem.rapporteur_name.isnot(None))
            else:
                query = query.filter(CommitteeWorkItem.rapporteur_name.is_(None))
            filters_applied['has_rapporteur'] = has_rapporteur

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        sort_column = getattr(CommitteeWorkItem, sort_by, CommitteeWorkItem.last_updated)
        if sort_desc:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        items = query.offset(offset).limit(limit).all()

        # eMeeting enrichment: attach the opinion / draft opinion this committee
        # tabled on this dossier (matched by procedure + committee). Surface-only.
        from services.linking.emeeting_links import docs_by_proc_committee
        opinions = docs_by_proc_committee(db, ("opinion", "draft_opinion"))
        summaries = []
        for item in items:
            s = CommitteeWorkItemSummary.model_validate(item)
            s.committee_documents = opinions.get((item.procedure_ref, item.committee_code), [])
            summaries.append(s)

        return CommitteeWorkListResponse(
            items=summaries,
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters_applied if filters_applied else None
        )

    except Exception as e:
        logger.exception(f"Failed to get work items: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve work items")


# ===== Get Single Item =====

@router.get(
    "/items/{item_id}",
    response_model=CommitteeWorkDetailResponse,
    summary="Get work item details",
    description="Get full details of a specific work item"
)
async def get_work_item(
    item_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CommitteeWorkDetailResponse:
    """Get a single work item by ID."""
    try:
        item = db.query(CommitteeWorkItem).filter(
            CommitteeWorkItem.id == item_id
        ).first()

        if not item:
            raise HTTPException(status_code=404, detail="Work item not found")

        response = CommitteeWorkDetailResponse.model_validate(item)

        # Check if user is tracking this item
        if current_user:
            track = db.query(UserCommitteeWorkTrack).filter(
                UserCommitteeWorkTrack.user_id == current_user.id,
                UserCommitteeWorkTrack.work_item_id == item_id
            ).first()
            if track:
                response.is_tracked = True
                response.user_notes = track.notes
                response.tracked_since = track.tracked_since

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get work item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve work item")


# ===== Get by Procedure Ref =====

@router.get(
    "/by-procedure/{procedure_ref}",
    response_model=List[CommitteeWorkItemResponse],
    summary="Get items by procedure reference",
    description="Get all work items for a procedure (may appear in multiple committees)"
)
async def get_by_procedure_ref(
    procedure_ref: str,
    db: Session = Depends(get_db)
) -> List[CommitteeWorkItemResponse]:
    """Get work items by procedure reference."""
    try:
        items = db.query(CommitteeWorkItem).filter(
            CommitteeWorkItem.procedure_ref == procedure_ref
        ).all()

        return [CommitteeWorkItemResponse.model_validate(item) for item in items]

    except Exception as e:
        logger.exception(f"Failed to get items for procedure {procedure_ref}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve work items")


# ===== Committees =====

@router.get(
    "/committees",
    response_model=CommitteesListResponse,
    summary="Get all EP committees",
    description="Get list of all 26 EP committees with metadata"
)
async def get_committees() -> CommitteesListResponse:
    """Get all EP committees."""
    committees = [
        CommitteeInfo(
            code=c.code,
            name=c.name,
            full_name=c.full_name,
            policy_area=c.policy_area
        )
        for c in EP_COMMITTEES
    ]

    return CommitteesListResponse(
        committees=committees,
        total=len(committees)
    )


# ===== Tracking =====

@router.get(
    "/tracked",
    response_model=TrackedWorkItemsListResponse,
    summary="Get user's tracked work items",
    description="Get all work items the current user is tracking"
)
def get_tracked_items(
    archived: bool = Query(False, description="False = active tracks (default); True = archived tracks"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TrackedWorkItemsListResponse:
    """Get user's tracked work items. Active by default; pass archived=true for the archived view."""
    try:
        q = db.query(UserCommitteeWorkTrack).filter(
            UserCommitteeWorkTrack.user_id == current_user.id
        )
        q = q.filter(UserCommitteeWorkTrack.archived_at.isnot(None)) if archived \
            else q.filter(UserCommitteeWorkTrack.archived_at.is_(None))
        tracks = q.all()

        items = []
        for track in tracks:
            work_item = db.query(CommitteeWorkItem).filter(
                CommitteeWorkItem.id == track.work_item_id
            ).first()

            if work_item:
                items.append(TrackedWorkItemResponse(
                    track_id=str(track.id),
                    archived_at=track.archived_at,
                    work_item=CommitteeWorkItemSummary.model_validate(work_item),
                    tracked_since=track.tracked_since,
                    notify_on_status_change=track.notify_on_status_change,
                    notify_on_rapporteur_change=track.notify_on_rapporteur_change,
                    notify_on_new_documents=track.notify_on_new_documents,
                    notes=track.notes,
                    last_notified_at=track.last_notified_at
                ))

        return TrackedWorkItemsListResponse(
            items=items,
            total=len(items)
        )

    except Exception as e:
        logger.exception(f"Failed to get tracked items: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked items")


@router.post(
    "/track/{item_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Track a work item",
    description="Start tracking a work item for updates"
)
async def track_work_item(
    item_id: UUID,
    request: TrackWorkItemRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track a work item."""
    try:
        # Check item exists
        item = db.query(CommitteeWorkItem).filter(
            CommitteeWorkItem.id == item_id
        ).first()

        if not item:
            raise HTTPException(status_code=404, detail="Work item not found")

        # Check if already tracking
        existing = db.query(UserCommitteeWorkTrack).filter(
            UserCommitteeWorkTrack.user_id == current_user.id,
            UserCommitteeWorkTrack.work_item_id == item_id
        ).first()

        if existing:
            return {"message": "Already tracking this work item", "id": str(item_id)}

        # Create tracking record
        if request is None:
            request = TrackWorkItemRequest()

        track = UserCommitteeWorkTrack(
            user_id=current_user.id,
            work_item_id=item_id,
            notify_on_status_change=request.notify_on_status_change,
            notify_on_rapporteur_change=request.notify_on_rapporteur_change,
            notify_on_new_documents=request.notify_on_new_documents,
            notes=request.notes,
            tracked_since=datetime.now()
        )
        db.add(track)
        db.commit()

        return {
            "message": "Now tracking work item",
            "id": str(item_id),
            "procedure_ref": item.procedure_ref,
            "committee_code": item.committee_code
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to track work item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track work item")


@router.delete(
    "/track/{item_id}",
    summary="Untrack a work item",
    description="Stop tracking a work item"
)
async def untrack_work_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Untrack a work item."""
    try:
        track = db.query(UserCommitteeWorkTrack).filter(
            UserCommitteeWorkTrack.user_id == current_user.id,
            UserCommitteeWorkTrack.work_item_id == item_id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this work item")

        db.delete(track)
        db.commit()

        return {"message": "Stopped tracking work item", "id": str(item_id)}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to untrack work item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to untrack work item")


@router.patch(
    "/track/{item_id}",
    summary="Update tracking preferences",
    description="Update notification preferences for a tracked item"
)
async def update_tracking(
    item_id: UUID,
    request: UpdateTrackingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update tracking preferences."""
    try:
        track = db.query(UserCommitteeWorkTrack).filter(
            UserCommitteeWorkTrack.user_id == current_user.id,
            UserCommitteeWorkTrack.work_item_id == item_id
        ).first()

        if not track:
            raise HTTPException(status_code=404, detail="Not tracking this work item")

        # Update fields that were provided
        if request.notify_on_status_change is not None:
            track.notify_on_status_change = request.notify_on_status_change
        if request.notify_on_rapporteur_change is not None:
            track.notify_on_rapporteur_change = request.notify_on_rapporteur_change
        if request.notify_on_new_documents is not None:
            track.notify_on_new_documents = request.notify_on_new_documents
        if request.notes is not None:
            track.notes = request.notes

        db.commit()

        return {"message": "Tracking preferences updated", "id": str(item_id)}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to update tracking for {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update tracking")


# ===== Sync Status =====

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
        # Get total count
        total = db.query(CommitteeWorkItem).count()

        # Get last updated item
        last_item = db.query(CommitteeWorkItem).order_by(
            CommitteeWorkItem.scraped_at.desc()
        ).first()
        last_sync = last_item.scraped_at if last_item else None

        # Get counts by committee
        committee_counts = db.query(
            CommitteeWorkItem.committee_code,
            func.count(CommitteeWorkItem.id)
        ).group_by(CommitteeWorkItem.committee_code).all()
        items_by_committee = {code: count for code, count in committee_counts}

        # Get counts by type
        type_counts = db.query(
            CommitteeWorkItem.procedure_type,
            func.count(CommitteeWorkItem.id)
        ).group_by(CommitteeWorkItem.procedure_type).all()
        # procedure_type is now a free varchar (migration 093), not an enum.
        items_by_type = {(t or 'unknown'): count for t, count in type_counts}

        return SyncStatusResponse(
            last_sync=last_sync,
            total_items=total,
            items_by_committee=items_by_committee,
            items_by_type=items_by_type
        )

    except Exception as e:
        logger.exception(f"Failed to get sync status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync status")


@router.get(
    "/my-committees",
    summary="Committees matching my policy interests",
    description=(
        "Returns the European Parliament committee codes that match the signed-in "
        "user's Policy Interests, so the In-committee view can pre-select them. "
        "Empty list for anonymous users or users with no mappable interests."
    ),
)
async def get_my_committees(
    current_user: Optional[User] = Depends(get_current_user),
) -> dict:
    """Resolve the user's Policy Interests to EP committee codes."""
    if not current_user:
        return {"committees": [], "interests": []}
    interests = _interest_list(current_user)
    committees = sorted(committees_for_interests(interests))
    return {"committees": committees, "interests": interests}


@router.post(
    "/sync",
    response_model=SyncResultResponse,
    summary="Trigger sync (Blue tier)",
    description="Manually trigger a sync of committee work data (requires Blue subscription)"
)
async def trigger_sync(
    committees: Optional[List[str]] = Query(None, description="Specific committees to sync"),
    max_pages: int = Query(5, ge=1, le=20, description="Max pages per committee"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SyncResultResponse:
    """Trigger a sync (Blue tier only)."""
    try:
        # Check Blue tier
        if current_user.subscription_tier not in ['blue', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Blue subscription required to trigger sync"
            )

        # Validate committee codes
        if committees:
            committees = [c.upper() for c in committees]
            invalid = [c for c in committees if c not in EP_COMMITTEE_CODES]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid committee codes: {', '.join(invalid)}"
                )

        # Import and run sync
        from services.scrapers.committee_work_sync_service import CommitteeWorkSyncService

        import time
        start_time = time.time()

        service = CommitteeWorkSyncService(db=db)
        result = await service.sync_all(
            max_pages_per_committee=max_pages,
            committees=committees,
            skip_existing=False
        )

        duration = time.time() - start_time

        return SyncResultResponse(
            added=result['added'],
            updated=result['updated'],
            skipped=result['skipped'],
            errors=result['errors'],
            status_changes=result.get('status_changes', 0),
            duration_seconds=duration
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to run sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
