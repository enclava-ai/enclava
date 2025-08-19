"""
Budget management endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from datetime import datetime, timedelta
from enum import Enum

from app.db.database import get_db
from app.models.budget import Budget
from app.models.user import User
from app.models.usage_tracking import UsageTracking
from app.core.security import get_current_user
from app.services.permission_manager import require_permission
from app.services.audit_service import log_audit_event
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


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
    db: AsyncSession = Depends(get_db)
):
    """List budgets with pagination and filtering"""
    
    # Check permissions - users can view their own budgets
    if user_id and int(user_id) != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:read")
    elif not user_id:
        require_permission(current_user.get("permissions", []), "platform:budgets:read")
        
    # If no user_id specified and user doesn't have admin permissions, show only their budgets
    if not user_id and "platform:budgets:read" not in current_user.get("permissions", []):
        user_id = current_user['id']
    
    # Build query
    query = select(Budget)
    
    # Apply filters
    if user_id:
        query = query.where(Budget.user_id == (int(user_id) if isinstance(user_id, str) else user_id))
    if budget_type:
        query = query.where(Budget.budget_type == budget_type.value)
    if is_enabled is not None:
        query = query.where(Budget.is_enabled == is_enabled)
    
    # Get total count
    count_query = select(func.count(Budget.id))
    
    # Apply same filters to count query
    if user_id:
        count_query = count_query.where(Budget.user_id == (int(user_id) if isinstance(user_id, str) else user_id))
    if budget_type:
        count_query = count_query.where(Budget.budget_type == budget_type.value)
    if is_enabled is not None:
        count_query = count_query.where(Budget.is_enabled == is_enabled)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Budget.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    budgets = result.scalars().all()
    
    # Calculate current usage for each budget
    budget_responses = []
    for budget in budgets:
        usage = await _calculate_budget_usage(db, budget)
        budget_data = BudgetResponse.model_validate(budget)
        budget_data.current_usage = usage
        budget_data.usage_percentage = (usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
        budget_responses.append(budget_data)
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="list_budgets",
        resource_type="budget",
        details={"page": page, "size": size, "filters": {"user_id": user_id, "budget_type": budget_type, "is_enabled": is_enabled}}
    )
    
    return BudgetListResponse(
        budgets=budget_responses,
        total=total,
        page=page,
        size=size
    )


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get budget by ID"""
    
    # Get budget
    query = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(query)
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Check permissions - users can view their own budgets
    if budget.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:read")
    
    # Calculate current usage
    usage = await _calculate_budget_usage(db, budget)
    
    # Build response
    budget_data = BudgetResponse.model_validate(budget)
    budget_data.current_usage = usage
    budget_data.usage_percentage = (usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_budget",
        resource_type="budget",
        resource_id=budget_id
    )
    
    return budget_data


@router.post("/", response_model=BudgetResponse)
async def create_budget(
    budget_data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new budget"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:budgets:create")
    
    # If user_id not specified, use current user
    target_user_id = budget_data.user_id or current_user['id']
    
    # If setting budget for another user, need admin permissions
    if int(target_user_id) != current_user['id'] if isinstance(target_user_id, str) else target_user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:admin")
    
    # Calculate period start and end
    now = datetime.utcnow()
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
        api_key_id=budget_data.api_key_id,
        is_enabled=budget_data.is_enabled,
        alert_threshold_percent=budget_data.alert_threshold_percent,
        allowed_resources=budget_data.allowed_resources,
        metadata=budget_data.metadata
    )
    
    db.add(new_budget)
    await db.commit()
    await db.refresh(new_budget)
    
    # Build response
    budget_response = BudgetResponse.model_validate(new_budget)
    budget_response.current_usage = 0.0
    budget_response.usage_percentage = 0.0
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="create_budget",
        resource_type="budget",
        resource_id=str(new_budget.id),
        details={"name": budget_data.name, "budget_type": budget_data.budget_type, "limit_amount": budget_data.limit_amount}
    )
    
    logger.info(f"Budget created: {new_budget.name} by {current_user['username']}")
    
    return budget_response


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    budget_data: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update budget"""
    
    # Get budget
    query = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(query)
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Check permissions - users can update their own budgets
    if budget.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:update")
    
    # Store original values for audit
    original_values = {
        "name": budget.name,
        "limit_amount": budget.limit_amount,
        "is_enabled": budget.is_enabled
    }
    
    # Update budget fields
    update_data = budget_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(budget, field, value)
    
    # Recalculate period if period_type changed
    if "period_type" in update_data:
        period_start, period_end = _calculate_period_bounds(datetime.utcnow(), budget.period_type)
        budget.period_start = period_start
        budget.period_end = period_end
    
    await db.commit()
    await db.refresh(budget)
    
    # Calculate current usage
    usage = await _calculate_budget_usage(db, budget)
    
    # Build response
    budget_response = BudgetResponse.model_validate(budget)
    budget_response.current_usage = usage
    budget_response.usage_percentage = (usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="update_budget",
        resource_type="budget",
        resource_id=budget_id,
        details={
            "updated_fields": list(update_data.keys()),
            "before_values": original_values,
            "after_values": {k: getattr(budget, k) for k in update_data.keys()}
        }
    )
    
    logger.info(f"Budget updated: {budget.name} by {current_user['username']}")
    
    return budget_response


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete budget"""
    
    # Get budget
    query = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(query)
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Check permissions - users can delete their own budgets
    if budget.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:delete")
    
    # Delete budget
    await db.delete(budget)
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="delete_budget",
        resource_type="budget",
        resource_id=budget_id,
        details={"name": budget.name}
    )
    
    logger.info(f"Budget deleted: {budget.name} by {current_user['username']}")
    
    return {"message": "Budget deleted successfully"}


@router.get("/{budget_id}/usage", response_model=BudgetUsageResponse)
async def get_budget_usage(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed budget usage information"""
    
    # Get budget
    query = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(query)
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Check permissions - users can view their own budget usage
    if budget.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:read")
    
    # Calculate usage
    current_usage = await _calculate_budget_usage(db, budget)
    usage_percentage = (current_usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
    remaining_amount = max(0, budget.limit_amount - current_usage)
    is_exceeded = current_usage > budget.limit_amount
    
    # Calculate days remaining in period
    now = datetime.utcnow()
    days_remaining = max(0, (budget.period_end - now).days)
    
    # Calculate projected usage
    projected_usage = None
    if days_remaining > 0 and current_usage > 0:
        days_elapsed = (now - budget.period_start).days + 1
        if days_elapsed > 0:
            daily_rate = current_usage / days_elapsed
            total_days = (budget.period_end - budget.period_start).days + 1
            projected_usage = daily_rate * total_days
    
    # Get usage history (last 30 days)
    usage_history = await _get_usage_history(db, budget, days=30)
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_budget_usage",
        resource_type="budget",
        resource_id=budget_id
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
        usage_history=usage_history
    )


@router.get("/{budget_id}/alerts", response_model=List[BudgetAlertResponse])
async def get_budget_alerts(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get budget alerts"""
    
    # Get budget
    query = select(Budget).where(Budget.id == budget_id)
    result = await db.execute(query)
    budget = result.scalar_one_or_none()
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Check permissions - users can view their own budget alerts
    if budget.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:budgets:read")
    
    # Calculate usage
    current_usage = await _calculate_budget_usage(db, budget)
    usage_percentage = (current_usage / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
    
    alerts = []
    
    # Check for alerts
    if usage_percentage >= 100:
        alerts.append(BudgetAlertResponse(
            budget_id=budget_id,
            budget_name=budget.name,
            alert_type="exceeded",
            current_usage=current_usage,
            limit_amount=budget.limit_amount,
            usage_percentage=usage_percentage,
            message=f"Budget '{budget.name}' has been exceeded ({usage_percentage:.1f}% used)"
        ))
    elif usage_percentage >= 90:
        alerts.append(BudgetAlertResponse(
            budget_id=budget_id,
            budget_name=budget.name,
            alert_type="critical",
            current_usage=current_usage,
            limit_amount=budget.limit_amount,
            usage_percentage=usage_percentage,
            message=f"Budget '{budget.name}' is critically high ({usage_percentage:.1f}% used)"
        ))
    elif usage_percentage >= budget.alert_threshold_percent:
        alerts.append(BudgetAlertResponse(
            budget_id=budget_id,
            budget_name=budget.name,
            alert_type="warning",
            current_usage=current_usage,
            limit_amount=budget.limit_amount,
            usage_percentage=usage_percentage,
            message=f"Budget '{budget.name}' has reached alert threshold ({usage_percentage:.1f}% used)"
        ))
    
    return alerts


# Helper functions
async def _calculate_budget_usage(db: AsyncSession, budget: Budget) -> float:
    """Calculate current usage for a budget"""
    
    # Build base query
    query = select(UsageTracking)
    
    # Filter by time period
    query = query.where(
        UsageTracking.created_at >= budget.period_start,
        UsageTracking.created_at <= budget.period_end
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
    
    # Convert cents to dollars for dollar budgets
    if budget.budget_type == "dollars":
        usage = usage / 100.0
    
    return float(usage)


def _calculate_period_bounds(current_time: datetime, period_type: str) -> tuple[datetime, datetime]:
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
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        end = start + timedelta(weeks=1) - timedelta(microseconds=1)
    elif period_type == "monthly":
        start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        end = next_month - timedelta(microseconds=1)
    elif period_type == "yearly":
        start = current_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1) - timedelta(microseconds=1)
    else:
        # Default to daily
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
    
    return start, end


async def _get_usage_history(db: AsyncSession, budget: Budget, days: int = 30) -> List[dict]:
    """Get usage history for the budget"""
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Build query
    query = select(
        func.date(UsageTracking.created_at).label('date'),
        func.sum(UsageTracking.total_tokens).label('tokens'),
        func.sum(UsageTracking.cost_cents).label('cost_cents'),
        func.count(UsageTracking.id).label('requests')
    ).where(
        UsageTracking.created_at >= start_date,
        UsageTracking.created_at <= end_date
    )
    
    # Filter by user or API key
    if budget.api_key_id:
        query = query.where(UsageTracking.api_key_id == budget.api_key_id)
    elif budget.user_id:
        query = query.where(UsageTracking.user_id == budget.user_id)
    
    query = query.group_by(func.date(UsageTracking.created_at)).order_by(func.date(UsageTracking.created_at))
    
    result = await db.execute(query)
    rows = result.fetchall()
    
    history = []
    for row in rows:
        usage_value = 0
        if budget.budget_type == "tokens":
            usage_value = row.tokens or 0
        elif budget.budget_type == "dollars":
            usage_value = (row.cost_cents or 0) / 100.0
        elif budget.budget_type == "requests":
            usage_value = row.requests or 0
        
        history.append({
            "date": row.date.isoformat(),
            "usage": usage_value,
            "tokens": row.tokens or 0,
            "cost_dollars": (row.cost_cents or 0) / 100.0,
            "requests": row.requests or 0
        })
    
    return history