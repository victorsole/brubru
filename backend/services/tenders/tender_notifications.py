"""
Tender Notification Service

Generates notifications for tender matches and digests.
Integrates with the main notification service and email system.

Usage:
    from backend.services.tenders.tender_notifications import TenderNotificationService

    service = TenderNotificationService(db)
    await service.send_match_notifications(user_id)
    await service.send_weekly_digest()
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ...models.tender import Tender, TenderProfile, TenderMatch
from ...models.user import User
from ...models.notification import Notification
from ..notification_service import NotificationService

logger = logging.getLogger(__name__)


class TenderNotificationService:
    """
    Service for tender-related notifications.

    Handles:
    - Individual match notifications (in-app)
    - Weekly digest emails
    - Deadline reminders
    - Match updates
    """

    def __init__(self, db: Session):
        """
        Initialize the tender notification service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.notification_service = NotificationService(db)

    async def notify_new_matches(
        self,
        user_id: str,
        match_ids: Optional[List[int]] = None
    ) -> int:
        """
        Send in-app notifications for new tender matches.

        Args:
            user_id: User UUID
            match_ids: Specific match IDs to notify (optional)

        Returns:
            Number of notifications sent
        """
        # Get user's notification preferences
        profile = self.db.query(TenderProfile).filter(
            TenderProfile.user_id == user_id
        ).first()

        if not profile or not profile.notification_in_app:
            return 0

        # Get unnotified matches
        query = self.db.query(TenderMatch).filter(
            and_(
                TenderMatch.user_id == user_id,
                TenderMatch.notified_at.is_(None),
                TenderMatch.is_dismissed == False
            )
        ).order_by(desc(TenderMatch.match_score))

        if match_ids:
            query = query.filter(TenderMatch.id.in_(match_ids))

        matches = query.limit(profile.max_matches_per_digest or 10).all()

        if not matches:
            return 0

        notifications_sent = 0

        for match in matches:
            tender = self.db.query(Tender).filter(
                Tender.id == match.tender_id
            ).first()

            if not tender:
                continue

            # Create notification
            self.notification_service.create_notification(
                user_id=user_id,
                notification_type="tender_match",
                title=f"New tender match: {tender.title[:80]}...",
                message=self._build_match_message(tender, match),
                priority="normal" if match.match_score < 80 else "high",
                action_url=f"/tenderator?match={match.id}",
                metadata={
                    "tender_id": tender.id,
                    "match_id": match.id,
                    "match_score": match.match_score,
                    "publication_number": tender.publication_number,
                    "buyer_country": tender.buyer_country,
                    "estimated_value": tender.estimated_value
                },
                related_entity_type="tender_match",
                related_entity_id=str(match.id)
            )

            # Mark match as notified
            match.notified_at = datetime.utcnow()
            match.notification_method = "in_app"
            notifications_sent += 1

        self.db.commit()
        logger.info(f"Sent {notifications_sent} tender match notifications to user {user_id}")

        return notifications_sent

    async def send_weekly_digest(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Send weekly digest of tender matches to users.

        Args:
            user_id: Optional specific user ID (None = all users)

        Returns:
            Statistics dictionary
        """
        stats = {
            "users_notified": 0,
            "matches_included": 0,
            "emails_sent": 0
        }

        # Get profiles with weekly notifications enabled
        query = self.db.query(TenderProfile).filter(
            and_(
                TenderProfile.is_active == True,
                TenderProfile.notification_email == True,
                TenderProfile.notification_frequency == "weekly"
            )
        )

        if user_id:
            query = query.filter(TenderProfile.user_id == user_id)

        profiles = query.all()

        for profile in profiles:
            # Get recent matches for this user
            week_ago = datetime.utcnow() - timedelta(days=7)

            matches = self.db.query(TenderMatch).filter(
                and_(
                    TenderMatch.user_id == profile.user_id,
                    TenderMatch.created_at >= week_ago,
                    TenderMatch.is_dismissed == False
                )
            ).order_by(desc(TenderMatch.match_score)).limit(
                profile.max_matches_per_digest or 10
            ).all()

            if not matches:
                continue

            # Get user info
            user = self.db.query(User).filter(User.id == profile.user_id).first()
            if not user:
                continue

            # Build digest
            digest = self._build_weekly_digest(user, profile, matches)

            # Create notification record
            self.notification_service.create_notification(
                user_id=str(profile.user_id),
                notification_type="tender_digest",
                title=f"Weekly Tender Digest - {len(matches)} new matches",
                message=digest["summary"],
                priority="normal",
                action_url="/tenderator",
                metadata={
                    "match_count": len(matches),
                    "top_match_score": matches[0].match_score if matches else 0,
                    "period": "weekly"
                }
            )

            # TODO: Send email using email service
            # For now, just log the digest
            logger.info(f"Would send weekly digest to {user.email} with {len(matches)} matches")

            stats["users_notified"] += 1
            stats["matches_included"] += len(matches)

        logger.info(f"Weekly digest complete: {stats}")
        return stats

    async def send_deadline_reminders(
        self,
        days_before: int = 7
    ) -> int:
        """
        Send reminders for tenders with approaching deadlines.

        Args:
            days_before: Days before deadline to send reminder

        Returns:
            Number of reminders sent
        """
        cutoff_date = datetime.utcnow() + timedelta(days=days_before)

        # Get saved matches with upcoming deadlines
        matches_with_deadlines = self.db.query(TenderMatch).join(Tender).filter(
            and_(
                TenderMatch.is_saved == True,
                TenderMatch.is_applied == False,
                Tender.submission_deadline <= cutoff_date,
                Tender.submission_deadline > datetime.utcnow()
            )
        ).all()

        reminders_sent = 0

        for match in matches_with_deadlines:
            tender = self.db.query(Tender).filter(
                Tender.id == match.tender_id
            ).first()

            if not tender:
                continue

            # Check if already reminded
            existing = self.db.query(Notification).filter(
                and_(
                    Notification.user_id == match.user_id,
                    Notification.notification_type == "tender_deadline",
                    Notification.related_entity_id == str(match.id),
                    Notification.created_at >= datetime.utcnow() - timedelta(days=3)
                )
            ).first()

            if existing:
                continue

            days_left = (tender.submission_deadline - datetime.utcnow()).days

            self.notification_service.create_notification(
                user_id=str(match.user_id),
                notification_type="tender_deadline",
                title=f"Deadline approaching: {tender.title[:60]}...",
                message=f"Only {days_left} days left to submit your bid for this saved tender.",
                priority="high",
                action_url=f"/tenderator?match={match.id}",
                metadata={
                    "tender_id": tender.id,
                    "match_id": match.id,
                    "days_left": days_left,
                    "deadline": tender.submission_deadline.isoformat()
                },
                related_entity_type="tender_match",
                related_entity_id=str(match.id)
            )

            reminders_sent += 1

        self.db.commit()
        logger.info(f"Sent {reminders_sent} deadline reminders")

        return reminders_sent

    async def notify_high_score_match(
        self,
        match: TenderMatch,
        tender: Tender
    ) -> bool:
        """
        Send immediate notification for high-scoring matches.

        Args:
            match: TenderMatch object
            tender: Tender object

        Returns:
            True if notification sent
        """
        # Only for scores above 80
        if match.match_score < 80:
            return False

        # Get user's profile to check preferences
        profile = self.db.query(TenderProfile).filter(
            TenderProfile.user_id == match.user_id
        ).first()

        if not profile or not profile.notification_in_app:
            return False

        self.notification_service.create_notification(
            user_id=str(match.user_id),
            notification_type="tender_match_high",
            title=f"Excellent match found! Score: {match.match_score:.0f}%",
            message=f"{tender.title[:100]}... matches your profile exceptionally well.",
            priority="high",
            action_url=f"/tenderator?match={match.id}",
            metadata={
                "tender_id": tender.id,
                "match_id": match.id,
                "match_score": match.match_score,
                "publication_number": tender.publication_number
            },
            related_entity_type="tender_match",
            related_entity_id=str(match.id)
        )

        match.notified_at = datetime.utcnow()
        match.notification_method = "in_app"
        self.db.commit()

        return True

    def _build_match_message(
        self,
        tender: Tender,
        match: TenderMatch
    ) -> str:
        """Build notification message for a match."""
        parts = []

        # Score info
        parts.append(f"Match score: {match.match_score:.0f}%")

        # Value info
        if tender.estimated_value:
            parts.append(f"Value: €{tender.estimated_value:,.0f}")

        # Deadline info
        if tender.submission_deadline:
            days = (tender.submission_deadline - datetime.utcnow()).days
            parts.append(f"Deadline: {days} days")

        # Country
        if tender.buyer_country:
            parts.append(f"Country: {tender.buyer_country}")

        return " | ".join(parts)

    def _build_weekly_digest(
        self,
        user: User,
        profile: TenderProfile,
        matches: List[TenderMatch]
    ) -> Dict[str, Any]:
        """Build weekly digest content."""
        # Get tenders for all matches
        tender_ids = [m.tender_id for m in matches]
        tenders = self.db.query(Tender).filter(
            Tender.id.in_(tender_ids)
        ).all()
        tender_map = {t.id: t for t in tenders}

        # Build summary
        high_score_count = len([m for m in matches if m.match_score >= 70])
        total_value = sum(
            tender_map[m.tender_id].estimated_value or 0
            for m in matches
            if m.tender_id in tender_map
        )

        summary = f"Found {len(matches)} matching tenders this week"
        if high_score_count:
            summary += f", {high_score_count} with excellent match scores"
        if total_value:
            summary += f". Combined value: €{total_value:,.0f}"

        # Build items list
        items = []
        for match in matches[:10]:
            tender = tender_map.get(match.tender_id)
            if tender:
                items.append({
                    "title": tender.title,
                    "match_score": match.match_score,
                    "value": tender.estimated_value,
                    "deadline": tender.submission_deadline.isoformat() if tender.submission_deadline else None,
                    "country": tender.buyer_country,
                    "publication_number": tender.publication_number
                })

        return {
            "user_name": user.full_name or user.email,
            "company_name": profile.company_name,
            "period_start": (datetime.utcnow() - timedelta(days=7)).date().isoformat(),
            "period_end": datetime.utcnow().date().isoformat(),
            "summary": summary,
            "match_count": len(matches),
            "high_score_count": high_score_count,
            "total_value": total_value,
            "items": items
        }

    def get_notification_stats(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get notification statistics.

        Args:
            user_id: Optional user ID to filter

        Returns:
            Statistics dictionary
        """
        query = self.db.query(Notification).filter(
            Notification.notification_type.in_([
                "tender_match",
                "tender_match_high",
                "tender_deadline",
                "tender_digest"
            ])
        )

        if user_id:
            query = query.filter(Notification.user_id == user_id)

        notifications = query.all()

        return {
            "total_tender_notifications": len(notifications),
            "unread_count": len([n for n in notifications if not n.is_read]),
            "by_type": {
                "matches": len([n for n in notifications if n.notification_type == "tender_match"]),
                "high_score": len([n for n in notifications if n.notification_type == "tender_match_high"]),
                "deadlines": len([n for n in notifications if n.notification_type == "tender_deadline"]),
                "digests": len([n for n in notifications if n.notification_type == "tender_digest"])
            }
        }


# Convenience functions
async def send_tender_match_notifications(
    db: Session,
    user_id: str
) -> int:
    """Send match notifications for a user."""
    service = TenderNotificationService(db)
    return await service.notify_new_matches(user_id)


async def send_tender_weekly_digests(db: Session) -> Dict[str, int]:
    """Send weekly digests to all eligible users."""
    service = TenderNotificationService(db)
    return await service.send_weekly_digest()


async def send_tender_deadline_reminders(
    db: Session,
    days_before: int = 7
) -> int:
    """Send deadline reminders."""
    service = TenderNotificationService(db)
    return await service.send_deadline_reminders(days_before)
