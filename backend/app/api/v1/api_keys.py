"""
API Key management endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from datetime import datetime, timedelta
import asyncio
import secrets
import string

from app.db.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.core.security import get_current_user
from app.services.permission_manager import require_permission
from app.services.audit_service import log_audit_event, log_audit_event_async
from app.core.logging import get_logger
from app.core.config import settings

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
    allowed_chatbots: List[str] = Field(default_factory=list)  # Chatbot restrictions
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
    allowed_chatbots: Optional[List[str]] = None  # Chatbot restrictions
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
    total_cost_cents: int = Field(alias='total_cost')
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None
    allowed_ips: List[str]
    allowed_models: List[str]  # Model restrictions
    allowed_chatbots: List[str]  # Chatbot restrictions
    budget_limit: Optional[int] = Field(None, alias='budget_limit_cents')  # Budget limit in cents
    budget_type: Optional[str] = None  # Budget type
    is_unlimited: bool = True  # Unlimited budget flag
    tags: List[str]

    class Config:
        from_attributes = True
        
    @classmethod
    def from_api_key(cls, api_key):
        """Create response from APIKey model with formatted key prefix"""
        data = {
            'id': api_key.id,
            'name': api_key.name,
            'description': api_key.description,
            'key_prefix': api_key.key_prefix + "..." if api_key.key_prefix else "",
            'scopes': api_key.scopes,
            'is_active': api_key.is_active,
            'expires_at': api_key.expires_at,
            'created_at': api_key.created_at,
            'last_used_at': api_key.last_used_at,
            'total_requests': api_key.total_requests,
            'total_tokens': api_key.total_tokens,
            'total_cost': api_key.total_cost,
            'rate_limit_per_minute': api_key.rate_limit_per_minute,
            'rate_limit_per_hour': api_key.rate_limit_per_hour,
            'rate_limit_per_day': api_key.rate_limit_per_day,
            'allowed_ips': api_key.allowed_ips,
            'allowed_models': api_key.allowed_models,
            'allowed_chatbots': api_key.allowed_chatbots,
            'budget_limit_cents': api_key.budget_limit_cents,
            'budget_type': api_key.budget_type,
            'is_unlimited': api_key.is_unlimited,
            'tags': api_key.tags
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


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and return (full_key, key_hash)"""
    # Generate random key part (32 characters)
    key_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
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
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List API keys with pagination and filtering"""
    
    # Check permissions - users can view their own API keys
    if user_id and int(user_id) != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:read")
    elif not user_id:
        require_permission(current_user.get("permissions", []), "platform:api-keys:read")
        
    # If no user_id specified and user doesn't have admin permissions, show only their keys
    if not user_id and "platform:api-keys:read" not in current_user.get("permissions", []):
        user_id = current_user['id']
    
    # Build query
    query = select(APIKey)
    
    # Apply filters
    if user_id:
        query = query.where(APIKey.user_id == (int(user_id) if isinstance(user_id, str) else user_id))
    if is_active is not None:
        query = query.where(APIKey.is_active == is_active)
    if search:
        query = query.where(
            (APIKey.name.ilike(f"%{search}%")) |
            (APIKey.description.ilike(f"%{search}%"))
        )
    
    # Get total count using func.count()
    total_query = select(func.count(APIKey.id))
    
    # Apply same filters for count
    if user_id:
        total_query = total_query.where(APIKey.user_id == (int(user_id) if isinstance(user_id, str) else user_id))
    if is_active is not None:
        total_query = total_query.where(APIKey.is_active == is_active)
    if search:
        total_query = total_query.where(
            (APIKey.name.ilike(f"%{search}%")) |
            (APIKey.description.ilike(f"%{search}%"))
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
        user_id=current_user['id'],
        action="list_api_keys",
        resource_type="api_key",
        details={"page": page, "size": size, "filters": {"user_id": user_id, "is_active": is_active, "search": search}}
    )
    
    return APIKeyListResponse(
        api_keys=[APIKeyResponse.model_validate(key) for key in api_keys],
        total=total,
        page=page,
        size=size
    )


@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get API key by ID"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can view their own API keys
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:read")
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_api_key",
        resource_type="api_key",
        resource_id=api_key_id
    )
    
    return APIKeyResponse.model_validate(api_key)


@router.post("/", response_model=APIKeyCreateResponse)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
        user_id=current_user['id'],
        scopes=api_key_data.scopes,
        expires_at=api_key_data.expires_at,
        rate_limit_per_minute=api_key_data.rate_limit_per_minute,
        rate_limit_per_hour=api_key_data.rate_limit_per_hour,
        rate_limit_per_day=api_key_data.rate_limit_per_day,
        allowed_ips=api_key_data.allowed_ips,
        allowed_models=api_key_data.allowed_models,
        allowed_chatbots=api_key_data.allowed_chatbots,
        is_unlimited=api_key_data.is_unlimited,
        budget_limit_cents=api_key_data.budget_limit_cents if not api_key_data.is_unlimited else None,
        budget_type=api_key_data.budget_type if not api_key_data.is_unlimited else None,
        tags=api_key_data.tags
    )
    
    db.add(new_api_key)
    await db.commit()
    await db.refresh(new_api_key)
    
    # Log audit event asynchronously (non-blocking)
    asyncio.create_task(log_audit_event_async(
        user_id=str(current_user['id']),
        action="create_api_key",
        resource_type="api_key",
        resource_id=str(new_api_key.id),
        details={"name": api_key_data.name, "scopes": api_key_data.scopes}
    ))
    
    logger.info(f"API key created: {new_api_key.name} by {current_user['username']}")
    
    return APIKeyCreateResponse(
        api_key=APIKeyResponse.model_validate(new_api_key),
        secret_key=full_key
    )


@router.put("/{api_key_id}", response_model=APIKeyResponse)
async def update_api_key(
    api_key_id: str,
    api_key_data: APIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update API key"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can update their own API keys
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:update")
    
    # Store original values for audit
    original_values = {
        "name": api_key.name,
        "scopes": api_key.scopes,
        "is_active": api_key.is_active
    }
    
    # Update API key fields
    update_data = api_key_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(api_key, field, value)
    
    await db.commit()
    await db.refresh(api_key)
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="update_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={
            "updated_fields": list(update_data.keys()),
            "before_values": original_values,
            "after_values": {k: getattr(api_key, k) for k in update_data.keys()}
        }
    )
    
    logger.info(f"API key updated: {api_key.name} by {current_user['username']}")
    
    return APIKeyResponse.model_validate(api_key)


@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete API key"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can delete their own API keys
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:delete")
    
    # Delete API key
    await db.delete(api_key)
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="delete_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name}
    )
    
    logger.info(f"API key deleted: {api_key.name} by {current_user['username']}")
    
    return {"message": "API key deleted successfully"}


@router.post("/{api_key_id}/regenerate", response_model=APIKeyCreateResponse)
async def regenerate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate API key secret"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can regenerate their own API keys
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:update")
    
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
        user_id=current_user['id'],
        action="regenerate_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name}
    )
    
    logger.info(f"API key regenerated: {api_key.name} by {current_user['username']}")
    
    return APIKeyCreateResponse(
        api_key=APIKeyResponse.model_validate(api_key),
        secret_key=full_key
    )


@router.get("/{api_key_id}/usage", response_model=APIKeyUsageResponse)
async def get_api_key_usage(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get API key usage statistics"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can view their own API key usage
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:read")
    
    # Calculate usage statistics
    from app.models.usage_tracking import UsageTracking
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    
    # Today's usage
    today_query = select(
        func.count(UsageTracking.id),
        func.sum(UsageTracking.total_tokens),
        func.sum(UsageTracking.cost_cents)
    ).where(
        UsageTracking.api_key_id == api_key_id,
        UsageTracking.created_at >= today_start
    )
    today_result = await db.execute(today_query)
    today_stats = today_result.first()
    
    # This hour's usage
    hour_query = select(
        func.count(UsageTracking.id),
        func.sum(UsageTracking.total_tokens),
        func.sum(UsageTracking.cost_cents)
    ).where(
        UsageTracking.api_key_id == api_key_id,
        UsageTracking.created_at >= hour_start
    )
    hour_result = await db.execute(hour_query)
    hour_stats = hour_result.first()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_api_key_usage",
        resource_type="api_key",
        resource_id=api_key_id
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
        last_used_at=api_key.last_used_at
    )


@router.post("/{api_key_id}/activate")
async def activate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Activate API key"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can activate their own API keys
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:update")
    
    # Activate API key
    api_key.is_active = True
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="activate_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name}
    )
    
    logger.info(f"API key activated: {api_key.name} by {current_user['username']}")
    
    return {"message": "API key activated successfully"}


@router.post("/{api_key_id}/deactivate")
async def deactivate_api_key(
    api_key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate API key"""
    
    # Get API key
    query = select(APIKey).where(APIKey.id == int(api_key_id))
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions - users can deactivate their own API keys
    if api_key.user_id != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:api-keys:update")
    
    # Deactivate API key
    api_key.is_active = False
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="deactivate_api_key",
        resource_type="api_key",
        resource_id=api_key_id,
        details={"name": api_key.name}
    )
    
    logger.info(f"API key deactivated: {api_key.name} by {current_user['username']}")
    
    return {"message": "API key deactivated successfully"}