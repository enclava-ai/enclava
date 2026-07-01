"""
Usage Record model for detailed API request tracking and billing

This is the source of truth for all LLM usage and billing data.
Every LLM request (success or failure) creates a record here.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.db.database import Base, utc_now


class UsageRecord(Base):
    """
    Usage record for tracking individual LLM requests.

    This model captures:
    - Token usage (input, output, total)
    - Cost in cents (derived from tokens + pricing snapshot)
    - Provider information
    - Request context (endpoint, agent)
    - Performance metrics (latency, TTFT)
    - Status and error information

    Costs are stored in cents (integer) for consistency with budgets.
    Pricing snapshot is stored per-record for audit trail.
    """

    __tablename__ = "usage_records"

    # Primary key
    id = Column(BigInteger, primary_key=True, index=True)

    # Unique request identifier for tracing across services
    request_id = Column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    # Ownership - at least one required
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Relationships
    api_key = relationship("APIKey", back_populates="usage_records")
    user = relationship("User", back_populates="usage_records")

    # Provider Information (critical for multi-provider billing)
    provider_id = Column(
        String(50), nullable=False, index=True
    )  # 'privatemode', 'redpill', etc.
    provider_model = Column(
        String(255), nullable=False
    )  # Full model name from provider
    normalized_model = Column(
        String(255), nullable=False, index=True
    )  # Our normalized model name

    # Token Metrics (core billing data - source of truth)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Cost in cents (derived from tokens + pricing snapshot)
    # Using BigInteger for large accumulations over time
    input_cost_cents = Column(BigInteger, nullable=False, default=0)
    output_cost_cents = Column(BigInteger, nullable=False, default=0)
    total_cost_cents = Column(BigInteger, nullable=False, default=0)

    # Pricing snapshot (price per million tokens in cents at time of usage)
    # This is critical for audit trail - prices change over time
    input_price_per_million_cents = Column(BigInteger, nullable=False)
    output_price_per_million_cents = Column(BigInteger, nullable=False)
    pricing_source = Column(
        String(20), nullable=False
    )  # 'api_sync', 'manual', 'default'
    pricing_effective_from = Column(DateTime, nullable=False)  # Price validity start

    # Request Context
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False, default="POST")
    agent_config_id = Column(
        Integer, nullable=True, index=True
    )  # NULL if not agent request
    session_id = Column(String(100), nullable=True)  # For conversation grouping

    # Request Characteristics
    is_streaming = Column(Boolean, nullable=False, default=False)
    is_tool_calling = Column(Boolean, nullable=False, default=False)
    message_count = Column(Integer, nullable=False, default=0)  # Messages in request

    # Performance Metrics
    latency_ms = Column(Integer, nullable=True)  # Total request time
    ttft_ms = Column(Integer, nullable=True)  # Time to first token (streaming only)

    # Status
    status = Column(
        String(20), nullable=False, default="success"
    )  # success, error, timeout, budget_exceeded
    error_type = Column(
        String(50), nullable=True
    )  # null, 'rate_limit', 'model_error', 'timeout', etc.
    error_message = Column(Text, nullable=True)

    # Client Info (for abuse detection and debugging)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)

    # Table-level constraints and indexes
    __table_args__ = (
        # Ensure at least api_key_id or user_id is set
        CheckConstraint(
            "api_key_id IS NOT NULL OR user_id IS NOT NULL",
            name="usage_records_api_key_or_user",
        ),
        # Composite indexes for common queries
        Index("idx_usage_records_api_key_created", "api_key_id", "created_at"),
        Index("idx_usage_records_user_created", "user_id", "created_at"),
        Index("idx_usage_records_provider_created", "provider_id", "created_at"),
        # Billing aggregation index
        Index(
            "idx_usage_records_billing",
            "api_key_id",
            "provider_id",
            "normalized_model",
            "created_at",
            postgresql_where="status = 'success'",
        ),
    )

    def __repr__(self):
        return (
            f"<UsageRecord(id={self.id}, request_id={self.request_id}, "
            f"provider={self.provider_id}, model={self.normalized_model}, "
            f"tokens={self.total_tokens}, cost_cents={self.total_cost_cents})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert usage record to dictionary for API responses"""
        return {
            "id": self.id,
            "request_id": str(self.request_id) if self.request_id else None,
            "api_key_id": self.api_key_id,
            "user_id": self.user_id,
            "provider_id": self.provider_id,
            "provider_model": self.provider_model,
            "normalized_model": self.normalized_model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "input_cost_cents": self.input_cost_cents,
            "output_cost_cents": self.output_cost_cents,
            "total_cost_cents": self.total_cost_cents,
            "input_price_per_million_cents": self.input_price_per_million_cents,
            "output_price_per_million_cents": self.output_price_per_million_cents,
            "pricing_source": self.pricing_source,
            "pricing_effective_from": (
                self.pricing_effective_from.isoformat()
                if self.pricing_effective_from
                else None
            ),
            "endpoint": self.endpoint,
            "method": self.method,
            "agent_config_id": self.agent_config_id,
            "session_id": self.session_id,
            "is_streaming": self.is_streaming,
            "is_tool_calling": self.is_tool_calling,
            "message_count": self.message_count,
            "latency_ms": self.latency_ms,
            "ttft_ms": self.ttft_ms,
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def total_cost_dollars(self) -> float:
        """Return total cost in dollars"""
        return self.total_cost_cents / 100.0

    @property
    def is_successful(self) -> bool:
        """Check if the request was successful"""
        return self.status == "success"
