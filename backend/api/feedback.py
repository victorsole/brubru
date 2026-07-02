"""
Feedback System API

Endpoints for users to submit feedback, bug reports, and feature requests.
Includes admin endpoints for managing feedback.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.database import get_db
from models.user import User
from models.feedback import (
    FeedbackSubmission,
    FeedbackComment,
    AdminActivityLog
)
from schemas.feedback_schemas import (
    FeedbackCreate,
    FeedbackUpdate,
    FeedbackResponse,
    FeedbackListResponse,
    CommentCreate,
    CommentResponse,
    FeedbackStats,
    ChatFeedbackCreate,
    ChatFeedbackResponse
)
from api.auth import get_current_user
from api.admin_auth import get_current_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


# User Endpoints

@router.post("/submit", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit new feedback, bug report, or feature request.

    Available to all authenticated users.
    """
    try:
        # Create feedback submission
        new_feedback = FeedbackSubmission(
            user_id=current_user.id,
            feedback_type=feedback.feedback_type,
            title=feedback.title,
            description=feedback.description,
            category=feedback.category,
            affected_feature=feedback.affected_feature,
            browser_info=feedback.browser_info,
            device_info=feedback.device_info,
            screenshot_url=feedback.screenshot_url,
            attachments=feedback.attachments,
            status='new',
            priority='medium'
        )

        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)

        logger.info(f"New feedback submitted: {new_feedback.id} by user {current_user.id}")

        return new_feedback

    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )


@router.get("/my-feedback", response_model=FeedbackListResponse)
async def get_my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's feedback submissions with pagination.
    """
    query = db.query(FeedbackSubmission).filter(FeedbackSubmission.user_id == current_user.id)

    if status_filter:
        query = query.filter(FeedbackSubmission.status == status_filter)

    if type_filter:
        query = query.filter(FeedbackSubmission.feedback_type == type_filter)

    # Get total count
    total = query.count()

    # Get paginated results
    feedback_items = query.order_by(FeedbackSubmission.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "feedback_items": feedback_items
    }


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback_detail(
    feedback_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed feedback information.

    Users can only view their own feedback unless they're an admin.
    """
    feedback = db.query(FeedbackSubmission).filter(FeedbackSubmission.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    # Check permissions: users can only see their own feedback, admins can see all
    if feedback.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own feedback"
        )

    return feedback


@router.post("/{feedback_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    feedback_id: UUID,
    comment: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a comment to feedback.

    Users can comment on their own feedback, admins can comment on any feedback.
    """
    feedback = db.query(FeedbackSubmission).filter(FeedbackSubmission.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    # Check permissions
    if feedback.user_id != current_user.id and current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only comment on your own feedback"
        )

    # Create comment
    new_comment = FeedbackComment(
        feedback_id=feedback_id,
        user_id=current_user.id,
        is_admin_response=(current_user.role == 'admin'),
        comment_text=comment.comment_text,
        attachments=comment.attachments
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return new_comment


# Admin Endpoints

@router.get("/admin/all", response_model=FeedbackListResponse)
def get_all_feedback_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None),
    type_filter: Optional[str] = Query(None),
    priority_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all feedback submissions (admin only).

    Supports filtering by status, type, priority, and search.
    """
    query = db.query(FeedbackSubmission)

    if status_filter:
        query = query.filter(FeedbackSubmission.status == status_filter)

    if type_filter:
        query = query.filter(FeedbackSubmission.feedback_type == type_filter)

    if priority_filter:
        query = query.filter(FeedbackSubmission.priority == priority_filter)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (FeedbackSubmission.title.ilike(search_pattern)) |
            (FeedbackSubmission.description.ilike(search_pattern))
        )

    total = query.count()

    feedback_items = query.order_by(FeedbackSubmission.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "feedback_items": feedback_items
    }


@router.patch("/admin/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback_admin(
    feedback_id: UUID,
    updates: FeedbackUpdate,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update feedback (admin only).

    Can update status, priority, assignment, admin notes, and admin response.
    """
    feedback = db.query(FeedbackSubmission).filter(FeedbackSubmission.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    # Update fields
    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(feedback, field, value)

    # If status is changed to resolved or closed, set resolved_at
    if updates.status in ['resolved', 'closed'] and not feedback.resolved_at:
        feedback.resolved_at = datetime.now()

    feedback.updated_at = datetime.now()

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="update_feedback",
        target_type="feedback",
        target_id=feedback_id,
        action_details=update_data
    )
    db.add(log_entry)

    db.commit()
    db.refresh(feedback)

    logger.info(f"Feedback {feedback_id} updated by admin {admin.id}")

    return feedback


@router.get("/admin/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get feedback statistics for admin dashboard.
    """
    # Total feedback
    total_feedback = db.query(func.count(FeedbackSubmission.id)).scalar()

    # By status
    by_status_raw = db.query(
        FeedbackSubmission.status,
        func.count(FeedbackSubmission.id)
    ).group_by(FeedbackSubmission.status).all()
    by_status = {status: count for status, count in by_status_raw}

    # By type
    by_type_raw = db.query(
        FeedbackSubmission.feedback_type,
        func.count(FeedbackSubmission.id)
    ).group_by(FeedbackSubmission.feedback_type).all()
    by_type = {ftype: count for ftype, count in by_type_raw}

    # By priority
    by_priority_raw = db.query(
        FeedbackSubmission.priority,
        func.count(FeedbackSubmission.id)
    ).group_by(FeedbackSubmission.priority).all()
    by_priority = {priority: count for priority, count in by_priority_raw}

    # Recent feedback (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_feedback = db.query(func.count(FeedbackSubmission.id)) \
        .filter(FeedbackSubmission.created_at >= seven_days_ago).scalar()

    # Unresolved count
    unresolved_count = db.query(func.count(FeedbackSubmission.id)) \
        .filter(FeedbackSubmission.status.in_(['new', 'in_review', 'in_progress'])).scalar()

    return {
        "total_feedback": total_feedback,
        "by_status": by_status,
        "by_type": by_type,
        "by_priority": by_priority,
        "recent_feedback": recent_feedback,
        "unresolved_count": unresolved_count
    }


@router.delete("/admin/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback_admin(
    feedback_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete feedback (admin only).

    Use with caution - this is permanent.
    """
    feedback = db.query(FeedbackSubmission).filter(FeedbackSubmission.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="delete_feedback",
        target_type="feedback",
        target_id=feedback_id,
        action_details={"title": feedback.title, "type": feedback.feedback_type}
    )
    db.add(log_entry)

    db.delete(feedback)
    db.commit()

    logger.info(f"Feedback {feedback_id} deleted by admin {admin.id}")

    return None


# Chat Feedback Endpoint

@router.post("/chat", response_model=ChatFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_chat_feedback(
    feedback: ChatFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit quick feedback for a chat message.

    This endpoint allows users to rate chat responses as positive or negative.
    The feedback is stored in the feedback system and visible in the Admin Panel.

    Args:
        feedback: Chat feedback data (chat_id, message_id, rating)
        current_user: Authenticated user

    Returns:
        Success response with feedback ID

    Example:
        POST /api/feedback/chat
        {
            "chat_id": "chat_123",
            "message_id": "msg_456",
            "rating": "positive",
            "message_content": "The AI Act was adopted..."
        }
    """
    try:
        # Validate rating
        if feedback.rating not in ['positive', 'negative', 'hallucination']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be 'positive', 'negative', or 'hallucination'"
            )

        # Determine feedback type and title based on rating
        if feedback.rating == 'hallucination':
            rating_emoji = "⚠️"
            title = f"Chat Message {rating_emoji} Incorrect Information Report"
            feedback_type = 'hallucination'
            priority = 'medium'  # Hallucination reports are higher priority
        else:
            rating_emoji = "👍" if feedback.rating == "positive" else "👎"
            title = f"Chat Message {rating_emoji} {feedback.rating.capitalize()}"
            feedback_type = 'chat_rating'
            priority = 'low'

        # Build description with context
        description_parts = [
            f"Chat feedback: {feedback.rating}",
            f"Chat ID: {feedback.chat_id}",
            f"Message ID: {feedback.message_id}"
        ]

        if feedback.message_content:
            content_preview = feedback.message_content[:200] + "..." if len(feedback.message_content) > 200 else feedback.message_content
            description_parts.append(f"Message preview: {content_preview}")

        # Add user's correction/explanation for hallucination reports
        if feedback.feedback_text:
            description_parts.append(f"User correction: {feedback.feedback_text}")

        description = "\n".join(description_parts)

        new_feedback = FeedbackSubmission(
            user_id=current_user.id,
            feedback_type=feedback_type,
            title=title,
            description=description,
            category='chat',
            status='new',
            priority=priority
        )

        db.add(new_feedback)
        db.commit()
        db.refresh(new_feedback)

        logger.info(
            f"Chat feedback submitted: {new_feedback.id} "
            f"(rating: {feedback.rating}, chat: {feedback.chat_id}, message: {feedback.message_id})"
        )

        return ChatFeedbackResponse(
            success=True,
            feedback_id=new_feedback.id,
            message=f"Thank you for your {feedback.rating} feedback!"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting chat feedback: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit chat feedback"
        )
