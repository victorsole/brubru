"""
Notifications API Endpoints

Provides REST API for user notifications and alerts.
Part of My EU Bubble - Phase 5: Advanced Features
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db
from ..models.user import User
from .auth_optional import get_current_user_dev as get_current_user
from ..services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# Pydantic Schemas
class NotificationResponse(BaseModel):
    """Notification response schema."""
    id: str
    user_id: str
    notification_type: str
    title: str
    message: str
    action_url: Optional[str]
    metadata: Optional[dict]
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]
    priority: str
    is_read: bool
    created_at: str
    read_at: Optional[str]


class NotificationListResponse(BaseModel):
    """List of notifications response."""
    notifications: List[NotificationResponse]
    unread_count: int
    total: int


class MarkAsReadRequest(BaseModel):
    """Request to mark notification as read."""
    notification_id: str


class UnreadCountResponse(BaseModel):
    """Unread notifications count response."""
    unread_count: int


# Endpoints

@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of notifications"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notifications for the current user.

    Returns list of notifications ordered by creation date (newest first).
    """
    service = NotificationService(db)

    try:
        notifications = service.get_user_notifications(
            str(current_user.id),
            unread_only=unread_only,
            limit=limit
        )

        unread_count = service.get_unread_count(str(current_user.id))

        return {
            "notifications": [n.to_dict() for n in notifications],
            "unread_count": unread_count,
            "total": len(notifications)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notifications: {str(e)}"
        )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get count of unread notifications.

    Useful for displaying notification badges.
    """
    service = NotificationService(db)

    try:
        unread_count = service.get_unread_count(str(current_user.id))
        return {"unread_count": unread_count}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get unread count: {str(e)}"
        )


@router.post("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a notification as read.

    Returns success status.
    """
    service = NotificationService(db)

    try:
        success = service.mark_as_read(notification_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )

        return {"success": True, "message": "Notification marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as read: {str(e)}"
        )


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read for the current user.

    Returns number of notifications marked as read.
    """
    service = NotificationService(db)

    try:
        count = service.mark_all_as_read(str(current_user.id))

        return {
            "success": True,
            "message": f"Marked {count} notifications as read",
            "count": count
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all notifications as read: {str(e)}"
        )


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a notification.

    Returns success status.
    """
    service = NotificationService(db)

    try:
        success = service.delete_notification(notification_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )

        return {"success": True, "message": "Notification deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notification: {str(e)}"
        )
