"""
API Health Checker

Periodic health monitoring for all EU API endpoints.
Part of Phase 9: Error Handling & Monitoring

Features:
- Periodic availability checks for all APIs
- Response time monitoring and tracking
- Success rate calculation
- Health status dashboard integration
- Automatic alerts on service degradation
- Historical health metrics
"""

import logging
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """API health status"""
    HEALTHY = "healthy"         # All checks passing
    DEGRADED = "degraded"       # Some checks failing
    UNHEALTHY = "unhealthy"     # Critical failures
    UNKNOWN = "unknown"         # No data / not monitored


@dataclass
class HealthCheck:
    """Individual health check result"""
    api_name: str
    endpoint: str
    timestamp: datetime
    success: bool
    response_time_ms: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'api_name': self.api_name,
            'endpoint': self.endpoint,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'response_time_ms': self.response_time_ms,
            'status_code': self.status_code,
            'error_message': self.error_message
        }


@dataclass
class APIHealthMetrics:
    """Health metrics for an API"""
    api_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

    # Response time metrics (milliseconds)
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p95_response_time: float = 0.0  # 95th percentile

    # Success metrics
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    success_rate: float = 0.0  # 0.0 to 1.0

    # Recent history
    recent_checks: List[HealthCheck] = field(default_factory=list)

    # Uptime
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for dashboard"""
        return {
            'api_name': self.api_name,
            'status': self.status.value,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'last_success': self.last_success.isoformat() if self.last_success else None,
            'last_failure': self.last_failure.isoformat() if self.last_failure else None,
            'response_time': {
                'avg': self.avg_response_time,
                'min': self.min_response_time,
                'max': self.max_response_time,
                'p95': self.p95_response_time
            },
            'success_metrics': {
                'total_checks': self.total_checks,
                'successful': self.successful_checks,
                'failed': self.failed_checks,
                'success_rate': f"{self.success_rate * 100:.2f}%"
            },
            'uptime_percentage': f"{self.uptime_percentage:.2f}%",
            'consecutive_failures': self.consecutive_failures,
            'consecutive_successes': self.consecutive_successes
        }


class APIHealthChecker:
    """
    Periodic health monitoring for EU API endpoints.

    Monitors critical endpoints across all EU institutions:
    - European Parliament: MEP directory, SPARQL endpoint
    - EUR-Lex: Document retrieval, SPARQL
    - Council: Press releases, RSS feeds
    - OEIL: Procedure data
    - JRC: PVGIS, Data Catalogue
    - TED: Procurement notices
    - IATE: Terminology lookup
    """

    # Health check endpoints for each API
    HEALTH_ENDPOINTS = {
        'european_parliament': {
            'endpoint': 'https://www.europarl.europa.eu/meps/en/directory/xml',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 300  # 5 minutes
        },
        'eurlex': {
            'endpoint': 'https://eur-lex.europa.eu/homepage.html',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 300
        },
        'eurlex_sparql': {
            'endpoint': 'https://publications.europa.eu/webapi/rdf/sparql',
            'method': 'GET',
            'timeout': 15.0,
            'check_interval': 600  # 10 minutes
        },
        'council': {
            'endpoint': 'https://www.consilium.europa.eu/en/press/press-releases/',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 300
        },
        'oeil': {
            'endpoint': 'https://oeil.secure.europarl.europa.eu/oeil/en/home',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 600
        },
        'jrc_pvgis': {
            'endpoint': 'https://re.jrc.ec.europa.eu/pvg_tools/en/',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 300
        },
        'ted': {
            'endpoint': 'https://ted.europa.eu/en/',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 300
        },
        'iate': {
            'endpoint': 'https://iate.europa.eu/home',
            'method': 'HEAD',
            'timeout': 10.0,
            'check_interval': 600
        },
        'data_europa': {
            'endpoint': 'https://data.europa.eu/api/hub/search/datasets',
            'method': 'GET',
            'timeout': 10.0,
            'check_interval': 300
        }
    }

    # Alert thresholds
    ALERT_THRESHOLDS = {
        'consecutive_failures': 3,      # Alert after 3 consecutive failures
        'success_rate_warning': 0.95,   # Alert if success rate < 95%
        'success_rate_critical': 0.80,  # Critical if success rate < 80%
        'response_time_warning': 5000,  # Warning if avg > 5s
        'response_time_critical': 10000 # Critical if avg > 10s
    }

    def __init__(
        self,
        alert_callback: Optional[Callable] = None,
        http_client: Optional[Any] = None
    ):
        """
        Initialize health checker.

        Args:
            alert_callback: Function to call on health degradation
            http_client: HTTP client (aiohttp session)
        """
        self.alert_callback = alert_callback
        self.http_client = http_client
        self.metrics: Dict[str, APIHealthMetrics] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False

        # Initialize metrics for all APIs
        for api_name in self.HEALTH_ENDPOINTS.keys():
            self.metrics[api_name] = APIHealthMetrics(api_name=api_name)

        logger.info(f"Initialized API Health Checker for {len(self.HEALTH_ENDPOINTS)} APIs")

    async def check_health(self, api_name: str) -> HealthCheck:
        """
        Perform health check for specific API.

        Args:
            api_name: API identifier

        Returns:
            HealthCheck result
        """
        if api_name not in self.HEALTH_ENDPOINTS:
            raise ValueError(f"Unknown API: {api_name}")

        config = self.HEALTH_ENDPOINTS[api_name]

        start_time = time.time()
        success = False
        status_code = None
        error_message = None

        try:
            # Perform HTTP request
            if self.http_client:
                # Use provided HTTP client (aiohttp)
                async with self.http_client.request(
                    config['method'],
                    config['endpoint'],
                    timeout=config['timeout']
                ) as response:
                    status_code = response.status
                    success = 200 <= status_code < 400
            else:
                # Simple connectivity check without external client
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        config['method'],
                        config['endpoint'],
                        timeout=aiohttp.ClientTimeout(total=config['timeout'])
                    ) as response:
                        status_code = response.status
                        success = 200 <= status_code < 400

        except asyncio.TimeoutError:
            error_message = "Request timeout"
            logger.warning(f"[{api_name}] Health check timeout")
        except Exception as e:
            error_message = str(e)
            logger.error(f"[{api_name}] Health check failed: {str(e)}")

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        # Create health check result
        check = HealthCheck(
            api_name=api_name,
            endpoint=config['endpoint'],
            timestamp=datetime.now(timezone.utc),
            success=success,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message
        )

        # Update metrics
        self._update_metrics(api_name, check)

        # Check for degradation
        self._check_degradation(api_name)

        return check

    def _update_metrics(self, api_name: str, check: HealthCheck):
        """
        Update health metrics with new check result.

        Args:
            api_name: API identifier
            check: Health check result
        """
        metrics = self.metrics[api_name]

        # Update timestamps
        metrics.last_check = check.timestamp
        if check.success:
            metrics.last_success = check.timestamp
            metrics.consecutive_failures = 0
            metrics.consecutive_successes += 1
        else:
            metrics.last_failure = check.timestamp
            metrics.consecutive_successes = 0
            metrics.consecutive_failures += 1

        # Update counts
        metrics.total_checks += 1
        if check.success:
            metrics.successful_checks += 1
        else:
            metrics.failed_checks += 1

        # Calculate success rate
        metrics.success_rate = metrics.successful_checks / metrics.total_checks

        # Add to recent history (keep last 100)
        metrics.recent_checks.append(check)
        if len(metrics.recent_checks) > 100:
            metrics.recent_checks = metrics.recent_checks[-100:]

        # Update response time metrics
        response_times = [c.response_time_ms for c in metrics.recent_checks if c.success]
        if response_times:
            metrics.avg_response_time = sum(response_times) / len(response_times)
            metrics.min_response_time = min(response_times)
            metrics.max_response_time = max(response_times)

            # Calculate 95th percentile
            sorted_times = sorted(response_times)
            p95_index = int(len(sorted_times) * 0.95)
            metrics.p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]

        # Calculate uptime (last 24 hours)
        metrics.uptime_percentage = self._calculate_uptime(api_name, hours=24)

        # Determine health status
        metrics.status = self._determine_health_status(metrics)

        logger.debug(
            f"[{api_name}] Health: {metrics.status.value}, "
            f"Success rate: {metrics.success_rate*100:.1f}%, "
            f"Avg response: {metrics.avg_response_time:.0f}ms"
        )

    def _determine_health_status(self, metrics: APIHealthMetrics) -> HealthStatus:
        """
        Determine overall health status.

        Args:
            metrics: API health metrics

        Returns:
            Health status
        """
        # No data yet
        if metrics.total_checks == 0:
            return HealthStatus.UNKNOWN

        # Critical: Multiple consecutive failures
        if metrics.consecutive_failures >= self.ALERT_THRESHOLDS['consecutive_failures']:
            return HealthStatus.UNHEALTHY

        # Critical: Very low success rate
        if metrics.success_rate < self.ALERT_THRESHOLDS['success_rate_critical']:
            return HealthStatus.UNHEALTHY

        # Degraded: Low success rate
        if metrics.success_rate < self.ALERT_THRESHOLDS['success_rate_warning']:
            return HealthStatus.DEGRADED

        # Degraded: High response time
        if metrics.avg_response_time > self.ALERT_THRESHOLDS['response_time_critical']:
            return HealthStatus.DEGRADED

        # Warning: Elevated response time
        if metrics.avg_response_time > self.ALERT_THRESHOLDS['response_time_warning']:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _calculate_uptime(self, api_name: str, hours: int = 24) -> float:
        """
        Calculate uptime percentage for time window.

        Args:
            api_name: API identifier
            hours: Time window in hours

        Returns:
            Uptime percentage (0-100)
        """
        metrics = self.metrics[api_name]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent = [c for c in metrics.recent_checks if c.timestamp > cutoff]
        if not recent:
            return 100.0

        successful = sum(1 for c in recent if c.success)
        return (successful / len(recent)) * 100

    def _check_degradation(self, api_name: str):
        """
        Check for service degradation and alert.

        Args:
            api_name: API identifier
        """
        metrics = self.metrics[api_name]
        alerts = []

        # Check consecutive failures
        if metrics.consecutive_failures >= self.ALERT_THRESHOLDS['consecutive_failures']:
            alerts.append({
                'type': 'consecutive_failures',
                'severity': 'critical',
                'message': f"{metrics.consecutive_failures} consecutive failures"
            })

        # Check success rate
        if metrics.success_rate < self.ALERT_THRESHOLDS['success_rate_critical']:
            alerts.append({
                'type': 'low_success_rate',
                'severity': 'critical',
                'message': f"Success rate: {metrics.success_rate*100:.1f}%"
            })
        elif metrics.success_rate < self.ALERT_THRESHOLDS['success_rate_warning']:
            alerts.append({
                'type': 'degraded_success_rate',
                'severity': 'warning',
                'message': f"Success rate: {metrics.success_rate*100:.1f}%"
            })

        # Check response time
        if metrics.avg_response_time > self.ALERT_THRESHOLDS['response_time_critical']:
            alerts.append({
                'type': 'high_response_time',
                'severity': 'critical',
                'message': f"Avg response time: {metrics.avg_response_time:.0f}ms"
            })

        # Send alerts
        for alert in alerts:
            self._send_alert(api_name, alert)

    def _send_alert(self, api_name: str, alert: Dict):
        """
        Send health degradation alert.

        Args:
            api_name: API identifier
            alert: Alert information
        """
        if not self.alert_callback:
            return

        metrics = self.metrics[api_name]

        alert_data = {
            'api_name': api_name,
            'alert_type': alert['type'],
            'severity': alert['severity'],
            'message': alert['message'],
            'status': metrics.status.value,
            'success_rate': metrics.success_rate,
            'avg_response_time': metrics.avg_response_time,
            'consecutive_failures': metrics.consecutive_failures,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        try:
            self.alert_callback(alert_data)
            logger.warning(f"[{api_name}] Health alert sent: {alert['message']}")
        except Exception as e:
            logger.error(f"Failed to send health alert: {str(e)}")

    async def start_monitoring(self, apis: Optional[List[str]] = None):
        """
        Start periodic health monitoring.

        Args:
            apis: List of APIs to monitor, or None for all
        """
        if self.is_running:
            logger.warning("Health monitoring already running")
            return

        self.is_running = True
        apis_to_monitor = apis or list(self.HEALTH_ENDPOINTS.keys())

        logger.info(f"Starting health monitoring for {len(apis_to_monitor)} APIs")

        for api_name in apis_to_monitor:
            task = asyncio.create_task(self._monitor_loop(api_name))
            self.monitoring_tasks[api_name] = task

    async def _monitor_loop(self, api_name: str):
        """
        Continuous monitoring loop for API.

        Args:
            api_name: API identifier
        """
        config = self.HEALTH_ENDPOINTS[api_name]
        check_interval = config['check_interval']

        logger.info(f"[{api_name}] Starting health monitoring (interval: {check_interval}s)")

        while self.is_running:
            try:
                await self.check_health(api_name)
            except Exception as e:
                logger.error(f"[{api_name}] Health check error: {str(e)}")

            await asyncio.sleep(check_interval)

    async def stop_monitoring(self):
        """Stop health monitoring"""
        logger.info("Stopping health monitoring")
        self.is_running = False

        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()

        # Wait for tasks to finish
        await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)

        self.monitoring_tasks = {}
        logger.info("Health monitoring stopped")

    def get_health_status(self, api_name: Optional[str] = None) -> Dict:
        """
        Get health status for dashboard.

        Args:
            api_name: Specific API or None for all

        Returns:
            Health status data
        """
        if api_name:
            if api_name not in self.metrics:
                return {}
            return self.metrics[api_name].to_dict()

        # All APIs
        return {
            'summary': {
                'total_apis': len(self.metrics),
                'healthy': sum(1 for m in self.metrics.values() if m.status == HealthStatus.HEALTHY),
                'degraded': sum(1 for m in self.metrics.values() if m.status == HealthStatus.DEGRADED),
                'unhealthy': sum(1 for m in self.metrics.values() if m.status == HealthStatus.UNHEALTHY),
                'unknown': sum(1 for m in self.metrics.values() if m.status == HealthStatus.UNKNOWN)
            },
            'apis': {
                api: metrics.to_dict()
                for api, metrics in self.metrics.items()
            }
        }

    def get_response_time_history(
        self,
        api_name: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get response time history for charts.

        Args:
            api_name: API identifier
            limit: Maximum data points

        Returns:
            Response time history
        """
        if api_name not in self.metrics:
            return []

        checks = self.metrics[api_name].recent_checks[-limit:]
        return [
            {
                'timestamp': c.timestamp.isoformat(),
                'response_time_ms': c.response_time_ms,
                'success': c.success
            }
            for c in checks
        ]


# Example alert callback

def health_alert_callback(alert_data: Dict):
    """
    Example health alert callback.

    Args:
        alert_data: Alert information
    """
    logger.critical(
        f"HEALTH ALERT [{alert_data['severity'].upper()}]: "
        f"{alert_data['api_name']} - {alert_data['message']}"
    )
    # Would send email/Slack/webhook
    pass


# Global singleton
_health_checker: Optional[APIHealthChecker] = None


def get_health_checker() -> APIHealthChecker:
    """Get global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = APIHealthChecker()
    return _health_checker
