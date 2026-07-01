"""
Provider Pricing Sync Service

Syncs model pricing from provider APIs (e.g., RedPill /v1/models)
and maintains pricing history in the database.
"""

import inspect
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.provider_pricing import PricingAuditLog, ProviderPricing
from app.services.alerts import get_alert_service
from app.services.metrics import get_metrics_service
from app.services.provider_registry import get_provider_currency

logger = get_logger(__name__)


@dataclass
class SyncResultModel:
    """Result for a single model sync"""

    model_id: str
    model_name: Optional[str]
    action: str  # 'created', 'updated', 'unchanged'
    old_input_price: Optional[int]
    old_output_price: Optional[int]
    new_input_price: int
    new_output_price: int


@dataclass
class SyncResult:
    """Result of a sync operation"""

    provider_id: str
    sync_job_id: uuid.UUID
    started_at: datetime
    completed_at: datetime
    total_models: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    error_count: int = 0
    models: List[SyncResultModel] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds"""
        return int((self.completed_at - self.started_at).total_seconds() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "provider_id": self.provider_id,
            "sync_job_id": str(self.sync_job_id),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "total_models": self.total_models,
            "created_count": self.created_count,
            "updated_count": self.updated_count,
            "unchanged_count": self.unchanged_count,
            "error_count": self.error_count,
            "models": [
                {
                    "model_id": m.model_id,
                    "model_name": m.model_name,
                    "action": m.action,
                    "old_input_price": m.old_input_price,
                    "old_output_price": m.old_output_price,
                    "new_input_price": m.new_input_price,
                    "new_output_price": m.new_output_price,
                }
                for m in self.models
            ],
            "errors": self.errors,
        }


class ProviderPricingSyncService:
    """
    Service for syncing pricing from provider APIs.

    Currently supports:
    - RedPill.ai: Fetches from /v1/models endpoint

    The service:
    1. Fetches model list from provider API
    2. Converts pricing to cents per million tokens
    3. Creates/updates ProviderPricing records
    4. Creates PricingAuditLog entries for all changes
    5. Marks old prices as effective_until when new prices arrive
    """

    # Provider-specific API configurations
    PROVIDER_CONFIGS = {
        "redpill": {
            "base_url": os.getenv("REDPILL_BASE_URL", "https://api.redpill.ai/v1"),
            "api_key_env": "REDPILL_API_KEY",
            "models_endpoint": "/models",
        },
    }

    def __init__(self, db: AsyncSession):
        """Initialize the sync service with a database session"""
        self.db = db

    async def sync_provider(self, provider_id: str) -> SyncResult:
        """
        Sync pricing from a provider API.

        Args:
            provider_id: Provider identifier (e.g., 'redpill')

        Returns:
            SyncResult with details of the sync operation

        Raises:
            ValueError: If provider is not configured for sync
        """
        if provider_id not in self.PROVIDER_CONFIGS:
            raise ValueError(f"Provider '{provider_id}' is not configured for API sync")

        sync_job_id = uuid.uuid4()
        started_at = datetime.now(timezone.utc)

        result = SyncResult(
            provider_id=provider_id,
            sync_job_id=sync_job_id,
            started_at=started_at,
            completed_at=started_at,  # Will be updated
        )

        logger.info(
            f"Starting pricing sync for provider '{provider_id}' (job: {sync_job_id})"
        )

        try:
            # Fetch models from provider API
            if provider_id == "redpill":
                models = await self._fetch_redpill_models()
            else:
                raise ValueError(
                    f"No fetch implementation for provider '{provider_id}'"
                )

            result.total_models = len(models)

            # Process each model
            for model_data in models:
                try:
                    model_result = await self._process_model(
                        provider_id=provider_id,
                        model_data=model_data,
                        sync_job_id=sync_job_id,
                    )

                    if model_result:
                        result.models.append(model_result)
                        if model_result.action == "created":
                            result.created_count += 1
                        elif model_result.action == "updated":
                            result.updated_count += 1
                        else:
                            result.unchanged_count += 1

                except Exception as e:
                    error_msg = f"Error processing model {model_data.get('id', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    result.error_count += 1

            # Commit all changes
            await self.db.commit()

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            await self.db.rollback()

        result.completed_at = datetime.now(timezone.utc)

        logger.info(
            f"Pricing sync completed for '{provider_id}': "
            f"created={result.created_count}, updated={result.updated_count}, "
            f"unchanged={result.unchanged_count}, errors={result.error_count}"
        )

        # Record metrics for Prometheus
        try:
            metrics_service = get_metrics_service()
            success = result.error_count == 0 and len(result.errors) == 0
            metrics_service.record_pricing_sync(
                provider=provider_id,
                duration_seconds=result.duration_ms / 1000.0,
                created_count=result.created_count,
                updated_count=result.updated_count,
                unchanged_count=result.unchanged_count,
                error_count=result.error_count,
                success=success,
            )

            # Send alert if sync failed
            if not success:
                alert_service = get_alert_service()
                error_summary = "; ".join(result.errors[:3])  # First 3 errors
                if len(result.errors) > 3:
                    error_summary += f"... and {len(result.errors) - 3} more"

                await alert_service.send_pricing_sync_failure_alert(
                    provider=provider_id,
                    error=error_summary,
                    duration_seconds=result.duration_ms / 1000.0,
                )
        except Exception as e:
            # Don't fail the sync if metrics/alerting fails
            logger.error(f"Failed to record pricing sync metrics/alerts: {e}")

        return result

    async def _fetch_redpill_models(self) -> List[Dict[str, Any]]:
        """
        Fetch model list from RedPill /v1/models endpoint.

        Returns:
            List of model dictionaries from the API

        Raises:
            Exception: If API request fails
        """
        config = self.PROVIDER_CONFIGS["redpill"]
        api_key = os.getenv(config["api_key_env"])

        if not api_key:
            raise ValueError(f"Missing API key: {config['api_key_env']}")

        url = f"{config['base_url']}{config['models_endpoint']}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"Fetching models from RedPill: {url}")

        fetch_error = None
        response_status = None
        response_text = None
        response_data = None

        session_context = aiohttp.ClientSession()
        session = (
            await session_context.__aenter__()
            if hasattr(session_context, "__aenter__")
            else session_context
        )

        try:
            request_context = session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            if inspect.isawaitable(request_context) and not hasattr(
                request_context, "__aenter__"
            ):
                request_context = await request_context

            if hasattr(request_context, "__aenter__"):
                response = await request_context.__aenter__()
                try:
                    if response is None:
                        raise Exception("RedPill API returned no response")

                    response_status = response.status
                    if inspect.isawaitable(response_status):
                        response_status = await response_status

                    if response_status != 200:
                        response_text = await response.text()
                    else:
                        response_data = await response.json()
                finally:
                    await request_context.__aexit__(None, None, None)
            else:
                response = request_context
                if response is None:
                    raise Exception("RedPill API returned no response")

                response_status = response.status
                if inspect.isawaitable(response_status):
                    response_status = await response_status

                if response_status != 200:
                    response_text = await response.text()
                else:
                    response_data = await response.json()

        except Exception as e:
            fetch_error = e
        finally:
            if hasattr(session_context, "__aexit__"):
                await session_context.__aexit__(None, None, None)
            else:
                close = getattr(session_context, "close", None)
                if close:
                    close_result = close()
                    if inspect.isawaitable(close_result):
                        await close_result

        if fetch_error:
            raise fetch_error

        if response_status != 200:
            raise Exception(
                f"RedPill API returned HTTP {response_status}: {response_text}"
            )

        # RedPill returns {"data": [...], "object": "list"}
        models = (response_data or {}).get("data", [])
        logger.info(f"Fetched {len(models)} models from RedPill API")

        return models

    def _convert_redpill_pricing(self, model: Dict[str, Any]) -> Tuple[int, int]:
        """
        Convert RedPill pricing format to cents per million tokens.

        RedPill pricing format (per their API):
        - pricing.completion: price per token for output (in USD)
        - pricing.prompt: price per token for input (in USD)

        OR simpler format:
        - pricing.input: price per million tokens (in USD)
        - pricing.output: price per million tokens (in USD)

        Args:
            model: Model data from RedPill API

        Returns:
            Tuple of (input_price_per_million_cents, output_price_per_million_cents)
        """
        pricing = model.get("pricing", {})

        # Try the per-million format first
        if "input" in pricing and "output" in pricing:
            # Price is per million tokens in dollars
            input_price_dollars = float(pricing.get("input", 0))
            output_price_dollars = float(pricing.get("output", 0))

            # Convert to cents per million
            input_cents = int(input_price_dollars * 100)
            output_cents = int(output_price_dollars * 100)

        elif "prompt" in pricing or "completion" in pricing:
            # Price is per token in dollars
            prompt_price = float(pricing.get("prompt", 0))
            completion_price = float(pricing.get("completion", 0))

            # Convert per-token dollars to per-million-token cents
            # per-token * 1,000,000 = per-million tokens in dollars
            # per-million dollars * 100 = per-million cents
            input_cents = int(prompt_price * 1_000_000 * 100)
            output_cents = int(completion_price * 1_000_000 * 100)

        else:
            # No pricing data available, use defaults
            logger.warning(
                f"No pricing data for model {model.get('id')}, using defaults"
            )
            input_cents = 100  # $1 per million
            output_cents = 200  # $2 per million

        return input_cents, output_cents

    async def _process_model(
        self,
        provider_id: str,
        model_data: Dict[str, Any],
        sync_job_id: uuid.UUID,
    ) -> Optional[SyncResultModel]:
        """
        Process a single model from the API response.

        Creates or updates the ProviderPricing record and creates
        an audit log entry.

        Args:
            provider_id: Provider identifier
            model_data: Model data from provider API
            sync_job_id: UUID of the current sync job

        Returns:
            SyncResultModel with the result of processing this model
        """
        model_id = model_data.get("id")
        if not model_id:
            logger.warning("Model data missing 'id' field, skipping")
            return None

        model_name = model_data.get("name")

        # Convert pricing
        input_price, output_price = self._convert_redpill_pricing(model_data)

        # Query existing current pricing for this model
        stmt = select(ProviderPricing).where(
            and_(
                ProviderPricing.provider_id == provider_id,
                ProviderPricing.model_id == model_id,
                ProviderPricing.effective_until.is_(None),  # Current pricing
            )
        )
        result = await self.db.execute(stmt)
        existing_pricing = result.scalar_one_or_none()

        # Get the native currency for this provider
        currency = get_provider_currency(provider_id)

        # Determine action and create records
        if existing_pricing is None:
            # Create new pricing record
            action = "created"
            old_input = None
            old_output = None

            new_pricing = ProviderPricing.create_from_api_sync(
                provider_id=provider_id,
                model_id=model_id,
                input_price_cents=input_price,
                output_price_cents=output_price,
                model_name=model_name,
                api_response=model_data,
                context_length=model_data.get("context_length"),
                architecture=model_data.get("architecture"),
                currency=currency,
            )
            self.db.add(new_pricing)

            # Create audit log entry
            audit_log = PricingAuditLog.create_for_sync(
                provider_id=provider_id,
                model_id=model_id,
                action="create",
                new_input_price=input_price,
                new_output_price=output_price,
                sync_job_id=sync_job_id,
                api_response=model_data,
            )
            self.db.add(audit_log)

        elif (
            existing_pricing.input_price_per_million_cents != input_price
            or existing_pricing.output_price_per_million_cents != output_price
        ):
            # Price changed - expire old record and create new one
            action = "updated"
            old_input = existing_pricing.input_price_per_million_cents
            old_output = existing_pricing.output_price_per_million_cents

            # Don't update overrides from API sync
            if existing_pricing.is_override:
                logger.info(f"Skipping update for {model_id} - has manual override")
                return SyncResultModel(
                    model_id=model_id,
                    model_name=model_name,
                    action="unchanged",
                    old_input_price=old_input,
                    old_output_price=old_output,
                    new_input_price=input_price,
                    new_output_price=output_price,
                )

            # Expire old pricing
            existing_pricing.expire()

            # Create new pricing record
            new_pricing = ProviderPricing.create_from_api_sync(
                provider_id=provider_id,
                model_id=model_id,
                input_price_cents=input_price,
                output_price_cents=output_price,
                model_name=model_name,
                api_response=model_data,
                context_length=model_data.get("context_length"),
                architecture=model_data.get("architecture"),
                currency=currency,
            )
            self.db.add(new_pricing)

            # Create audit log entry
            audit_log = PricingAuditLog.create_for_sync(
                provider_id=provider_id,
                model_id=model_id,
                action="update",
                new_input_price=input_price,
                new_output_price=output_price,
                old_input_price=old_input,
                old_output_price=old_output,
                sync_job_id=sync_job_id,
                api_response=model_data,
            )
            self.db.add(audit_log)

        else:
            # No change
            action = "unchanged"
            old_input = existing_pricing.input_price_per_million_cents
            old_output = existing_pricing.output_price_per_million_cents

        return SyncResultModel(
            model_id=model_id,
            model_name=model_name,
            action=action,
            old_input_price=old_input,
            old_output_price=old_output,
            new_input_price=input_price,
            new_output_price=output_price,
        )

    @classmethod
    def get_syncable_providers(cls) -> List[str]:
        """Get list of providers that support API sync"""
        return list(cls.PROVIDER_CONFIGS.keys())
