"""
User management API endpoints
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.api_key import APIKey
from app.models.budget import Budget
from app.core.security import get_current_user, get_password_hash, verify_password
from app.services.permission_manager import require_permission
from app.services.audit_service import log_audit_event
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str
    role: str = "user"
    is_active: bool = True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    size: int


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    new_password: str


# User CRUD endpoints
@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users with pagination and filtering"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:users:read")
    
    # Build query
    query = select(User)
    
    # Apply filters
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.full_name.ilike(f"%{search}%"))
        )
    
    # Get total count
    total_query = select(User.id).select_from(query.subquery())
    total_result = await db.execute(total_query)
    total = len(total_result.fetchall())
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="list_users",
        resource_type="user",
        details={"page": page, "size": size, "filters": {"role": role, "is_active": is_active, "search": search}}
    )
    
    return UserListResponse(
        users=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        size=size
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID"""
    
    # Check permissions (users can view their own profile)
    if int(user_id) != current_user['id']:
        require_permission(current_user.get("permissions", []), "platform:users:read")
    
    # Get user
    query = select(User).where(User.id == int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_user",
        resource_type="user",
        resource_id=user_id
    )
    
    return UserResponse.model_validate(user)


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:users:create")
    
    # Check if user already exists
    query = select(User).where(
        (User.username == user_data.username) | (User.email == user_data.email)
    )
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username or email already exists"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=user_data.is_active
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="create_user",
        resource_type="user",
        resource_id=str(new_user.id),
        details={"username": user_data.username, "email": user_data.email, "role": user_data.role}
    )
    
    logger.info(f"User created: {new_user.username} by {current_user['username']}")
    
    return UserResponse.model_validate(new_user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user"""
    
    # Check permissions (users can update their own profile with limited fields)
    is_self_update = int(user_id) == current_user['id']
    if not is_self_update:
        require_permission(current_user.get("permissions", []), "platform:users:update")
    
    # Get user
    query = select(User).where(User.id == int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # For self-updates, restrict what can be changed
    if is_self_update:
        allowed_fields = {"username", "email", "full_name"}
        update_data = user_data.model_dump(exclude_unset=True)
        restricted_fields = set(update_data.keys()) - allowed_fields
        if restricted_fields:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot update fields: {restricted_fields}"
            )
    
    # Store original values for audit
    original_values = {
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }
    
    # Update user fields
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="update_user",
        resource_type="user",
        resource_id=user_id,
        details={
            "updated_fields": list(update_data.keys()),
            "before_values": original_values,
            "after_values": {k: getattr(user, k) for k in update_data.keys()}
        }
    )
    
    logger.info(f"User updated: {user.username} by {current_user['username']}")
    
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user (soft delete by deactivating)"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:users:delete")
    
    # Prevent self-deletion
    if int(user_id) == current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Get user
    query = select(User).where(User.id == int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Soft delete by deactivating
    user.is_active = False
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="delete_user",
        resource_type="user",
        resource_id=user_id,
        details={"username": user.username, "email": user.email}
    )
    
    logger.info(f"User deleted: {user.username} by {current_user['username']}")
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/change-password")
async def change_password(
    user_id: str,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    
    # Users can only change their own password, or admins can change any password
    is_self_update = int(user_id) == current_user['id']
    if not is_self_update:
        require_permission(current_user.get("permissions", []), "platform:users:update")
    
    # Get user
    query = select(User).where(User.id == int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # For self-updates, verify current password
    if is_self_update:
        if not verify_password(password_data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
    
    # Update password
    user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="change_password",
        resource_type="user",
        resource_id=user_id,
        details={"target_user": user.username}
    )
    
    logger.info(f"Password changed for user: {user.username} by {current_user['username']}")
    
    return {"message": "Password changed successfully"}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    password_data: PasswordResetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset user password (admin only)"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:users:update")
    
    # Get user
    query = select(User).where(User.id == int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Reset password
    user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="reset_password",
        resource_type="user",
        resource_id=user_id,
        details={"target_user": user.username}
    )
    
    logger.info(f"Password reset for user: {user.username} by {current_user['username']}")
    
    return {"message": "Password reset successfully"}


@router.get("/{user_id}/api-keys", response_model=List[dict])
async def get_user_api_keys(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get API keys for a user"""
    
    # Check permissions (users can view their own API keys)
    is_self_request = int(user_id) == current_user['id']
    if not is_self_request:
        require_permission(current_user.get("permissions", []), "platform:api-keys:read")
    
    # Get API keys
    query = select(APIKey).where(APIKey.user_id == int(user_id))
    result = await db.execute(query)
    api_keys = result.scalars().all()
    
    # Return safe representation (no key values)
    return [
        {
            "id": str(api_key.id),
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "scopes": api_key.scopes,
            "is_active": api_key.is_active,
            "created_at": api_key.created_at.isoformat(),
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None
        }
        for api_key in api_keys
    ]