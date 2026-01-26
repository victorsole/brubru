"""
Notification Service

Generates and manages user notifications and alerts.
Part of My EU Bubble - Phase 5: Advanced Features

Features:
- Create notifications for new RSS entries
- Alert on legislative status changes
- Notify about amendment deadlines
- Smart filtering based on user interests
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, desc

from models.notification import Notification
from models.user import User
from models.rss_entry import RSSEntry
from models.user_feed_subscription import UserFeedSubscription
from models.user_document import UserDocument
from models.legislative_train import LegislativeCarriage
from models.amendment import Amendment

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for creating and managing user notifications.

    Generates smart alerts based on:
    - User policy interests
    - Feed subscriptions
    - Document tracking
    - Legislative changes
    """

    def __init__(self, db_session: Session):
        """
        Initialize notification service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        logger.info("Initialized Notification Service")

    def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        priority: str = "normal",
        action_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None
    ) -> Notification:
        """
        Create a new notification.

        Args:
            user_id: User UUID
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high, urgent)
            action_url: Optional URL for action
            metadata: Optional metadata dictionary
            related_entity_type: Optional related entity type
            related_entity_id: Optional related entity UUID

        Returns:
            Created notification
        """
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            action_url=action_url,
            metadata=metadata,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        logger.info(f"Created {notification_type} notification for user {user_id}")
        return notification

    async def generate_rss_entry_notifications(
        self,
        rss_entry_id: str
    ) -> List[Notification]:
        """
        Generate notifications for users interested in a new RSS entry.

        Args:
            rss_entry_id: RSS entry UUID

        Returns:
            List of created notifications
        """
        logger.info(f"Generating notifications for RSS entry {rss_entry_id}")

        notifications = []

        try:
            # Get RSS entry
            stmt = select(RSSEntry).where(RSSEntry.id == rss_entry_id)
            rss_entry = self.db.execute(stmt).scalar_one_or_none()

            if not rss_entry:
                logger.warning(f"RSS entry {rss_entry_id} not found")
                return notifications

            # Get policy areas from metadata
            policy_areas = []
            if rss_entry.entry_metadata and "policy_areas" in rss_entry.entry_metadata:
                policy_areas = rss_entry.entry_metadata["policy_areas"]

            # Find users subscribed to this feed
            stmt = select(UserFeedSubscription).where(
                and_(
                    UserFeedSubscription.feed_id == rss_entry.feed_id,
                    UserFeedSubscription.is_active == True,
                    UserFeedSubscription.notification_enabled == True
                )
            )
            subscriptions = self.db.execute(stmt).scalars().all()

            for subscription in subscriptions:
                # Check if entry matches user interests
                if self._matches_user_interests(subscription.user_id, policy_areas):
                    notification = self.create_notification(
                        user_id=str(subscription.user_id),
                        notification_type="new_feed_entry",
                        title=f"New: {rss_entry.title[:100]}",
                        message=f"A new article from {rss_entry.institution} matches your interests.",
                        priority="normal",
                        action_url=rss_entry.link,
                        metadata={
                            "policy_areas": policy_areas,
                            "source": rss_entry.institution
                        },
                        related_entity_type="rss_entry",
                        related_entity_id=str(rss_entry.id)
                    )
                    notifications.append(notification)

        except Exception as e:
            logger.error(f"Failed to generate RSS entry notifications: {e}")

        logger.info(f"Generated {len(notifications)} notifications for RSS entry")
        return notifications

    async def generate_status_change_notification(
        self,
        user_id: str,
        change_data: Dict[str, Any]
    ) -> Notification:
        """
        Generate notification for legislative status change.

        Args:
            user_id: User UUID
            change_data: Status change information

        Returns:
            Created notification
        """
        logger.info(f"Generating status change notification for user {user_id}")

        title = f"Update: {change_data.get('title', 'Tracked Item')[:100]}"

        message = f"Status changed for {change_data.get('procedure_reference', 'tracked item')}. "
        if change_data.get("recent_events"):
            message += f"{len(change_data['recent_events'])} new event(s) detected."

        notification = self.create_notification(
            user_id=user_id,
            notification_type="status_change",
            title=title,
            message=message,
            priority="high",
            metadata=change_data,
            related_entity_type="procedure",
            related_entity_id=None  # Procedures don't have UUIDs in our system
        )

        return notification

    async def generate_amendment_deadline_notifications(
        self,
        days_before: int = 7
    ) -> List[Notification]:
        """
        Generate notifications for upcoming amendment deadlines.

        Args:
            days_before: Notify N days before deadline

        Returns:
            List of created notifications
        """
        logger.info(f"Generating amendment deadline notifications ({days_before} days)")

        notifications = []

        try:
            # Find amendments with upcoming deadlines
            # Note: This requires a deadline field in UserDocument model
            # For now, we'll use a simplified version

            cutoff_date = datetime.now(timezone.utc) + timedelta(days=days_before)

            stmt = select(UserDocument).where(
                and_(
                    UserDocument.document_type == "amendment",
                    UserDocument.amendment_status.in_(["draft", "submitted"])
                )
            )
            amendments = self.db.execute(stmt).scalars().all()

            for amendment in amendments:
                # Check if user has already been notified recently
                if not self._has_recent_deadline_notification(amendment.user_id, amendment.id):
                    notification = self.create_notification(
                        user_id=str(amendment.user_id),
                        notification_type="deadline",
                        title=f"Deadline approaching: {amendment.title[:100]}",
                        message=f"Your amendment '{amendment.title}' needs attention.",
                        priority="high",
                        action_url=f"/bubble?tab=amendments&id={amendment.id}",
                        metadata={
                            "document_id": str(amendment.id),
                            "status": amendment.amendment_status
                        },
                        related_entity_type="user_document",
                        related_entity_id=str(amendment.id)
                    )
                    notifications.append(notification)

        except Exception as e:
            logger.error(f"Failed to generate deadline notifications: {e}")

        logger.info(f"Generated {len(notifications)} deadline notifications")
        return notifications

    async def generate_amendment_context_notifications(
        self,
        carriage_id: str,
        change_type: str,
        change_data: Dict[str, Any]
    ) -> List[Notification]:
        """
        Generate notifications for users with amendments linked to a carriage that changed.

        This is called when a tracked legislative file changes status, has new events,
        or other significant updates. Users who have drafted amendments for this file
        are notified so they can review and update their amendments if needed.

        Args:
            carriage_id: Legislative carriage UUID
            change_type: Type of change (status_change, new_event, blocking_detected)
            change_data: Change information dict containing:
                - title: File title
                - old_status: Previous status (if status change)
                - new_status: New status (if status change)
                - procedure_ref: OEIL procedure reference
                - event_description: Description of the event

        Returns:
            List of created notifications
        """
        logger.info(f"Generating amendment context notifications for carriage {carriage_id}")

        notifications = []

        try:
            # Find all amendments linked to this carriage
            stmt = select(Amendment).where(Amendment.carriage_id == carriage_id)
            amendments = self.db.execute(stmt).scalars().all()

            if not amendments:
                logger.info(f"No amendments linked to carriage {carriage_id}")
                return notifications

            # Get unique user IDs that have amendments for this file
            user_ids = set(str(a.user_id) for a in amendments if a.user_id)

            # Get the carriage details for the notification message
            carriage_stmt = select(LegislativeCarriage).where(LegislativeCarriage.id == carriage_id)
            carriage = self.db.execute(carriage_stmt).scalar_one_or_none()

            file_title = change_data.get('title') or (carriage.title if carriage else 'Tracked file')
            procedure_ref = change_data.get('procedure_ref') or (carriage.oeil_procedure_ref if carriage else None)

            # Build notification message based on change type
            if change_type == 'status_change':
                old_status = change_data.get('old_status', 'unknown').replace('_', ' ')
                new_status = change_data.get('new_status', 'unknown').replace('_', ' ')
                title = f"Status Update: {file_title[:60]}..."
                message = f"Status changed from '{old_status}' to '{new_status}'. You have amendments for this file - review them for relevance."
                priority = "high"
            elif change_type == 'blocking_detected':
                title = f"File Blocked: {file_title[:60]}..."
                message = f"This legislative file has been blocked. Your amendments may need revision."
                priority = "urgent"
            elif change_type == 'new_event':
                event_desc = change_data.get('event_description', 'New activity detected')
                title = f"New Event: {file_title[:60]}..."
                message = f"{event_desc}. Review your amendments for this file."
                priority = "normal"
            else:
                title = f"Update: {file_title[:60]}..."
                message = f"There's an update on this file. You have amendments that may be affected."
                priority = "normal"

            # Create notification for each user with amendments
            for user_id in user_ids:
                # Check if we've already sent a similar notification recently
                if not self._has_recent_amendment_context_notification(user_id, carriage_id, change_type):
                    notification = self.create_notification(
                        user_id=user_id,
                        notification_type=f"amendment_context_{change_type}",
                        title=title,
                        message=message,
                        priority=priority,
                        action_url=f"/bubble?tab=amendments",
                        metadata={
                            "carriage_id": carriage_id,
                            "procedure_ref": procedure_ref,
                            "change_type": change_type,
                            "amendment_count": len([a for a in amendments if str(a.user_id) == user_id]),
                            **change_data
                        },
                        related_entity_type="legislative_carriage",
                        related_entity_id=carriage_id
                    )
                    notifications.append(notification)

        except Exception as e:
            logger.error(f"Failed to generate amendment context notifications: {e}")

        logger.info(f"Generated {len(notifications)} amendment context notifications")
        return notifications

    def _has_recent_amendment_context_notification(
        self,
        user_id: str,
        carriage_id: str,
        change_type: str,
        hours: int = 24
    ) -> bool:
        """
        Check if user already received an amendment context notification recently.

        Args:
            user_id: User UUID
            carriage_id: Carriage UUID
            change_type: Type of change
            hours: Recent time window in hours

        Returns:
            True if recent notification exists
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        stmt = select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.notification_type == f"amendment_context_{change_type}",
                Notification.related_entity_id == carriage_id,
                Notification.created_at >= cutoff_time
            )
        )

        notifications = self.db.execute(stmt).scalars().all()
        return len(notifications) > 0

    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """
        Get notifications for a user.

        Args:
            user_id: User UUID
            unread_only: Only return unread notifications
            limit: Maximum number of notifications

        Returns:
            List of notifications
        """
        stmt = select(Notification).where(
            Notification.user_id == user_id
        )

        if unread_only:
            stmt = stmt.where(Notification.is_read == False)

        stmt = stmt.order_by(desc(Notification.created_at)).limit(limit)

        notifications = self.db.execute(stmt).scalars().all()
        return list(notifications)

    def mark_as_read(self, notification_id: str) -> bool:
        """
        Mark notification as read.

        Args:
            notification_id: Notification UUID

        Returns:
            True if successful
        """
        try:
            stmt = select(Notification).where(Notification.id == notification_id)
            notification = self.db.execute(stmt).scalar_one_or_none()

            if notification:
                notification.mark_as_read()
                self.db.commit()
                logger.info(f"Marked notification {notification_id} as read")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
            self.db.rollback()
            return False

    def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of notifications marked as read
        """
        try:
            stmt = select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            )
            notifications = self.db.execute(stmt).scalars().all()

            count = 0
            for notification in notifications:
                notification.mark_as_read()
                count += 1

            self.db.commit()
            logger.info(f"Marked {count} notifications as read for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"Failed to mark all notifications as read: {e}")
            self.db.rollback()
            return 0

    def delete_notification(self, notification_id: str) -> bool:
        """
        Delete a notification.

        Args:
            notification_id: Notification UUID

        Returns:
            True if successful
        """
        try:
            stmt = select(Notification).where(Notification.id == notification_id)
            notification = self.db.execute(stmt).scalar_one_or_none()

            if notification:
                self.db.delete(notification)
                self.db.commit()
                logger.info(f"Deleted notification {notification_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete notification: {e}")
            self.db.rollback()
            return False

    def get_unread_count(self, user_id: str) -> int:
        """
        Get count of unread notifications for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of unread notifications
        """
        stmt = select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
        notifications = self.db.execute(stmt).scalars().all()
        return len(notifications)

    def _matches_user_interests(
        self,
        user_id: str,
        policy_areas: List[str]
    ) -> bool:
        """
        Check if policy areas match user interests.

        Args:
            user_id: User UUID
            policy_areas: List of policy areas

        Returns:
            True if matches user interests
        """
        if not policy_areas:
            return True  # Default to match if no policy areas

        try:
            stmt = select(User).where(User.id == user_id)
            user = self.db.execute(stmt).scalar_one_or_none()

            if not user or not user.policy_interests:
                return True  # Default to match if no user interests defined

            # Parse user interests (stored as JSON text)
            user_interests = json.loads(user.policy_interests)

            # Check if any policy area matches user interests
            for area in policy_areas:
                if area in user_interests:
                    return True

        except Exception as e:
            logger.warning(f"Failed to check user interests: {e}")
            return True  # Default to match on error

        return False

    def _has_recent_deadline_notification(
        self,
        user_id: str,
        document_id: str,
        hours: int = 24
    ) -> bool:
        """
        Check if user already received deadline notification recently.

        Args:
            user_id: User UUID
            document_id: Document UUID
            hours: Recent time window in hours

        Returns:
            True if recent notification exists
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        stmt = select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.notification_type == "deadline",
                Notification.related_entity_id == document_id,
                Notification.created_at >= cutoff_time
            )
        )

        notifications = self.db.execute(stmt).scalars().all()
        return len(notifications) > 0
