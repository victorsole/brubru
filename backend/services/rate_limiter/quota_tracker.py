"""
API Quota Tracker

Tracks daily/monthly API usage quotas and sends alerts when approaching limits.
Part of Phase 8: Rate Limiting

Features:
- Daily and monthly quota tracking per API
- Alert thresholds (50%, 75%, 90%, 100%)
- Usage history and statistics
- Quota reset scheduling
- Email/webhook alerts for quota warnings
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class QuotaType(str, Enum):
    """Quota period types"""
    DAILY = "daily"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"          # 50% usage
    WARNING = "warning"    # 75% usage
    CRITICAL = "critical"  # 90% usage
    EXCEEDED = "exceeded"  # 100% usage


@dataclass
class APIQuota:
    """API quota configuration"""
    api_name: str
    quota_type: QuotaType
    limit: int  # Maximum calls per period
    current_usage: int = 0
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    alert_thresholds: List[int] = field(default_factory=lambda: [50, 75, 90, 100])
    alerts_sent: List[int] = field(default_factory=list)  # Which thresholds already alerted

    @property
    def usage_percentage(self) -> float:
        """Calculate current usage as percentage"""
        if self.limit == 0:
            return 0.0
        return (self.current_usage / self.limit) * 100

    @property
    def remaining(self) -> int:
        """Remaining quota"""
        return max(0, self.limit - self.current_usage)

    @property
    def is_exceeded(self) -> bool:
        """Check if quota is exceeded"""
        return self.current_usage >= self.limit

    @property
    def needs_reset(self) -> bool:
        """Check if quota period has elapsed"""
        now = datetime.now(timezone.utc)

        if self.quota_type == QuotaType.DAILY:
            return now.date() > self.period_start.date()
        elif self.quota_type == QuotaType.MONTHLY:
            return (now.year, now.month) > (self.period_start.year, self.period_start.month)
        elif self.quota_type == QuotaType.YEARLY:
            return now.year > self.period_start.year

        return False


class QuotaTracker:
    """
    Track API usage quotas and send alerts.

    Monitors API call quotas for services with daily/monthly limits:
    - PVGIS: 30 calls/second (monitored separately by rate limiter)
    - EUR-Lex SOAP: 100 calls/day (estimated)
    - European Parliament API: varies by endpoint
    - Custom API limits
    """

    # Known API quotas (calls per day unless specified)
    DEFAULT_QUOTAS = {
        'eurlex_soap': {'type': QuotaType.DAILY, 'limit': 100},
        'eurlex_sparql': {'type': QuotaType.DAILY, 'limit': 1000},
        'ep_sparql': {'type': QuotaType.DAILY, 'limit': 1000},
        'pvgis': {'type': QuotaType.DAILY, 'limit': 2592000},  # 30/sec * 86400 sec
        'jrc_data_catalogue': {'type': QuotaType.DAILY, 'limit': 10000},
        'ted_api': {'type': QuotaType.DAILY, 'limit': 1000},
        'iate_api': {'type': QuotaType.DAILY, 'limit': 5000},
    }

    def __init__(
        self,
        storage_backend: Optional[any] = None,
        alert_callback: Optional[callable] = None
    ):
        """
        Initialize quota tracker.

        Args:
            storage_backend: Optional storage backend (Redis, database)
            alert_callback: Function to call when alert threshold reached
        """
        self.quotas: Dict[str, APIQuota] = {}
        self.storage = storage_backend
        self.alert_callback = alert_callback
        self.usage_history: Dict[str, List[Dict]] = {}

        # Initialize default quotas
        self._initialize_default_quotas()

        logger.info("Initialized Quota Tracker")

    def _initialize_default_quotas(self):
        """Initialize quotas for known APIs"""
        for api_name, config in self.DEFAULT_QUOTAS.items():
            self.add_quota(
                api_name=api_name,
                quota_type=config['type'],
                limit=config['limit']
            )

    def add_quota(
        self,
        api_name: str,
        quota_type: QuotaType,
        limit: int,
        alert_thresholds: Optional[List[int]] = None
    ) -> APIQuota:
        """
        Add or update API quota.

        Args:
            api_name: API identifier
            quota_type: Quota period type
            limit: Maximum calls per period
            alert_thresholds: Alert percentage thresholds

        Returns:
            APIQuota instance
        """
        if alert_thresholds is None:
            alert_thresholds = [50, 75, 90, 100]

        quota = APIQuota(
            api_name=api_name,
            quota_type=quota_type,
            limit=limit,
            alert_thresholds=alert_thresholds
        )

        self.quotas[api_name] = quota
        self.usage_history[api_name] = []

        logger.info(f"Added quota for {api_name}: {limit} calls per {quota_type.value}")
        return quota

    def record_call(self, api_name: str, call_count: int = 1) -> Tuple[bool, Optional[str]]:
        """
        Record API call(s) and check quota.

        Args:
            api_name: API identifier
            call_count: Number of calls to record

        Returns:
            Tuple of (allowed: bool, message: Optional[str])
        """
        # Get or create quota
        if api_name not in self.quotas:
            logger.warning(f"No quota defined for {api_name}, allowing call")
            return True, None

        quota = self.quotas[api_name]

        # Check if quota needs reset
        if quota.needs_reset:
            self._reset_quota(api_name)
            quota = self.quotas[api_name]

        # Check if quota exceeded
        if quota.current_usage + call_count > quota.limit:
            message = f"Quota exceeded for {api_name}: {quota.current_usage}/{quota.limit}"
            logger.warning(message)
            self._trigger_alert(api_name, AlertLevel.EXCEEDED, quota)
            return False, message

        # Record usage
        quota.current_usage += call_count

        # Record in history
        self.usage_history[api_name].append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'calls': call_count,
            'total_usage': quota.current_usage,
            'percentage': quota.usage_percentage
        })

        # Check alert thresholds
        self._check_thresholds(api_name, quota)

        # Persist if storage backend available
        if self.storage:
            self._save_quota(api_name, quota)

        return True, None

    def _check_thresholds(self, api_name: str, quota: APIQuota):
        """Check if usage crossed alert thresholds"""
        usage_pct = quota.usage_percentage

        for threshold in quota.alert_thresholds:
            # Skip if already alerted for this threshold
            if threshold in quota.alerts_sent:
                continue

            # Check if threshold crossed
            if usage_pct >= threshold:
                quota.alerts_sent.append(threshold)

                # Determine alert level
                if threshold >= 100:
                    level = AlertLevel.EXCEEDED
                elif threshold >= 90:
                    level = AlertLevel.CRITICAL
                elif threshold >= 75:
                    level = AlertLevel.WARNING
                else:
                    level = AlertLevel.INFO

                self._trigger_alert(api_name, level, quota)

    def _trigger_alert(self, api_name: str, level: AlertLevel, quota: APIQuota):
        """
        Trigger quota alert.

        Args:
            api_name: API identifier
            level: Alert severity level
            quota: Quota instance
        """
        alert_data = {
            'api_name': api_name,
            'level': level.value,
            'usage': quota.current_usage,
            'limit': quota.limit,
            'percentage': quota.usage_percentage,
            'remaining': quota.remaining,
            'quota_type': quota.quota_type.value,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        logger.log(
            logging.CRITICAL if level == AlertLevel.EXCEEDED else logging.WARNING,
            f"Quota alert [{level.value.upper()}] for {api_name}: "
            f"{quota.usage_percentage:.1f}% used ({quota.current_usage}/{quota.limit})"
        )

        # Call alert callback if provided
        if self.alert_callback:
            try:
                self.alert_callback(alert_data)
            except Exception as e:
                logger.error(f"Alert callback failed: {str(e)}")

    def _reset_quota(self, api_name: str):
        """
        Reset quota for new period.

        Args:
            api_name: API identifier
        """
        quota = self.quotas[api_name]

        logger.info(
            f"Resetting quota for {api_name}: "
            f"used {quota.current_usage}/{quota.limit} in previous period"
        )

        # Archive old quota stats
        if api_name in self.usage_history:
            archive_entry = {
                'period_start': quota.period_start.isoformat(),
                'period_end': datetime.now(timezone.utc).isoformat(),
                'total_calls': quota.current_usage,
                'quota_limit': quota.limit,
                'usage_percentage': quota.usage_percentage
            }
            # Keep last 30 periods in memory
            if len(self.usage_history[api_name]) > 30:
                self.usage_history[api_name] = self.usage_history[api_name][-30:]

        # Reset quota
        now = datetime.now(timezone.utc)
        quota.current_usage = 0
        quota.period_start = now
        quota.last_reset = now
        quota.alerts_sent = []

        # Persist
        if self.storage:
            self._save_quota(api_name, quota)

    def get_quota_status(self, api_name: str) -> Optional[Dict]:
        """
        Get current quota status.

        Args:
            api_name: API identifier

        Returns:
            Quota status dict or None
        """
        if api_name not in self.quotas:
            return None

        quota = self.quotas[api_name]

        return {
            'api_name': api_name,
            'quota_type': quota.quota_type.value,
            'limit': quota.limit,
            'current_usage': quota.current_usage,
            'remaining': quota.remaining,
            'percentage': quota.usage_percentage,
            'is_exceeded': quota.is_exceeded,
            'period_start': quota.period_start.isoformat(),
            'last_reset': quota.last_reset.isoformat(),
            'needs_reset': quota.needs_reset
        }

    def get_all_quotas_status(self) -> List[Dict]:
        """
        Get status of all tracked quotas.

        Returns:
            List of quota status dicts
        """
        return [
            self.get_quota_status(api_name)
            for api_name in self.quotas.keys()
        ]

    def get_usage_history(
        self,
        api_name: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get usage history for API.

        Args:
            api_name: API identifier
            limit: Maximum entries to return

        Returns:
            Usage history entries
        """
        if api_name not in self.usage_history:
            return []

        history = self.usage_history[api_name]
        return history[-limit:] if len(history) > limit else history

    def get_usage_summary(self, api_name: str) -> Optional[Dict]:
        """
        Get usage summary statistics.

        Args:
            api_name: API identifier

        Returns:
            Summary statistics
        """
        if api_name not in self.quotas:
            return None

        quota = self.quotas[api_name]
        history = self.usage_history.get(api_name, [])

        # Calculate statistics
        total_calls = sum(entry['calls'] for entry in history)
        avg_per_day = total_calls / max(1, len(set(
            datetime.fromisoformat(entry['timestamp']).date()
            for entry in history
        ))) if history else 0

        return {
            'api_name': api_name,
            'current_period': {
                'usage': quota.current_usage,
                'limit': quota.limit,
                'percentage': quota.usage_percentage
            },
            'historical': {
                'total_calls': total_calls,
                'avg_per_day': avg_per_day,
                'periods_tracked': len(history)
            },
            'quota_info': {
                'type': quota.quota_type.value,
                'period_start': quota.period_start.isoformat(),
                'last_reset': quota.last_reset.isoformat()
            }
        }

    def check_availability(self, api_name: str, required_calls: int = 1) -> bool:
        """
        Check if quota has capacity for required calls.

        Args:
            api_name: API identifier
            required_calls: Number of calls needed

        Returns:
            True if quota available
        """
        if api_name not in self.quotas:
            return True  # No quota defined, allow

        quota = self.quotas[api_name]

        # Check reset
        if quota.needs_reset:
            return True  # Will reset before use

        return quota.remaining >= required_calls

    def reset_all_quotas(self):
        """Reset all quotas (for testing/admin)"""
        for api_name in self.quotas.keys():
            self._reset_quota(api_name)
        logger.info("Reset all quotas")

    def _save_quota(self, api_name: str, quota: APIQuota):
        """
        Save quota to storage backend.

        Args:
            api_name: API identifier
            quota: Quota instance
        """
        # This would save to Redis/database
        # For now, just log
        logger.debug(f"Saved quota for {api_name}")

    def _load_quota(self, api_name: str) -> Optional[APIQuota]:
        """
        Load quota from storage backend.

        Args:
            api_name: API identifier

        Returns:
            APIQuota or None
        """
        # This would load from Redis/database
        return None

    def export_statistics(self) -> Dict:
        """
        Export all quota statistics.

        Returns:
            Complete statistics export
        """
        return {
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'quotas': self.get_all_quotas_status(),
            'summaries': {
                api_name: self.get_usage_summary(api_name)
                for api_name in self.quotas.keys()
            }
        }

    def set_alert_callback(self, callback: callable):
        """
        Set or update alert callback function.

        Args:
            callback: Function(alert_data: Dict) to call on alerts
        """
        self.alert_callback = callback
        logger.info("Updated alert callback")


# Example alert callback functions

def email_alert_callback(alert_data: Dict):
    """
    Send email alert (example implementation).

    Args:
        alert_data: Alert information dict
    """
    logger.info(f"EMAIL ALERT: {alert_data['api_name']} - {alert_data['level']}")
    # Would integrate with email service
    pass


def webhook_alert_callback(alert_data: Dict):
    """
    Send webhook alert (example implementation).

    Args:
        alert_data: Alert information dict
    """
    logger.info(f"WEBHOOK ALERT: {alert_data['api_name']} - {alert_data['level']}")
    # Would POST to webhook URL
    pass


def slack_alert_callback(alert_data: Dict):
    """
    Send Slack alert (example implementation).

    Args:
        alert_data: Alert information dict
    """
    level_emoji = {
        'info': 'ℹ️',
        'warning': '⚠️',
        'critical': '🚨',
        'exceeded': '🛑'
    }

    message = (
        f"{level_emoji.get(alert_data['level'], '📊')} "
        f"API Quota Alert: {alert_data['api_name']}\n"
        f"Usage: {alert_data['usage']}/{alert_data['limit']} "
        f"({alert_data['percentage']:.1f}%)\n"
        f"Remaining: {alert_data['remaining']} calls"
    )

    logger.info(f"SLACK ALERT: {message}")
    # Would send to Slack webhook
    pass
