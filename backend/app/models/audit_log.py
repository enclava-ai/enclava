"""
Audit log model for tracking system events and user actions
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base
from enum import Enum


class AuditAction(str, Enum):
    """Audit action types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    API_KEY_CREATE = "api_key_create"
    API_KEY_DELETE = "api_key_delete"
    BUDGET_CREATE = "budget_create"
    BUDGET_UPDATE = "budget_update"
    BUDGET_EXCEED = "budget_exceed"
    MODULE_ENABLE = "module_enable"
    MODULE_DISABLE = "module_disable"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    SYSTEM_CONFIG = "system_config"
    SECURITY_EVENT = "security_event"


class AuditSeverity(str, Enum):
    """Audit severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLog(Base):
    """Audit log model for tracking system events and user actions"""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # User relationship (nullable for system events)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="audit_logs")
    
    # Event details
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)  # user, api_key, budget, module, etc.
    resource_id = Column(String, nullable=True)  # ID of the affected resource
    
    # Event description and details
    description = Column(Text, nullable=False)
    details = Column(JSON, default=dict)  # Additional event details
    
    # Request context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
    
    # Event classification
    severity = Column(String, default=AuditSeverity.LOW)
    category = Column(String, nullable=True)  # security, access, data, system
    
    # Success/failure tracking
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Additional metadata
    tags = Column(JSON, default=list)
    audit_metadata = Column("metadata", JSON, default=dict)  # Map to 'metadata' column in DB
    
    # Before/after values for data changes
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
    
    def to_dict(self):
        """Convert audit log to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "severity": self.severity,
            "category": self.category,
            "success": self.success,
            "error_message": self.error_message,
            "tags": self.tags,
            "metadata": self.audit_metadata,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def is_security_event(self) -> bool:
        """Check if this is a security-related event"""
        security_actions = [
            AuditAction.LOGIN,
            AuditAction.LOGOUT,
            AuditAction.API_KEY_CREATE,
            AuditAction.API_KEY_DELETE,
            AuditAction.PERMISSION_GRANT,
            AuditAction.PERMISSION_REVOKE,
            AuditAction.SECURITY_EVENT
        ]
        return self.action in security_actions or self.category == "security"
    
    def is_high_severity(self) -> bool:
        """Check if this is a high severity event"""
        return self.severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]
    
    def add_tag(self, tag: str):
        """Add a tag to the audit log"""
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str):
        """Remove a tag from the audit log"""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def update_metadata(self, key: str, value: Any):
        """Update metadata"""
        if self.audit_metadata is None:
            self.audit_metadata = {}
        self.audit_metadata[key] = value
    
    def set_before_after(self, old_values: Dict[str, Any], new_values: Dict[str, Any]):
        """Set before and after values for data changes"""
        self.old_values = old_values
        self.new_values = new_values
    
    @classmethod
    def create_login_event(cls, user_id: int, success: bool = True, 
                          ip_address: str = None, user_agent: str = None, 
                          session_id: str = None, error_message: str = None) -> "AuditLog":
        """Create a login audit event"""
        return cls(
            user_id=user_id,
            action=AuditAction.LOGIN,
            resource_type="user",
            resource_id=str(user_id),
            description=f"User login {'successful' if success else 'failed'}",
            details={
                "login_method": "password",
                "success": success
            },
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            severity=AuditSeverity.LOW if success else AuditSeverity.MEDIUM,
            category="security",
            success=success,
            error_message=error_message,
            tags=["authentication", "login"]
        )
    
    @classmethod
    def create_logout_event(cls, user_id: int, session_id: str = None) -> "AuditLog":
        """Create a logout audit event"""
        return cls(
            user_id=user_id,
            action=AuditAction.LOGOUT,
            resource_type="user",
            resource_id=str(user_id),
            description="User logout",
            details={
                "logout_method": "manual"
            },
            session_id=session_id,
            severity=AuditSeverity.LOW,
            category="security",
            success=True,
            tags=["authentication", "logout"]
        )
    
    @classmethod
    def create_api_key_event(cls, user_id: int, action: str, api_key_id: int, 
                           api_key_name: str, success: bool = True, 
                           error_message: str = None) -> "AuditLog":
        """Create an API key audit event"""
        return cls(
            user_id=user_id,
            action=action,
            resource_type="api_key",
            resource_id=str(api_key_id),
            description=f"API key {action}: {api_key_name}",
            details={
                "api_key_name": api_key_name,
                "action": action
            },
            severity=AuditSeverity.MEDIUM,
            category="security",
            success=success,
            error_message=error_message,
            tags=["api_key", action]
        )
    
    @classmethod
    def create_budget_event(cls, user_id: int, action: str, budget_id: int, 
                          budget_name: str, details: Dict[str, Any] = None, 
                          success: bool = True) -> "AuditLog":
        """Create a budget audit event"""
        return cls(
            user_id=user_id,
            action=action,
            resource_type="budget",
            resource_id=str(budget_id),
            description=f"Budget {action}: {budget_name}",
            details=details or {},
            severity=AuditSeverity.MEDIUM if action == AuditAction.BUDGET_EXCEED else AuditSeverity.LOW,
            category="financial",
            success=success,
            tags=["budget", action]
        )
    
    @classmethod
    def create_module_event(cls, user_id: int, action: str, module_name: str, 
                          success: bool = True, error_message: str = None, 
                          details: Dict[str, Any] = None) -> "AuditLog":
        """Create a module audit event"""
        return cls(
            user_id=user_id,
            action=action,
            resource_type="module",
            resource_id=module_name,
            description=f"Module {action}: {module_name}",
            details=details or {},
            severity=AuditSeverity.MEDIUM,
            category="system",
            success=success,
            error_message=error_message,
            tags=["module", action]
        )
    
    @classmethod
    def create_permission_event(cls, user_id: int, action: str, target_user_id: int, 
                              permission: str, success: bool = True) -> "AuditLog":
        """Create a permission audit event"""
        return cls(
            user_id=user_id,
            action=action,
            resource_type="permission",
            resource_id=str(target_user_id),
            description=f"Permission {action}: {permission} for user {target_user_id}",
            details={
                "permission": permission,
                "target_user_id": target_user_id
            },
            severity=AuditSeverity.HIGH,
            category="security",
            success=success,
            tags=["permission", action]
        )
    
    @classmethod
    def create_security_event(cls, user_id: int, event_type: str, description: str, 
                            severity: str = AuditSeverity.HIGH, 
                            details: Dict[str, Any] = None, 
                            ip_address: str = None) -> "AuditLog":
        """Create a security audit event"""
        return cls(
            user_id=user_id,
            action=AuditAction.SECURITY_EVENT,
            resource_type="security",
            resource_id=event_type,
            description=description,
            details=details or {},
            ip_address=ip_address,
            severity=severity,
            category="security",
            success=False,  # Security events are typically failures
            tags=["security", event_type]
        )
    
    @classmethod
    def create_system_event(cls, action: str, description: str, 
                          resource_type: str = "system", 
                          resource_id: str = None, 
                          severity: str = AuditSeverity.LOW, 
                          details: Dict[str, Any] = None) -> "AuditLog":
        """Create a system audit event"""
        return cls(
            user_id=None,  # System events don't have a user
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            details=details or {},
            severity=severity,
            category="system",
            success=True,
            tags=["system", action]
        )
    
    @classmethod
    def create_data_change_event(cls, user_id: int, action: str, resource_type: str, 
                               resource_id: str, description: str, 
                               old_values: Dict[str, Any], 
                               new_values: Dict[str, Any]) -> "AuditLog":
        """Create a data change audit event"""
        return cls(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            old_values=old_values,
            new_values=new_values,
            severity=AuditSeverity.LOW,
            category="data",
            success=True,
            tags=["data_change", action]
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the audit log"""
        return {
            "id": self.id,
            "action": self.action,
            "resource_type": self.resource_type,
            "description": self.description,
            "severity": self.severity,
            "success": self.success,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_id": self.user_id
        }