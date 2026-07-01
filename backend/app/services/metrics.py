"""
Prometheus Metrics Service for Token Stats System

Provides comprehensive metrics collection for:
- Usage tracking (requests, tokens, costs, latency)
- Budget monitoring
- Pricing sync operations
- API key status

Thread-safe singleton implementation using prometheus_client.
"""

import os
from typing import Optional

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.multiprocess import MultiProcessCollector

from app.core.logging import get_logger

logger = get_logger(__name__)


class MetricsService:
    """
    Singleton service for collecting and exposing Prometheus metrics.

    All metrics are prefixed with 'enclava_' to avoid collisions.
    Thread-safe implementation suitable for async FastAPI applications.
    """

    _instance: Optional["MetricsService"] = None
    _initialized: bool = False

    def __new__(cls):
        """Ensure singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize metrics collectors (only once)"""
        if self._initialized:
            return

        # Check if we're in a multiprocess environment (Gunicorn, etc.)
        if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
            self.registry = CollectorRegistry()
            MultiProcessCollector(self.registry)
        else:
            self.registry = CollectorRegistry()

        # Usage Metrics
        self.usage_requests_total = Counter(
            "enclava_usage_requests_total",
            "Total number of LLM requests",
            ["provider", "model", "status"],
            registry=self.registry,
        )

        self.usage_tokens_total = Counter(
            "enclava_usage_tokens_total",
            "Total tokens processed",
            ["provider", "model", "type"],
            registry=self.registry,
        )

        self.usage_cost_cents_total = Counter(
            "enclava_usage_cost_cents_total",
            "Total cost in cents",
            ["provider", "model"],
            registry=self.registry,
        )

        self.usage_latency_seconds = Histogram(
            "enclava_usage_latency_seconds",
            "Request latency distribution in seconds",
            ["provider", "model"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry,
        )

        self.usage_ttft_seconds = Histogram(
            "enclava_usage_ttft_seconds",
            "Time to first token distribution in seconds (streaming only)",
            ["provider", "model"],
            buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry,
        )

        self.usage_errors_total = Counter(
            "enclava_usage_errors_total",
            "Total errors by type",
            ["provider", "model", "error_type"],
            registry=self.registry,
        )

        # Budget Metrics
        self.budget_usage_cents = Gauge(
            "enclava_budget_usage_cents",
            "Current budget usage in cents",
            ["budget_id", "budget_name", "user_id"],
            registry=self.registry,
        )

        self.budget_limit_cents = Gauge(
            "enclava_budget_limit_cents",
            "Budget limit in cents",
            ["budget_id", "budget_name", "user_id"],
            registry=self.registry,
        )

        self.budget_remaining_cents = Gauge(
            "enclava_budget_remaining_cents",
            "Remaining budget in cents",
            ["budget_id", "budget_name", "user_id"],
            registry=self.registry,
        )

        self.budget_exceeded_total = Counter(
            "enclava_budget_exceeded_total",
            "Total budget exceeded events",
            ["budget_id", "budget_name", "user_id"],
            registry=self.registry,
        )

        # Pricing Sync Metrics
        self.pricing_sync_duration_seconds = Histogram(
            "enclava_pricing_sync_duration_seconds",
            "Pricing sync operation duration in seconds",
            ["provider"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
            registry=self.registry,
        )

        self.pricing_sync_models_total = Counter(
            "enclava_pricing_sync_models_total",
            "Models synced by result type",
            ["provider", "result"],
            registry=self.registry,
        )

        self.pricing_sync_last_success_timestamp = Gauge(
            "enclava_pricing_sync_last_success_timestamp",
            "Timestamp of last successful sync",
            ["provider"],
            registry=self.registry,
        )

        self.pricing_sync_failures_total = Counter(
            "enclava_pricing_sync_failures_total",
            "Total pricing sync failures",
            ["provider"],
            registry=self.registry,
        )

        # API Key Metrics
        self.api_keys_active_total = Gauge(
            "enclava_api_keys_active_total",
            "Number of active API keys",
            registry=self.registry,
        )

        self.api_keys_deleted_total = Gauge(
            "enclava_api_keys_deleted_total",
            "Number of soft-deleted API keys",
            registry=self.registry,
        )

        self._initialized = True
        logger.info("Prometheus metrics service initialized successfully")

    def record_usage(
        self,
        provider: str,
        model: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        cost_cents: int,
        latency_ms: Optional[int] = None,
        ttft_ms: Optional[int] = None,
        error_type: Optional[str] = None,
    ):
        """
        Record usage metrics for a completed request.

        Args:
            provider: Provider identifier (e.g., 'privatemode', 'openai')
            model: Normalized model name
            status: Request status ('success', 'error', 'timeout', etc.)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_cents: Total cost in cents
            latency_ms: Request latency in milliseconds
            ttft_ms: Time to first token in milliseconds (streaming only)
            error_type: Error type if status is 'error'
        """
        try:
            # Record request
            self.usage_requests_total.labels(
                provider=provider, model=model, status=status
            ).inc()

            # Record tokens
            if input_tokens > 0:
                self.usage_tokens_total.labels(
                    provider=provider, model=model, type="input"
                ).inc(input_tokens)

            if output_tokens > 0:
                self.usage_tokens_total.labels(
                    provider=provider, model=model, type="output"
                ).inc(output_tokens)

            # Record cost
            if cost_cents > 0:
                self.usage_cost_cents_total.labels(provider=provider, model=model).inc(
                    cost_cents
                )

            # Record latency
            if latency_ms is not None:
                self.usage_latency_seconds.labels(
                    provider=provider, model=model
                ).observe(latency_ms / 1000.0)

            # Record TTFT (streaming only)
            if ttft_ms is not None:
                self.usage_ttft_seconds.labels(provider=provider, model=model).observe(
                    ttft_ms / 1000.0
                )

            # Record errors
            if status == "error" and error_type:
                self.usage_errors_total.labels(
                    provider=provider, model=model, error_type=error_type
                ).inc()

        except Exception as e:
            logger.error(f"Error recording usage metrics: {e}")

    def record_budget_usage(
        self,
        budget_id: int,
        budget_name: str,
        user_id: int,
        usage_cents: int,
        limit_cents: int,
    ):
        """
        Update budget usage metrics.

        Args:
            budget_id: Budget identifier
            budget_name: Budget name for display
            user_id: User who owns the budget
            usage_cents: Current usage in cents
            limit_cents: Budget limit in cents
        """
        try:
            labels = {
                "budget_id": str(budget_id),
                "budget_name": budget_name,
                "user_id": str(user_id),
            }

            self.budget_usage_cents.labels(**labels).set(usage_cents)
            self.budget_limit_cents.labels(**labels).set(limit_cents)
            self.budget_remaining_cents.labels(**labels).set(
                max(0, limit_cents - usage_cents)
            )

        except Exception as e:
            logger.error(f"Error recording budget usage metrics: {e}")

    def record_budget_exceeded(self, budget_id: int, budget_name: str, user_id: int):
        """
        Record a budget exceeded event.

        Args:
            budget_id: Budget identifier
            budget_name: Budget name
            user_id: User who owns the budget
        """
        try:
            self.budget_exceeded_total.labels(
                budget_id=str(budget_id),
                budget_name=budget_name,
                user_id=str(user_id),
            ).inc()

        except Exception as e:
            logger.error(f"Error recording budget exceeded event: {e}")

    def record_pricing_sync(
        self,
        provider: str,
        duration_seconds: float,
        created_count: int = 0,
        updated_count: int = 0,
        unchanged_count: int = 0,
        error_count: int = 0,
        success: bool = True,
    ):
        """
        Record pricing sync operation metrics.

        Args:
            provider: Provider identifier
            duration_seconds: Sync duration in seconds
            created_count: Number of models created
            updated_count: Number of models updated
            unchanged_count: Number of models unchanged
            error_count: Number of errors encountered
            success: Whether the sync completed successfully
        """
        try:
            # Record duration
            self.pricing_sync_duration_seconds.labels(provider=provider).observe(
                duration_seconds
            )

            # Record model counts by result
            if created_count > 0:
                self.pricing_sync_models_total.labels(
                    provider=provider, result="created"
                ).inc(created_count)

            if updated_count > 0:
                self.pricing_sync_models_total.labels(
                    provider=provider, result="updated"
                ).inc(updated_count)

            if unchanged_count > 0:
                self.pricing_sync_models_total.labels(
                    provider=provider, result="unchanged"
                ).inc(unchanged_count)

            if error_count > 0:
                self.pricing_sync_models_total.labels(
                    provider=provider, result="error"
                ).inc(error_count)

            # Update last success timestamp
            if success:
                import time

                self.pricing_sync_last_success_timestamp.labels(provider=provider).set(
                    time.time()
                )
            else:
                self.pricing_sync_failures_total.labels(provider=provider).inc()

        except Exception as e:
            logger.error(f"Error recording pricing sync metrics: {e}")

    def update_api_key_counts(self, active_count: int, deleted_count: int):
        """
        Update API key count metrics.

        Args:
            active_count: Number of active API keys
            deleted_count: Number of soft-deleted API keys
        """
        try:
            self.api_keys_active_total.set(active_count)
            self.api_keys_deleted_total.set(deleted_count)

        except Exception as e:
            logger.error(f"Error updating API key metrics: {e}")

    def get_metrics(self) -> bytes:
        """
        Generate Prometheus metrics in text format.

        Returns:
            Metrics data as bytes in Prometheus format
        """
        try:
            return generate_latest(self.registry)
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return b""

    def get_content_type(self) -> str:
        """
        Get the content type for metrics response.

        Returns:
            Content type string for HTTP response
        """
        return CONTENT_TYPE_LATEST


# Singleton instance
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """
    Get or create the metrics service singleton.

    Returns:
        MetricsService instance
    """
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service


def setup_metrics(app):
    """
    Setup Prometheus metrics endpoint for the FastAPI application.

    Adds a /metrics endpoint that Prometheus can scrape.

    Args:
        app: FastAPI application instance
    """
    from fastapi import Response

    # Initialize the metrics service
    metrics_service = get_metrics_service()

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        """Prometheus metrics endpoint"""
        metrics_data = metrics_service.get_metrics()
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

    logger.info("Prometheus metrics endpoint setup at /metrics")
