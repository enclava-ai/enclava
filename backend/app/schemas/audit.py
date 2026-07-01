"""
Audit Schemas for Billing Audit Log API

Pydantic models for billing audit log endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EntityTypeEnum(str, Enum):
    """Types of billing entities that can be audited"""

    API_KEY = "api_key"
    BUDGET = "budget"
    PRICING = "pricing"
    USAGE_RECORD = "usage_record"


class ActionTypeEnum(str, Enum):
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


class ActorTypeEnum(str, Enum):
    """Types of actors that can perform billing operations"""

    USER = "user"
    SYSTEM = "system"
    API_SYNC = "api_sync"


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry"""

    id: int = Field(..., description="Unique audit log entry ID")
    entity_type: str = Field(
        ..., description="Type of entity (api_key, budget, pricing, usage_record)"
    )
    entity_id: str = Field(..., description="ID of the entity that was modified")
    action: str = Field(..., description="Action performed on the entity")
    changes: Dict[str, Any] = Field(
        ..., description="Changes made: {field: {old: value, new: value}}"
    )
    actor_type: str = Field(..., description="Type of actor (user, system, api_sync)")
    actor_user_id: Optional[int] = Field(
        None, description="User ID of the actor (if applicable)"
    )
    actor_description: Optional[str] = Field(
        None, description="Description of the actor"
    )
    reason: Optional[str] = Field(None, description="Reason for the change")
    ip_address: Optional[str] = Field(None, description="IP address of the request")
    user_agent: Optional[str] = Field(None, description="User agent of the request")
    request_id: Optional[str] = Field(None, description="UUID of the request")
    related_api_key_id: Optional[int] = Field(None, description="Related API key ID")
    related_budget_id: Optional[int] = Field(None, description="Related budget ID")
    related_user_id: Optional[int] = Field(None, description="Related user ID")
    created_at: datetime = Field(..., description="When the audit entry was created")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "entity_type": "api_key",
                "entity_id": "42",
                "action": "create",
                "changes": {
                    "name": {"old": None, "new": "My API Key"},
                    "is_active": {"old": None, "new": True},
                },
                "actor_type": "user",
                "actor_user_id": 1,
                "actor_description": None,
                "reason": "Created new API key for production",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "related_api_key_id": 42,
                "related_budget_id": None,
                "related_user_id": 1,
                "created_at": "2025-01-15T10:30:00Z",
            }
        }


class AuditLogSearchParams(BaseModel):
    """Query parameters for searching audit logs"""

    entity_type: Optional[str] = Field(
        None,
        description="Filter by entity type (api_key, budget, pricing, usage_record)",
    )
    action: Optional[str] = Field(None, description="Filter by action type")
    actor_user_id: Optional[int] = Field(None, description="Filter by actor user ID")
    actor_type: Optional[str] = Field(
        None, description="Filter by actor type (user, system, api_sync)"
    )
    start_date: Optional[datetime] = Field(
        None, description="Filter by start date (inclusive)"
    )
    end_date: Optional[datetime] = Field(
        None, description="Filter by end date (inclusive)"
    )
    limit: int = Field(100, ge=1, le=500, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")

    class Config:
        json_schema_extra = {
            "example": {
                "entity_type": "api_key",
                "action": "create",
                "actor_type": "user",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-31T23:59:59Z",
                "limit": 100,
                "offset": 0,
            }
        }


class AuditLogSummary(BaseModel):
    """Summary statistics for audit logs"""

    total_entries: int = Field(..., description="Total number of audit entries")
    entries_by_entity_type: Dict[str, int] = Field(
        ..., description="Count of entries by entity type"
    )
    entries_by_action: Dict[str, int] = Field(
        ..., description="Count of entries by action type"
    )
    entries_by_actor_type: Dict[str, int] = Field(
        ..., description="Count of entries by actor type"
    )
    period_start: Optional[datetime] = Field(
        None, description="Start of the summary period"
    )
    period_end: Optional[datetime] = Field(
        None, description="End of the summary period"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_entries": 1500,
                "entries_by_entity_type": {
                    "api_key": 500,
                    "budget": 300,
                    "pricing": 600,
                    "usage_record": 100,
                },
                "entries_by_action": {
                    "create": 400,
                    "update": 600,
                    "sync_update": 400,
                    "exceeded": 100,
                },
                "entries_by_actor_type": {"user": 700, "system": 200, "api_sync": 600},
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-01-31T23:59:59Z",
            }
        }


class AuditTrailResponse(BaseModel):
    """Response for audit trail queries"""

    entries: List[AuditLogResponse] = Field(..., description="List of audit entries")
    total: int = Field(..., description="Total number of entries matching the query")
    entity_type: Optional[str] = Field(
        None, description="Entity type of the audit trail"
    )
    entity_id: Optional[str] = Field(None, description="Entity ID of the audit trail")

    class Config:
        json_schema_extra = {
            "example": {
                "entries": [
                    {
                        "id": 1,
                        "entity_type": "api_key",
                        "entity_id": "42",
                        "action": "create",
                        "changes": {"name": {"old": None, "new": "My API Key"}},
                        "actor_type": "user",
                        "actor_user_id": 1,
                        "created_at": "2025-01-15T10:30:00Z",
                    }
                ],
                "total": 1,
                "entity_type": "api_key",
                "entity_id": "42",
            }
        }
