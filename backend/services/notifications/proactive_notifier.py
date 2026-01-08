"""
Proactive Notifier

Monitor RSS feeds and send AI-powered summaries to users when relevant updates occur.
Part of Phase 13: AI Context Injection - Task 13.9

Features:
- Monitor RSS feeds for updates
- Match updates against user interests/subscriptions
- Generate AI summaries of updates
- Send notifications via email/webhook
- Batch notifications to avoid spam
- Track notification history
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from anthropic import AsyncAnthropic

from ...scrapers.rss_manager import RSSManager
from ..indexing.metadata_extractor import MetadataExtractor, get_metadata_extractor

logger = logging.getLogger(__name__)


@dataclass
class UserSubscription:
    """User subscription preferences"""
    user_id: str
    keywords: List[str]  # Keywords to watch for
    meps: List[str]  # MEPs to follow
    committees: List[str]  # Committee codes to follow
    policy_areas: List[str]  # Policy areas of interest
    celex_numbers: List[str]  # Specific legislation to follow
    notification_frequency: str  # 'immediate', 'hourly', 'daily', 'weekly'
    email: Optional[str] = None
    webhook_url: Optional[str] = None


@dataclass
class Notification:
    """Notification to send to user"""
    user_id: str
    title: str
    summary: str
    rss_entries: List[Dict[str, Any]]
    generated_at: datetime
    sent: bool = False


class ProactiveNotifier:
    """
    Monitor RSS and send proactive notifications.

    Workflow:
    1. Periodically check RSS feeds for new entries
    2. Match entries against user subscriptions
    3. Generate AI summaries of relevant updates
    4. Batch notifications based on user preferences
    5. Send via email/webhook
    """

    MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        api_key: str,
        rss_manager: RSSManager,
        metadata_extractor: MetadataExtractor,
        check_interval_minutes: int = 60
    ):
        """
        Initialize proactive notifier.

        Args:
            api_key: Anthropic API key for summaries
            rss_manager: RSS feed manager
            metadata_extractor: Entity extraction service
            check_interval_minutes: How often to check for updates
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.rss_manager = rss_manager
        self.metadata_extractor = metadata_extractor
        self.check_interval_minutes = check_interval_minutes

        # User subscriptions (in production, load from database)
        self.subscriptions: List[UserSubscription] = []

        # Notification queue
        self.notification_queue: List[Notification] = []

        logger.info(f"Initialized ProactiveNotifier (check_interval={check_interval_minutes}m)")

    async def start_monitoring(self):
        """
        Start monitoring RSS feeds continuously.

        Runs in background task.
        """
        logger.info("Starting RSS monitoring")

        while True:
            try:
                await self.check_for_updates()
                await asyncio.sleep(self.check_interval_minutes * 60)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def check_for_updates(self):
        """
        Check for new RSS entries and generate notifications.
        """
        logger.info("Checking for RSS updates")

        # Get recent RSS entries
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=self.check_interval_minutes)

        recent_entries = await self.rss_manager.get_entries_by_date_range(
            start_date=start_time,
            end_date=end_time,
            limit=100
        )

        if not recent_entries:
            logger.debug("No new RSS entries")
            return

        logger.info(f"Found {len(recent_entries)} new RSS entries")

        # Match entries against subscriptions
        for subscription in self.subscriptions:
            matched_entries = self._match_entries_to_subscription(
                entries=recent_entries,
                subscription=subscription
            )

            if matched_entries:
                await self._generate_notification(
                    subscription=subscription,
                    entries=matched_entries
                )

        # Send notifications
        await self._send_pending_notifications()

    def _match_entries_to_subscription(
        self,
        entries: List[Dict[str, Any]],
        subscription: UserSubscription
    ) -> List[Dict[str, Any]]:
        """
        Match RSS entries against user subscription.

        Args:
            entries: RSS entries to check
            subscription: User subscription

        Returns:
            List of matching entries
        """
        matched = []

        for entry in entries:
            title = entry.get('title', '').lower()
            summary = entry.get('summary', '').lower()
            text = f"{title} {summary}"

            # Check keywords
            if subscription.keywords:
                if any(keyword.lower() in text for keyword in subscription.keywords):
                    matched.append(entry)
                    continue

            # Extract entities from entry
            entities = self.metadata_extractor.extract_all(text)

            # Check CELEX numbers
            if subscription.celex_numbers:
                if any(celex in entities['celex_numbers'] for celex in subscription.celex_numbers):
                    matched.append(entry)
                    continue

            # Check MEPs
            if subscription.meps:
                if any(mep in entities['mep_mentions'] for mep in subscription.meps):
                    matched.append(entry)
                    continue

            # Check committees
            if subscription.committees:
                entry_committees = [c['code'] for c in entities['committees']]
                if any(committee in entry_committees for committee in subscription.committees):
                    matched.append(entry)
                    continue

            # Check policy areas
            if subscription.policy_areas:
                entry_policy_areas = self.metadata_extractor.extract_policy_areas(text)
                if any(area in entry_policy_areas for area in subscription.policy_areas):
                    matched.append(entry)
                    continue

        logger.debug(f"Matched {len(matched)} entries for user {subscription.user_id}")

        return matched

    async def _generate_notification(
        self,
        subscription: UserSubscription,
        entries: List[Dict[str, Any]]
    ):
        """
        Generate AI summary notification for user.

        Args:
            subscription: User subscription
            entries: Matching RSS entries
        """
        if not entries:
            return

        # Generate AI summary
        summary = await self._generate_ai_summary(entries, subscription)

        # Create notification
        notification = Notification(
            user_id=subscription.user_id,
            title=f"EU Policy Updates: {len(entries)} new items",
            summary=summary,
            rss_entries=entries,
            generated_at=datetime.now(),
            sent=False
        )

        # Add to queue
        self.notification_queue.append(notification)

        logger.info(f"Generated notification for user {subscription.user_id}")

    async def _generate_ai_summary(
        self,
        entries: List[Dict[str, Any]],
        subscription: UserSubscription
    ) -> str:
        """
        Generate AI summary of RSS entries.

        Args:
            entries: RSS entries
            subscription: User subscription (for personalization)

        Returns:
            Summary text
        """
        # Build prompt
        entries_text = "\n\n".join([
            f"[{entry.get('published', '')}] {entry.get('title', '')}\n{entry.get('summary', '')[:200]}"
            for entry in entries[:10]  # Max 10 entries
        ])

        system_prompt = """You are an expert in EU legislative affairs.
Summarize EU policy updates in a clear, concise manner for professionals monitoring EU developments."""

        user_prompt = f"""Generate a brief summary of these EU policy updates:

USER INTERESTS: {', '.join(subscription.keywords + subscription.policy_areas)}

RECENT UPDATES:
{entries_text}

Provide:
1. Brief overview (2-3 sentences)
2. Key highlights (bullet points, max 5)
3. Why these are relevant to the user's interests

Be concise and focus on actionable information."""

        try:
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=1000,
                temperature=0.6,
                system=system_prompt,
                messages=[{'role': 'user', 'content': user_prompt}]
            )

            summary = response.content[0].text if response.content else ""

            logger.debug(f"Generated AI summary: {len(summary)} chars")

            return summary

        except Exception as e:
            logger.error(f"Failed to generate AI summary: {str(e)}")

            # Fallback to simple summary
            return f"Found {len(entries)} new updates related to your interests:\n" + "\n".join([
                f"- {entry.get('title', '')}"
                for entry in entries[:5]
            ])

    async def _send_pending_notifications(self):
        """
        Send all pending notifications.
        """
        if not self.notification_queue:
            return

        # Group by user and frequency
        batched = self._batch_notifications()

        for user_id, notifications in batched.items():
            try:
                # Get user subscription
                subscription = next(
                    (s for s in self.subscriptions if s.user_id == user_id),
                    None
                )

                if not subscription:
                    continue

                # Send notification
                await self._send_notification(subscription, notifications)

                # Mark as sent
                for notification in notifications:
                    notification.sent = True

            except Exception as e:
                logger.error(f"Failed to send notification to {user_id}: {str(e)}")

        # Clear sent notifications
        self.notification_queue = [n for n in self.notification_queue if not n.sent]

        logger.info(f"Sent {len(batched)} batched notifications")

    def _batch_notifications(self) -> Dict[str, List[Notification]]:
        """
        Batch notifications by user and frequency.

        Returns:
            Dict mapping user_id to list of notifications
        """
        batched = {}

        for notification in self.notification_queue:
            if notification.user_id not in batched:
                batched[notification.user_id] = []

            batched[notification.user_id].append(notification)

        return batched

    async def _send_notification(
        self,
        subscription: UserSubscription,
        notifications: List[Notification]
    ):
        """
        Send notification to user via configured channel.

        Args:
            subscription: User subscription with email/webhook
            notifications: Notifications to send
        """
        # Combine summaries
        combined_summary = "\n\n---\n\n".join([
            f"{n.title}\n\n{n.summary}"
            for n in notifications
        ])

        # Send via email
        if subscription.email:
            await self._send_email(
                to_email=subscription.email,
                subject=f"EU Policy Updates ({len(notifications)} items)",
                body=combined_summary
            )

        # Send via webhook
        if subscription.webhook_url:
            await self._send_webhook(
                url=subscription.webhook_url,
                payload={
                    'user_id': subscription.user_id,
                    'notifications': [
                        {
                            'title': n.title,
                            'summary': n.summary,
                            'entries': n.rss_entries
                        }
                        for n in notifications
                    ]
                }
            )

        logger.info(f"Sent {len(notifications)} notifications to {subscription.user_id}")

    async def _send_email(self, to_email: str, subject: str, body: str):
        """
        Send email notification.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body
        """
        # In production, integrate with email service (SendGrid, AWS SES, etc.)
        logger.info(f"[EMAIL] To: {to_email}, Subject: {subject}")
        logger.debug(f"[EMAIL] Body: {body[:200]}...")

    async def _send_webhook(self, url: str, payload: Dict[str, Any]):
        """
        Send webhook notification.

        Args:
            url: Webhook URL
            payload: JSON payload
        """
        # In production, make HTTP POST request
        logger.info(f"[WEBHOOK] URL: {url}")
        logger.debug(f"[WEBHOOK] Payload: {payload}")

    def subscribe_user(self, subscription: UserSubscription):
        """
        Add user subscription.

        Args:
            subscription: User subscription preferences
        """
        self.subscriptions.append(subscription)
        logger.info(f"Added subscription for user {subscription.user_id}")

    def unsubscribe_user(self, user_id: str):
        """
        Remove user subscription.

        Args:
            user_id: User ID
        """
        self.subscriptions = [s for s in self.subscriptions if s.user_id != user_id]
        logger.info(f"Removed subscription for user {user_id}")

    def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """
        Get user subscription.

        Args:
            user_id: User ID

        Returns:
            UserSubscription or None
        """
        return next((s for s in self.subscriptions if s.user_id == user_id), None)

    def get_notification_history(self, user_id: str, limit: int = 10) -> List[Notification]:
        """
        Get notification history for user.

        Args:
            user_id: User ID
            limit: Max notifications to return

        Returns:
            List of notifications
        """
        user_notifications = [
            n for n in self.notification_queue
            if n.user_id == user_id and n.sent
        ]

        return sorted(user_notifications, key=lambda x: x.generated_at, reverse=True)[:limit]


# Global singleton
_proactive_notifier: Optional[ProactiveNotifier] = None


def get_proactive_notifier(
    api_key: Optional[str] = None,
    rss_manager: Optional[RSSManager] = None,
    metadata_extractor: Optional[MetadataExtractor] = None,
    check_interval_minutes: int = 60
) -> ProactiveNotifier:
    """
    Get global proactive notifier instance.

    Args:
        api_key: Anthropic API key
        rss_manager: RSS manager
        metadata_extractor: Entity extractor
        check_interval_minutes: Check interval

    Returns:
        ProactiveNotifier instance
    """
    global _proactive_notifier

    if _proactive_notifier is None:
        if api_key is None:
            raise ValueError("api_key required for first initialization")

        _proactive_notifier = ProactiveNotifier(
            api_key=api_key,
            rss_manager=rss_manager,
            metadata_extractor=metadata_extractor or get_metadata_extractor(),
            check_interval_minutes=check_interval_minutes
        )

    return _proactive_notifier
