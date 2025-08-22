"""
User model
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class UserRole(str, Enum):
    """User role enumeration"""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    """User model for authentication and user management"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    
    # User status and permissions
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    
    # Role-based access control
    role = Column(String, default=UserRole.USER.value)  # user, admin, super_admin
    permissions = Column(JSON, default=dict)  # Custom permissions
    
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
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    usage_tracking = relationship("UsageTracking", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    installed_plugins = relationship("Plugin", back_populates="installed_by_user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
    
    def to_dict(self):
        """Convert user to dictionary for API responses"""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "is_verified": self.is_verified,
            "role": self.role,
            "permissions": self.permissions,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "company": self.company,
            "website": self.website,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preferences": self.preferences,
            "notification_settings": self.notification_settings
        }
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        if self.is_superuser:
            return True
        
        # Check role-based permissions
        role_permissions = {
            "user": ["read_own", "create_own", "update_own"],
            "admin": ["read_all", "create_all", "update_all", "delete_own"],
            "super_admin": ["read_all", "create_all", "update_all", "delete_all", "manage_users", "manage_modules"]
        }
        
        if self.role in role_permissions and permission in role_permissions[self.role]:
            return True
        
        # Check custom permissions
        return permission in self.permissions
    
    def can_access_module(self, module_name: str) -> bool:
        """Check if user can access a specific module"""
        if self.is_superuser:
            return True
        
        # Check module-specific permissions
        module_permissions = self.permissions.get("modules", {})
        return module_permissions.get(module_name, False)
    
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
    
    @classmethod
    def create_default_admin(cls, email: str, username: str, password_hash: str) -> "User":
        """Create a default admin user"""
        return cls(
            email=email,
            username=username,
            hashed_password=password_hash,
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
            is_verified=True,
            role="super_admin",
            permissions={
                "modules": {
                    "cache": True,
                    "analytics": True,
                    "rag": True
                }
            },
            preferences={
                "theme": "dark",
                "language": "en",
                "timezone": "UTC"
            },
            notification_settings={
                "email_notifications": True,
                "security_alerts": True,
                "system_updates": True
            }
        )