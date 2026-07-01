"""
API Key management endpoints
"""

import asyncio
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.database import get_db, utc_now
from app.models.api_key import APIKey
from app.models.user import User
from app.services.audit_service import log_audit_event, log_audit_event_async
from app.services.permission_manager import require_permission

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scopes: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=100000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    allowed_ips: List[str] = Field(default_factory=list)
    allowed_models: List[str] = Field(default_factory=list)  # Model restrictions
    allowed_agents: List[str] = Field(default_factory=list)  # Agent config restrictions
    allowed_extract_templates: List[str] = Field(
        default_factory=list
    )  # Extract template restrictions
    is_unlimited: bool = True  # Unlimited budget flag
    budget_limit_cents: Optional[int] = Field(None, ge=0)  # Budget limit in cents
    budget_type: Optional[str] = Field(None, pattern="^(total|monthly)$")  # Budget type
    tags: List[str] = Field(default_factory=list)


class APIKeyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scopes: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=100000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    allowed_ips: Optional[List[str]] = None
    allowed_models: Optional[List[str]] = None  # Model restrictions
    allowed_agents: Optional[List[str]] = None  # Agent config restrictions
    allowed_extract_templates: Optional[List[str]] = (
        None  # Extract template restrictions
    )
    is_unlimited: Optional[bool] = None  # Unlimited budget flag
    budget_limit_cents: Optional[int] = Field(None, ge=0)  # Budget limit in cents
    budget_type: Optional[str] = Field(None, pattern="^(total|monthly)$")  # Budget type
    tags: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    key_prefix: str
    scopes: List[str]
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    total_requests: int
    total_tokens: int
    total_cost_cents: int = Field(alias="total_cost")
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None
    allowed_ips: List[str]
    allowed_models: List[str]  # Model restrictions
    allowed_agents: List[str]  # Agent config restrictions
    allowed_extract_templates: List[str]  # Extract template restrictions
    budget_limit: Optional[int] = Field(
        None, alias="budget_limit_cents"
    )  # Budget limit in cents
    budget_type: Optional[str] = None  # Budget type
    is_unlimited: bool = True  # Unlimited budget flag
    tags: List[str]
    # Soft delete fields (optional - only present when include_deleted=true)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_api_key(cls, api_key):
        """Create response from APIKey model with formatted key prefix"""
        data = {
            "id": api_key.id,
            "name": api_key.name,
            "description": api_key.description,
            "key_prefix": api_key.key_prefix + "..." if api_key.key_prefix else "",
            "scopes": api_key.scopes,
            "is_active": api_key.is_active,
            "expires_at": api_key.expires_at,
            "created_at": api_key.created_at,
            "last_used_at": api_key.last_used_at,
            "total_requests": api_key.total_requests,
            "total_tokens": api_key.total_tokens,
            "total_cost": api_key.total_cost,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "rate_limit_per_hour": api_key.rate_limit_per_hour,
            "rate_limit_per_day": api_key.rate_limit_per_day,
            "allowed_ips": api_key.allowed_ips,
            "allowed_models": api_key.allowed_models,
            "allowed_agents": api_key.allowed_agents or [],
            "budget_limit_cents": api_key.budget_limit_cents,
            "budget_type": api_key.budget_type,
            "is_unlimited": api_key.is_unlimited,
            "tags": api_key.tags,
            "is_deleted": api_key.is_deleted,
            "deleted_at": api_key.deleted_at,
        }
        return cls(**data)


class APIKeyCreateResponse(BaseModel):
    api_key: APIKeyResponse
    secret_key: str  # Only returned on creation


class APIKeyListResponse(BaseModel):
    api_keys: List[APIKeyResponse]
    total: int
    page: int
    size: int


class APIKeyUsageResponse(BaseModel):
    api_key_id: str
    total_requests: int
    total_tokens: int
    total_cost_cents: int
    requests_today: int
    tokens_today: int
    cost_today_cents: int
    requests_this_hour: int
    tokens_this_hour: int
    cost_this_hour_cents: int
    last_used_at: Optional[datetime] = None


class APIKeyDeleteRequest(BaseModel):
    """Request body for soft deleting an API key"""

    reason: Optional[str] = Field(None, max_length=500)


class APIKeyAdminResponse(APIKeyResponse):
    """Extended response for admin endpoints with soft delete info"""

    deleted_at: Optional[datetime] = None
    deleted_by_user_id: Optional[int] = None
    deletion_reason: Optional[str] = None
    user_id: int

    @classmethod
    def from_api_key(cls, api_key):
        """Create admin response from APIKey model"""
        data = {
            "id": api_key.id,
            "name": api_key.name,
            "description": api_key.description,
            "key_prefix": api_key.key_prefix + "..." if api_key.key_prefix else "",
            "scopes": api_key.scopes,
            "is_active": api_key.is_active,
            "expires_at": api_key.expires_at,
            "created_at": api_key.created_at,
            "last_used_at": api_key.last_used_at,
            "total_requests": api_key.total_requests,
            "total_tokens": api_key.total_tokens,
            "total_cost": api_key.total_cost,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "rate_limit_per_hour": api_key.rate_limit_per_hour,
            "rate_limit_per_day": api_key.rate_limit_per_day,
            "allowed_ips": api_key.allowed_ips,
            "allowed_models": api_key.allowed_models,
            "allowed_agents": api_key.allowed_agents or [],
            "budget_limit_cents": api_key.budget_limit_cents,
            "budget_type": api_key.budget_type,
            "is_unlimited": api_key.is_unlimited,
            "tags": api_key.tags,
            "deleted_at": api_key.deleted_at,
            "deleted_by_user_id": api_key.deleted_by_user_id,
            "deletion_reason": api_key.deletion_reason,
            "user_id": api_key.user_id,
        }
        return cls(**data)


class APIKeyAdminListResponse(BaseModel):
    """Response for admin list of API keys"""

    api_keys: List[APIKeyAdminResponse]
    total: int
    page: int
    size: int


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and return (full_key, key_hash)"""
    # Generate random key part (32 characters)
    key_part = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )

    # Create full key with prefix
    full_key = f"{settings.API_KEY_PREFIX}{key_part}"

    # Create hash for storage
    from app.core.security import get_api_key_hash

    key_hash = get_api_key_hash(full_key)

    return full_key, key_hash


# API Key CRUD endpoints
@router.get("/", response_model=APIKeyListResponse)
async def list_api_keys(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    include_deleted: bool = Query(
        False, description="Include soft-deleted API keys in the results"
    ),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List API keys with pagination and filtering.

    By default, soft-deleted keys are excluded. Use include_deleted=true to see them.
    """

    # Check permissions - users can view their own API keys
    if user_id and int(user_id) != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:read"
        )
    elif not user_id:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:read"
        )

    # If no user_id specified and user doesn't have admin permissions, show only their keys
    if not user_id and "platform:api-keys:read" not in current_user.get(
        "permissions", []
    ):
        user_id = current_user["id"]

    # Build query
    query = select(APIKey)

    # By default, exclude deleted keys
    if not include_deleted:
        query = query.where(APIKey.deleted_at.is_(None))

    # Apply filters
    if user_id:
        query = query.where(
            APIKey.user_id == (int(user_id) if isinstance(user_id, str) else user_id)
        )
    if is_active is not None:
        query = query.where(APIKey.is_active == is_active)
    if search:
        query = query.where(
            (APIKey.name.ilike(f"%{search}%"))
            | (APIKey.description.ilike(f"%{search}%"))
        )

    # Get total count using func.count()
    total_query = select(func.count(APIKey.id))

    # Apply same filters for count (including deleted filter)
    if not include_deleted:
        total_query = total_query.where(APIKey.deleted_at.is_(None))
    if user_id:
        total_query = total_query.where(
            APIKey.user_id == (int(user_id) if isinstance(user_id, str) else user_id)
        )
    if is_active is not None:
        total_query = total_query.where(APIKey.is_active == is_active)
    if search:
        total_query = total_query.where(
            (APIKey.name.ilike(f"%{search}%"))
            | (APIKey.description.ilike(f"%{search}%"))
        )

    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(APIKey.created_at.desc())

    # Execute query
    result = await db.execute(query)
    api_keys = result.scalars().all()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="list_api_keys",
        resource_type="api_key",
        details={
            "page": page,
            "size": size,
            "filters": {"user_id": user_id, "is_active": is_active, "search": search},
        },
    )

    return APIKeyListResponse(
        api_keys=[APIKeyResponse.model_validate(key) for key in api_keys],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get API key by ID"""

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check permissions - users can view their own API keys
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:read"
        )

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
    )

    return APIKeyResponse.model_validate(api_key)


@router.post("/", response_model=APIKeyCreateResponse)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key"""

    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:api-keys:create")

    # Generate API key
    full_key, key_hash = generate_api_key()
    key_prefix = full_key[:8]  # Store only first 8 characters for lookup

    # Create API key
    new_api_key = APIKey(
        name=api_key_data.name,
        description=api_key_data.description,
        key_hash=key_hash,
        key_prefix=key_prefix,
        user_id=current_user["id"],
        scopes=api_key_data.scopes,
        expires_at=api_key_data.expires_at,
        rate_limit_per_minute=api_key_data.rate_limit_per_minute,
        rate_limit_per_hour=api_key_data.rate_limit_per_hour,
        rate_limit_per_day=api_key_data.rate_limit_per_day,
        allowed_ips=api_key_data.allowed_ips,
        allowed_models=api_key_data.allowed_models,
        allowed_agents=api_key_data.allowed_agents,
        allowed_extract_templates=api_key_data.allowed_extract_templates,
        is_unlimited=api_key_data.is_unlimited,
        budget_limit_cents=(
            api_key_data.budget_limit_cents if not api_key_data.is_unlimited else None
        ),
        budget_type=api_key_data.budget_type if not api_key_data.is_unlimited else None,
        tags=api_key_data.tags,
    )

    db.add(new_api_key)
    await db.commit()
    await db.refresh(new_api_key)

    # Log audit event asynchronously (non-blocking)
    asyncio.create_task(
        log_audit_event_async(
            user_id=str(current_user["id"]),
            action="create_api_key",
            resource_type="api_key",
            resource_id=str(new_api_key.id),
            details={"name": api_key_data.name, "scopes": api_key_data.scopes},
        )
    )

    logger.info(f"API key created: {new_api_key.name} by {current_user['username']}")

    return APIKeyCreateResponse(
        api_key=APIKeyResponse.model_validate(new_api_key), secret_key=full_key
    )


@router.put("/{api_key_id}", response_model=APIKeyResponse)
async def update_api_key(
    api_key_id: str,
    api_key_data: APIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update API key"""

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check permissions - users can update their own API keys
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:update"
        )

    # Store original values for audit
    original_values = {
        "name": api_key.name,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active,
    }

    # Update API key fields
    update_data = api_key_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(api_key, field, value)

    await db.commit()
    await db.refresh(api_key)

    # Invalidate API key cache to ensure changes take effect immediately
    from app.services.cached_api_key import cached_api_key_service

    await cached_api_key_service.invalidate_api_key_cache(api_key.key_prefix)

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="update_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={
            "updated_fields": list(update_data.keys()),
            "before_values": original_values,
            "after_values": {k: getattr(api_key, k) for k in update_data.keys()},
        },
    )

    logger.info(f"API key updated: {api_key.name} by {current_user['username']}")

    return APIKeyResponse.model_validate(api_key)


@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: str,
    delete_request: Optional[APIKeyDeleteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete an API key.

    The key will no longer work but is preserved for billing history.
    Usage records maintain their foreign key reference to this key.
    """

    # Get API key (including already deleted ones to provide proper error message)
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check if already deleted
    if api_key.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is already deleted",
        )

    # Check permissions - users can delete their own API keys
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:delete"
        )

    # Extract deletion reason from request body
    reason = delete_request.reason if delete_request else None

    # SECURITY FIX #8: Invalidate cache BEFORE commit to prevent race condition
    # Previously, there was a window between commit and cache invalidation where
    # a deleted key could still authenticate from stale cache data
    from app.services.cached_api_key import cached_api_key_service

    # Invalidate cache first - if this fails, the key remains valid (safe failure mode)
    # If commit fails after this, the cache will be repopulated on next auth attempt
    await cached_api_key_service.invalidate_api_key_cache(api_key.key_prefix)

    # Soft delete API key (preserves for billing)
    api_key.soft_delete(deleted_by_user_id=current_user["id"], reason=reason)
    await db.commit()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="soft_delete_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name, "reason": reason},
    )

    logger.info(
        f"API key soft deleted: {api_key.name} by {current_user['username']} (reason: {reason})"
    )

    return {
        "message": "API key deleted successfully",
        "deleted_at": api_key.deleted_at.isoformat(),
    }


@router.post("/{api_key_id}/regenerate", response_model=APIKeyCreateResponse)
async def regenerate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate API key secret"""

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check permissions - users can regenerate their own API keys
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:update"
        )

    # Generate new API key
    full_key, key_hash = generate_api_key()
    key_prefix = full_key[:8]  # Store only first 8 characters for lookup

    # Update API key
    api_key.key_hash = key_hash
    api_key.key_prefix = key_prefix

    await db.commit()
    await db.refresh(api_key)

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="regenerate_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name},
    )

    logger.info(f"API key regenerated: {api_key.name} by {current_user['username']}")

    return APIKeyCreateResponse(
        api_key=APIKeyResponse.model_validate(api_key), secret_key=full_key
    )


@router.get("/{api_key_id}/usage", response_model=APIKeyUsageResponse)
async def get_api_key_usage(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get API key usage statistics"""

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check permissions - users can view their own API key usage
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:read"
        )

    # Calculate usage statistics
    from app.models.usage_tracking import UsageTracking

    now = utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # Today's usage
    today_query = select(
        func.count(UsageTracking.id),
        func.sum(UsageTracking.total_tokens),
        func.sum(UsageTracking.cost_cents),
    ).where(
        UsageTracking.api_key_id == api_key_id, UsageTracking.created_at >= today_start
    )
    today_result = await db.execute(today_query)
    today_stats = today_result.first()

    # This hour's usage
    hour_query = select(
        func.count(UsageTracking.id),
        func.sum(UsageTracking.total_tokens),
        func.sum(UsageTracking.cost_cents),
    ).where(
        UsageTracking.api_key_id == api_key_id, UsageTracking.created_at >= hour_start
    )
    hour_result = await db.execute(hour_query)
    hour_stats = hour_result.first()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_api_key_usage",
        resource_type="api_key",
        resource_id=api_key_id,
    )

    return APIKeyUsageResponse(
        api_key_id=api_key_id,
        total_requests=api_key.total_requests,
        total_tokens=api_key.total_tokens,
        total_cost_cents=api_key.total_cost_cents,
        requests_today=today_stats[0] or 0,
        tokens_today=today_stats[1] or 0,
        cost_today_cents=today_stats[2] or 0,
        requests_this_hour=hour_stats[0] or 0,
        tokens_this_hour=hour_stats[1] or 0,
        cost_this_hour_cents=hour_stats[2] or 0,
        last_used_at=api_key.last_used_at,
    )


@router.post("/{api_key_id}/activate")
async def activate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate API key"""

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check permissions - users can activate their own API keys
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:update"
        )

    # Activate API key
    api_key.is_active = True
    await db.commit()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="activate_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name},
    )

    logger.info(f"API key activated: {api_key.name} by {current_user['username']}")

    return {"message": "API key activated successfully"}


@router.post("/{api_key_id}/deactivate")
async def deactivate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate API key"""

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check permissions - users can deactivate their own API keys
    if api_key.user_id != current_user["id"]:
        require_permission(
            current_user.get("permissions", []), "platform:api-keys:update"
        )

    # Deactivate API key
    api_key.is_active = False
    await db.commit()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="deactivate_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name},
    )

    logger.info(f"API key deactivated: {api_key.name} by {current_user['username']}")

    return {"message": "API key deactivated successfully"}


# =============================================================================
# Admin Endpoints for Soft-Deleted API Keys
# =============================================================================


@router.get("/admin/deleted", response_model=APIKeyAdminListResponse)
async def list_deleted_api_keys(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all soft-deleted API keys.

    Admin-only endpoint for viewing deleted keys across the platform.
    Useful for auditing and restoration.
    """

    # Require admin permission
    require_permission(current_user.get("permissions", []), "platform:api-keys:admin")

    # Build query - only deleted keys
    query = select(APIKey).where(APIKey.deleted_at.isnot(None))

    # Apply filters
    if user_id:
        query = query.where(APIKey.user_id == user_id)
    if search:
        query = query.where(
            (APIKey.name.ilike(f"%{search}%"))
            | (APIKey.description.ilike(f"%{search}%"))
        )

    # Get total count
    total_query = select(func.count(APIKey.id)).where(APIKey.deleted_at.isnot(None))
    if user_id:
        total_query = total_query.where(APIKey.user_id == user_id)
    if search:
        total_query = total_query.where(
            (APIKey.name.ilike(f"%{search}%"))
            | (APIKey.description.ilike(f"%{search}%"))
        )

    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(APIKey.deleted_at.desc())

    # Execute query
    result = await db.execute(query)
    api_keys = result.scalars().all()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="list_deleted_api_keys",
        resource_type="api_key",
        details={"page": page, "size": size, "user_id_filter": user_id},
    )

    return APIKeyAdminListResponse(
        api_keys=[APIKeyAdminResponse.from_api_key(key) for key in api_keys],
        total=total,
        page=page,
        size=size,
    )


@router.get("/admin/all", response_model=APIKeyAdminListResponse)
async def list_all_api_keys_admin(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    include_deleted: bool = Query(
        True, description="Include deleted keys (default: True)"
    ),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all API keys (admin view).

    Admin-only endpoint that returns all API keys including deleted ones by default.
    Provides complete visibility for billing, auditing, and support purposes.
    """

    # Require admin permission
    require_permission(current_user.get("permissions", []), "platform:api-keys:admin")

    # Build query
    query = select(APIKey)

    # Apply deleted filter
    if not include_deleted:
        query = query.where(APIKey.deleted_at.is_(None))

    # Apply filters
    if user_id:
        query = query.where(APIKey.user_id == user_id)
    if is_active is not None:
        query = query.where(APIKey.is_active == is_active)
    if search:
        query = query.where(
            (APIKey.name.ilike(f"%{search}%"))
            | (APIKey.description.ilike(f"%{search}%"))
        )

    # Get total count
    total_query = select(func.count(APIKey.id))
    if not include_deleted:
        total_query = total_query.where(APIKey.deleted_at.is_(None))
    if user_id:
        total_query = total_query.where(APIKey.user_id == user_id)
    if is_active is not None:
        total_query = total_query.where(APIKey.is_active == is_active)
    if search:
        total_query = total_query.where(
            (APIKey.name.ilike(f"%{search}%"))
            | (APIKey.description.ilike(f"%{search}%"))
        )

    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(APIKey.created_at.desc())

    # Execute query
    result = await db.execute(query)
    api_keys = result.scalars().all()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="list_all_api_keys_admin",
        resource_type="api_key",
        details={
            "page": page,
            "size": size,
            "user_id_filter": user_id,
            "include_deleted": include_deleted,
        },
    )

    return APIKeyAdminListResponse(
        api_keys=[APIKeyAdminResponse.from_api_key(key) for key in api_keys],
        total=total,
        page=page,
        size=size,
    )


@router.post("/admin/{api_key_id}/restore", response_model=APIKeyAdminResponse)
async def restore_api_key(
    api_key_id: str,
    activate: bool = Query(False, description="Also activate the key after restoring"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore a soft-deleted API key.

    Admin-only endpoint to restore a deleted API key.
    The key's is_active status is NOT automatically changed unless activate=true.
    """

    # Require admin permission
    require_permission(current_user.get("permissions", []), "platform:api-keys:admin")

    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Check if the key is actually deleted
    if not api_key.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is not deleted",
        )

    # Store original deleted info for audit
    original_deleted_at = api_key.deleted_at
    original_deleted_by = api_key.deleted_by_user_id
    original_reason = api_key.deletion_reason

    # Restore the key
    api_key.restore()

    # Optionally activate the key
    if activate:
        api_key.is_active = True

    await db.commit()
    await db.refresh(api_key)

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="restore_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={
            "name": api_key.name,
            "activated": activate,
            "original_deleted_at": (
                original_deleted_at.isoformat() if original_deleted_at else None
            ),
            "original_deleted_by": original_deleted_by,
            "original_reason": original_reason,
        },
    )

    logger.info(
        f"API key restored: {api_key.name} by {current_user['username']} "
        f"(activated: {activate})"
    )

    return APIKeyAdminResponse.from_api_key(api_key)


@router.get("/admin/{api_key_id}", response_model=APIKeyAdminResponse)
async def get_api_key_admin(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get API key details (admin view).

    Admin-only endpoint that returns complete API key info including
    soft-delete details. Works for both deleted and non-deleted keys.
    """

    # Require admin permission
    require_permission(current_user.get("permissions", []), "platform:api-keys:admin")

    # Get API key (including deleted ones)
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_api_key_admin",
        resource_type="api_key",
        resource_id=api_key_id,
    )

    return APIKeyAdminResponse.from_api_key(api_key)
