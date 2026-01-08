"""
API Error Handler

Comprehensive error handling for all EU API clients.
Part of Phase 9: Error Handling & Monitoring

Features:
- HTTP status code handling with retry logic
- API-specific error patterns
- Automatic token refresh for auth errors
- Exponential backoff for overload
- Contextual error logging
- Admin alerts for critical failures
"""

import logging
from typing import Optional, Dict, Any, Callable, Tuple
from datetime import datetime
from enum import Enum
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    INFO = "info"           # Transient, auto-recoverable
    WARNING = "warning"     # Temporary issue, may need attention
    ERROR = "error"         # Significant issue, requires investigation
    CRITICAL = "critical"   # System failure, immediate attention needed


class ErrorCategory(str, Enum):
    """Error categories"""
    RATE_LIMIT = "rate_limit"           # 429 - Too many requests
    AUTHENTICATION = "authentication"    # 401/403 - Auth failed
    SERVER_ERROR = "server_error"        # 500-599 - Server issues
    CLIENT_ERROR = "client_error"        # 400-499 - Client issues
    TIMEOUT = "timeout"                  # Request timeout
    CONNECTION = "connection"            # Connection failed
    VALIDATION = "validation"            # Data validation failed
    UNKNOWN = "unknown"                  # Unknown error


@dataclass
class ErrorContext:
    """Context information for an error"""
    api_name: str
    endpoint: str
    method: str = "GET"
    status_code: Optional[int] = None
    error_message: str = ""
    request_params: Optional[Dict] = None
    response_body: Optional[str] = None
    timestamp: datetime = None
    retry_count: int = 0
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.ERROR

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            'api_name': self.api_name,
            'endpoint': self.endpoint,
            'method': self.method,
            'status_code': self.status_code,
            'error_message': self.error_message,
            'category': self.category.value,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'retry_count': self.retry_count,
            'request_params': self.request_params,
            'response_body': self.response_body[:500] if self.response_body else None
        }


class APIErrorHandler:
    """
    Comprehensive error handler for EU API clients.

    Handles HTTP errors with intelligent retry logic:
    - 429 (Rate Limited): Wait and retry with backoff
    - 401/403 (Auth): Refresh tokens and retry
    - 500-599 (Server): Exponential backoff
    - 529 (Overloaded): Extended backoff
    - Connection errors: Retry with backoff
    """

    # Retry configuration per error type
    RETRY_CONFIG = {
        429: {  # Too Many Requests
            'max_retries': 5,
            'base_delay': 2.0,
            'backoff_multiplier': 2.0,
            'max_delay': 60.0
        },
        401: {  # Unauthorized
            'max_retries': 2,
            'base_delay': 1.0,
            'backoff_multiplier': 1.0,
            'max_delay': 2.0
        },
        403: {  # Forbidden
            'max_retries': 2,
            'base_delay': 1.0,
            'backoff_multiplier': 1.0,
            'max_delay': 2.0
        },
        500: {  # Internal Server Error
            'max_retries': 3,
            'base_delay': 5.0,
            'backoff_multiplier': 2.0,
            'max_delay': 120.0
        },
        502: {  # Bad Gateway
            'max_retries': 3,
            'base_delay': 5.0,
            'backoff_multiplier': 2.0,
            'max_delay': 120.0
        },
        503: {  # Service Unavailable
            'max_retries': 3,
            'base_delay': 10.0,
            'backoff_multiplier': 2.0,
            'max_delay': 300.0
        },
        504: {  # Gateway Timeout
            'max_retries': 3,
            'base_delay': 5.0,
            'backoff_multiplier': 2.0,
            'max_delay': 120.0
        },
        529: {  # Site Overloaded (CloudFlare)
            'max_retries': 5,
            'base_delay': 30.0,
            'backoff_multiplier': 2.0,
            'max_delay': 600.0
        },
    }

    def __init__(
        self,
        alert_callback: Optional[Callable] = None,
        token_refresh_callback: Optional[Callable] = None
    ):
        """
        Initialize error handler.

        Args:
            alert_callback: Function to call for admin alerts
            token_refresh_callback: Function to refresh auth tokens
        """
        self.alert_callback = alert_callback
        self.token_refresh_callback = token_refresh_callback
        self.error_history: Dict[str, list] = {}  # API name -> error list
        self.error_counts: Dict[str, Dict[int, int]] = {}  # API -> status code -> count

        logger.info("Initialized API Error Handler")

    def classify_error(
        self,
        status_code: Optional[int],
        error: Optional[Exception]
    ) -> Tuple[ErrorCategory, ErrorSeverity]:
        """
        Classify error by category and severity.

        Args:
            status_code: HTTP status code
            error: Exception object

        Returns:
            Tuple of (category, severity)
        """
        if status_code:
            if status_code == 429:
                return ErrorCategory.RATE_LIMIT, ErrorSeverity.WARNING
            elif status_code in [401, 403]:
                return ErrorCategory.AUTHENTICATION, ErrorSeverity.ERROR
            elif 500 <= status_code < 600:
                severity = ErrorSeverity.CRITICAL if status_code in [503, 529] else ErrorSeverity.ERROR
                return ErrorCategory.SERVER_ERROR, severity
            elif 400 <= status_code < 500:
                return ErrorCategory.CLIENT_ERROR, ErrorSeverity.WARNING

        if error:
            error_str = str(error).lower()
            if 'timeout' in error_str:
                return ErrorCategory.TIMEOUT, ErrorSeverity.WARNING
            elif 'connection' in error_str or 'connect' in error_str:
                return ErrorCategory.CONNECTION, ErrorSeverity.ERROR
            elif 'validation' in error_str:
                return ErrorCategory.VALIDATION, ErrorSeverity.WARNING

        return ErrorCategory.UNKNOWN, ErrorSeverity.ERROR

    async def handle_error(
        self,
        context: ErrorContext,
        request_func: Callable,
        **request_kwargs
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        Handle API error with retry logic.

        Args:
            context: Error context
            request_func: Async function to retry
            **request_kwargs: Arguments for request function

        Returns:
            Tuple of (success: bool, result: Any, error_message: Optional[str])
        """
        # Classify error
        context.category, context.severity = self.classify_error(
            context.status_code,
            None
        )

        # Log error
        self._log_error(context)

        # Track error
        self._track_error(context)

        # Check if error is retryable
        if not self._is_retryable(context):
            logger.error(f"[{context.api_name}] Non-retryable error: {context.error_message}")
            self._alert_if_critical(context)
            return False, None, context.error_message

        # Get retry configuration
        retry_config = self.RETRY_CONFIG.get(
            context.status_code,
            {'max_retries': 3, 'base_delay': 5.0, 'backoff_multiplier': 2.0, 'max_delay': 60.0}
        )

        # Retry loop
        for retry in range(retry_config['max_retries']):
            context.retry_count = retry + 1

            # Handle authentication errors
            if context.status_code in [401, 403] and self.token_refresh_callback:
                logger.info(f"[{context.api_name}] Attempting token refresh")
                try:
                    await self.token_refresh_callback(context.api_name)
                except Exception as e:
                    logger.error(f"Token refresh failed: {str(e)}")

            # Calculate backoff delay
            delay = self._calculate_delay(
                retry,
                retry_config['base_delay'],
                retry_config['backoff_multiplier'],
                retry_config['max_delay']
            )

            logger.info(
                f"[{context.api_name}] Retry {retry + 1}/{retry_config['max_retries']} "
                f"after {delay:.2f}s (status: {context.status_code})"
            )

            # Wait before retry
            await asyncio.sleep(delay)

            # Retry request
            try:
                result = await request_func(**request_kwargs)
                logger.info(f"[{context.api_name}] Retry successful")
                return True, result, None

            except Exception as e:
                context.error_message = str(e)
                logger.warning(f"[{context.api_name}] Retry {retry + 1} failed: {str(e)}")

                # Update status code if available
                if hasattr(e, 'status_code'):
                    context.status_code = e.status_code

        # All retries exhausted
        logger.error(
            f"[{context.api_name}] All retries exhausted for {context.endpoint}"
        )
        self._alert_if_critical(context)
        return False, None, context.error_message

    def _is_retryable(self, context: ErrorContext) -> bool:
        """
        Check if error is retryable.

        Args:
            context: Error context

        Returns:
            True if retryable
        """
        # Rate limits are always retryable
        if context.category == ErrorCategory.RATE_LIMIT:
            return True

        # Server errors are retryable
        if context.category == ErrorCategory.SERVER_ERROR:
            return True

        # Timeouts and connection errors are retryable
        if context.category in [ErrorCategory.TIMEOUT, ErrorCategory.CONNECTION]:
            return True

        # Auth errors are retryable (will try to refresh)
        if context.category == ErrorCategory.AUTHENTICATION:
            return True

        # Client errors are generally not retryable (except 429)
        if context.status_code and 400 <= context.status_code < 500:
            return context.status_code == 429

        # Unknown errors - retry cautiously
        return True

    def _calculate_delay(
        self,
        retry: int,
        base_delay: float,
        multiplier: float,
        max_delay: float
    ) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            retry: Current retry attempt (0-indexed)
            base_delay: Base delay in seconds
            multiplier: Backoff multiplier
            max_delay: Maximum delay cap

        Returns:
            Delay in seconds
        """
        delay = base_delay * (multiplier ** retry)
        return min(delay, max_delay)

    def _log_error(self, context: ErrorContext):
        """
        Log error with full context.

        Args:
            context: Error context
        """
        log_level = {
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }[context.severity]

        logger.log(
            log_level,
            f"[{context.api_name}] API Error - "
            f"Endpoint: {context.endpoint}, "
            f"Status: {context.status_code}, "
            f"Category: {context.category.value}, "
            f"Message: {context.error_message}"
        )

    def _track_error(self, context: ErrorContext):
        """
        Track error for statistics.

        Args:
            context: Error context
        """
        # Initialize tracking for API
        if context.api_name not in self.error_history:
            self.error_history[context.api_name] = []
            self.error_counts[context.api_name] = {}

        # Add to history
        self.error_history[context.api_name].append(context.to_dict())

        # Keep last 100 errors per API
        if len(self.error_history[context.api_name]) > 100:
            self.error_history[context.api_name] = self.error_history[context.api_name][-100:]

        # Increment count
        if context.status_code:
            self.error_counts[context.api_name][context.status_code] = \
                self.error_counts[context.api_name].get(context.status_code, 0) + 1

    def _alert_if_critical(self, context: ErrorContext):
        """
        Send alert if error is critical.

        Args:
            context: Error context
        """
        if context.severity == ErrorSeverity.CRITICAL:
            self._send_alert(context)

        # Alert on high error rate
        error_rate = self.get_error_rate(context.api_name, minutes=10)
        if error_rate > 0.5:  # >50% errors in last 10 minutes
            logger.critical(
                f"[{context.api_name}] High error rate detected: {error_rate*100:.1f}%"
            )
            self._send_alert(context, high_error_rate=True)

    def _send_alert(self, context: ErrorContext, high_error_rate: bool = False):
        """
        Send admin alert.

        Args:
            context: Error context
            high_error_rate: Whether this is a high error rate alert
        """
        if not self.alert_callback:
            return

        alert_data = {
            **context.to_dict(),
            'alert_type': 'high_error_rate' if high_error_rate else 'critical_error',
            'requires_attention': True
        }

        try:
            self.alert_callback(alert_data)
        except Exception as e:
            logger.error(f"Failed to send alert: {str(e)}")

    def get_error_rate(self, api_name: str, minutes: int = 10) -> float:
        """
        Calculate error rate for API in time window.

        Args:
            api_name: API identifier
            minutes: Time window in minutes

        Returns:
            Error rate (0.0 to 1.0)
        """
        if api_name not in self.error_history:
            return 0.0

        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        recent_errors = [
            e for e in self.error_history[api_name]
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]

        if not recent_errors:
            return 0.0

        # Simple approximation: assume 1 error per failed request
        # In production, would track total requests too
        return min(1.0, len(recent_errors) / max(1, minutes * 10))

    def get_error_statistics(self, api_name: Optional[str] = None) -> Dict:
        """
        Get error statistics.

        Args:
            api_name: Specific API or None for all

        Returns:
            Error statistics
        """
        if api_name:
            if api_name not in self.error_history:
                return {}

            return {
                'api_name': api_name,
                'total_errors': len(self.error_history[api_name]),
                'status_codes': self.error_counts.get(api_name, {}),
                'recent_errors': self.error_history[api_name][-10:],
                'error_rate_10min': self.get_error_rate(api_name, 10)
            }

        # All APIs
        return {
            api: self.get_error_statistics(api)
            for api in self.error_history.keys()
        }

    def clear_history(self, api_name: Optional[str] = None):
        """
        Clear error history (for testing/admin).

        Args:
            api_name: Specific API or None for all
        """
        if api_name:
            if api_name in self.error_history:
                self.error_history[api_name] = []
                self.error_counts[api_name] = {}
        else:
            self.error_history = {}
            self.error_counts = {}


# Example alert callback

def admin_alert_callback(alert_data: Dict):
    """
    Example admin alert callback.

    Args:
        alert_data: Alert information
    """
    logger.critical(
        f"ADMIN ALERT: {alert_data['alert_type']} - "
        f"{alert_data['api_name']} - {alert_data['error_message']}"
    )
    # Would send email/Slack/webhook
    pass


# Global singleton
_error_handler: Optional[APIErrorHandler] = None


def get_error_handler() -> APIErrorHandler:
    """Get global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = APIErrorHandler()
    return _error_handler
