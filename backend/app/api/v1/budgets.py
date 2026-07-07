"""
Budget management endpoints
"""

import inspect
from datetime import datetime, timedelta, timezone
from enum import Enum
from numbers import Number
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.database import get_db, utc_now
from app.models.budget import Budget
from app.models.usage_tracking import UsageTracking
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.permission_manager import require_permission

logger = get_logger(__name__)

router = APIRouter()


def _current_user_id(current_user: Dict[str, Any]) -> int:
    return int(current_user["id"])


def _is_admin(current_user: Dict[str, Any]) -> bool:
    permissions = current_user.get("permissions", [])
    return bool(
        current_user.get("is_superuser")
        or "platform:*" in permissions
        or "platform:budgets:admin" in permissions
    )


def _require_permission_unless_admin(
    current_user: Dict[str, Any], required_permission: str
) -> None:
    if _is_admin(current_user):
        return
    require_permission(current_user.get("permissions", []), required_permission)


def _coerce_optional_int(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _number_or_default(value: Any, default: float = 0.0) -> float:
    if isinstance(value, Number):
        return float(value)
    return default


def _days_between(end: datetime, start: datetime) -> int:
    try:
        return max(0, (end - start).days)
    except TypeError:
        return max(
            0,
            (end.replace(tzinfo=None) - start.replace(tzinfo=None)).days,
        )


def _budget_response_dict(
    budget: Budget, usage: Optional[float] = None
) -> Dict[str, Any]:
    limit_amount = _number_or_default(getattr(budget, "limit_amount", 0.0))
    current_usage = _number_or_default(
        usage if usage is not None else getattr(budget, "current_usage", 0.0)
    )
    usage_percentage = (current_usage / limit_amount * 100) if limit_amount > 0 else 0.0

    return {
        "id": str(budget.id),
        "name": budget.name,
        "description": budget.description,
        "budget_type": getattr(budget, "budget_type", "dollars"),
        "limit_amount": limit_amount,
        "period_type": budget.period_type,
        "period_start": budget.period_start or utc_now(),
        "period_end": budget.period_end or utc_now(),
        "current_usage": current_usage,
        "usage_percentage": usage_percentage,
        "is_enabled": bool(getattr(budget, "is_enabled", True)),
        "alert_threshold_percent": _number_or_default(
            getattr(budget, "alert_threshold_percent", 80.0), 80.0
        ),
        "user_id": str(budget.user_id) if budget.user_id is not None else None,
        "api_key_id": str(budget.api_key_id) if budget.api_key_id is not None else None,
        "allowed_resources": list(getattr(budget, "allowed_resources", []) or []),
        "metadata": getattr(budget, "notification_settings", None) or {},
        "created_at": budget.created_at or utc_now(),
        "updated_at": budget.updated_at,
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _log_budget_audit_event(db: AsyncSession, **kwargs: Any) -> None:
    await log_audit_event(db=db, **kwargs)


async def _get_budget_or_404(db: AsyncSession, budget_id: str) -> Budget:
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
        )
    return budget


def _ensure_budget_access(
    budget: Budget, current_user: Dict[str, Any], permission: str
) -> None:
    if int(budget.user_id) == _current_user_id(current_user):
        return
    _require_permission_unless_admin(current_user, permission)


# Enums
class BudgetType(str, Enum):
    TOKENS = "tokens"
    DOLLARS = "dollars"
    REQUESTS = "requests"


class PeriodType(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


# Pydantic models
class BudgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    budget_type: BudgetType
    limit_amount: float = Field(..., gt=0)
    period_type: PeriodType
    user_id: Optional[str] = None  # Admin can set budgets for other users
    api_key_id: Optional[str] = None  # Budget can be linked to specific API key
    is_enabled: bool = True
    alert_threshold_percent: float = Field(80.0, ge=0, le=100)
    allowed_resources: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    limit_amount: Optional[float] = Field(None, gt=0)
    period_type: Optional[PeriodType] = None
    is_enabled: Optional[bool] = None
    alert_threshold_percent: Optional[float] = Field(None, ge=0, le=100)
    allowed_resources: Optional[List[str]] = None
    metadata: Optional[dict] = None


class BudgetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    budget_type: str
    limit_amount: float
    period_type: str
    period_start: datetime
    period_end: datetime
    current_usage: float
    usage_percentage: float
    is_enabled: bool
    alert_threshold_percent: float
    user_id: Optional[str] = None
    api_key_id: Optional[str] = None
    allowed_resources: List[str]
    metadata: dict
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BudgetListResponse(BaseModel):
    budgets: List[BudgetResponse]
    total: int
    page: int
    size: int


class BudgetUsageResponse(BaseModel):
    budget_id: str
    current_usage: float
    limit_amount: float
    usage_percentage: float
    remaining_amount: float
    period_start: datetime
    period_end: datetime
    is_exceeded: bool
    days_remaining: int
    projected_usage: Optional[float] = None
    usage_history: List[dict] = Field(default_factory=list)


class BudgetAlertResponse(BaseModel):
    budget_id: str
    budget_name: str
    alert_type: str  # "warning", "critical", "exceeded"
    current_usage: float
    limit_amount: float
    usage_percentage: float
    message: str


# Budget CRUD endpoints
@router.get("/", response_model=BudgetListResponse)
async def list_budgets(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    budget_type: Optional[BudgetType] = Query(None),
    is_enabled: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List budgets with pagination and filtering"""

    # Check permissions - users can view their own budgets
    if user_id and int(user_id) != _current_user_id(current_user):
        _require_permission_unless_admin(current_user, "platform:budgets:read")

    # If no user_id specified and user doesn't have admin permissions, show only their budgets
    if not user_id and not _is_admin(current_user):
        user_id = current_user["id"]

    # Build query
    query = select(Budget)

    # Apply filters
    if user_id:
        query = query.where(
            Budget.user_id == (int(user_id) if isinstance(user_id, str) else user_id)
        )
    # Budget type is a legacy API field, not a persisted column in the current schema.
    if is_enabled is not None:
        query = query.where(Budget.is_active == is_enabled)

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Budget.created_at.desc())

    # Execute query
    try:
        result = await db.execute(query)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to list budgets: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while listing budgets",
        ) from exc

    budgets = result.scalars().all()

    budget_responses = [_budget_response_dict(budget) for budget in budgets]
    total = len(budget_responses)

    # Log audit event
    await _log_budget_audit_event(
        db=db,
        user_id=current_user["id"],
        action="list_budgets",
        resource_type="budget",
        details={
            "page": page,
            "size": size,
            "filters": {
                "user_id": user_id,
                "budget_type": budget_type,
                "is_enabled": is_enabled,
            },
        },
    )

    return {"budgets": budget_responses, "total": total, "page": page, "size": size}


@router.get("/{budget_id}")
async def get_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get budget by ID"""

    # Get budget
    budget = await _get_budget_or_404(db, budget_id)

    # Check permissions - users can view their own budgets
    _ensure_budget_access(budget, current_user, "platform:budgets:read")

    # Use stored usage for the compact retrieval endpoint; detailed usage has its own route.
    usage = _number_or_default(getattr(budget, "current_usage", 0.0))

    # Log audit event
    await _log_budget_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_budget",
        resource_type="budget",
        resource_id=budget_id,
    )

    return {"budget": _budget_response_dict(budget, usage)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget_data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new budget"""

    # If user_id not specified, use current user
    target_user_id = _coerce_optional_int(budget_data.user_id) or _current_user_id(
        current_user
    )

    # Users may create their own budgets; creating for another user is admin-only.
    if target_user_id != _current_user_id(current_user):
        _require_permission_unless_admin(current_user, "platform:budgets:admin")

    # Calculate period start and end
    now = utc_now()
    period_start, period_end = _calculate_period_bounds(now, budget_data.period_type)

    # Create budget
    new_budget = Budget(
        name=budget_data.name,
        description=budget_data.description,
        budget_type=budget_data.budget_type.value,
        limit_amount=budget_data.limit_amount,
        period_type=budget_data.period_type.value,
        period_start=period_start,
        period_end=period_end,
        user_id=target_user_id,
        api_key_id=_coerce_optional_int(budget_data.api_key_id),
        is_enabled=budget_data.is_enabled,
        alert_threshold_percent=budget_data.alert_threshold_percent,
        allowed_resources=budget_data.allowed_resources,
        metadata=budget_data.metadata,
    )

    await _maybe_await(db.add(new_budget))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget already exists or duplicate budget name",
        ) from exc

    await db.refresh(new_budget)

    # Log audit event
    await _log_budget_audit_event(
        db=db,
        user_id=current_user["id"],
        action="create_budget",
        resource_type="budget",
        resource_id=str(new_budget.id),
        details={
            "name": budget_data.name,
            "budget_type": budget_data.budget_type,
            "limit_amount": budget_data.limit_amount,
        },
    )

    logger.info(f"Budget created: {new_budget.name} by {current_user['username']}")

    return {"budget": _budget_response_dict(new_budget, 0.0)}


@router.patch("/{budget_id}")
@router.put("/{budget_id}")
async def update_budget(
    budget_id: str,
    budget_data: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update budget"""

    # Get budget
    budget = await _get_budget_or_404(db, budget_id)

    # Check permissions - users can update their own budgets
    _ensure_budget_access(budget, current_user, "platform:budgets:update")

    # Store original values for audit
    original_values = {
        "name": budget.name,
        "limit_amount": budget.limit_amount,
        "is_enabled": budget.is_enabled,
    }

    # Update budget fields
    update_data = budget_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "metadata":
            budget.notification_settings = value
        elif field == "allowed_resources":
            budget.allowed_resources = value
        else:
            setattr(budget, field, value)

    # Recalculate period if period_type changed
    if "period_type" in update_data:
        period_start, period_end = _calculate_period_bounds(
            utc_now(), budget.period_type
        )
        budget.period_start = period_start
        budget.period_end = period_end

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if exc.__class__.__name__ == "OptimisticLockError":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Budget conflict: record was modified concurrently",
            ) from exc
        raise
    await db.refresh(budget)

    # Calculate current usage
    usage = await _calculate_budget_usage(db, budget)

    # Log audit event
    await _log_budget_audit_event(
        db=db,
        user_id=current_user["id"],
        action="update_budget",
        resource_type="budget",
        resource_id=budget_id,
        details={
            "updated_fields": list(update_data.keys()),
            "before_values": original_values,
            "after_values": {k: getattr(budget, k) for k in update_data.keys()},
        },
    )

    logger.info(f"Budget updated: {budget.name} by {current_user['username']}")

    return {"budget": _budget_response_dict(budget, usage)}


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete budget"""

    # Get budget
    budget = await _get_budget_or_404(db, budget_id)

    # Check permissions - users can delete their own budgets
    _ensure_budget_access(budget, current_user, "platform:budgets:delete")

    # Delete budget
    await db.delete(budget)
    await db.commit()

    # Log audit event
    await _log_budget_audit_event(
        db=db,
        user_id=current_user["id"],
        action="delete_budget",
        resource_type="budget",
        resource_id=budget_id,
        details={"name": budget.name},
    )

    logger.info(f"Budget deleted: {budget.name} by {current_user['username']}")

    return {"message": "Budget deleted successfully"}


@router.get("/{budget_id}/usage", response_model=BudgetUsageResponse)
async def get_budget_usage(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed budget usage information"""

    # Get budget
    budget = await _get_budget_or_404(db, budget_id)

    # Check permissions - users can view their own budget usage
    _ensure_budget_access(budget, current_user, "platform:budgets:read")

    # Calculate usage
    current_usage = _number_or_default(getattr(budget, "current_usage", 0.0))
    usage_percentage = (
        (current_usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
    )
    remaining_amount = max(0, budget.limit_amount - current_usage)
    is_exceeded = current_usage > budget.limit_amount

    # Calculate days remaining in period
    now = utc_now()
    days_remaining = _days_between(budget.period_end, now)

    # Calculate projected usage
    projected_usage = None
    if days_remaining > 0 and current_usage > 0:
        days_elapsed = (now - budget.period_start).days + 1
        if days_elapsed > 0:
            daily_rate = current_usage / days_elapsed
            total_days = _days_between(budget.period_end, budget.period_start) + 1
            projected_usage = daily_rate * total_days

    # Get usage history (last 30 days)
    usage_history = await _get_usage_history(db, budget, days=30)

    # Log audit event
    await _log_budget_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_budget_usage",
        resource_type="budget",
        resource_id=budget_id,
    )

    return BudgetUsageResponse(
        budget_id=budget_id,
        current_usage=current_usage,
        limit_amount=budget.limit_amount,
        usage_percentage=usage_percentage,
        remaining_amount=remaining_amount,
        period_start=budget.period_start,
        period_end=budget.period_end,
        is_exceeded=is_exceeded,
        days_remaining=days_remaining,
        projected_usage=projected_usage,
        usage_history=usage_history,
    )


@router.get("/{budget_id}/status")
async def get_budget_status(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get compact budget status for legacy clients."""

    budget = await _get_budget_or_404(db, budget_id)
    _ensure_budget_access(budget, current_user, "platform:budgets:read")

    current_usage = _number_or_default(getattr(budget, "current_usage", 0.0))
    limit_amount = _number_or_default(getattr(budget, "limit_amount", 0.0))
    usage_percentage = (current_usage / limit_amount * 100) if limit_amount > 0 else 0.0
    remaining_amount = max(0.0, limit_amount - current_usage)

    return {
        "status": {
            "budget_id": str(budget.id),
            "usage_percentage": usage_percentage,
            "remaining_amount": remaining_amount,
            "days_remaining_in_period": _days_between(budget.period_end, utc_now()),
            "is_exceeded": current_usage > limit_amount if limit_amount > 0 else False,
        }
    }


@router.post("/{budget_id}/reset")
async def reset_budget_usage(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset tracked usage for a budget."""

    budget = await _get_budget_or_404(db, budget_id)
    _ensure_budget_access(budget, current_user, "platform:budgets:update")

    budget.current_usage = 0.0
    budget.is_exceeded = False
    budget.is_warning_sent = False
    budget.last_reset_at = utc_now()

    await db.commit()
    await db.refresh(budget)

    return {"message": "Budget usage reset successfully"}


@router.post("/{budget_id}/alerts")
async def configure_budget_alerts(
    budget_id: str,
    alert_config: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update budget alert notification settings."""

    budget = await _get_budget_or_404(db, budget_id)
    _ensure_budget_access(budget, current_user, "platform:budgets:update")

    budget.notification_settings = alert_config
    await db.commit()
    await db.refresh(budget)

    return {"message": "Budget alert configuration updated successfully"}


@router.get("/admin/all")
async def admin_list_all_budgets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all budgets for administrators."""

    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    result = await db.execute(select(Budget).order_by(Budget.created_at.desc()))
    budgets = result.scalars().all()
    return {"budgets": [_budget_response_dict(budget) for budget in budgets]}


@router.post("/admin/create", status_code=status.HTTP_201_CREATED)
async def admin_create_user_budget(
    budget_data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a budget for any user as an administrator."""

    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return await create_budget(budget_data, current_user, db)


@router.get("/{budget_id}/alerts", response_model=List[BudgetAlertResponse])
async def get_budget_alerts(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get budget alerts"""

    # Get budget
    budget = await _get_budget_or_404(db, budget_id)

    # Check permissions - users can view their own budget alerts
    _ensure_budget_access(budget, current_user, "platform:budgets:read")

    # Calculate usage
    current_usage = await _calculate_budget_usage(db, budget)
    usage_percentage = (
        (current_usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
    )

    alerts = []

    # Check for alerts
    if usage_percentage >= 100:
        alerts.append(
            BudgetAlertResponse(
                budget_id=budget_id,
                budget_name=budget.name,
                alert_type="exceeded",
                current_usage=current_usage,
                limit_amount=budget.limit_amount,
                usage_percentage=usage_percentage,
                message=f"Budget '{budget.name}' has been exceeded ({usage_percentage:.1f}% used)",
            )
        )
    elif usage_percentage >= 90:
        alerts.append(
            BudgetAlertResponse(
                budget_id=budget_id,
                budget_name=budget.name,
                alert_type="critical",
                current_usage=current_usage,
                limit_amount=budget.limit_amount,
                usage_percentage=usage_percentage,
                message=f"Budget '{budget.name}' is critically high ({usage_percentage:.1f}% used)",
            )
        )
    elif usage_percentage >= budget.alert_threshold_percent:
        alerts.append(
            BudgetAlertResponse(
                budget_id=budget_id,
                budget_name=budget.name,
                alert_type="warning",
                current_usage=current_usage,
                limit_amount=budget.limit_amount,
                usage_percentage=usage_percentage,
                message=f"Budget '{budget.name}' has reached alert threshold ({usage_percentage:.1f}% used)",
            )
        )

    return alerts


# Helper functions
async def _calculate_budget_usage(db: AsyncSession, budget: Budget) -> float:
    """Calculate current usage for a budget"""

    # Build base query
    query = select(UsageTracking)

    # Filter by time period
    query = query.where(
        UsageTracking.created_at >= budget.period_start,
        UsageTracking.created_at <= budget.period_end,
    )

    # Filter by user or API key
    if budget.api_key_id:
        query = query.where(UsageTracking.api_key_id == budget.api_key_id)
    elif budget.user_id:
        query = query.where(UsageTracking.user_id == budget.user_id)

    # Calculate usage based on budget type
    if budget.budget_type == "tokens":
        usage_query = query.with_only_columns(func.sum(UsageTracking.total_tokens))
    elif budget.budget_type == "dollars":
        usage_query = query.with_only_columns(func.sum(UsageTracking.cost_cents))
    elif budget.budget_type == "requests":
        usage_query = query.with_only_columns(func.count(UsageTracking.id))
    else:
        return 0.0

    result = await db.execute(usage_query)
    usage = result.scalar() or 0
    if not isinstance(usage, Number):
        return _number_or_default(getattr(budget, "current_usage", 0.0))

    # Convert cents to dollars for dollar budgets
    if budget.budget_type == "dollars":
        usage = usage / 100.0

    return float(usage)


def _calculate_period_bounds(
    current_time: datetime, period_type: str
) -> tuple[datetime, datetime]:
    """Calculate period start and end dates"""

    if period_type == "hourly":
        start = current_time.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1) - timedelta(microseconds=1)
    elif period_type == "daily":
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
    elif period_type == "weekly":
        # Start of week (Monday)
        days_since_monday = current_time.weekday()
        start = current_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=days_since_monday)
        end = start + timedelta(weeks=1) - timedelta(microseconds=1)
    elif period_type == "monthly":
        start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        end = next_month - timedelta(microseconds=1)
    elif period_type == "yearly":
        start = current_time.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = start.replace(year=start.year + 1) - timedelta(microseconds=1)
    else:
        # Default to daily
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)

    return start, end


async def _get_usage_history(
    db: AsyncSession, budget: Budget, days: int = 30
) -> List[dict]:
    """Get usage history for the budget"""

    end_date = utc_now()
    start_date = end_date - timedelta(days=days)

    # Build query
    query = select(UsageTracking).where(
        UsageTracking.created_at >= start_date, UsageTracking.created_at <= end_date
    )

    # Filter by user or API key
    if budget.api_key_id:
        query = query.where(UsageTracking.api_key_id == budget.api_key_id)
    elif budget.user_id:
        query = query.where(UsageTracking.user_id == budget.user_id)

    query = query.order_by(UsageTracking.created_at.desc())

    result = await db.execute(query)
    rows = result.scalars().all()

    history = []
    for row in rows:
        usage_value = 0.0
        if budget.budget_type == "tokens":
            usage_value = _number_or_default(row.total_tokens)
        elif budget.budget_type == "dollars":
            usage_value = _number_or_default(row.cost_cents) / 100.0
        elif budget.budget_type == "requests":
            usage_value = 1.0

        created_at = row.created_at or utc_now()

        history.append(
            {
                "date": created_at.date().isoformat(),
                "usage": usage_value,
                "tokens": row.total_tokens or 0,
                "cost_dollars": _number_or_default(row.cost_cents) / 100.0,
                "requests": 1,
                "request_type": row.endpoint,
            }
        )

    return history
