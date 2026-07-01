"""
API Key model
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from app.db.database import Base, utc_now


class UTCDateTime(TypeDecorator):
    """Store naive UTC datetimes and return timezone-aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class APIKey(Base):
    """API Key model for authentication and access control"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable name for the API key
    key_hash = Column(String, unique=True, index=True, nullable=False)  # Hashed API key
    key_prefix = Column(
        String, index=True, nullable=False
    )  # First 8 characters for identification

    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="api_keys", foreign_keys=[user_id])

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
    allowed_agents = Column(
        JSON, default=list
    )  # List of allowed agent config IDs for agent-specific keys
    allowed_extract_templates = Column(
        JSON, default=list
    )  # List of allowed extract template IDs for extract-specific keys

    # Budget configuration
    is_unlimited = Column(Boolean, default=True)  # Unlimited budget flag
    budget_limit_cents = Column(Integer, nullable=True)  # Budget limit in cents
    budget_type = Column(String, nullable=True)  # "total" or "monthly"

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)  # For organizing keys

    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(UTCDateTime, nullable=True)  # Optional expiration

    # Soft delete columns (added in migration 017)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deletion_reason = Column(Text, nullable=True)

    # SECURITY FIX #35: Use BigInteger for counters to prevent overflow
    # Usage tracking
    total_requests = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    total_cost = Column(BigInteger, default=0)  # In cents

    # Relationships
    usage_tracking = relationship(
        "UsageTracking", back_populates="api_key", cascade="all, delete-orphan"
    )
    budgets = relationship(
        "Budget", back_populates="api_key", cascade="all, delete-orphan"
    )
    plugin_audit_logs = relationship("PluginAuditLog", back_populates="api_key")
    usage_records = relationship(
        "UsageRecord", back_populates="api_key", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        legacy_budget_id = kwargs.pop("budget_id", None)
        hashed_key = kwargs.pop("hashed_key", None)

        key_hash = kwargs.get("key_hash") or hashed_key
        if key_hash is not None:
            kwargs.setdefault("key_hash", key_hash)
            kwargs.setdefault("key_prefix", str(key_hash)[:8])

        raw_id = kwargs.get("id")
        if isinstance(raw_id, str) and not raw_id.isdigit():
            kwargs.pop("id", None)
        elif isinstance(raw_id, str):
            kwargs["id"] = int(raw_id)

        for int_field in ("user_id", "deleted_by_user_id"):
            raw_value = kwargs.get(int_field)
            if isinstance(raw_value, str) and raw_value.isdigit():
                kwargs[int_field] = int(raw_value)

        kwargs.setdefault("name", "API Key")
        kwargs.setdefault("key_prefix", "unknown")
        kwargs.setdefault("permissions", {})
        kwargs.setdefault("scopes", [])
        kwargs.setdefault("allowed_models", [])
        kwargs.setdefault("allowed_endpoints", [])
        kwargs.setdefault("allowed_ips", [])
        kwargs.setdefault("allowed_agents", [])
        kwargs.setdefault("allowed_extract_templates", [])
        kwargs.setdefault("tags", [])
        kwargs.setdefault("is_active", True)
        kwargs.setdefault("is_unlimited", True)
        kwargs.setdefault("total_requests", 0)
        kwargs.setdefault("total_tokens", 0)
        kwargs.setdefault("total_cost", 0)

        super().__init__(**kwargs)
        self._legacy_budget_id = legacy_budget_id

    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    @property
    def is_deleted(self) -> bool:
        """Check if the API key has been soft deleted"""
        return self.deleted_at is not None

    @property
    def usage_count(self) -> int:
        return self.total_requests or 0

    @usage_count.setter
    def usage_count(self, value: int) -> None:
        self.total_requests = value

    @property
    def budget_id(self):
        return getattr(self, "_legacy_budget_id", None)

    @budget_id.setter
    def budget_id(self, value) -> None:
        self._legacy_budget_id = value

    @property
    def is_active_and_not_deleted(self) -> bool:
        """Check if the API key is active and not deleted (for filtering)"""
        return self.is_active and not self.is_deleted

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
            "allowed_agents": self.allowed_agents,
            "allowed_extract_templates": self.allowed_extract_templates,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": (
                self.last_used_at.isoformat() if self.last_used_at else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_cost_cents": self.total_cost,
            "is_unlimited": self.is_unlimited,
            "budget_limit": self.budget_limit_cents,  # Map to budget_limit for API response
            "budget_type": self.budget_type,
            # Soft delete fields
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "deleted_by_user_id": self.deleted_by_user_id,
            "deletion_reason": self.deletion_reason,
        }

        if include_sensitive:
            data["key_hash"] = self.key_hash

        return data

    def is_expired(self) -> bool:
        """Check if the API key has expired"""
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc) if self.expires_at.tzinfo else utc_now()
        return now > self.expires_at

    def is_valid(self) -> bool:
        """Check if the API key is valid, active, and not deleted"""
        return self.is_active and not self.is_expired() and not self.is_deleted

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

    def can_access_agent(self, agent_id: int) -> bool:
        """Check if the API key can access a specific agent config"""
        if not self.allowed_agents:  # Empty list means all agents allowed
            return True
        # Convert to string for comparison since JSON stores as strings
        return str(agent_id) in [str(a) for a in self.allowed_agents]

    def can_access_template(self, template_id: str) -> bool:
        """Check if the API key can access a specific extract template"""
        if not self.allowed_extract_templates:  # Empty list means all templates allowed
            return True
        return template_id in self.allowed_extract_templates

    def update_usage(self, tokens_used: int = 0, cost_cents: int = 0):
        """Update usage statistics"""
        self.total_requests += 1
        self.total_tokens += tokens_used
        self.total_cost += cost_cents
        self.last_used_at = utc_now()

    def set_expiration(self, days: int):
        """Set expiration date in days from now"""
        self.expires_at = utc_now() + timedelta(days=days)

    def extend_expiration(self, days: int):
        """Extend expiration date by specified days"""
        if self.expires_at is None:
            self.expires_at = utc_now() + timedelta(days=days)
        else:
            self.expires_at = self.expires_at + timedelta(days=days)

    def revoke(self):
        """Revoke the API key"""
        self.is_active = False
        self.updated_at = utc_now()

    def soft_delete(self, deleted_by_user_id: int, reason: str = None):
        """
        Soft delete the API key.
        - Sets deleted_at to current timestamp
        - Sets deleted_by_user_id
        - Sets is_active to False
        - Stores deletion_reason
        """
        self.deleted_at = utc_now()
        self.deleted_by_user_id = deleted_by_user_id
        self.deletion_reason = reason
        self.is_active = False
        self.updated_at = utc_now()

    def restore(self):
        """
        Restore a soft-deleted API key.
        - Clears deleted_at
        - Clears deleted_by_user_id
        - Clears deletion_reason
        - Does NOT automatically set is_active to True (admin decision)
        """
        self.deleted_at = None
        self.deleted_by_user_id = None
        self.deletion_reason = None
        self.updated_at = utc_now()

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

    def add_allowed_agent(self, agent_id: int):
        """Add an allowed agent config"""
        agent_id_str = str(agent_id)
        if agent_id_str not in [str(a) for a in self.allowed_agents]:
            self.allowed_agents.append(agent_id_str)

    def remove_allowed_agent(self, agent_id: int):
        """Remove an allowed agent config"""
        agent_id_str = str(agent_id)
        self.allowed_agents = [a for a in self.allowed_agents if str(a) != agent_id_str]

    def add_allowed_template(self, template_id: str):
        """Add an allowed extract template"""
        if template_id not in self.allowed_extract_templates:
            self.allowed_extract_templates.append(template_id)

    def remove_allowed_template(self, template_id: str):
        """Remove an allowed extract template"""
        if template_id in self.allowed_extract_templates:
            self.allowed_extract_templates.remove(template_id)

    @classmethod
    def create_default_key(
        cls, user_id: int, name: str, key_hash: str, key_prefix: str
    ) -> "APIKey":
        """Create a default API key with standard permissions"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={"read": True, "write": True, "chat": True, "embeddings": True},
            scopes=["chat.completions", "embeddings.create", "models.list"],
            rate_limit_per_minute=60,
            rate_limit_per_hour=3600,
            rate_limit_per_day=86400,
            allowed_models=[],  # All models allowed by default
            allowed_endpoints=[],  # All endpoints allowed by default
            allowed_ips=[],  # All IPs allowed by default
            description="Default API key with standard permissions",
            tags=["default"],
        )

    @classmethod
    def create_restricted_key(
        cls,
        user_id: int,
        name: str,
        key_hash: str,
        key_prefix: str,
        models: List[str],
        endpoints: List[str],
    ) -> "APIKey":
        """Create a restricted API key with limited permissions"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={"read": True, "chat": True},
            scopes=["chat.completions"],
            rate_limit_per_minute=30,
            rate_limit_per_hour=1800,
            rate_limit_per_day=43200,
            allowed_models=models,
            allowed_endpoints=endpoints,
            allowed_ips=[],
            description="Restricted API key with limited permissions",
            tags=["restricted"],
        )

    @classmethod
    def create_agent_key(
        cls,
        user_id: int,
        name: str,
        key_hash: str,
        key_prefix: str,
        agent_id: int,
        agent_name: str,
    ) -> "APIKey":
        """Create an agent-specific API key"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={"agent": True},
            scopes=["agent.chat"],
            rate_limit_per_minute=100,
            rate_limit_per_hour=6000,
            rate_limit_per_day=144000,
            allowed_models=[],  # Will use agent's configured model
            allowed_endpoints=[
                f"/agent/{agent_id}/v1/chat/completions",
            ],
            allowed_ips=[],
            allowed_agents=[str(agent_id)],
            description=f"API key for agent: {agent_name}",
            tags=["agent", f"agent-{agent_id}"],
        )

    @classmethod
    def create_extract_key(
        cls,
        user_id: int,
        name: str,
        key_hash: str,
        key_prefix: str,
        template_ids: Optional[List[str]] = None,
    ) -> "APIKey":
        """Create an extract-specific API key"""
        return cls(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            is_active=True,
            permissions={"extract": True},
            scopes=["extract"],  # Single scope for all Extract operations
            # Rate limits will use model defaults (60/min, 3600/hour, 86400/day)
            allowed_models=[],  # Will use template's configured model
            allowed_endpoints=[
                "/api/v1/extract/process",
                "/api/v1/extract/jobs",
                "/api/v1/extract/templates",
            ],
            allowed_ips=[],
            allowed_extract_templates=template_ids or [],
            description=f"API key for Extract: {', '.join(template_ids) if template_ids else 'all templates'}",
            tags=["extract"]
            + ([f"template-{t}" for t in template_ids] if template_ids else []),
        )
