"""
Usage Recording Service for tracking LLM request usage

This service is responsible for:
- Creating UsageRecord entries for every LLM request
- Calculating costs using the PricingService
- Recording both successful and failed requests

This is the source of truth for billing and must be called
for every LLM request regardless of success/failure.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import utc_now
from app.models.usage_record import UsageRecord
from app.services.metrics import get_metrics_service
from app.services.pricing import PricingService

logger = get_logger(__name__)


class UsageRecordingService:
    """
    Records every LLM request with full token and cost attribution.
    This is the source of truth for billing.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the usage recording service.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db
        self.pricing_service = PricingService(db)

    async def record_request(
        self,
        # Identity
        request_id: Optional[UUID] = None,
        user_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        # Provider
        provider_id: str = "privatemode",
        provider_model: str = "",
        # Tokens
        input_tokens: int = 0,
        output_tokens: int = 0,
        # Context
        endpoint: str = "",
        method: str = "POST",
        agent_config_id: Optional[int] = None,
        session_id: Optional[str] = None,
        # Characteristics
        is_streaming: bool = False,
        is_tool_calling: bool = False,
        message_count: int = 0,
        # Performance
        latency_ms: Optional[int] = None,
        ttft_ms: Optional[int] = None,
        # Status
        status: str = "success",
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        # Client
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UsageRecord:
        """
        Record a single LLM request with all metrics.

        This method MUST be called for every LLM request:
        - Successful completions
        - Failed requests (for debugging and rate tracking)
        - Budget-exceeded requests (status='budget_exceeded')
        - Timeouts (status='timeout')

        Args:
            request_id: Unique request identifier (generated if not provided)
            user_id: User ID making the request
            api_key_id: API key ID used for the request (optional for JWT auth)
            provider_id: LLM provider identifier
            provider_model: Full model name from provider
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
            endpoint: API endpoint path
            method: HTTP method
            agent_config_id: Agent config ID if request is via agent
            session_id: Session ID for conversation grouping
            is_streaming: Whether streaming was used
            is_tool_calling: Whether tools/functions were used
            message_count: Number of messages in the request
            latency_ms: Total request latency in milliseconds
            ttft_ms: Time to first token in milliseconds (streaming only)
            status: Request status (success, error, timeout, budget_exceeded)
            error_type: Error classification if failed
            error_message: Error message if failed
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            The created UsageRecord

        Raises:
            ValueError: If neither user_id nor api_key_id is provided
        """
        # Generate request_id if not provided
        if request_id is None:
            request_id = uuid4()

        # Validate we have at least one identifier
        if user_id is None and api_key_id is None:
            raise ValueError("Either user_id or api_key_id must be provided")

        # Get pricing information
        pricing = await self.pricing_service.get_pricing(provider_id, provider_model)

        # Calculate costs using ceiling division
        input_cost_cents, output_cost_cents, total_cost_cents = (
            self.pricing_service.calculate_cost_cents(
                input_tokens,
                output_tokens,
                pricing,
            )
        )

        # Normalize model name for consistent reporting
        normalized_model = self.pricing_service.normalize_model(provider_model)

        # Create the usage record
        record = UsageRecord(
            request_id=request_id,
            user_id=user_id,
            api_key_id=api_key_id,
            provider_id=provider_id,
            provider_model=provider_model,
            normalized_model=normalized_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_cents=input_cost_cents,
            output_cost_cents=output_cost_cents,
            total_cost_cents=total_cost_cents,
            input_price_per_million_cents=pricing.input_price_per_million_cents,
            output_price_per_million_cents=pricing.output_price_per_million_cents,
            pricing_source=pricing.price_source,
            pricing_effective_from=pricing.effective_from,
            endpoint=endpoint,
            method=method,
            agent_config_id=agent_config_id,
            session_id=session_id,
            is_streaming=is_streaming,
            is_tool_calling=is_tool_calling,
            message_count=message_count,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            status=status,
            error_type=error_type,
            error_message=(
                error_message[:1000] if error_message else None
            ),  # Truncate long errors
            ip_address=ip_address,
            user_agent=(
                user_agent[:500] if user_agent else None
            ),  # Truncate long user agents
            created_at=utc_now(),  # Naive datetime for DB compatibility
        )

        # Add to session
        self.db.add(record)

        # Flush to get ID without committing (caller manages transaction)
        await self.db.flush()

        logger.debug(
            f"Recorded usage: request_id={request_id}, "
            f"provider={provider_id}, model={normalized_model}, "
            f"tokens={input_tokens}+{output_tokens}={input_tokens + output_tokens}, "
            f"cost_cents={total_cost_cents}, status={status}"
        )

        # Record metrics for Prometheus
        try:
            metrics_service = get_metrics_service()
            metrics_service.record_usage(
                provider=provider_id,
                model=normalized_model,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_cents=total_cost_cents,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                error_type=error_type,
            )
        except Exception as e:
            # Don't fail the request if metrics recording fails
            logger.error(f"Failed to record usage metrics: {e}")

        return record

    async def record_error(
        self,
        user_id: Optional[int],
        api_key_id: Optional[int],
        provider_id: str,
        model: str,
        endpoint: str,
        error: Exception,
        latency_ms: int,
        request_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        message_count: int = 0,
        is_streaming: bool = False,
    ) -> UsageRecord:
        """
        Convenience method to record a failed request.

        Args:
            user_id: User ID
            api_key_id: API key ID
            provider_id: Provider identifier
            model: Model name
            endpoint: API endpoint
            error: The exception that occurred
            latency_ms: Request latency
            request_id: Request ID (generated if not provided)
            ip_address: Client IP
            user_agent: Client user agent
            message_count: Number of messages in request
            is_streaming: Whether streaming was requested

        Returns:
            The created UsageRecord with error details
        """
        error_type = self._classify_error(error)

        return await self.record_request(
            request_id=request_id,
            user_id=user_id,
            api_key_id=api_key_id,
            provider_id=provider_id,
            provider_model=model,
            input_tokens=0,  # Unknown for failed requests
            output_tokens=0,
            endpoint=endpoint,
            status="error",
            error_type=error_type,
            error_message=str(error),
            latency_ms=latency_ms,
            ip_address=ip_address,
            user_agent=user_agent,
            message_count=message_count,
            is_streaming=is_streaming,
        )

    def _classify_error(self, error: Exception) -> str:
        """
        Classify an error into a standard error type.

        Args:
            error: The exception to classify

        Returns:
            Error type string
        """
        error_str = str(error).lower()
        error_class = error.__class__.__name__

        # Check for common error patterns
        if "rate limit" in error_str or "429" in error_str:
            return "rate_limit"
        if "timeout" in error_str or error_class == "TimeoutError":
            return "timeout"
        if "authentication" in error_str or "401" in error_str:
            return "auth_error"
        if "permission" in error_str or "403" in error_str:
            return "permission_error"
        if "not found" in error_str or "404" in error_str:
            return "not_found"
        if "validation" in error_str or error_class == "ValidationError":
            return "validation_error"
        if "budget" in error_str:
            return "budget_exceeded"
        if "provider" in error_str or error_class == "ProviderError":
            return "provider_error"
        if "connection" in error_str:
            return "connection_error"

        return "unknown_error"


# Convenience function for creating the service
def get_usage_recording_service(db: AsyncSession) -> UsageRecordingService:
    """
    Factory function to create UsageRecordingService.

    Args:
        db: Database session

    Returns:
        UsageRecordingService instance
    """
    return UsageRecordingService(db)
