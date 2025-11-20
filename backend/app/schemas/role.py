"""
Role Management Schemas
Pydantic models for role management API
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, validator


class RoleBase(BaseModel):
    """Base role schema"""

    name: str
    display_name: str
    description: Optional[str] = None
    level: str = "user"
    permissions: Dict[str, Any] = {}
    can_manage_users: bool = False
    can_manage_budgets: bool = False
    can_view_reports: bool = False
    can_manage_tools: bool = False
    inherits_from: List[str] = []
    is_active: bool = True

    @validator("name")
    def validate_name(cls, v):
        if len(v) < 2:
            raise ValueError("Role name must be at least 2 characters long")
        if len(v) > 50:
            raise ValueError("Role name must be less than 50 characters long")
        if not v.isalnum() and "_" not in v:
            raise ValueError(
                "Role name must contain only alphanumeric characters and underscores"
            )
        return v.lower()

    @validator("display_name")
    def validate_display_name(cls, v):
        if len(v) < 2:
            raise ValueError("Display name must be at least 2 characters long")
        if len(v) > 100:
            raise ValueError("Display name must be less than 100 characters long")
        return v

    @validator("level")
    def validate_level(cls, v):
        valid_levels = ["read_only", "user", "admin", "super_admin"]
        if v not in valid_levels:
            raise ValueError(f'Level must be one of: {", ".join(valid_levels)}')
        return v


class RoleCreate(RoleBase):
    """Schema for creating a role"""

    is_system_role: bool = False


class RoleUpdate(BaseModel):
    """Schema for updating a role"""

    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    can_manage_users: Optional[bool] = None
    can_manage_budgets: Optional[bool] = None
    can_view_reports: Optional[bool] = None
    can_manage_tools: Optional[bool] = None
    is_active: Optional[bool] = None

    @validator("display_name")
    def validate_display_name(cls, v):
        if v is not None:
            if len(v) < 2:
                raise ValueError("Display name must be at least 2 characters long")
            if len(v) > 100:
                raise ValueError("Display name must be less than 100 characters long")
        return v


class RoleResponse(BaseModel):
    """Role response schema"""

    id: int
    name: str
    display_name: str
    description: Optional[str]
    level: str
    permissions: Dict[str, Any]
    can_manage_users: bool
    can_manage_budgets: bool
    can_view_reports: bool
    can_manage_tools: bool
    inherits_from: List[str]
    is_active: bool
    is_system_role: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    user_count: Optional[int] = 0  # Number of users with this role

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Create response from ORM object"""
        data = obj.to_dict()
        # Add user count if available
        if hasattr(obj, "users"):
            data["user_count"] = len([u for u in obj.users if u.is_active])
        return cls(**data)


class RoleListResponse(BaseModel):
    """Role list response schema"""

    roles: List[RoleResponse]
    total: int
    skip: int
    limit: int


class RoleAssignmentRequest(BaseModel):
    """Schema for role assignment"""

    role_id: int

    @validator("role_id")
    def validate_role_id(cls, v):
        if v <= 0:
            raise ValueError("Role ID must be a positive integer")
        return v


class RoleBulkAction(BaseModel):
    """Schema for bulk role actions"""

    role_ids: List[int]
    action: str  # activate, deactivate, delete
    action_data: Optional[Dict[str, Any]] = None

    @validator("action")
    def validate_action(cls, v):
        valid_actions = ["activate", "deactivate", "delete"]
        if v not in valid_actions:
            raise ValueError(f'Action must be one of: {", ".join(valid_actions)}')
        return v

    @validator("role_ids")
    def validate_role_ids(cls, v):
        if not v:
            raise ValueError("At least one role ID must be provided")
        if len(v) > 50:
            raise ValueError("Cannot perform bulk action on more than 50 roles at once")
        return v


class RoleStatistics(BaseModel):
    """Role statistics schema"""

    total_roles: int
    active_roles: int
    system_roles: int
    roles_by_level: Dict[str, int]
    roles_with_users: int
    unused_roles: int


class RolePermission(BaseModel):
    """Individual role permission schema"""

    permission: str
    granted: bool = True
    description: Optional[str] = None


class RolePermissionTemplate(BaseModel):
    """Role permission template schema"""

    name: str
    display_name: str
    description: str
    level: str
    permissions: List[RolePermission]
    can_manage_users: bool = False
    can_manage_budgets: bool = False
    can_view_reports: bool = False
    can_manage_tools: bool = False


class RoleHierarchy(BaseModel):
    """Role hierarchy schema"""

    role: RoleResponse
    parent_roles: List[RoleResponse] = []
    child_roles: List[RoleResponse] = []
    effective_permissions: Dict[str, Any]


class RoleComparison(BaseModel):
    """Role comparison schema"""

    role1: RoleResponse
    role2: RoleResponse
    common_permissions: List[str]
    unique_to_role1: List[str]
    unique_to_role2: List[str]


class RoleUsage(BaseModel):
    """Role usage statistics schema"""

    role_id: int
    role_name: str
    user_count: int
    active_user_count: int
    last_assigned: Optional[datetime]
    usage_trend: Dict[str, int]  # Monthly usage data


class RoleSearchFilter(BaseModel):
    """Role search filter schema"""

    search: Optional[str] = None
    level: Optional[str] = None
    is_active: Optional[bool] = None
    is_system_role: Optional[bool] = None
    has_users: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


# Predefined permission templates
ROLE_TEMPLATES = {
    "read_only": RolePermissionTemplate(
        name="read_only",
        display_name="Read Only",
        description="Can view own data only",
        level="read_only",
        permissions=[
            RolePermission(
                permission="read_own", granted=True, description="Read own data"
            ),
            RolePermission(
                permission="create", granted=False, description="Create new resources"
            ),
            RolePermission(
                permission="update",
                granted=False,
                description="Update existing resources",
            ),
            RolePermission(
                permission="delete", granted=False, description="Delete resources"
            ),
        ],
    ),
    "user": RolePermissionTemplate(
        name="user",
        display_name="User",
        description="Standard user with full access to own resources",
        level="user",
        permissions=[
            RolePermission(
                permission="read_own", granted=True, description="Read own data"
            ),
            RolePermission(
                permission="create_own",
                granted=True,
                description="Create own resources",
            ),
            RolePermission(
                permission="update_own",
                granted=True,
                description="Update own resources",
            ),
            RolePermission(
                permission="delete_own",
                granted=True,
                description="Delete own resources",
            ),
            RolePermission(
                permission="manage_users",
                granted=False,
                description="Manage other users",
            ),
            RolePermission(
                permission="manage_all",
                granted=False,
                description="Manage all resources",
            ),
        ],
        inherits_from=["read_only"],
    ),
    "admin": RolePermissionTemplate(
        name="admin",
        display_name="Administrator",
        description="Can manage users and view reports",
        level="admin",
        permissions=[
            RolePermission(
                permission="read_all", granted=True, description="Read all data"
            ),
            RolePermission(
                permission="create_all",
                granted=True,
                description="Create any resources",
            ),
            RolePermission(
                permission="update_all",
                granted=True,
                description="Update any resources",
            ),
            RolePermission(
                permission="manage_users", granted=True, description="Manage users"
            ),
            RolePermission(
                permission="view_reports",
                granted=True,
                description="View system reports",
            ),
            RolePermission(
                permission="system_settings",
                granted=False,
                description="Modify system settings",
            ),
        ],
        can_manage_users=True,
        can_view_reports=True,
        inherits_from=["user"],
    ),
    "super_admin": RolePermissionTemplate(
        name="super_admin",
        display_name="Super Administrator",
        description="Full system access",
        level="super_admin",
        permissions=[
            RolePermission(permission="*", granted=True, description="All permissions")
        ],
        can_manage_users=True,
        can_manage_budgets=True,
        can_view_reports=True,
        can_manage_tools=True,
        inherits_from=["admin"],
    ),
}


# Common permission definitions
COMMON_PERMISSIONS = {
    "read_own": "Read own data and resources",
    "read_all": "Read all data and resources",
    "create_own": "Create own resources",
    "create_all": "Create any resources",
    "update_own": "Update own resources",
    "update_all": "Update any resources",
    "delete_own": "Delete own resources",
    "delete_all": "Delete any resources",
    "manage_users": "Manage user accounts",
    "manage_roles": "Manage role assignments",
    "manage_budgets": "Manage budget settings",
    "view_reports": "View system reports",
    "manage_tools": "Manage custom tools",
    "system_settings": "Modify system settings",
    "create_api_key": "Create API keys",
    "create_tool": "Create custom tools",
    "export_data": "Export system data",
}
