"""
Billing Audit Log model for comprehensive billing entity audit logging

This model provides a centralized audit trail for all billing-related changes:
- API key operations (create, update, soft_delete, restore, regenerate, etc.)
- Budget operations (create, update, delete, reset_period, exceeded, etc.)
- Pricing changes (sync_create, sync_update, manual_override, etc.)
- Usage record corrections (rare manual adjustments)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.db.database import Base, utc_now


class EntityType(str, Enum):
    """Types of billing entities that can be audited"""

    API_KEY = "api_key"
    BUDGET = "budget"
    PRICING = "pricing"
    USAGE_RECORD = "usage_record"


class ActionType(str, Enum):
    """Types of actions that can be performed on billing entities"""

    # Common actions
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # API Key specific actions
    SOFT_DELETE = "soft_delete"
    RESTORE = "restore"
    REGENERATE = "regenerate"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"

    # Budget specific actions
    RESET_PERIOD = "reset_period"
    EXCEEDED = "exceeded"
    WARNING_TRIGGERED = "warning_triggered"
    SPEND_UPDATE = "spend_update"

    # Pricing specific actions
    SYNC_CREATE = "sync_create"
    SYNC_UPDATE = "sync_update"
    MANUAL_OVERRIDE = "manual_override"
    REMOVE_OVERRIDE = "remove_override"

    # Usage record specific actions
    CORRECTION = "correction"
    VOID = "void"


class ActorType(str, Enum):
    """Types of actors that can perform billing operations"""

    USER = "user"
    SYSTEM = "system"
    API_SYNC = "api_sync"


class BillingAuditLog(Base):
    """
    Centralized audit log for all billing-related entity changes.

    This model captures:
    - What changed (entity_type, entity_id, changes JSONB)
    - Who made the change (actor_type, actor_user_id, actor_description)
    - Why it changed (reason)
    - When it happened (created_at)
    - Request context (ip_address, user_agent, request_id)
    - Related entities for efficient querying (related_api_key_id, etc.)

    The 'changes' field stores diffs as:
    {"field_name": {"old": old_value, "new": new_value}, ...}
    """

    __tablename__ = "billing_audit_log"

    # Primary key
    id = Column(BigInteger, primary_key=True, index=True)

    # Entity identification
    entity_type = Column(String(30), nullable=False)  # EntityType enum value
    entity_id = Column(String(100), nullable=False)

    # Action type
    action = Column(String(30), nullable=False)  # ActionType enum value

    # Changes stored as JSONB: {"field": {"old": x, "new": y}, ...}
    changes = Column(JSONB, nullable=False)

    # Actor information
    actor_type = Column(String(20), nullable=False)  # ActorType enum value
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_description = Column(
        Text, nullable=True
    )  # e.g., "System scheduler", "API sync from RedPill"

    # Context
    reason = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(PGUUID(as_uuid=True), nullable=True)

    # Related entities for efficient querying
    related_api_key_id = Column(Integer, nullable=True)
    related_budget_id = Column(Integer, nullable=True)
    related_user_id = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    actor_user = relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self):
        return (
            f"<BillingAuditLog(id={self.id}, entity={self.entity_type}:{self.entity_id}, "
            f"action={self.action}, actor={self.actor_type})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary for API responses"""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "changes": self.changes,
            "actor_type": self.actor_type,
            "actor_user_id": self.actor_user_id,
            "actor_description": self.actor_description,
            "reason": self.reason,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "request_id": str(self.request_id) if self.request_id else None,
            "related_api_key_id": self.related_api_key_id,
            "related_budget_id": self.related_budget_id,
            "related_user_id": self.related_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def create_api_key_audit(
        cls,
        api_key_id: int,
        action: str,
        changes: Dict[str, Any],
        actor_user_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
        related_user_id: Optional[int] = None,
    ) -> "BillingAuditLog":
        """Create an audit log entry for API key operations"""
        return cls(
            entity_type=EntityType.API_KEY.value,
            entity_id=str(api_key_id),
            action=action,
            changes=changes,
            actor_type=ActorType.USER.value,
            actor_user_id=actor_user_id,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            related_api_key_id=api_key_id,
            related_user_id=related_user_id or actor_user_id,
        )

    @classmethod
    def create_budget_audit(
        cls,
        budget_id: int,
        action: str,
        changes: Dict[str, Any],
        actor_user_id: Optional[int] = None,
        actor_type: str = ActorType.USER.value,
        actor_description: Optional[str] = None,
        reason: Optional[str] = None,
        related_api_key_id: Optional[int] = None,
        related_user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> "BillingAuditLog":
        """Create an audit log entry for budget operations"""
        return cls(
            entity_type=EntityType.BUDGET.value,
            entity_id=str(budget_id),
            action=action,
            changes=changes,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            actor_description=actor_description,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            related_budget_id=budget_id,
            related_api_key_id=related_api_key_id,
            related_user_id=related_user_id,
        )

    @classmethod
    def create_pricing_audit(
        cls,
        provider_id: str,
        model_id: str,
        action: str,
        changes: Dict[str, Any],
        actor_user_id: Optional[int] = None,
        actor_type: str = ActorType.API_SYNC.value,
        actor_description: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> "BillingAuditLog":
        """Create an audit log entry for pricing operations"""
        entity_id = f"{provider_id}/{model_id}"
        return cls(
            entity_type=EntityType.PRICING.value,
            entity_id=entity_id,
            action=action,
            changes=changes,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            actor_description=actor_description,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

    @classmethod
    def create_usage_correction_audit(
        cls,
        usage_record_id: int,
        changes: Dict[str, Any],
        actor_user_id: int,
        reason: str,
        related_api_key_id: Optional[int] = None,
        related_user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[UUID] = None,
    ) -> "BillingAuditLog":
        """Create an audit log entry for usage record corrections"""
        return cls(
            entity_type=EntityType.USAGE_RECORD.value,
            entity_id=str(usage_record_id),
            action=ActionType.CORRECTION.value,
            changes=changes,
            actor_type=ActorType.USER.value,
            actor_user_id=actor_user_id,
            reason=reason,  # Required for corrections
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            related_api_key_id=related_api_key_id,
            related_user_id=related_user_id,
        )
