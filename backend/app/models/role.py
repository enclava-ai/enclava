"""
Role model for hierarchical permission management
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class RoleLevel(str, Enum):
    """Role hierarchy levels"""

    READ_ONLY = "read_only"  # Level 1: Can only view
    USER = "user"  # Level 2: Can create and manage own resources
    ADMIN = "admin"  # Level 3: Can manage users and settings
    SUPER_ADMIN = "super_admin"  # Level 4: Full system access


class Role(Base):
    """Role model with hierarchical permissions"""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    level = Column(String(20), nullable=False)  # RoleLevel enum

    # Permissions configuration
    permissions = Column(JSON, default=dict)  # Granular permissions
    can_manage_users = Column(Boolean, default=False)
    can_manage_budgets = Column(Boolean, default=False)
    can_view_reports = Column(Boolean, default=False)
    can_manage_tools = Column(Boolean, default=False)

    # Role hierarchy
    inherits_from = Column(JSON, default=list)  # List of parent role names

    # Status
    is_active = Column(Boolean, default=True)
    is_system_role = Column(Boolean, default=False)  # System roles cannot be deleted

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}', level='{self.level}')>"

    def to_dict(self):
        """Convert role to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "level": self.level,
            "permissions": self.permissions,
            "can_manage_users": self.can_manage_users,
            "can_manage_budgets": self.can_manage_budgets,
            "can_view_reports": self.can_view_reports,
            "can_manage_tools": self.can_manage_tools,
            "inherits_from": self.inherits_from,
            "is_active": self.is_active,
            "is_system_role": self.is_system_role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def has_permission(self, permission: str) -> bool:
        """Check if role has a specific permission"""
        if self.level == RoleLevel.SUPER_ADMIN:
            return True

        # Check direct permissions
        if permission in self.permissions.get("granted", []):
            return True

        # Check denied permissions
        if permission in self.permissions.get("denied", []):
            return False

        # Check inherited permissions (simplified)
        for parent_role in self.inherits_from:
            # This would require recursive checking in a real implementation
            pass

        return False

    @classmethod
    def create_default_roles(cls):
        """Create default system roles"""
        roles = [
            cls(
                name="read_only",
                display_name="Read Only",
                description="Can view own data only",
                level=RoleLevel.READ_ONLY,
                permissions={
                    "granted": ["read_own"],
                    "denied": ["create", "update", "delete"],
                },
                is_system_role=True,
            ),
            cls(
                name="user",
                display_name="User",
                description="Standard user with full access to own resources",
                level=RoleLevel.USER,
                permissions={
                    "granted": ["read_own", "create_own", "update_own", "delete_own"],
                    "denied": ["manage_users", "manage_all"],
                },
                inherits_from=["read_only"],
                is_system_role=True,
            ),
            cls(
                name="admin",
                display_name="Administrator",
                description="Can manage users and view reports",
                level=RoleLevel.ADMIN,
                permissions={
                    "granted": [
                        "read_all",
                        "create_all",
                        "update_all",
                        "manage_users",
                        "view_reports",
                    ],
                    "denied": ["system_settings"],
                },
                inherits_from=["user"],
                can_manage_users=True,
                can_manage_budgets=True,
                can_view_reports=True,
                is_system_role=True,
            ),
            cls(
                name="super_admin",
                display_name="Super Administrator",
                description="Full system access",
                level=RoleLevel.SUPER_ADMIN,
                permissions={"granted": ["*"]},  # All permissions
                inherits_from=["admin"],
                can_manage_users=True,
                can_manage_budgets=True,
                can_view_reports=True,
                can_manage_tools=True,
                is_system_role=True,
            ),
        ]
        return roles
