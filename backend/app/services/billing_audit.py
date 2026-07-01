"""
Billing Audit Service

Centralized audit logging for all billing-related changes.
This service MUST be called whenever any billing entity is modified:
- API keys (create, update, soft_delete, restore, regenerate, activate, deactivate)
- Budgets (create, update, delete, reset_period, exceeded, warning_triggered)
- Pricing (sync_create, sync_update, manual_override, remove_override)
- Usage records (correction - rare manual adjustments)

Usage:
    from app.services.billing_audit import BillingAuditService

    audit_service = BillingAuditService(db)
    await audit_service.log_api_key_change(
        api_key_id=123,
        action="create",
        changes={"name": {"old": None, "new": "My API Key"}},
        actor_user_id=1,
    )
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.billing_audit_log import (
    ActionType,
    ActorType,
    BillingAuditLog,
    EntityType,
)

logger = get_logger(__name__)


class BillingAuditService:
    """
    Centralized audit logging for all billing-related changes.
    This service MUST be called whenever any billing entity is modified.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # API Key Audit Logging
    # =========================================================================

    async def log_api_key_change(
        self,
        api_key_id: int,
        action: str,
        changes: Dict[str, Any],
        actor_user_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
        related_user_id: Optional[int] = None,
    ) -> BillingAuditLog:
        """
        Log API key changes.

        Actions: create, update, soft_delete, restore, regenerate, activate, deactivate

        Args:
            api_key_id: ID of the API key
            action: The action performed (see ActionType enum)
            changes: Dict of changes {"field": {"old": x, "new": y}}
            actor_user_id: ID of the user who made the change
            reason: Optional reason for the change
            ip_address: IP address of the request
            user_agent: User agent string
            request_id: UUID of the request
            related_user_id: User ID that owns the API key

        Returns:
            The created BillingAuditLog entry
        """
        audit_log = BillingAuditLog.create_api_key_audit(
            api_key_id=api_key_id,
            action=action,
            changes=changes,
            actor_user_id=actor_user_id,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            related_user_id=related_user_id,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            f"API key audit logged: api_key={api_key_id}, action={action}, "
            f"actor={actor_user_id}"
        )

        return audit_log

    # =========================================================================
    # Budget Audit Logging
    # =========================================================================

    async def log_budget_change(
        self,
        budget_id: int,
        action: str,
        changes: Dict[str, Any],
        actor_user_id: Optional[int] = None,
        actor_type: str = ActorType.USER.value,
        actor_description: Optional[str] = None,
        reason: Optional[str] = None,
        related_api_key_id: Optional[int] = None,
        related_user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> BillingAuditLog:
        """
        Log budget changes.

        Actions: create, update, delete, reset_period, exceeded, warning_triggered, spend_update

        Args:
            budget_id: ID of the budget
            action: The action performed (see ActionType enum)
            changes: Dict of changes {"field": {"old": x, "new": y}}
            actor_user_id: ID of the user who made the change (null for system)
            actor_type: Type of actor (user, system, api_sync)
            actor_description: Description of the actor (e.g., "System scheduler")
            reason: Optional reason for the change
            related_api_key_id: ID of the related API key
            related_user_id: User ID that owns the budget
            ip_address: IP address of the request
            user_agent: User agent string
            request_id: UUID of the request

        Returns:
            The created BillingAuditLog entry
        """
        audit_log = BillingAuditLog.create_budget_audit(
            budget_id=budget_id,
            action=action,
            changes=changes,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            actor_description=actor_description,
            reason=reason,
            related_api_key_id=related_api_key_id,
            related_user_id=related_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            f"Budget audit logged: budget={budget_id}, action={action}, "
            f"actor_type={actor_type}"
        )

        return audit_log

    # =========================================================================
    # Pricing Audit Logging
    # =========================================================================

    async def log_pricing_change(
        self,
        provider_id: str,
        model_id: str,
        action: str,
        changes: Dict[str, Any],
        actor_user_id: Optional[int] = None,
        actor_type: str = ActorType.API_SYNC.value,
        actor_description: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> BillingAuditLog:
        """
        Log pricing changes.

        Actions: sync_create, sync_update, manual_override, remove_override

        Args:
            provider_id: Provider identifier (e.g., "privatemode", "redpill")
            model_id: Model identifier (e.g., "meta-llama/llama-3.1-70b")
            action: The action performed (see ActionType enum)
            changes: Dict of changes {"field": {"old": x, "new": y}}
            actor_user_id: ID of the user who made the change (null for sync)
            actor_type: Type of actor (user, system, api_sync)
            actor_description: Description of the actor (e.g., "RedPill API sync")
            reason: Optional reason for the change
            ip_address: IP address of the request
            user_agent: User agent string
            request_id: UUID of the request (or sync job ID)

        Returns:
            The created BillingAuditLog entry
        """
        audit_log = BillingAuditLog.create_pricing_audit(
            provider_id=provider_id,
            model_id=model_id,
            action=action,
            changes=changes,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            actor_description=actor_description,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            f"Pricing audit logged: {provider_id}/{model_id}, action={action}, "
            f"actor_type={actor_type}"
        )

        return audit_log

    # =========================================================================
    # Usage Record Audit Logging
    # =========================================================================

    async def log_usage_correction(
        self,
        usage_record_id: int,
        changes: Dict[str, Any],
        actor_user_id: int,
        reason: str,
        related_api_key_id: Optional[int] = None,
        related_user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> BillingAuditLog:
        """
        Log usage record corrections (rare manual adjustments).

        Args:
            usage_record_id: ID of the usage record
            changes: Dict of changes {"field": {"old": x, "new": y}}
            actor_user_id: ID of the user making the correction
            reason: REQUIRED reason for the correction
            related_api_key_id: ID of the related API key
            related_user_id: User ID associated with the usage
            ip_address: IP address of the request
            user_agent: User agent string
            request_id: UUID of the request

        Returns:
            The created BillingAuditLog entry

        Note:
            Reason is required for usage corrections to ensure accountability.
        """
        if not reason:
            raise ValueError("Reason is required for usage corrections")

        audit_log = BillingAuditLog.create_usage_correction_audit(
            usage_record_id=usage_record_id,
            changes=changes,
            actor_user_id=actor_user_id,
            reason=reason,
            related_api_key_id=related_api_key_id,
            related_user_id=related_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.warning(
            f"Usage correction audit logged: record={usage_record_id}, "
            f"actor={actor_user_id}, reason={reason}"
        )

        return audit_log

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_api_key_audit_trail(
        self,
        api_key_id: int,
        limit: int = 100,
    ) -> List[BillingAuditLog]:
        """
        Get all audit entries for an API key.

        Args:
            api_key_id: ID of the API key
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, most recent first
        """
        query = (
            select(BillingAuditLog)
            .where(BillingAuditLog.related_api_key_id == api_key_id)
            .order_by(desc(BillingAuditLog.created_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_budget_audit_trail(
        self,
        budget_id: int,
        limit: int = 100,
    ) -> List[BillingAuditLog]:
        """
        Get all audit entries for a budget.

        Args:
            budget_id: ID of the budget
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, most recent first
        """
        query = (
            select(BillingAuditLog)
            .where(BillingAuditLog.related_budget_id == budget_id)
            .order_by(desc(BillingAuditLog.created_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user_audit_trail(
        self,
        user_id: int,
        limit: int = 100,
    ) -> List[BillingAuditLog]:
        """
        Get all audit entries related to a user.

        This includes entries where:
        - The user is the actor (made the change)
        - The user is the related_user_id (owns the entity)

        Args:
            user_id: ID of the user
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, most recent first
        """
        query = (
            select(BillingAuditLog)
            .where(
                (BillingAuditLog.actor_user_id == user_id)
                | (BillingAuditLog.related_user_id == user_id)
            )
            .order_by(desc(BillingAuditLog.created_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_pricing_audit_trail(
        self,
        provider_id: str,
        model_id: str,
        limit: int = 100,
    ) -> List[BillingAuditLog]:
        """
        Get all audit entries for a specific model pricing.

        Args:
            provider_id: Provider identifier
            model_id: Model identifier
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, most recent first
        """
        entity_id = f"{provider_id}/{model_id}"
        query = (
            select(BillingAuditLog)
            .where(
                and_(
                    BillingAuditLog.entity_type == EntityType.PRICING.value,
                    BillingAuditLog.entity_id == entity_id,
                )
            )
            .order_by(desc(BillingAuditLog.created_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_audit_log(
        self,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        actor_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BillingAuditLog]:
        """
        Search audit log with filters.

        Args:
            entity_type: Filter by entity type (api_key, budget, pricing, usage_record)
            action: Filter by action type
            actor_user_id: Filter by actor user ID
            actor_type: Filter by actor type (user, system, api_sync)
            start_date: Filter by start date (inclusive)
            end_date: Filter by end date (inclusive)
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of audit entries matching the filters, most recent first
        """
        conditions = []

        if entity_type:
            conditions.append(BillingAuditLog.entity_type == entity_type)
        if action:
            conditions.append(BillingAuditLog.action == action)
        if actor_user_id:
            conditions.append(BillingAuditLog.actor_user_id == actor_user_id)
        if actor_type:
            conditions.append(BillingAuditLog.actor_type == actor_type)
        if start_date:
            conditions.append(BillingAuditLog.created_at >= start_date)
        if end_date:
            conditions.append(BillingAuditLog.created_at <= end_date)

        query = select(BillingAuditLog)
        if conditions:
            query = query.where(and_(*conditions))

        query = (
            query.order_by(desc(BillingAuditLog.created_at)).offset(offset).limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_recent_audit_entries(
        self,
        limit: int = 50,
    ) -> List[BillingAuditLog]:
        """
        Get the most recent audit entries across all entity types.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit entries, most recent first
        """
        query = (
            select(BillingAuditLog)
            .order_by(desc(BillingAuditLog.created_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def compute_changes(
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute the changes between old and new values.

        Args:
            old_values: Dictionary of old field values
            new_values: Dictionary of new field values

        Returns:
            Dictionary of changes {"field": {"old": x, "new": y}}
        """
        changes = {}

        all_keys = set(old_values.keys()) | set(new_values.keys())

        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)

            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes
