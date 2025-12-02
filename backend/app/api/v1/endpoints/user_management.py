"""
User Management API endpoints
Admin endpoints for managing users, roles, and audit logs
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, validator, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.role import Role
from app.models.audit_log import AuditLog
from app.services.user_management_service import UserManagementService
from app.services.permission_manager import require_permission
from app.schemas.role import RoleCreate, RoleUpdate

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


# Request/Response Models
class CreateUserRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    is_active: bool = True
    force_password_change: bool = False

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @validator("username")
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must contain only alphanumeric characters, underscores, and hyphens")
        return v


class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    custom_permissions: Optional[Dict[str, Any]] = None

    @validator("username")
    def validate_username(cls, v):
        if v is not None and len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return v


class AdminPasswordResetRequest(BaseModel):
    new_password: str
    force_change_on_login: bool = True

    @validator("new_password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role_id: Optional[int]
    role: Optional[Dict[str, Any]]
    is_active: bool
    is_verified: bool
    account_locked: bool
    force_password_change: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    audit_summary: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    skip: int
    limit: int


class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    level: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: str
    resource_id: Optional[str]
    description: str
    details: Dict[str, Any]
    severity: str
    category: Optional[str]
    success: bool
    created_at: datetime

    class Config:
        from_attributes = True


# User Management Endpoints
@router.get("/users", response_model=UserListResponse)
async def get_users(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    include_audit_summary: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all users with filtering options"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:read",
        context={"user_id": current_user["id"]}
    )

    service = UserManagementService(db)
    users_data = await service.get_users(
        skip=skip,
        limit=limit,
        search=search,
        role_id=role_id,
        is_active=is_active,
    )

    # Convert to response format
    users = []
    for user in users_data:
        user_dict = user.to_dict()
        if include_audit_summary:
            # Get audit summary for user
            audit_logs = await service.get_user_audit_logs(user.id, limit=10)
            user_dict["audit_summary"] = {
                "recent_actions": len(audit_logs),
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }
        user_response = UserResponse(**user_dict)
        users.append(user_response)

    return UserListResponse(
        users=users,
        total=len(users),  # Would need actual count query for large datasets
        skip=skip,
        limit=limit,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    include_audit_summary: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get specific user by ID"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:read",
        context={"user_id": current_user["id"], "owner_id": user_id}
    )

    service = UserManagementService(db)
    user = await service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_dict = user.to_dict()

    if include_audit_summary:
        # Get audit summary for user
        audit_logs = await service.get_user_audit_logs(user_id, limit=10)
        user_dict["audit_summary"] = {
            "recent_actions": len(audit_logs),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    return UserResponse(**user_dict)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:create",
    )

    service = UserManagementService(db)

    user = await service.create_user(
        email=user_data.email,
        username=user_data.username,
        password=user_data.password,
        full_name=user_data.full_name,
        role_id=user_data.role_id,
        is_active=user_data.is_active,
        is_verified=True,  # Admin-created users are verified by default
        custom_permissions={},  # Empty by default
    )

    # Log user creation in audit
    await service._log_audit_event(
        user_id=current_user["id"],
        action="create",
        resource_type="user",
        resource_id=str(user.id),
        description=f"User created by admin: {user.email}",
        details={
            "created_by": current_user["email"],
            "target_user": user.email,
            "role_id": user_data.role_id,
        },
        severity="medium",
    )

    user_dict = user.to_dict()
    return UserResponse(**user_dict)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UpdateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user information"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:update",
        context={"user_id": current_user["id"], "owner_id": user_id}
    )

    service = UserManagementService(db)

    # Get current user for audit comparison
    current_user_data = await service.get_user_by_id(user_id)
    if not current_user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    old_values = current_user_data.to_dict()

    # Update user
    user = await service.update_user(
        user_id=user_id,
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        role_id=user_data.role_id,
        is_active=user_data.is_active,
        is_verified=user_data.is_verified,
        custom_permissions=user_data.custom_permissions,
    )

    # Log user update in audit
    await service._log_audit_event(
        user_id=current_user["id"],
        action="update",
        resource_type="user",
        resource_id=str(user_id),
        description=f"User updated by admin: {user.email}",
        details={
            "updated_by": current_user["email"],
            "target_user": user.email,
        },
        old_values=old_values,
        new_values=user.to_dict(),
        severity="medium",
    )

    user_dict = user.to_dict()
    return UserResponse(**user_dict)


@router.post("/users/{user_id}/password-reset")
async def admin_reset_password(
    user_id: int,
    password_data: AdminPasswordResetRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin reset user password with forced change option"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:manage",
    )

    service = UserManagementService(db)

    user = await service.admin_reset_user_password(
        user_id=user_id,
        new_password=password_data.new_password,
        force_change_on_login=password_data.force_change_on_login,
        admin_user_id=current_user["id"],
    )

    return {
        "message": f"Password reset for user {user.email}",
        "force_change_on_login": password_data.force_change_on_login,
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    hard_delete: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete or deactivate user"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:delete",
    )

    service = UserManagementService(db)

    # Get user info for audit before deletion
    user = await service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_email = user.email

    # Delete user
    success = await service.delete_user(user_id, hard_delete=hard_delete)

    # Log user deletion in audit
    await service._log_audit_event(
        user_id=current_user["id"],
        action="delete",
        resource_type="user",
        resource_id=str(user_id),
        description=f"User {'hard deleted' if hard_delete else 'deactivated'} by admin: {user_email}",
        details={
            "deleted_by": current_user["email"],
            "target_user": user_email,
            "hard_delete": hard_delete,
        },
        severity="high",
    )

    return {
        "message": f"User {'deleted' if hard_delete else 'deactivated'} successfully",
        "user_email": user_email,
    }


# Role Management Endpoints
@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all available roles"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:roles:read",
    )

    service = UserManagementService(db)
    roles = await service.get_roles(is_active=True)

    return [RoleResponse(**role.to_dict()) for role in roles]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new role"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:roles:create",
    )

    service = UserManagementService(db)

    # Create role
    role = await service.create_role(
        name=role_data.name,
        display_name=role_data.display_name,
        description=role_data.description,
        level=role_data.level,
        permissions=role_data.permissions,
        can_manage_users=role_data.can_manage_users,
        can_manage_budgets=role_data.can_manage_budgets,
        can_view_reports=role_data.can_view_reports,
        can_manage_tools=role_data.can_manage_tools,
        inherits_from=role_data.inherits_from,
        is_active=role_data.is_active,
        is_system_role=role_data.is_system_role,
    )

    # Log role creation
    await service._log_audit_event(
        user_id=current_user["id"],
        action="create",
        resource_type="role",
        resource_id=str(role.id),
        description=f"Role created: {role.name}",
        details={
            "created_by": current_user["email"],
            "role_name": role.name,
            "level": role.level,
        },
        severity="medium",
    )

    return RoleResponse(**role.to_dict())


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a role"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:roles:update",
    )

    service = UserManagementService(db)

    # Get current role for audit
    current_role = await service.get_role_by_id(role_id)
    if not current_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Prevent updating system roles
    if current_role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system roles"
        )

    old_values = current_role.to_dict()

    # Update role
    role = await service.update_role(
        role_id=role_id,
        display_name=role_data.display_name,
        description=role_data.description,
        permissions=role_data.permissions,
        can_manage_users=role_data.can_manage_users,
        can_manage_budgets=role_data.can_manage_budgets,
        can_view_reports=role_data.can_view_reports,
        can_manage_tools=role_data.can_manage_tools,
        is_active=role_data.is_active,
    )

    # Log role update
    await service._log_audit_event(
        user_id=current_user["id"],
        action="update",
        resource_type="role",
        resource_id=str(role_id),
        description=f"Role updated: {role.name}",
        details={
            "updated_by": current_user["email"],
            "role_name": role.name,
        },
        old_values=old_values,
        new_values=role.to_dict(),
        severity="medium",
    )

    return RoleResponse(**role.to_dict())


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a role"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:roles:delete",
    )

    service = UserManagementService(db)

    # Get role info for audit before deletion
    role = await service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Prevent deleting system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system roles"
        )

    role_name = role.name

    # Delete role
    success = await service.delete_role(role_id)

    # Log role deletion
    await service._log_audit_event(
        user_id=current_user["id"],
        action="delete",
        resource_type="role",
        resource_id=str(role_id),
        description=f"Role deleted: {role_name}",
        details={
            "deleted_by": current_user["email"],
            "role_name": role_name,
        },
        severity="high",
    )

    return {
        "message": f"Role {role_name} deleted successfully",
        "role_name": role_name,
    }


# Audit Log Endpoints
@router.get("/users/{user_id}/audit-logs", response_model=List[AuditLogResponse])
async def get_user_audit_logs(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    action_filter: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs for a specific user"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:audit:read",
        context={"user_id": current_user["id"], "owner_id": user_id}
    )

    service = UserManagementService(db)
    audit_logs = await service.get_user_audit_logs(
        user_id=user_id,
        skip=skip,
        limit=limit,
        action_filter=action_filter,
    )

    return [AuditLogResponse(**log.to_dict()) for log in audit_logs]


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_all_audit_logs(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    action_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all audit logs with filtering"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:audit:read",
    )

    # Direct database query for audit logs with filters
    from sqlalchemy import select, and_, desc

    query = select(AuditLog)
    conditions = []

    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action_filter:
        conditions.append(AuditLog.action == action_filter)
    if category_filter:
        conditions.append(AuditLog.category == category_filter)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(desc(AuditLog.created_at))
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    audit_logs = result.scalars().all()

    return [AuditLogResponse(**log.to_dict()) for log in audit_logs]


# Statistics Endpoints
@router.get("/statistics")
async def get_user_management_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user management statistics"""

    # Check permission
    require_permission(
        current_user.get("permissions", []),
        "platform:users:read",
    )

    service = UserManagementService(db)
    user_stats = await service.get_user_statistics()
    role_stats = await service.get_role_statistics()

    return {
        "users": user_stats,
        "roles": role_stats,
        "generated_at": datetime.utcnow().isoformat(),
    }