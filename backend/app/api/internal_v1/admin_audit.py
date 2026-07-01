"""
Admin Billing Audit API Endpoints

Internal API endpoints for querying billing audit logs.
These endpoints require admin privileges.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import RequiresRole
from app.db.database import get_db
from app.models.billing_audit_log import EntityType
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogSummary,
    AuditTrailResponse,
)
from app.services.billing_audit import BillingAuditService

logger = get_logger(__name__)

router = APIRouter()

# Dependency for admin access
require_admin = RequiresRole("admin")


def _audit_to_response(audit) -> AuditLogResponse:
    """Convert BillingAuditLog model to response schema"""
    return AuditLogResponse(
        id=audit.id,
        entity_type=audit.entity_type,
        entity_id=audit.entity_id,
        action=audit.action,
        changes=audit.changes,
        actor_type=audit.actor_type,
        actor_user_id=audit.actor_user_id,
        actor_description=audit.actor_description,
        reason=audit.reason,
        ip_address=str(audit.ip_address) if audit.ip_address else None,
        user_agent=audit.user_agent,
        request_id=str(audit.request_id) if audit.request_id else None,
        related_api_key_id=audit.related_api_key_id,
        related_budget_id=audit.related_budget_id,
        related_user_id=audit.related_user_id,
        created_at=audit.created_at,
    )


@router.get("/billing-audit/api-key/{api_key_id}")
async def get_api_key_audit(
    api_key_id: int,
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """
    Get audit trail for an API key.

    Returns all audit entries related to the specified API key,
    ordered by most recent first.

    Requires admin role.
    """
    logger.info(
        f"Admin {current_user.get('id')} fetching audit for API key {api_key_id}"
    )

    service = BillingAuditService(db)
    entries = await service.get_api_key_audit_trail(api_key_id, limit=limit)

    return AuditTrailResponse(
        entries=[_audit_to_response(e) for e in entries],
        total=len(entries),
        entity_type=EntityType.API_KEY.value,
        entity_id=str(api_key_id),
    )


@router.get("/billing-audit/budget/{budget_id}")
async def get_budget_audit(
    budget_id: int,
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """
    Get audit trail for a budget.

    Returns all audit entries related to the specified budget,
    ordered by most recent first.

    Requires admin role.
    """
    logger.info(f"Admin {current_user.get('id')} fetching audit for budget {budget_id}")

    service = BillingAuditService(db)
    entries = await service.get_budget_audit_trail(budget_id, limit=limit)

    return AuditTrailResponse(
        entries=[_audit_to_response(e) for e in entries],
        total=len(entries),
        entity_type=EntityType.BUDGET.value,
        entity_id=str(budget_id),
    )


@router.get("/billing-audit/user/{user_id}")
async def get_user_audit(
    user_id: int,
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """
    Get audit trail for a user.

    Returns all audit entries where the user is either:
    - The actor who made the change
    - The owner of the affected entity

    Ordered by most recent first.

    Requires admin role.
    """
    logger.info(f"Admin {current_user.get('id')} fetching audit for user {user_id}")

    service = BillingAuditService(db)
    entries = await service.get_user_audit_trail(user_id, limit=limit)

    return AuditTrailResponse(
        entries=[_audit_to_response(e) for e in entries],
        total=len(entries),
        entity_type=None,
        entity_id=None,
    )


@router.get("/billing-audit/pricing/{provider}/{model:path}")
async def get_pricing_audit(
    provider: str,
    model: str,
    limit: int = Query(default=100, le=500),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """
    Get audit trail for model pricing.

    The model path parameter can contain slashes (e.g., 'meta-llama/llama-3.1-70b').

    Requires admin role.
    """
    logger.info(
        f"Admin {current_user.get('id')} fetching pricing audit for {provider}/{model}"
    )

    service = BillingAuditService(db)
    entries = await service.get_pricing_audit_trail(provider, model, limit=limit)

    return AuditTrailResponse(
        entries=[_audit_to_response(e) for e in entries],
        total=len(entries),
        entity_type=EntityType.PRICING.value,
        entity_id=f"{provider}/{model}",
    )


@router.get("/billing-audit/search")
async def search_audit(
    entity_type: Optional[str] = Query(
        default=None,
        description="Filter by entity type: api_key, budget, pricing, usage_record",
    ),
    action: Optional[str] = Query(default=None, description="Filter by action type"),
    actor_user_id: Optional[int] = Query(
        default=None, description="Filter by actor user ID"
    ),
    actor_type: Optional[str] = Query(
        default=None, description="Filter by actor type: user, system, api_sync"
    ),
    start_date: Optional[datetime] = Query(
        default=None, description="Filter by start date (inclusive)"
    ),
    end_date: Optional[datetime] = Query(
        default=None, description="Filter by end date (inclusive)"
    ),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[AuditLogResponse]:
    """
    Search audit log with filters.

    Supports filtering by:
    - entity_type: api_key, budget, pricing, usage_record
    - action: create, update, soft_delete, etc.
    - actor_user_id: ID of the user who made the change
    - actor_type: user, system, api_sync
    - start_date / end_date: Date range

    Results are ordered by most recent first.

    Requires admin role.
    """
    logger.info(
        f"Admin {current_user.get('id')} searching audit log: "
        f"entity_type={entity_type}, action={action}"
    )

    # Validate entity_type if provided
    if entity_type:
        valid_types = [e.value for e in EntityType]
        if entity_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid entity_type. Must be one of: {valid_types}",
            )

    service = BillingAuditService(db)
    entries = await service.search_audit_log(
        entity_type=entity_type,
        action=action,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return [_audit_to_response(e) for e in entries]


@router.get("/billing-audit/recent")
async def get_recent_audit(
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[AuditLogResponse]:
    """
    Get the most recent audit entries across all entity types.

    Useful for dashboard displays showing recent billing activity.

    Requires admin role.
    """
    logger.info(f"Admin {current_user.get('id')} fetching recent audit entries")

    service = BillingAuditService(db)
    entries = await service.get_recent_audit_entries(limit=limit)

    return [_audit_to_response(e) for e in entries]


@router.get("/billing-audit/summary")
async def get_audit_summary(
    start_date: Optional[datetime] = Query(
        default=None, description="Start of summary period"
    ),
    end_date: Optional[datetime] = Query(
        default=None, description="End of summary period"
    ),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditLogSummary:
    """
    Get summary statistics for audit logs.

    Returns counts by entity type, action type, and actor type.

    Requires admin role.
    """
    from sqlalchemy import and_, func, select

    from app.models.billing_audit_log import BillingAuditLog

    logger.info(f"Admin {current_user.get('id')} fetching audit summary")

    conditions = []
    if start_date:
        conditions.append(BillingAuditLog.created_at >= start_date)
    if end_date:
        conditions.append(BillingAuditLog.created_at <= end_date)

    # Total entries
    total_query = select(func.count(BillingAuditLog.id))
    if conditions:
        total_query = total_query.where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_entries = total_result.scalar() or 0

    # Entries by entity type
    entity_query = select(
        BillingAuditLog.entity_type, func.count(BillingAuditLog.id)
    ).group_by(BillingAuditLog.entity_type)
    if conditions:
        entity_query = entity_query.where(and_(*conditions))
    entity_result = await db.execute(entity_query)
    entries_by_entity_type = dict(entity_result.fetchall())

    # Entries by action
    action_query = select(
        BillingAuditLog.action, func.count(BillingAuditLog.id)
    ).group_by(BillingAuditLog.action)
    if conditions:
        action_query = action_query.where(and_(*conditions))
    action_result = await db.execute(action_query)
    entries_by_action = dict(action_result.fetchall())

    # Entries by actor type
    actor_query = select(
        BillingAuditLog.actor_type, func.count(BillingAuditLog.id)
    ).group_by(BillingAuditLog.actor_type)
    if conditions:
        actor_query = actor_query.where(and_(*conditions))
    actor_result = await db.execute(actor_query)
    entries_by_actor_type = dict(actor_result.fetchall())

    return AuditLogSummary(
        total_entries=total_entries,
        entries_by_entity_type=entries_by_entity_type,
        entries_by_action=entries_by_action,
        entries_by_actor_type=entries_by_actor_type,
        period_start=start_date,
        period_end=end_date,
    )
