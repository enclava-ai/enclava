"""
Pricing Service for LLM model pricing management

This service provides:
- Database pricing lookup (primary source)
- Static pricing fallbacks for known models
- Model name normalization
- Price per million tokens in cents
- Pricing source tracking for audit

Pricing is stored in cents per 1 million tokens to avoid floating point issues.
Example: $2 per 1M tokens = 200 cents per 1M tokens

Phase 2 Update: Added database pricing lookup with automatic fallback to static pricing.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import utc_now

logger = get_logger(__name__)


@dataclass
class ModelPricing:
    """Pricing information for a model"""

    provider_id: str
    model_id: str
    input_price_per_million_cents: int  # Cents per 1M input tokens
    output_price_per_million_cents: int  # Cents per 1M output tokens
    price_source: str  # 'api_sync', 'manual', 'default'
    effective_from: datetime


# Static pricing for known providers and models
# Prices are in cents per 1 million tokens
STATIC_PRICING: Dict[str, Dict[str, Dict[str, int]]] = {
    "privatemode": {
        # PrivateMode.ai models - confidential inference
        # Pricing estimated based on underlying model costs + TEE overhead
        "meta-llama/llama-3.1-70b-instruct": {"input": 40, "output": 40},
        "meta-llama/llama-3.1-8b-instruct": {"input": 10, "output": 10},
        "meta-llama/llama-3.3-70b-instruct": {"input": 40, "output": 40},
        "mistralai/mixtral-8x7b-instruct": {"input": 24, "output": 24},
        "mistralai/mistral-7b-instruct": {"input": 10, "output": 10},
        "deepseek/deepseek-chat": {"input": 14, "output": 28},
        "qwen/qwen2.5-72b-instruct": {"input": 40, "output": 40},
        # Embedding models
        "baai/bge-large-en-v1.5": {"input": 2, "output": 0},
        "baai/bge-m3": {"input": 2, "output": 0},
    },
    "redpill": {
        # RedPill.ai models - will be synced from API in Phase 2
        # These are fallback prices if API sync fails
        "phala/deepseek-chat-v3-0324": {"input": 14, "output": 28},
        "phala/deepseek-r1-0528": {"input": 55, "output": 219},
        "meta-llama/llama-3.1-405b-instruct": {"input": 300, "output": 300},
        "meta-llama/llama-3.1-70b-instruct": {"input": 52, "output": 75},
        "anthropic/claude-3.5-sonnet": {"input": 300, "output": 1500},
        "openai/gpt-4o": {"input": 250, "output": 1000},
        "openai/gpt-4o-mini": {"input": 15, "output": 60},
    },
    "openai": {
        # OpenAI direct pricing (if ever used)
        "gpt-4": {"input": 3000, "output": 6000},
        "gpt-4-turbo": {"input": 1000, "output": 3000},
        "gpt-4o": {"input": 250, "output": 1000},
        "gpt-4o-mini": {"input": 15, "output": 60},
        "gpt-3.5-turbo": {"input": 50, "output": 150},
        "text-embedding-ada-002": {"input": 10, "output": 0},
        "text-embedding-3-small": {"input": 2, "output": 0},
        "text-embedding-3-large": {"input": 13, "output": 0},
    },
    "anthropic": {
        # Anthropic direct pricing
        "claude-3-opus": {"input": 1500, "output": 7500},
        "claude-3-sonnet": {"input": 300, "output": 1500},
        "claude-3-haiku": {"input": 25, "output": 125},
        "claude-3.5-sonnet": {"input": 300, "output": 1500},
    },
}

# Default pricing for unknown models
DEFAULT_PRICING = {
    "input": 100,  # $1 per 1M input tokens (conservative)
    "output": 200,  # $2 per 1M output tokens (conservative)
}

# Model name normalization patterns
MODEL_NORMALIZATION_PATTERNS = [
    # Remove version suffixes like -20240229, -v1.0, etc.
    (r"-\d{8}$", ""),
    (r"-v\d+(\.\d+)*$", ""),
    # Normalize common prefixes
    (r"^openai/", ""),
    (r"^anthropic/", ""),
    (r"^google/", ""),
    (r"^gemini/", ""),
    (r"^phala/", ""),
]


class PricingService:
    """
    Service for retrieving model pricing information.

    Pricing lookup order:
    1. Database (provider_pricing table) - primary source
    2. Static pricing tables - fallback
    3. Default pricing - last resort

    Use get_pricing() for async database-aware lookups.
    Use get_pricing_static() for synchronous static-only lookups.
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        """
        Initialize pricing service.

        Args:
            db: Optional database session for database lookups.
                If not provided, only static pricing will be used.
        """
        self._db = db
        self._static_pricing = STATIC_PRICING
        self._default_pricing = DEFAULT_PRICING
        # Timestamp for static pricing (service start time)
        # Using naive datetime for PostgreSQL TIMESTAMP WITHOUT TIME ZONE compatibility
        self._static_effective_from = utc_now()

    async def get_pricing(
        self,
        provider_id: str,
        model_id: str,
    ) -> ModelPricing:
        """
        Get pricing for a specific provider and model.

        Lookup order:
        1. Database (if session available)
        2. Static pricing tables
        3. Default pricing

        Args:
            provider_id: Provider identifier (e.g., 'privatemode', 'redpill')
            model_id: Model identifier from the provider

        Returns:
            ModelPricing with input/output prices in cents per million tokens
        """
        # Try database lookup first (if session available)
        if self._db is not None:
            db_pricing = await self._get_pricing_from_db(provider_id, model_id)
            if db_pricing:
                logger.debug(
                    f"Found database pricing for {provider_id}/{model_id}: "
                    f"input={db_pricing.input_price_per_million_cents}, "
                    f"output={db_pricing.output_price_per_million_cents}"
                )
                return db_pricing

        # Fall back to static pricing
        return self.get_pricing_static(provider_id, model_id)

    async def _get_pricing_from_db(
        self,
        provider_id: str,
        model_id: str,
    ) -> Optional[ModelPricing]:
        """
        Query pricing from the database.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier

        Returns:
            ModelPricing if found in database, None otherwise
        """
        if self._db is None:
            return None

        try:
            # Import here to avoid circular imports
            from app.models.provider_pricing import ProviderPricing

            # Query current pricing (effective_until IS NULL)
            stmt = select(ProviderPricing).where(
                and_(
                    ProviderPricing.provider_id == provider_id.lower(),
                    ProviderPricing.model_id == model_id,
                    ProviderPricing.effective_until.is_(None),
                )
            )

            result = await self._db.execute(stmt)
            db_pricing = result.scalar_one_or_none()

            if db_pricing:
                return ModelPricing(
                    provider_id=db_pricing.provider_id,
                    model_id=db_pricing.model_id,
                    input_price_per_million_cents=db_pricing.input_price_per_million_cents,
                    output_price_per_million_cents=db_pricing.output_price_per_million_cents,
                    price_source=db_pricing.price_source,
                    effective_from=db_pricing.effective_from,
                )

            # Try fuzzy matching in database
            # Look for partial matches if exact match not found
            normalized = self.normalize_model(model_id)
            stmt_fuzzy = select(ProviderPricing).where(
                and_(
                    ProviderPricing.provider_id == provider_id.lower(),
                    ProviderPricing.effective_until.is_(None),
                )
            )

            result_fuzzy = await self._db.execute(stmt_fuzzy)
            all_pricing = result_fuzzy.scalars().all()

            for p in all_pricing:
                p_normalized = self.normalize_model(p.model_id)
                if p_normalized in normalized or normalized in p_normalized:
                    logger.debug(
                        f"Database fuzzy matched '{model_id}' to '{p.model_id}'"
                    )
                    return ModelPricing(
                        provider_id=p.provider_id,
                        model_id=model_id,  # Use original model_id
                        input_price_per_million_cents=p.input_price_per_million_cents,
                        output_price_per_million_cents=p.output_price_per_million_cents,
                        price_source=p.price_source,
                        effective_from=p.effective_from,
                    )

            return None

        except Exception as e:
            logger.warning(f"Database pricing lookup failed: {e}")
            return None

    def get_pricing_static(
        self,
        provider_id: str,
        model_id: str,
    ) -> ModelPricing:
        """
        Get pricing from static tables only (synchronous).

        Use this when you don't have a database session or need synchronous access.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier

        Returns:
            ModelPricing from static tables or defaults
        """
        # Normalize model ID for lookup
        normalized_model = self.normalize_model(model_id)

        # Try to find pricing in static table
        provider_pricing = self._static_pricing.get(provider_id.lower(), {})

        # First try exact match
        if model_id in provider_pricing:
            pricing = provider_pricing[model_id]
            return ModelPricing(
                provider_id=provider_id,
                model_id=model_id,
                input_price_per_million_cents=pricing["input"],
                output_price_per_million_cents=pricing["output"],
                price_source="manual",  # Static prices are manually configured
                effective_from=self._static_effective_from,
            )

        # Try normalized model name
        if normalized_model in provider_pricing:
            pricing = provider_pricing[normalized_model]
            return ModelPricing(
                provider_id=provider_id,
                model_id=model_id,
                input_price_per_million_cents=pricing["input"],
                output_price_per_million_cents=pricing["output"],
                price_source="manual",
                effective_from=self._static_effective_from,
            )

        # Try fuzzy matching by checking if model_id contains any known model
        for known_model, pricing in provider_pricing.items():
            known_normalized = self.normalize_model(known_model)
            model_normalized = normalized_model
            known_basename = known_normalized.split("/")[-1]
            model_basename = model_normalized.split("/")[-1]

            if (
                known_normalized in model_normalized
                or model_normalized in known_normalized
                or known_basename in model_basename
                or model_basename in known_basename
            ):
                logger.debug(
                    f"Fuzzy matched model '{model_id}' to '{known_model}' for provider '{provider_id}'"
                )
                return ModelPricing(
                    provider_id=provider_id,
                    model_id=model_id,
                    input_price_per_million_cents=pricing["input"],
                    output_price_per_million_cents=pricing["output"],
                    price_source="manual",
                    effective_from=self._static_effective_from,
                )

        # Fall back to default pricing
        logger.warning(
            f"No pricing found for provider '{provider_id}' model '{model_id}', using defaults"
        )
        return ModelPricing(
            provider_id=provider_id,
            model_id=model_id,
            input_price_per_million_cents=self._default_pricing["input"],
            output_price_per_million_cents=self._default_pricing["output"],
            price_source="default",
            effective_from=self._static_effective_from,
        )

    def normalize_model(self, model_id: str) -> str:
        """
        Normalize model name for consistent lookup and reporting.

        Removes version suffixes, provider prefixes, and converts to lowercase.

        Args:
            model_id: Raw model identifier from provider

        Returns:
            Normalized model name
        """
        normalized = model_id.lower().strip()

        # Apply normalization patterns
        for pattern, replacement in MODEL_NORMALIZATION_PATTERNS:
            normalized = re.sub(pattern, replacement, normalized)

        return normalized

    def calculate_cost_cents(
        self,
        input_tokens: int,
        output_tokens: int,
        pricing: ModelPricing,
    ) -> tuple[int, int, int]:
        """
        Calculate costs in cents from tokens and pricing.

        Uses ceiling division to ensure we never under-charge
        (important for budget enforcement).

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            pricing: ModelPricing object with price per million

        Returns:
            Tuple of (input_cost_cents, output_cost_cents, total_cost_cents)
        """
        # Ceiling division: (a + b - 1) // b is equivalent to ceil(a / b)
        # This ensures we round up to avoid under-charging
        input_cost_cents = (
            input_tokens * pricing.input_price_per_million_cents + 999_999
        ) // 1_000_000
        output_cost_cents = (
            output_tokens * pricing.output_price_per_million_cents + 999_999
        ) // 1_000_000
        total_cost_cents = input_cost_cents + output_cost_cents

        return input_cost_cents, output_cost_cents, total_cost_cents

    def get_all_supported_models(
        self, provider_id: Optional[str] = None
    ) -> Dict[str, list]:
        """
        Get all models with static pricing defined.

        Args:
            provider_id: Optional filter by provider

        Returns:
            Dict of provider -> list of model IDs
        """
        if provider_id:
            return {
                provider_id: list(
                    self._static_pricing.get(provider_id.lower(), {}).keys()
                )
            }

        return {
            provider: list(models.keys())
            for provider, models in self._static_pricing.items()
        }


# Convenience function for simple cost calculation
def calculate_cost_cents_simple(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    provider_id: str = "privatemode",
) -> int:
    """
    Calculate cost in cents for a simple request.

    This is a synchronous helper for cases where async is not needed.
    For full functionality, use PricingService.

    Args:
        model_name: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        provider_id: Provider identifier

    Returns:
        Total cost in cents
    """
    service = PricingService()

    # Get provider pricing
    provider_pricing = service._static_pricing.get(provider_id.lower(), {})

    # Find matching pricing
    pricing = None
    if model_name in provider_pricing:
        pricing = provider_pricing[model_name]
    else:
        # Try normalized
        normalized = service.normalize_model(model_name)
        if normalized in provider_pricing:
            pricing = provider_pricing[normalized]
        else:
            # Fuzzy match
            for known_model, p in provider_pricing.items():
                if (
                    known_model in model_name.lower()
                    or model_name.lower() in known_model
                ):
                    pricing = p
                    break

    if not pricing:
        pricing = service._default_pricing

    # Calculate with ceiling division
    input_cost = (input_tokens * pricing["input"] + 999_999) // 1_000_000
    output_cost = (output_tokens * pricing["output"] + 999_999) // 1_000_000

    return input_cost + output_cost
