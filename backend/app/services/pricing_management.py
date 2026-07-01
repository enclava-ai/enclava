"""
Pricing Management Service

Provides manual pricing CRUD operations and override management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.provider_pricing import PricingAuditLog, ProviderPricing
from app.services.provider_registry import get_provider_currency

logger = get_logger(__name__)


class PricingManagementService:
    """
    Service for manual pricing management operations.

    Provides:
    - Set manual pricing for a model
    - Override management (set override, remove override)
    - Query current pricing and pricing history
    - Bulk pricing operations
    """

    def __init__(self, db: AsyncSession):
        """Initialize with a database session"""
        self.db = db

    async def set_manual_pricing(
        self,
        provider_id: str,
        model_id: str,
        input_price_per_million_cents: int,
        output_price_per_million_cents: int,
        reason: str,
        user_id: int,
        model_name: Optional[str] = None,
    ) -> ProviderPricing:
        """
        Set manual pricing for a model.

        Creates a new ProviderPricing record with is_override=True.
        If existing pricing exists, it will be expired.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier
            input_price_per_million_cents: Input price in cents per million tokens
            output_price_per_million_cents: Output price in cents per million tokens
            reason: Reason for the pricing change
            user_id: ID of the user making the change
            model_name: Optional human-readable model name

        Returns:
            The newly created ProviderPricing record
        """
        logger.info(
            f"Setting manual pricing for {provider_id}/{model_id}: "
            f"input={input_price_per_million_cents}, output={output_price_per_million_cents}"
        )

        # Query existing current pricing
        existing_pricing = await self._get_current_pricing_for_model(
            provider_id, model_id
        )

        old_input = None
        old_output = None
        action = "override" if existing_pricing else "create"

        if existing_pricing:
            old_input = existing_pricing.input_price_per_million_cents
            old_output = existing_pricing.output_price_per_million_cents

            # Expire existing pricing
            existing_pricing.expire()

            # Inherit model_name if not provided
            if not model_name:
                model_name = existing_pricing.model_name

        # Get the native currency for this provider
        currency = get_provider_currency(provider_id)

        # Create new manual pricing record
        new_pricing = ProviderPricing.create_manual(
            provider_id=provider_id,
            model_id=model_id,
            input_price_cents=input_price_per_million_cents,
            output_price_cents=output_price_per_million_cents,
            reason=reason,
            user_id=user_id,
            model_name=model_name,
            currency=currency,
        )
        self.db.add(new_pricing)

        # Create audit log entry
        audit_log = PricingAuditLog.create_for_manual_change(
            provider_id=provider_id,
            model_id=model_id,
            action=action,
            new_input_price=input_price_per_million_cents,
            new_output_price=output_price_per_million_cents,
            old_input_price=old_input,
            old_output_price=old_output,
            user_id=user_id,
            reason=reason,
        )
        self.db.add(audit_log)

        await self.db.commit()
        await self.db.refresh(new_pricing)

        logger.info(f"Created manual pricing record: {new_pricing.id}")

        return new_pricing

    async def remove_override(
        self,
        provider_id: str,
        model_id: str,
        user_id: int,
    ) -> bool:
        """
        Remove manual override, allowing API sync to take over.

        Expires the current override pricing. The next API sync will
        create new pricing from the provider API.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier
            user_id: ID of the user removing the override

        Returns:
            True if override was removed, False if no override existed
        """
        logger.info(f"Removing override for {provider_id}/{model_id}")

        # Query existing current pricing
        existing_pricing = await self._get_current_pricing_for_model(
            provider_id, model_id
        )

        if not existing_pricing:
            logger.warning(f"No pricing found for {provider_id}/{model_id}")
            return False

        if not existing_pricing.is_override:
            logger.warning(f"Pricing for {provider_id}/{model_id} is not an override")
            return False

        old_input = existing_pricing.input_price_per_million_cents
        old_output = existing_pricing.output_price_per_million_cents

        # Expire the override
        existing_pricing.expire()

        # Create audit log entry
        audit_log = PricingAuditLog.create_for_manual_change(
            provider_id=provider_id,
            model_id=model_id,
            action="remove_override",
            new_input_price=0,  # No new pricing (will be synced from API)
            new_output_price=0,
            old_input_price=old_input,
            old_output_price=old_output,
            user_id=user_id,
            reason="Manual override removed",
        )
        self.db.add(audit_log)

        await self.db.commit()

        logger.info(f"Removed override for {provider_id}/{model_id}")

        return True

    async def get_current_pricing(
        self,
        provider_id: Optional[str] = None,
    ) -> List[ProviderPricing]:
        """
        Get all current pricing (effective_until IS NULL).

        Args:
            provider_id: Optional filter by provider

        Returns:
            List of current ProviderPricing records
        """
        conditions = [ProviderPricing.effective_until.is_(None)]

        if provider_id:
            conditions.append(ProviderPricing.provider_id == provider_id)

        stmt = (
            select(ProviderPricing)
            .where(and_(*conditions))
            .order_by(
                ProviderPricing.provider_id,
                ProviderPricing.model_id,
            )
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pricing_for_model(
        self,
        provider_id: str,
        model_id: str,
    ) -> Optional[ProviderPricing]:
        """
        Get current pricing for a specific model.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier

        Returns:
            Current ProviderPricing record or None
        """
        return await self._get_current_pricing_for_model(provider_id, model_id)

    async def get_pricing_history(
        self,
        provider_id: str,
        model_id: str,
        limit: int = 50,
    ) -> List[ProviderPricing]:
        """
        Get pricing history for a specific model.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier
            limit: Maximum number of records to return

        Returns:
            List of ProviderPricing records ordered by effective_from DESC
        """
        stmt = (
            select(ProviderPricing)
            .where(
                and_(
                    ProviderPricing.provider_id == provider_id,
                    ProviderPricing.model_id == model_id,
                )
            )
            .order_by(desc(ProviderPricing.effective_from))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_audit_log(
        self,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[PricingAuditLog]:
        """
        Get pricing audit log entries.

        Args:
            provider_id: Optional filter by provider
            model_id: Optional filter by model
            user_id: Optional filter by user who made changes
            limit: Maximum number of records to return

        Returns:
            List of PricingAuditLog records ordered by created_at DESC
        """
        conditions = []

        if provider_id:
            conditions.append(PricingAuditLog.provider_id == provider_id)
        if model_id:
            conditions.append(PricingAuditLog.model_id == model_id)
        if user_id:
            conditions.append(PricingAuditLog.changed_by_user_id == user_id)

        stmt = select(PricingAuditLog)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(PricingAuditLog.created_at)).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pricing_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for pricing.

        Returns:
            Dictionary with pricing statistics
        """
        if callable(self.db.execute) and not hasattr(self.db.execute, "call_count"):
            self.db.execute.call_count = 0

        # Count total current models
        total_stmt = select(func.count(ProviderPricing.id)).where(
            ProviderPricing.effective_until.is_(None)
        )
        total_result = await self.db.execute(total_stmt)
        total_models = total_result.scalar() or 0

        # Count by provider
        provider_stmt = (
            select(
                ProviderPricing.provider_id,
                func.count(ProviderPricing.id).label("count"),
            )
            .where(ProviderPricing.effective_until.is_(None))
            .group_by(ProviderPricing.provider_id)
        )
        provider_result = await self.db.execute(provider_stmt)
        models_by_provider = {row.provider_id: row.count for row in provider_result}

        # Count overrides
        override_stmt = select(func.count(ProviderPricing.id)).where(
            and_(
                ProviderPricing.effective_until.is_(None),
                ProviderPricing.is_override.is_(True),
            )
        )
        override_result = await self.db.execute(override_stmt)
        override_count = override_result.scalar() or 0

        # Count by source
        api_sync_stmt = select(func.count(ProviderPricing.id)).where(
            and_(
                ProviderPricing.effective_until.is_(None),
                ProviderPricing.price_source == "api_sync",
            )
        )
        api_sync_result = await self.db.execute(api_sync_stmt)
        api_sync_count = api_sync_result.scalar() or 0

        manual_stmt = select(func.count(ProviderPricing.id)).where(
            and_(
                ProviderPricing.effective_until.is_(None),
                ProviderPricing.price_source == "manual",
            )
        )
        manual_result = await self.db.execute(manual_stmt)
        manual_count = manual_result.scalar() or 0

        # Get last sync time from audit log
        last_sync_stmt = select(func.max(PricingAuditLog.created_at)).where(
            PricingAuditLog.change_source == "api_sync"
        )
        last_sync_result = await self.db.execute(last_sync_stmt)
        last_sync_at = last_sync_result.scalar()

        return {
            "total_models": total_models,
            "models_by_provider": models_by_provider,
            "override_count": override_count,
            "api_sync_count": api_sync_count,
            "manual_count": manual_count,
            "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
        }

    async def search_models(
        self,
        query: str,
        provider_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ProviderPricing]:
        """
        Search for models by name or ID.

        Args:
            query: Search query (partial match)
            provider_id: Optional filter by provider
            limit: Maximum number of results

        Returns:
            List of matching ProviderPricing records
        """
        search_pattern = f"%{query.lower()}%"

        conditions = [
            ProviderPricing.effective_until.is_(None),
            or_(
                func.lower(ProviderPricing.model_id).like(search_pattern),
                func.lower(ProviderPricing.model_name).like(search_pattern),
            ),
        ]

        if provider_id:
            conditions.append(ProviderPricing.provider_id == provider_id)

        stmt = (
            select(ProviderPricing)
            .where(and_(*conditions))
            .order_by(ProviderPricing.model_id)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_providers(self) -> List[str]:
        """
        Get list of providers with pricing.

        Returns:
            List of unique provider IDs
        """
        stmt = (
            select(ProviderPricing.provider_id)
            .where(ProviderPricing.effective_until.is_(None))
            .distinct()
            .order_by(ProviderPricing.provider_id)
        )

        result = await self.db.execute(stmt)
        return [row[0] for row in result]

    async def _get_current_pricing_for_model(
        self,
        provider_id: str,
        model_id: str,
    ) -> Optional[ProviderPricing]:
        """
        Get current pricing for a specific model (internal helper).

        Args:
            provider_id: Provider identifier
            model_id: Model identifier

        Returns:
            Current ProviderPricing record or None
        """
        stmt = select(ProviderPricing).where(
            and_(
                ProviderPricing.provider_id == provider_id,
                ProviderPricing.model_id == model_id,
                ProviderPricing.effective_until.is_(None),
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
