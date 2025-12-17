"""
User model
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Numeric,
)
from sqlalchemy.orm import relationship
from sqlalchemy import inspect as sa_inspect
from app.db.database import Base
from decimal import Decimal


class User(Base):
    """User model for authentication and user management"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)  # Legacy field for compatibility

    # Role-based access control (using new Role model)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    custom_permissions = Column(JSON, default=dict)  # Custom permissions override

    # Account management
    account_locked = Column(Boolean, default=False)
    account_locked_until = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime, nullable=True)
    force_password_change = Column(Boolean, default=False)

    # Profile information
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    company = Column(String, nullable=True)
    website = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Settings
    preferences = Column(JSON, default=dict)
    notification_settings = Column(JSON, default=dict)

    # Relationships
    role = relationship("Role", back_populates="users")
    api_keys = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    usage_tracking = relationship(
        "UsageTracking", back_populates="user", cascade="all, delete-orphan"
    )
    budgets = relationship(
        "Budget", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )
    installed_plugins = relationship("Plugin", back_populates="installed_by_user")
    created_tools = relationship(
        "Tool", back_populates="created_by", cascade="all, delete-orphan"
    )
    created_agent_configs = relationship(
        "AgentConfig", back_populates="created_by", cascade="all, delete-orphan", foreign_keys="AgentConfig.created_by_user_id"
    )
    created_mcp_servers = relationship(
        "MCPServer", back_populates="created_by", cascade="all, delete-orphan", foreign_keys="MCPServer.created_by_user_id"
    )
    tool_executions = relationship(
        "ToolExecution", back_populates="executed_by", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"

    def to_dict(self):
        """Convert user to dictionary for API responses"""
        # Check if role relationship is loaded to avoid lazy loading in async context
        inspector = sa_inspect(self)
        role_loaded = "role" not in inspector.unloaded

        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "is_superuser": self.is_superuser,
            "role_id": self.role_id,
            "role": self.role.to_dict() if role_loaded and self.role else None,
            "custom_permissions": self.custom_permissions,
            "account_locked": self.account_locked,
            "account_locked_until": self.account_locked_until.isoformat()
            if self.account_locked_until
            else None,
            "failed_login_attempts": self.failed_login_attempts,
            "last_failed_login": self.last_failed_login.isoformat()
            if self.last_failed_login
            else None,
            "force_password_change": self.force_password_change,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "company": self.company,
            "website": self.website,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preferences": self.preferences,
            "notification_settings": self.notification_settings,
        }

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission using role hierarchy"""
        if self.is_superuser:
            return True

        # Check custom permissions first (override)
        if permission in self.custom_permissions.get("denied", []):
            return False
        if permission in self.custom_permissions.get("granted", []):
            return True

        # Check role permissions if user has a role assigned
        if self.role:
            return self.role.has_permission(permission)

        return False

    def can_access_module(self, module_name: str) -> bool:
        """Check if user can access a specific module"""
        if self.is_superuser:
            return True

        # Check custom permissions first
        module_permissions = self.custom_permissions.get("modules", {})
        if module_name in module_permissions:
            return module_permissions[module_name]

        # Check role permissions
        if self.role:
            # For admin roles, allow all modules
            if self.role.level in ["admin", "super_admin"]:
                return True
            # For regular users, check module access
            elif self.role.level == "user":
                return True  # Basic users can access all modules
            # For read-only users, limit access
            elif self.role.level == "read_only":
                return module_name in ["chatbot", "analytics"]  # Only certain modules

        return False

    def update_last_login(self):
        """Update the last login timestamp"""
        self.last_login = datetime.utcnow()

    def update_preferences(self, preferences: dict):
        """Update user preferences"""
        if self.preferences is None:
            self.preferences = {}
        self.preferences.update(preferences)

    def update_notification_settings(self, settings: dict):
        """Update notification settings"""
        if self.notification_settings is None:
            self.notification_settings = {}
        self.notification_settings.update(settings)

    def get_effective_permissions(self) -> dict:
        """Get all effective permissions combining role and custom permissions"""
        permissions = {"granted": set(), "denied": set()}

        # Start with role permissions
        if self.role:
            role_perms = self.role.permissions
            permissions["granted"].update(role_perms.get("granted", []))
            permissions["denied"].update(role_perms.get("denied", []))

        # Apply custom permissions (override role permissions)
        permissions["granted"].update(self.custom_permissions.get("granted", []))
        permissions["denied"].update(self.custom_permissions.get("denied", []))

        # Remove any denied permissions from granted
        permissions["granted"] -= permissions["denied"]

        return {
            "granted": list(permissions["granted"]),
            "denied": list(permissions["denied"]),
        }

    def can_create_api_key(self) -> bool:
        """Check if user can create API keys based on role and limits"""
        if not self.is_active or self.account_locked:
            return False

        # Check permission
        if not self.has_permission("create_api_key"):
            return False

        # Check if user has reached their API key limit
        current_keys = [key for key in self.api_keys if key.is_active]
        max_keys = (
            self.role.permissions.get("limits", {}).get("max_api_keys", 5)
            if self.role
            else 5
        )

        return len(current_keys) < max_keys

    def can_create_tool(self) -> bool:
        """Check if user can create custom tools"""
        return (
            self.is_active
            and not self.account_locked
            and self.has_permission("create_tool")
        )

    def is_budget_exceeded(self) -> bool:
        """Check if user has exceeded their budget limits"""
        if not self.budgets:
            return False

        active_budget = next((b for b in self.budgets if b.is_active), None)
        if not active_budget:
            return False

        return active_budget.current_usage > active_budget.limit

    def lock_account(self, duration_hours: int = 24):
        """Lock user account for specified duration"""
        from datetime import timedelta

        self.account_locked = True
        self.account_locked_until = datetime.utcnow() + timedelta(hours=duration_hours)

    def unlock_account(self):
        """Unlock user account"""
        self.account_locked = False
        self.account_locked_until = None
        self.failed_login_attempts = 0

    def record_failed_login(self):
        """Record a failed login attempt"""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()

        # Lock account after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.lock_account(24)  # Lock for 24 hours

    def reset_failed_logins(self):
        """Reset failed login counter"""
        self.failed_login_attempts = 0
        self.last_failed_login = None

    @classmethod
    def create_default_admin(
        cls, email: str, username: str, password_hash: str
    ) -> "User":
        """Create a default admin user"""
        return cls(
            email=email,
            username=username,
            hashed_password=password_hash,
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,  # Legacy compatibility
            is_verified=True,
            # Note: role_id will be set after role is created in init_db
            custom_permissions={
                "modules": {"cache": True, "analytics": True, "rag": True}
            },
            preferences={"theme": "dark", "language": "en", "timezone": "UTC"},
            notification_settings={
                "email_notifications": True,
                "security_alerts": True,
                "system_updates": True,
            },
        )
