"""
API Key model
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class APIKey(Base):
    """API Key model for authentication and access control"""
    
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable name for the API key
    key_hash = Column(String, unique=True, index=True, nullable=False)  # Hashed API key
    key_prefix = Column(String, index=True, nullable=False)  # First 8 characters for identification
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="api_keys")
    
    # Related data relationships
    budgets = relationship("Budget", back_populates="api_key", cascade="all, delete-orphan")
    usage_tracking = relationship("UsageTracking", back_populates="api_key", cascade="all, delete-orphan")
    
    # Key status and permissions
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, default=dict)  # Specific permissions for this key
    scopes = Column(JSON, default=list)  # OAuth-like scopes
    
    # Usage limits
    rate_limit_per_minute = Column(Integer, default=60)  # Requests per minute
    rate_limit_per_hour = Column(Integer, default=3600)  # Requests per hour
    rate_limit_per_day = Column(Integer, default=86400)  # Requests per day
    
    # Allowed resources
    allowed_models = Column(JSON, default=list)  # List of allowed LLM models
    allowed_endpoints = Column(JSON, default=list)  # List of allowed API endpoints
    allowed_ips = Column(JSON, default=list)  # IP whitelist
    allowed_chatbots = Column(JSON, default=list)  # List of allowed chatbot IDs for chatbot-specific keys
    
    # Budget configuration
    is_unlimited = Column(Boolean, default=True)  # Unlimited budget flag
    budget_limit_cents = Column(Integer, nullable=True)  # Budget limit in cents
    budget_type = Column(String, nullable=True)  # "total" or "monthly"
    
    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)  # For organizing keys
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    
    # Usage tracking
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Integer, default=0)  # In cents
    
    # Relationships
    usage_tracking = relationship("UsageTracking", back_populates="api_key", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="api_key", cascade="all, delete-orphan")
    plugin_audit_logs = relationship("PluginAuditLog", back_populates="api_key")
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', user_id={self.user_id})>"
    
    def to_dict(self, include_sensitive: bool = False):
        """Convert API key to dictionary for API responses"""
        data = {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "user_id": self.user_id,
            "is_active": self.is_active,
            "permissions": self.permissions,
            "scopes": self.scopes,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "rate_limit_per_day": self.rate_limit_per_day,
            "allowed_models": self.allowed_models,
            "allowed_endpoints": self.allowed_endpoints,
            "allowed_ips": self.allowed_ips,
            "allowed_chatbots": self.allowed_chatbots,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_cost_cents": self.total_cost,
            "is_unlimited": self.is_unlimited,
            "budget_limit": self.budget_limit_cents,  # Map to budget_limit for API response
            "budget_type": self.budget_type
        }
        
        if include_sensitive:
            data["key_hash"] = self.key_hash
        
        return data
    
    def is_expired(self) -> bool:
        """Check if the API key has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the API key is valid and active"""
        return self.is_active and not self.is_expired()
    
    def has_permission(self, permission: str) -> bool:
        """Check if the API key has a specific permission"""
        return permission in self.permissions
    
    def has_scope(self, scope: str) -> bool:
        """Check if the API key has a specific scope"""
        return scope in self.scopes
    
    def can_access_model(self, model_name: str) -> bool:
        """Check if the API key can access a specific model"""
        if not self.allowed_models:  # Empty list means all models allowed
            return True
        return model_name in self.allowed_models
    
    def can_access_endpoint(self, endpoint: str) -> bool:
        """Check if the API key can access a specific endpoint"""
        if not self.allowed_endpoints:  # Empty list means all endpoints allowed
            return True
        return endpoint in self.allowed_endpoints
    
    def can_access_from_ip(self, ip_address: str) -> bool:
        """Check if the API key can be used from a specific IP"""
        if not self.allowed_ips:  # Empty list means all IPs allowed
            return True
        return ip_address in self.allowed_ips
    
    def can_access_chatbot(self, chatbot_id: str) -> bool:
        """Check if the API key can access a specific chatbot"""
        if not self.allowed_chatbots:  # Empty list means all chatbots allowed
            return True
        return chatbot_id in self.allowed_chatbots
    
    def update_usage(self, tokens_used: int = 0, cost_cents: int = 0):
        """Update usage statistics"""
        self.total_requests += 1
        self.total_tokens += tokens_used
        self.total_cost += cost_cents
        self.last_used_at = datetime.utcnow()
    
    def set_expiration(self, days: int):
        """Set expiration date in days from now"""
        self.expires_at = datetime.utcnow() + timedelta(days=days)
    
    def extend_expiration(self, days: int):
        """Extend expiration date by specified days"""
        if self.expires_at is None:
            self.expires_at = datetime.utcnow() + timedelta(days=days)
        else:
            self.expires_at = self.expires_at + timedelta(days=days)
    
    def revoke(self):
        """Revoke the API key"""
        self.is_active = False
        self.updated_at = datetime.utcnow()
    
    def add_scope(self, scope: str):
        """Add a scope to the API key"""
        if scope not in self.scopes:
            self.scopes.append(scope)
    
    def remove_scope(self, scope: str):
        """Remove a scope from the API key"""
        if scope in self.scopes:
            self.scopes.remove(scope)
    
    def add_allowed_model(self, model_name: str):
        """Add an allowed model"""
        if model_name not in self.allowed_models:
            self.allowed_models.append(model_name)
    
    def remove_allowed_model(self, model_name: str):
        """Remove an allowed model"""
        if model_name in self.allowed_models:
            self.allowed_models.remove(model_name)
    
    def add_allowed_endpoint(self, endpoint: str):
        """Add an allowed endpoint"""
        if endpoint not in self.allowed_endpoints:
            self.allowed_endpoints.append(endpoint)
    
    def remove_allowed_endpoint(self, endpoint: str):
        """Remove an allowed endpoint"""
        if endpoint in self.allowed_endpoints:
            self.allowed_endpoints.remove(endpoint)
    
    def add_allowed_ip(self, ip_address: str):
        """Add an allowed IP address"""
        if ip_address not in self.allowed_ips:
            self.allowed_ips.append(ip_address)
    
    def remove_allowed_ip(self, ip_address: str):
        """Remove an allowed IP address"""
        if ip_address in self.allowed_ips:
            self.allowed_ips.remove(ip_address)
    
    def add_allowed_chatbot(self, chatbot_id: str):
        """Add an allowed chatbot"""
        if chatbot_id not in self.allowed_chatbots:
            self.allowed_chatbots.append(chatbot_id)
    
    def remove_allowed_chatbot(self, chatbot_id: str):
        """Remove an allowed chatbot"""
        if chatbot_id in self.allowed_chatbots:
            self.allowed_chatbots.remove(chatbot_id)
    
    @classmethod
    def create_default_key(cls, user_id: int, name: str, key_hash: str, key_prefix: str) -> "APIKey":
        """Create a default API key with standard permissions"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={
                "read": True,
                "write": True,
                "chat": True,
                "embeddings": True
            },
            scopes=[
                "chat.completions",
                "embeddings.create",
                "models.list"
            ],
            rate_limit_per_minute=60,
            rate_limit_per_hour=3600,
            rate_limit_per_day=86400,
            allowed_models=[],  # All models allowed by default
            allowed_endpoints=[],  # All endpoints allowed by default
            allowed_ips=[],  # All IPs allowed by default
            description="Default API key with standard permissions",
            tags=["default"]
        )
    
    @classmethod
    def create_restricted_key(cls, user_id: int, name: str, key_hash: str, key_prefix: str,
                            models: List[str], endpoints: List[str]) -> "APIKey":
        """Create a restricted API key with limited permissions"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={
                "read": True,
                "chat": True
            },
            scopes=[
                "chat.completions"
            ],
            rate_limit_per_minute=30,
            rate_limit_per_hour=1800,
            rate_limit_per_day=43200,
            allowed_models=models,
            allowed_endpoints=endpoints,
            allowed_ips=[],
            description="Restricted API key with limited permissions",
            tags=["restricted"]
        )
    
    @classmethod
    def create_chatbot_key(cls, user_id: int, name: str, key_hash: str, key_prefix: str,
                          chatbot_id: str, chatbot_name: str) -> "APIKey":
        """Create a chatbot-specific API key"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={
                "chatbot": True
            },
            scopes=[
                "chatbot.chat"
            ],
            rate_limit_per_minute=100,
            rate_limit_per_hour=6000,
            rate_limit_per_day=144000,
            allowed_models=[],  # Will use chatbot's configured model
            allowed_endpoints=[
                f"/api/v1/chatbot/external/{chatbot_id}/chat",
                f"/api/v1/chatbot/external/{chatbot_id}/chat/completions"
            ],
            allowed_ips=[],
            allowed_chatbots=[chatbot_id],
            description=f"API key for chatbot: {chatbot_name}",
            tags=["chatbot", f"chatbot-{chatbot_id}"]
        )