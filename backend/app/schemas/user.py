"""
User Management Schemas
Pydantic models for user management API
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, validator


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr
    username: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False

    @validator("username")
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be less than 50 characters long")
        return v

    @validator("email")
    def validate_email(cls, v):
        if len(v) > 255:
            raise ValueError("Email must be less than 255 characters long")
        return v


class UserCreate(UserBase):
    """Schema for creating a user"""

    password: str
    role_id: Optional[int] = None
    custom_permissions: Dict[str, Any] = {}

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    custom_permissions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

    @validator("username")
    def validate_username(cls, v):
        if v is not None:
            if len(v) < 3:
                raise ValueError("Username must be at least 3 characters long")
            if len(v) > 50:
                raise ValueError("Username must be less than 50 characters long")
        return v


class PasswordChange(BaseModel):
    """Schema for changing password"""

    current_password: Optional[str] = None
    new_password: str
    confirm_password: str

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class RoleInfo(BaseModel):
    """Role information schema"""

    id: int
    name: str
    display_name: str
    level: str
    permissions: Dict[str, Any]

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """User response schema"""

    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_superuser: bool
    role_id: Optional[int]
    role: Optional[RoleInfo]
    custom_permissions: Dict[str, Any]
    account_locked: Optional[bool] = False
    account_locked_until: Optional[datetime]
    failed_login_attempts: Optional[int] = 0
    last_failed_login: Optional[datetime]
    avatar_url: Optional[str]
    bio: Optional[str]
    company: Optional[str]
    website: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    preferences: Dict[str, Any]
    notification_settings: Dict[str, Any]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Create response from ORM object with proper role handling"""
        data = obj.to_dict()
        if obj.role:
            data["role"] = RoleInfo.from_orm(obj.role)
        return cls(**data)


class UserListResponse(BaseModel):
    """User list response schema"""

    users: List[UserResponse]
    total: int
    skip: int
    limit: int


class AccountLockResponse(BaseModel):
    """Account lock response schema"""

    user_id: int
    is_locked: bool
    locked_until: Optional[datetime]
    message: str


class UserProfileUpdate(BaseModel):
    """Schema for user profile updates (limited fields)"""

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    notification_settings: Optional[Dict[str, Any]] = None


class UserPreferences(BaseModel):
    """User preferences schema"""

    theme: Optional[str] = "light"
    language: Optional[str] = "en"
    timezone: Optional[str] = "UTC"
    email_notifications: Optional[bool] = True
    security_alerts: Optional[bool] = True
    system_updates: Optional[bool] = True


class UserSearchFilter(BaseModel):
    """User search filter schema"""

    search: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_login_after: Optional[datetime] = None
    last_login_before: Optional[datetime] = None


class UserBulkAction(BaseModel):
    """Schema for bulk user actions"""

    user_ids: List[int]
    action: str  # activate, deactivate, lock, unlock, assign_role, remove_role
    action_data: Optional[Dict[str, Any]] = None

    @validator("action")
    def validate_action(cls, v):
        valid_actions = [
            "activate",
            "deactivate",
            "lock",
            "unlock",
            "assign_role",
            "remove_role",
        ]
        if v not in valid_actions:
            raise ValueError(f'Action must be one of: {", ".join(valid_actions)}')
        return v

    @validator("user_ids")
    def validate_user_ids(cls, v):
        if not v:
            raise ValueError("At least one user ID must be provided")
        if len(v) > 100:
            raise ValueError(
                "Cannot perform bulk action on more than 100 users at once"
            )
        return v


class UserStatistics(BaseModel):
    """User statistics schema"""

    total_users: int
    active_users: int
    verified_users: int
    locked_users: int
    users_by_role: Dict[str, int]
    recent_registrations: int
    registrations_by_month: Dict[str, int]


class UserActivity(BaseModel):
    """User activity schema"""

    user_id: int
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class UserActivityFilter(BaseModel):
    """User activity filter schema"""

    user_id: Optional[int] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    ip_address: Optional[str] = None
