"""
User Preferences API Endpoints

Handles user preferences including tour progress, UI settings, etc.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from models.user import User
from .auth import get_current_user

router = APIRouter(prefix="/api/user", tags=["user-preferences"])


# Request/Response Models

class TourProgressUpdate(BaseModel):
    """Request to update tour progress"""
    completed_tours: Optional[List[str]] = None
    skipped_tours: Optional[List[str]] = None


class TourProgressResponse(BaseModel):
    """Response with tour progress"""
    completed_tours: List[str]
    skipped_tours: List[str]


class PreferencesUpdate(BaseModel):
    """Request to update user preferences"""
    preferences: Dict[str, Any]


class PreferencesResponse(BaseModel):
    """Response with user preferences"""
    preferences: Dict[str, Any]


# Endpoints

@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all user preferences"""
    return PreferencesResponse(
        preferences=current_user.preferences or {}
    )


@router.patch("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    update: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user preferences (merge with existing)"""
    current_prefs = current_user.preferences or {}
    merged_prefs = {**current_prefs, **update.preferences}

    current_user.preferences = merged_prefs
    db.commit()
    db.refresh(current_user)

    return PreferencesResponse(preferences=current_user.preferences or {})


@router.get("/tour-progress", response_model=TourProgressResponse)
async def get_tour_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's tour progress"""
    prefs = current_user.preferences or {}
    tour_progress = prefs.get("tour_progress", {})

    return TourProgressResponse(
        completed_tours=tour_progress.get("completed_tours", []),
        skipped_tours=tour_progress.get("skipped_tours", [])
    )


@router.patch("/tour-progress", response_model=TourProgressResponse)
async def update_tour_progress(
    update: TourProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's tour progress"""
    current_prefs = current_user.preferences or {}
    tour_progress = current_prefs.get("tour_progress", {
        "completed_tours": [],
        "skipped_tours": []
    })

    # Merge with existing progress
    if update.completed_tours is not None:
        existing = set(tour_progress.get("completed_tours", []))
        existing.update(update.completed_tours)
        tour_progress["completed_tours"] = list(existing)

    if update.skipped_tours is not None:
        existing = set(tour_progress.get("skipped_tours", []))
        existing.update(update.skipped_tours)
        tour_progress["skipped_tours"] = list(existing)

    # Update preferences
    current_prefs["tour_progress"] = tour_progress
    current_user.preferences = current_prefs

    db.commit()
    db.refresh(current_user)

    return TourProgressResponse(
        completed_tours=tour_progress.get("completed_tours", []),
        skipped_tours=tour_progress.get("skipped_tours", [])
    )


@router.delete("/tour-progress/{tour_key}")
async def reset_tour(
    tour_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset a specific tour (remove from completed and skipped)"""
    current_prefs = current_user.preferences or {}
    tour_progress = current_prefs.get("tour_progress", {
        "completed_tours": [],
        "skipped_tours": []
    })

    # Remove from both lists
    completed = tour_progress.get("completed_tours", [])
    skipped = tour_progress.get("skipped_tours", [])

    if tour_key in completed:
        completed.remove(tour_key)
    if tour_key in skipped:
        skipped.remove(tour_key)

    tour_progress["completed_tours"] = completed
    tour_progress["skipped_tours"] = skipped

    current_prefs["tour_progress"] = tour_progress
    current_user.preferences = current_prefs

    db.commit()

    return {"status": "ok", "message": f"Tour '{tour_key}' has been reset"}
