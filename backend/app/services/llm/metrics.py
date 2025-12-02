"""
LLM Service Metrics Collection

Collects and manages metrics for LLM operations.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading

from .models import LLMMetrics

logger = logging.getLogger(__name__)


@dataclass
class RequestMetric:
    """Individual request metric"""

    timestamp: datetime
    provider: str
    model: str
    request_type: str  # chat, embedding, etc.
    success: bool
    latency_ms: float
    token_usage: Optional[Dict[str, int]] = None
    security_risk_score: float = 0.0
    error_code: Optional[str] = None
    user_id: Optional[str] = None
    api_key_id: Optional[int] = None


class MetricsCollector:
    """Collects and aggregates LLM service metrics"""

    def __init__(self, max_history_size: int = 10000):
        """
        Initialize metrics collector

        Args:
            max_history_size: Maximum number of metrics to keep in memory
        """
        self.max_history_size = max_history_size
        self._metrics: deque = deque(maxlen=max_history_size)
        self._provider_metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._lock = threading.RLock()

        # Aggregated metrics cache
        self._cache_timestamp: Optional[datetime] = None
        self._cached_metrics: Optional[LLMMetrics] = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute

        logger.info(
            f"Metrics collector initialized with max history: {max_history_size}"
        )

    def record_request(
        self,
        provider: str,
        model: str,
        request_type: str,
        success: bool,
        latency_ms: float,
        token_usage: Optional[Dict[str, int]] = None,
        security_risk_score: float = 0.0,
        error_code: Optional[str] = None,
        user_id: Optional[str] = None,
        api_key_id: Optional[int] = None,
    ):
        """Record a request metric"""
        metric = RequestMetric(
            timestamp=datetime.utcnow(),
            provider=provider,
            model=model,
            request_type=request_type,
            success=success,
            latency_ms=latency_ms,
            token_usage=token_usage,
            security_risk_score=security_risk_score,
            error_code=error_code,
            user_id=user_id,
            api_key_id=api_key_id,
        )

        with self._lock:
            self._metrics.append(metric)
            self._provider_metrics[provider].append(metric)

            # Invalidate cache
            self._cached_metrics = None
            self._cache_timestamp = None

        # Log significant events
        if not success:
            logger.warning(
                f"Request failed: {provider}/{model} - {error_code or 'Unknown error'}"
            )
        elif security_risk_score > 0.6:
            logger.info(
                f"High risk request: {provider}/{model} - risk score: {security_risk_score:.3f}"
            )

    def get_metrics(self, force_refresh: bool = False) -> LLMMetrics:
        """Get aggregated metrics"""
        with self._lock:
            # Check cache validity
            if (
                not force_refresh
                and self._cached_metrics
                and self._cache_timestamp
                and (datetime.utcnow() - self._cache_timestamp).total_seconds()
                < self._cache_ttl_seconds
            ):
                return self._cached_metrics

            # Calculate fresh metrics
            metrics = self._calculate_metrics()

            # Cache results
            self._cached_metrics = metrics
            self._cache_timestamp = datetime.utcnow()

            return metrics

    def _calculate_metrics(self) -> LLMMetrics:
        """Calculate aggregated metrics from recorded data"""
        if not self._metrics:
            return LLMMetrics()

        total_requests = len(self._metrics)
        successful_requests = sum(1 for m in self._metrics if m.success)
        failed_requests = total_requests - successful_requests

        # Calculate averages
        latencies = [m.latency_ms for m in self._metrics if m.latency_ms > 0]
        risk_scores = [m.security_risk_score for m in self._metrics]

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0

        # Provider-specific metrics
        provider_metrics = {}
        for provider, provider_data in self._provider_metrics.items():
            if provider_data:
                provider_metrics[provider] = self._calculate_provider_metrics(
                    provider_data
                )

        return LLMMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_latency_ms=avg_latency,
            average_risk_score=avg_risk_score,
            provider_metrics=provider_metrics,
            last_updated=datetime.utcnow(),
        )

    def _calculate_provider_metrics(self, provider_data: deque) -> Dict[str, Any]:
        """Calculate metrics for a specific provider"""
        if not provider_data:
            return {}

        total = len(provider_data)
        successful = sum(1 for m in provider_data if m.success)
        failed = total - successful

        latencies = [m.latency_ms for m in provider_data if m.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # Token usage aggregation
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0

        for metric in provider_data:
            if metric.token_usage:
                total_prompt_tokens += metric.token_usage.get("prompt_tokens", 0)
                total_completion_tokens += metric.token_usage.get(
                    "completion_tokens", 0
                )
                total_tokens += metric.token_usage.get("total_tokens", 0)

        # Model distribution
        model_counts = defaultdict(int)
        for metric in provider_data:
            model_counts[metric.model] += 1

        # Request type distribution
        request_type_counts = defaultdict(int)
        for metric in provider_data:
            request_type_counts[metric.request_type] += 1

        # Error analysis
        error_counts = defaultdict(int)
        for metric in provider_data:
            if not metric.success and metric.error_code:
                error_counts[metric.error_code] += 1

        return {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": successful / total if total > 0 else 0.0,
            "average_latency_ms": avg_latency,
            "token_usage": {
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "avg_prompt_tokens": total_prompt_tokens / total if total > 0 else 0,
                "avg_completion_tokens": total_completion_tokens / successful
                if successful > 0
                else 0,
            },
            "model_distribution": dict(model_counts),
            "request_type_distribution": dict(request_type_counts),
            "error_distribution": dict(error_counts),
            "recent_requests": total,
        }

    def get_provider_metrics(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific provider"""
        with self._lock:
            if provider not in self._provider_metrics:
                return None

            return self._calculate_provider_metrics(self._provider_metrics[provider])

    def get_recent_metrics(self, minutes: int = 5) -> List[RequestMetric]:
        """Get metrics from the last N minutes"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        with self._lock:
            return [m for m in self._metrics if m.timestamp >= cutoff_time]

    def get_error_metrics(self, hours: int = 1) -> Dict[str, int]:
        """Get error distribution from the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        error_counts = defaultdict(int)

        with self._lock:
            for metric in self._metrics:
                if (
                    metric.timestamp >= cutoff_time
                    and not metric.success
                    and metric.error_code
                ):
                    error_counts[metric.error_code] += 1

        return dict(error_counts)

    def get_performance_metrics(self, minutes: int = 15) -> Dict[str, Dict[str, float]]:
        """Get performance metrics by provider from the last N minutes"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        provider_perf = defaultdict(list)

        with self._lock:
            for metric in self._metrics:
                if metric.timestamp >= cutoff_time and metric.success:
                    provider_perf[metric.provider].append(metric.latency_ms)

        performance = {}
        for provider, latencies in provider_perf.items():
            if latencies:
                performance[provider] = {
                    "avg_latency_ms": sum(latencies) / len(latencies),
                    "min_latency_ms": min(latencies),
                    "max_latency_ms": max(latencies),
                    "p95_latency_ms": self._percentile(latencies, 95),
                    "p99_latency_ms": self._percentile(latencies, 99),
                    "request_count": len(latencies),
                }

        return performance

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list of numbers"""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def clear_metrics(self):
        """Clear all metrics (use with caution)"""
        with self._lock:
            self._metrics.clear()
            self._provider_metrics.clear()
            self._cached_metrics = None
            self._cache_timestamp = None

        logger.info("All metrics cleared")

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a health summary for monitoring"""
        metrics = self.get_metrics()
        recent_metrics = self.get_recent_metrics(minutes=5)
        error_metrics = self.get_error_metrics(hours=1)

        # Calculate health scores
        total_recent = len(recent_metrics)
        successful_recent = sum(1 for m in recent_metrics if m.success)
        success_rate = successful_recent / total_recent if total_recent > 0 else 1.0

        # Determine health status
        if success_rate >= 0.95:
            health_status = "healthy"
        elif success_rate >= 0.80:
            health_status = "degraded"
        else:
            health_status = "unhealthy"

        return {
            "health_status": health_status,
            "success_rate_5min": success_rate,
            "total_requests_5min": total_recent,
            "average_latency_ms": metrics.average_latency_ms,
            "error_count_1hour": sum(error_metrics.values()),
            "top_errors": dict(
                sorted(error_metrics.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "provider_count": len(metrics.provider_metrics),
            "last_updated": datetime.utcnow().isoformat(),
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()
