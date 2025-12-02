"""
Budget model for managing spending limits and cost control
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
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
    Float,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class BudgetType(str, Enum):
    """Budget type enumeration"""

    USER = "user"
    API_KEY = "api_key"
    GLOBAL = "global"


class BudgetPeriod(str, Enum):
    """Budget period types"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class Budget(Base):
    """Budget model for setting and managing spending limits"""

    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable name for the budget

    # User and API Key relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="budgets")

    api_key_id = Column(
        Integer, ForeignKey("api_keys.id"), nullable=True
    )  # Optional: specific to an API key
    api_key = relationship("APIKey", back_populates="budgets")

    # Usage tracking relationship
    usage_tracking = relationship(
        "UsageTracking", back_populates="budget", cascade="all, delete-orphan"
    )

    # Budget limits (in cents)
    limit_cents = Column(Integer, nullable=False)  # Maximum spend limit
    warning_threshold_cents = Column(
        Integer, nullable=True
    )  # Warning threshold (e.g., 80% of limit)

    # Time period settings
    period_type = Column(
        String, nullable=False, default="monthly"
    )  # daily, weekly, monthly, yearly, custom
    period_start = Column(DateTime, nullable=False)  # Start of current period
    period_end = Column(DateTime, nullable=False)  # End of current period

    # Current usage (in cents)
    current_usage_cents = Column(Integer, default=0)  # Spent in current period

    # Budget status
    is_active = Column(Boolean, default=True)
    is_exceeded = Column(Boolean, default=False)
    is_warning_sent = Column(Boolean, default=False)

    # Enforcement settings
    enforce_hard_limit = Column(
        Boolean, default=True
    )  # Block requests when limit exceeded
    enforce_warning = Column(Boolean, default=True)  # Send warnings at threshold

    # Allowed resources (optional filters)
    allowed_models = Column(
        JSON, default=list
    )  # Specific models this budget applies to
    allowed_endpoints = Column(
        JSON, default=list
    )  # Specific endpoints this budget applies to

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    currency = Column(String, default="USD")

    # Auto-renewal settings
    auto_renew = Column(
        Boolean, default=True
    )  # Automatically renew budget for next period
    rollover_unused = Column(
        Boolean, default=False
    )  # Rollover unused budget to next period

    # Notification settings
    notification_settings = Column(JSON, default=dict)  # Email, webhook, etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_reset_at = Column(DateTime, nullable=True)  # Last time budget was reset

    def __repr__(self):
        return f"<Budget(id={self.id}, name='{self.name}', user_id={self.user_id}, limit=${self.limit_cents/100:.2f})>"

    def to_dict(self):
        """Convert budget to dictionary for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "api_key_id": self.api_key_id,
            "limit_cents": self.limit_cents,
            "limit_dollars": self.limit_cents / 100,
            "warning_threshold_cents": self.warning_threshold_cents,
            "warning_threshold_dollars": self.warning_threshold_cents / 100
            if self.warning_threshold_cents
            else None,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat()
            if self.period_start
            else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "current_usage_cents": self.current_usage_cents,
            "current_usage_dollars": self.current_usage_cents / 100,
            "remaining_cents": max(0, self.limit_cents - self.current_usage_cents),
            "remaining_dollars": max(
                0, (self.limit_cents - self.current_usage_cents) / 100
            ),
            "usage_percentage": (self.current_usage_cents / self.limit_cents * 100)
            if self.limit_cents > 0
            else 0,
            "is_active": self.is_active,
            "is_exceeded": self.is_exceeded,
            "is_warning_sent": self.is_warning_sent,
            "enforce_hard_limit": self.enforce_hard_limit,
            "enforce_warning": self.enforce_warning,
            "allowed_models": self.allowed_models,
            "allowed_endpoints": self.allowed_endpoints,
            "description": self.description,
            "tags": self.tags,
            "currency": self.currency,
            "auto_renew": self.auto_renew,
            "rollover_unused": self.rollover_unused,
            "notification_settings": self.notification_settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_reset_at": self.last_reset_at.isoformat()
            if self.last_reset_at
            else None,
        }

    def is_in_period(self) -> bool:
        """Check if current time is within budget period"""
        now = datetime.utcnow()
        return self.period_start <= now <= self.period_end

    def is_expired(self) -> bool:
        """Check if budget period has expired"""
        return datetime.utcnow() > self.period_end

    def can_spend(self, amount_cents: int) -> bool:
        """Check if spending amount is within budget"""
        if not self.is_active or not self.is_in_period():
            return False

        if not self.enforce_hard_limit:
            return True

        return (self.current_usage_cents + amount_cents) <= self.limit_cents

    def would_exceed_warning(self, amount_cents: int) -> bool:
        """Check if spending amount would exceed warning threshold"""
        if not self.warning_threshold_cents:
            return False

        return (self.current_usage_cents + amount_cents) >= self.warning_threshold_cents

    def add_usage(self, amount_cents: int):
        """Add usage to current budget"""
        self.current_usage_cents += amount_cents

        # Check if budget is exceeded
        if self.current_usage_cents >= self.limit_cents:
            self.is_exceeded = True

        # Check if warning threshold is reached
        if (
            self.warning_threshold_cents
            and self.current_usage_cents >= self.warning_threshold_cents
        ):
            if not self.is_warning_sent:
                self.is_warning_sent = True

        self.updated_at = datetime.utcnow()

    def reset_period(self):
        """Reset budget for new period"""
        if self.rollover_unused and self.current_usage_cents < self.limit_cents:
            # Rollover unused budget
            unused_amount = self.limit_cents - self.current_usage_cents
            self.limit_cents += unused_amount

        self.current_usage_cents = 0
        self.is_exceeded = False
        self.is_warning_sent = False
        self.last_reset_at = datetime.utcnow()

        # Calculate next period
        if self.period_type == "daily":
            self.period_start = self.period_end
            self.period_end = self.period_start + timedelta(days=1)
        elif self.period_type == "weekly":
            self.period_start = self.period_end
            self.period_end = self.period_start + timedelta(weeks=1)
        elif self.period_type == "monthly":
            self.period_start = self.period_end
            # Handle month boundaries properly
            if self.period_start.month == 12:
                next_month = self.period_start.replace(
                    year=self.period_start.year + 1, month=1
                )
            else:
                next_month = self.period_start.replace(
                    month=self.period_start.month + 1
                )
            self.period_end = next_month
        elif self.period_type == "yearly":
            self.period_start = self.period_end
            self.period_end = self.period_start.replace(year=self.period_start.year + 1)

        self.updated_at = datetime.utcnow()

    def get_period_days_remaining(self) -> int:
        """Get number of days remaining in current period"""
        if self.is_expired():
            return 0
        return (self.period_end - datetime.utcnow()).days

    def get_daily_burn_rate(self) -> float:
        """Get average daily spend rate in current period"""
        if not self.is_in_period():
            return 0.0

        days_elapsed = (datetime.utcnow() - self.period_start).days
        if days_elapsed == 0:
            days_elapsed = 1  # Avoid division by zero

        return self.current_usage_cents / days_elapsed / 100  # Return in dollars

    def get_projected_spend(self) -> float:
        """Get projected spend for entire period based on current burn rate"""
        daily_burn = self.get_daily_burn_rate()
        total_period_days = (self.period_end - self.period_start).days
        return daily_burn * total_period_days

    @classmethod
    def create_monthly_budget(
        cls,
        user_id: int,
        name: str,
        limit_dollars: float,
        api_key_id: Optional[int] = None,
        warning_threshold_percentage: float = 0.8,
    ) -> "Budget":
        """Create a monthly budget"""
        now = datetime.utcnow()
        # Start of current month
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Start of next month
        if now.month == 12:
            period_end = period_start.replace(year=now.year + 1, month=1)
        else:
            period_end = period_start.replace(month=now.month + 1)

        limit_cents = int(limit_dollars * 100)
        warning_threshold_cents = int(limit_cents * warning_threshold_percentage)

        return cls(
            name=name,
            user_id=user_id,
            api_key_id=api_key_id,
            limit_cents=limit_cents,
            warning_threshold_cents=warning_threshold_cents,
            period_type="monthly",
            period_start=period_start,
            period_end=period_end,
            is_active=True,
            enforce_hard_limit=True,
            enforce_warning=True,
            auto_renew=True,
            notification_settings={"email_on_warning": True, "email_on_exceeded": True},
        )

    @classmethod
    def create_daily_budget(
        cls,
        user_id: int,
        name: str,
        limit_dollars: float,
        api_key_id: Optional[int] = None,
    ) -> "Budget":
        """Create a daily budget"""
        now = datetime.utcnow()
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)

        limit_cents = int(limit_dollars * 100)
        warning_threshold_cents = int(limit_cents * 0.8)  # 80% warning threshold

        return cls(
            name=name,
            user_id=user_id,
            api_key_id=api_key_id,
            limit_cents=limit_cents,
            warning_threshold_cents=warning_threshold_cents,
            period_type="daily",
            period_start=period_start,
            period_end=period_end,
            is_active=True,
            enforce_hard_limit=True,
            enforce_warning=True,
            auto_renew=True,
        )
