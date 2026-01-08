"""
Notification Services

Proactive notifications for EU policy updates.
Part of Phase 13: AI Context Injection - Task 13.9

Components:
- ProactiveNotifier: Monitor RSS and send AI-powered notifications
"""

from .proactive_notifier import (
    ProactiveNotifier,
    UserSubscription,
    Notification,
    get_proactive_notifier
)

__all__ = [
    'ProactiveNotifier',
    'UserSubscription',
    'Notification',
    'get_proactive_notifier'
]
