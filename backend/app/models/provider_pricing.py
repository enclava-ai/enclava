"""
Provider Pricing models for LLM model pricing management

These models support:
- ProviderPricing: Current and historical pricing for provider models
- PricingAuditLog: Audit trail for all pricing changes
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.db.database import Base, utc_now


class ProviderPricing(Base):
    """
    Provider pricing model for storing model pricing information.

    Pricing is stored in cents per 1 million tokens.
    Example: $2 per 1M tokens = 200 cents per 1M tokens

    Supports:
    - API-synced pricing (from provider APIs like RedPill)
    - Manual pricing overrides (for PrivateMode or custom pricing)
    - Price history tracking via effective_from/effective_until
    """

    __tablename__ = "provider_pricing"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Provider and model identification
    provider_id = Column(
        String(50), nullable=False, index=True
    )  # 'privatemode', 'redpill', etc.
    model_id = Column(String(255), nullable=False)  # Full model ID from provider
    model_name = Column(String(255), nullable=True)  # Human-readable name

    # Pricing (in cents per 1M tokens, in native currency)
    input_price_per_million_cents = Column(BigInteger, nullable=False)
    output_price_per_million_cents = Column(BigInteger, nullable=False)
    currency = Column(
        String(3), nullable=False, default="USD"
    )  # ISO 4217 currency code

    # Source tracking
    price_source = Column(String(20), nullable=False)  # 'api_sync', 'manual', 'default'
    source_api_response = Column(JSONB, nullable=True)  # Snapshot of API response

    # Override support
    is_override = Column(Boolean, nullable=False, default=False)
    override_reason = Column(Text, nullable=True)
    override_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Model metadata
    context_length = Column(Integer, nullable=True)
    architecture = Column(JSONB, nullable=True)  # Model architecture info
    quantization = Column(String(20), nullable=True)  # e.g., 'fp16', 'int8'

    # Validity period
    effective_from = Column(DateTime, nullable=False, default=utc_now)
    effective_until = Column(DateTime, nullable=True)  # NULL = current pricing

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    override_by_user = relationship("User", foreign_keys=[override_by_user_id])

    # Note: Indexes and unique constraint are defined in migration 017
    # - idx_provider_pricing_lookup (provider_id, model_id, effective_from)
    # - idx_provider_pricing_current (partial, effective_until IS NULL)
    # - idx_provider_pricing_overrides (partial, is_override = TRUE)
    # - provider_pricing_unique (provider_id, model_id, effective_from)

    def __init__(self, **kwargs):
        now = utc_now()
        kwargs.setdefault("currency", "USD")
        kwargs.setdefault("is_override", False)
        kwargs.setdefault("effective_from", now)
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        super().__init__(**kwargs)

    def __repr__(self):
        return (
            f"<ProviderPricing(id={self.id}, provider={self.provider_id}, "
            f"model={self.model_id}, input={self.input_price_per_million_cents}, "
            f"output={self.output_price_per_million_cents})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing record to dictionary for API responses"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "input_price_per_million_cents": self.input_price_per_million_cents,
            "output_price_per_million_cents": self.output_price_per_million_cents,
            "input_price_per_million_dollars": self.input_price_per_million_cents
            / 100.0,
            "output_price_per_million_dollars": self.output_price_per_million_cents
            / 100.0,
            "currency": self.currency or "USD",
            "price_source": self.price_source,
            "is_override": self.is_override,
            "override_reason": self.override_reason,
            "override_by_user_id": self.override_by_user_id,
            "context_length": self.context_length,
            "architecture": self.architecture,
            "quantization": self.quantization,
            "effective_from": (
                self.effective_from.isoformat() if self.effective_from else None
            ),
            "effective_until": (
                self.effective_until.isoformat() if self.effective_until else None
            ),
            "is_current": self.is_current,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def is_current(self) -> bool:
        """Check if this pricing is currently active"""
        return self.effective_until is None

    @property
    def input_price_dollars(self) -> float:
        """Return input price in dollars per million tokens"""
        return self.input_price_per_million_cents / 100.0

    @property
    def output_price_dollars(self) -> float:
        """Return output price in dollars per million tokens"""
        return self.output_price_per_million_cents / 100.0

    def calculate_cost_cents(
        self, input_tokens: int, output_tokens: int
    ) -> tuple[int, int, int]:
        """
        Calculate costs in cents from tokens.

        Uses ceiling division to ensure we never under-charge.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Tuple of (input_cost_cents, output_cost_cents, total_cost_cents)
        """
        # Ceiling division: (a + b - 1) // b is equivalent to ceil(a / b)
        input_cost_cents = (
            input_tokens * self.input_price_per_million_cents + 999_999
        ) // 1_000_000
        output_cost_cents = (
            output_tokens * self.output_price_per_million_cents + 999_999
        ) // 1_000_000
        total_cost_cents = input_cost_cents + output_cost_cents

        return input_cost_cents, output_cost_cents, total_cost_cents

    def expire(self) -> None:
        """Mark this pricing as expired (no longer current)"""
        expires_at = utc_now()
        if self.effective_from and self.effective_from.tzinfo is not None:
            expires_at = datetime.now(timezone.utc)

        self.effective_until = expires_at
        self.updated_at = expires_at

    @classmethod
    def create_from_api_sync(
        cls,
        provider_id: str,
        model_id: str,
        input_price_cents: int,
        output_price_cents: int,
        model_name: Optional[str] = None,
        api_response: Optional[Dict[str, Any]] = None,
        context_length: Optional[int] = None,
        architecture: Optional[Dict[str, Any]] = None,
        quantization: Optional[str] = None,
        currency: str = "USD",
    ) -> "ProviderPricing":
        """Create a new pricing record from API sync"""
        return cls(
            provider_id=provider_id,
            model_id=model_id,
            model_name=model_name,
            input_price_per_million_cents=input_price_cents,
            output_price_per_million_cents=output_price_cents,
            currency=currency,
            price_source="api_sync",
            source_api_response=api_response,
            is_override=False,
            context_length=context_length,
            architecture=architecture,
            quantization=quantization,
            effective_from=utc_now(),
        )

    @classmethod
    def create_manual(
        cls,
        provider_id: str,
        model_id: str,
        input_price_cents: int,
        output_price_cents: int,
        reason: str,
        user_id: int,
        model_name: Optional[str] = None,
        currency: str = "USD",
    ) -> "ProviderPricing":
        """Create a new manual pricing override"""
        return cls(
            provider_id=provider_id,
            model_id=model_id,
            model_name=model_name,
            input_price_per_million_cents=input_price_cents,
            output_price_per_million_cents=output_price_cents,
            currency=currency,
            price_source="manual",
            is_override=True,
            override_reason=reason,
            override_by_user_id=user_id,
            effective_from=utc_now(),
        )


class PricingAuditLog(Base):
    """
    Audit log for tracking all pricing changes.

    Records every create, update, sync, and override operation
    for complete audit trail of pricing history.
    """

    __tablename__ = "pricing_audit_log"

    # Primary key
    id = Column(BigInteger, primary_key=True, index=True)

    # Provider and model identification
    provider_id = Column(String(50), nullable=False)
    model_id = Column(String(255), nullable=False)

    # Action type
    action = Column(
        String(20), nullable=False
    )  # 'create', 'update', 'sync', 'override', 'remove_override'

    # Old pricing values (null for create actions)
    old_input_price_per_million_cents = Column(BigInteger, nullable=True)
    old_output_price_per_million_cents = Column(BigInteger, nullable=True)

    # New pricing values
    new_input_price_per_million_cents = Column(BigInteger, nullable=False)
    new_output_price_per_million_cents = Column(BigInteger, nullable=False)

    # Source tracking
    change_source = Column(
        String(20), nullable=False
    )  # 'api_sync', 'admin_manual', 'system_default'

    # User who made the change (null for system/sync operations)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Additional context
    change_reason = Column(Text, nullable=True)
    sync_job_id = Column(PGUUID(as_uuid=True), nullable=True)
    api_response_snapshot = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utc_now)

    # Relationships
    changed_by_user = relationship("User", foreign_keys=[changed_by_user_id])

    def __repr__(self):
        return (
            f"<PricingAuditLog(id={self.id}, action={self.action}, "
            f"provider={self.provider_id}, model={self.model_id})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary for API responses"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "action": self.action,
            "old_input_price_per_million_cents": self.old_input_price_per_million_cents,
            "old_output_price_per_million_cents": self.old_output_price_per_million_cents,
            "new_input_price_per_million_cents": self.new_input_price_per_million_cents,
            "new_output_price_per_million_cents": self.new_output_price_per_million_cents,
            "change_source": self.change_source,
            "changed_by_user_id": self.changed_by_user_id,
            "change_reason": self.change_reason,
            "sync_job_id": str(self.sync_job_id) if self.sync_job_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def create_for_sync(
        cls,
        provider_id: str,
        model_id: str,
        action: str,
        new_input_price: int,
        new_output_price: int,
        sync_job_id: Optional[UUID] = None,
        api_response: Optional[Dict[str, Any]] = None,
        old_input_price: Optional[int] = None,
        old_output_price: Optional[int] = None,
    ) -> "PricingAuditLog":
        """Create an audit log entry for API sync operations"""
        return cls(
            provider_id=provider_id,
            model_id=model_id,
            action=action,
            old_input_price_per_million_cents=old_input_price,
            old_output_price_per_million_cents=old_output_price,
            new_input_price_per_million_cents=new_input_price,
            new_output_price_per_million_cents=new_output_price,
            change_source="api_sync",
            sync_job_id=sync_job_id,
            api_response_snapshot=api_response,
        )

    @classmethod
    def create_for_manual_change(
        cls,
        provider_id: str,
        model_id: str,
        action: str,
        new_input_price: int,
        new_output_price: int,
        user_id: int,
        reason: str,
        old_input_price: Optional[int] = None,
        old_output_price: Optional[int] = None,
    ) -> "PricingAuditLog":
        """Create an audit log entry for manual pricing changes"""
        return cls(
            provider_id=provider_id,
            model_id=model_id,
            action=action,
            old_input_price_per_million_cents=old_input_price,
            old_output_price_per_million_cents=old_output_price,
            new_input_price_per_million_cents=new_input_price,
            new_output_price_per_million_cents=new_output_price,
            change_source="admin_manual",
            changed_by_user_id=user_id,
            change_reason=reason,
        )
