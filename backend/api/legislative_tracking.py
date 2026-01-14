"""
Legislative Tracking API Endpoints

Provides REST API for tracking EU legislation and procedures.
Part of My EU Bubble - Phase 5: Advanced Features
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from models.user import User
from .auth_optional import get_current_user_dev as get_current_user
from services.legislative_tracker import LegislativeTracker

router = APIRouter(prefix="/api/legislation", tags=["Legislative Tracking"])


# Pydantic Schemas
class TrackLegislationRequest(BaseModel):
    """Request to track legislation by CELEX."""
    celex_number: str


class TrackProcedureRequest(BaseModel):
    """Request to track OEIL procedure."""
    procedure_reference: str


class LegislationTrackingResponse(BaseModel):
    """Response with tracking information."""
    celex_number: str
    status: str
    related_amendments: List[dict]
    related_rss_entries: List[dict]
    procedure_reference: Optional[str]
    last_update: Optional[str]


class ProcedureTrackingResponse(BaseModel):
    """Response with procedure tracking information."""
    procedure_reference: str
    status: str
    current_stage: Optional[str]
    timeline: List[dict]
    related_documents: List[dict]
    next_milestone: Optional[dict]
    last_update: Optional[str]


class TrackedItemsResponse(BaseModel):
    """Response with all tracked items."""
    legislation: List[dict]
    procedures: List[dict]
    amendments: List[dict]


class StatusChangeResponse(BaseModel):
    """Response with detected status changes."""
    changes: List[dict]


class ProgressSummaryResponse(BaseModel):
    """Response with progress summary."""
    total_tracked: int
    active_procedures: int
    pending_amendments: int
    recent_updates: List[dict]
    upcoming_milestones: List[dict]
    generated_at: str


# Endpoints

@router.post("/track/celex", response_model=LegislationTrackingResponse)
async def track_legislation(
    request: TrackLegislationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track EU legislation by CELEX number.

    Returns tracking information including related amendments and RSS entries.
    """
    tracker = LegislativeTracker(db)

    try:
        tracking_info = await tracker.track_legislation_by_celex(
            request.celex_number,
            str(current_user.id)
        )

        if "error" in tracking_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=tracking_info["error"]
            )

        return tracking_info

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track legislation: {str(e)}"
        )


@router.post("/track/procedure", response_model=ProcedureTrackingResponse)
async def track_procedure(
    request: TrackProcedureRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track OEIL procedure progress.

    Returns detailed procedure information including timeline and milestones.
    """
    tracker = LegislativeTracker(db)

    try:
        tracking_info = await tracker.track_procedure(
            request.procedure_reference,
            str(current_user.id)
        )

        if "error" in tracking_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=tracking_info["error"]
            )

        return tracking_info

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track procedure: {str(e)}"
        )


@router.get("/tracked", response_model=TrackedItemsResponse)
async def get_tracked_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tracked legislation and procedures for the current user.

    Returns lists of tracked items organized by type.
    """
    tracker = LegislativeTracker(db)

    try:
        tracked_items = await tracker.get_user_tracked_items(str(current_user.id))
        return tracked_items

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tracked items: {str(e)}"
        )


@router.get("/changes", response_model=StatusChangeResponse)
async def get_status_changes(
    since_hours: int = Query(24, ge=1, le=168, description="Check changes in last N hours"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Detect status changes in tracked legislation/procedures.

    Returns list of recent changes in the specified time window.
    """
    tracker = LegislativeTracker(db)

    try:
        changes = await tracker.detect_status_changes(
            str(current_user.id),
            since_hours=since_hours
        )

        return {"changes": changes}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect status changes: {str(e)}"
        )


@router.get("/summary", response_model=ProgressSummaryResponse)
async def get_progress_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get progress summary for all tracked items.

    Returns statistics and highlights of legislative tracking activity.
    """
    tracker = LegislativeTracker(db)

    try:
        summary = await tracker.generate_progress_summary(str(current_user.id))

        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=summary["error"]
            )

        return summary

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate progress summary: {str(e)}"
        )
