"""
Metrics and monitoring service
"""
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict, deque

from app.core.config import settings
from app.core.logging import log_module_event, log_security_event


@dataclass
class MetricData:
    """Individual metric data point"""

    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class RequestMetrics:
    """Request-related metrics"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    total_tokens_used: int = 0
    total_cost: float = 0.0
    requests_by_model: Dict[str, int] = field(default_factory=dict)
    requests_by_user: Dict[str, int] = field(default_factory=dict)
    requests_by_endpoint: Dict[str, int] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System-related metrics"""

    uptime: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    active_connections: int = 0
    module_status: Dict[str, bool] = field(default_factory=dict)


class MetricsService:
    """Service for collecting and managing metrics"""

    def __init__(self):
        self.request_metrics = RequestMetrics()
        self.system_metrics = SystemMetrics()
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.start_time = time.time()
        self.response_times: deque = deque(maxlen=100)  # Keep last 100 response times
        self.active_requests: Dict[str, float] = {}  # Track active requests

    async def initialize(self):
        """Initialize the metrics service"""
        log_module_event("metrics_service", "initializing", {})
        self.start_time = time.time()

        # Start background tasks
        asyncio.create_task(self._collect_system_metrics())
        asyncio.create_task(self._cleanup_old_metrics())

        log_module_event("metrics_service", "initialized", {"success": True})

    async def _collect_system_metrics(self):
        """Collect system metrics periodically"""
        while True:
            try:
                # Update uptime
                self.system_metrics.uptime = time.time() - self.start_time

                # Update active connections
                self.system_metrics.active_connections = len(self.active_requests)

                # Store historical data
                self._store_metric("uptime", self.system_metrics.uptime)
                self._store_metric(
                    "active_connections", self.system_metrics.active_connections
                )

                await asyncio.sleep(60)  # Collect every minute

            except Exception as e:
                log_module_event(
                    "metrics_service", "system_metrics_error", {"error": str(e)}
                )
                await asyncio.sleep(60)

    async def _cleanup_old_metrics(self):
        """Clean up old metric data"""
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=24)

                for metric_name, metric_data in self.metric_history.items():
                    # Remove old data points
                    while metric_data and metric_data[0].timestamp < cutoff_time:
                        metric_data.popleft()

                await asyncio.sleep(3600)  # Clean up every hour

            except Exception as e:
                log_module_event("metrics_service", "cleanup_error", {"error": str(e)})
                await asyncio.sleep(3600)

    def _store_metric(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ):
        """Store a metric data point"""
        if labels is None:
            labels = {}

        metric_data = MetricData(timestamp=datetime.now(), value=value, labels=labels)

        self.metric_history[name].append(metric_data)

    def start_request(
        self, request_id: str, endpoint: str, user_id: Optional[str] = None
    ):
        """Start tracking a request"""
        self.active_requests[request_id] = time.time()

        # Update request metrics
        self.request_metrics.total_requests += 1

        # Track by endpoint
        self.request_metrics.requests_by_endpoint[endpoint] = (
            self.request_metrics.requests_by_endpoint.get(endpoint, 0) + 1
        )

        # Track by user
        if user_id:
            self.request_metrics.requests_by_user[user_id] = (
                self.request_metrics.requests_by_user.get(user_id, 0) + 1
            )

        # Store metric
        self._store_metric("requests_total", self.request_metrics.total_requests)
        self._store_metric("requests_by_endpoint", 1, {"endpoint": endpoint})

        if user_id:
            self._store_metric("requests_by_user", 1, {"user_id": user_id})

    def end_request(
        self,
        request_id: str,
        success: bool = True,
        model: Optional[str] = None,
        tokens_used: int = 0,
        cost: float = 0.0,
    ):
        """End tracking a request"""
        if request_id not in self.active_requests:
            return

        # Calculate response time
        response_time = time.time() - self.active_requests[request_id]
        self.response_times.append(response_time)

        # Update metrics
        if success:
            self.request_metrics.successful_requests += 1
        else:
            self.request_metrics.failed_requests += 1

        # Update average response time
        if self.response_times:
            self.request_metrics.average_response_time = sum(self.response_times) / len(
                self.response_times
            )

        # Update token and cost metrics
        self.request_metrics.total_tokens_used += tokens_used
        self.request_metrics.total_cost += cost

        # Track by model
        if model:
            self.request_metrics.requests_by_model[model] = (
                self.request_metrics.requests_by_model.get(model, 0) + 1
            )

        # Store metrics
        self._store_metric("response_time", response_time)
        self._store_metric("tokens_used", tokens_used)
        self._store_metric("cost", cost)

        if model:
            self._store_metric("requests_by_model", 1, {"model": model})

        # Clean up
        del self.active_requests[request_id]

    def record_error(
        self,
        error_type: str,
        error_message: str,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Record an error occurrence"""
        labels = {"error_type": error_type}

        if endpoint:
            labels["endpoint"] = endpoint
        if user_id:
            labels["user_id"] = user_id

        self._store_metric("errors_total", 1, labels)

        # Log security events for authentication/authorization errors
        if error_type in [
            "authentication_failed",
            "authorization_failed",
            "invalid_api_key",
        ]:
            log_security_event(
                error_type,
                user_id or "anonymous",
                {"error": error_message, "endpoint": endpoint},
            )

    def record_module_status(self, module_name: str, is_healthy: bool):
        """Record module health status"""
        self.system_metrics.module_status[module_name] = is_healthy
        self._store_metric(
            "module_health", 1 if is_healthy else 0, {"module": module_name}
        )

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            "request_metrics": {
                "total_requests": self.request_metrics.total_requests,
                "successful_requests": self.request_metrics.successful_requests,
                "failed_requests": self.request_metrics.failed_requests,
                "success_rate": (
                    self.request_metrics.successful_requests
                    / self.request_metrics.total_requests
                    if self.request_metrics.total_requests > 0
                    else 0
                ),
                "average_response_time": self.request_metrics.average_response_time,
                "total_tokens_used": self.request_metrics.total_tokens_used,
                "total_cost": self.request_metrics.total_cost,
                "requests_by_model": dict(self.request_metrics.requests_by_model),
                "requests_by_user": dict(self.request_metrics.requests_by_user),
                "requests_by_endpoint": dict(self.request_metrics.requests_by_endpoint),
            },
            "system_metrics": {
                "uptime": self.system_metrics.uptime,
                "active_connections": self.system_metrics.active_connections,
                "module_status": dict(self.system_metrics.module_status),
            },
        }

    def get_metrics_history(
        self, metric_name: str, hours: int = 1
    ) -> List[Dict[str, Any]]:
        """Get historical metrics data"""
        if metric_name not in self.metric_history:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)

        return [
            {
                "timestamp": data.timestamp.isoformat(),
                "value": data.value,
                "labels": data.labels,
            }
            for data in self.metric_history[metric_name]
            if data.timestamp > cutoff_time
        ]

    def get_top_metrics(self, metric_type: str, limit: int = 10) -> Dict[str, Any]:
        """Get top metrics by type"""
        if metric_type == "models":
            return dict(
                sorted(
                    self.request_metrics.requests_by_model.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:limit]
            )
        elif metric_type == "users":
            return dict(
                sorted(
                    self.request_metrics.requests_by_user.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:limit]
            )
        elif metric_type == "endpoints":
            return dict(
                sorted(
                    self.request_metrics.requests_by_endpoint.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:limit]
            )
        else:
            return {}

    def get_health_check(self) -> Dict[str, Any]:
        """Get health check information"""
        return {
            "status": "healthy",
            "uptime": self.system_metrics.uptime,
            "active_connections": self.system_metrics.active_connections,
            "total_requests": self.request_metrics.total_requests,
            "success_rate": (
                self.request_metrics.successful_requests
                / self.request_metrics.total_requests
                if self.request_metrics.total_requests > 0
                else 1.0
            ),
            "modules": self.system_metrics.module_status,
            "timestamp": datetime.now().isoformat(),
        }

    async def reset_metrics(self):
        """Reset all metrics (for testing purposes)"""
        self.request_metrics = RequestMetrics()
        self.system_metrics = SystemMetrics()
        self.metric_history.clear()
        self.response_times.clear()
        self.active_requests.clear()
        self.start_time = time.time()

        log_module_event("metrics_service", "metrics_reset", {"success": True})


# Global metrics service instance
metrics_service = MetricsService()


def setup_metrics(app):
    """Setup metrics service with FastAPI app"""
    # Store metrics service in app state
    app.state.metrics_service = metrics_service

    # Initialize metrics service
    import asyncio

    asyncio.create_task(metrics_service.initialize())
