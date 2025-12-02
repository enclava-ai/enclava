"""
Usage Tracking model for API key usage statistics
"""

from datetime import datetime
from typing import Optional
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


class UsageTracking(Base):
    """Usage tracking model for detailed API key usage statistics"""

    __tablename__ = "usage_tracking"

    id = Column(Integer, primary_key=True, index=True)

    # API Key relationship
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False)
    api_key = relationship("APIKey", back_populates="usage_tracking")

    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="usage_tracking")

    # Budget relationship (optional)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=True)
    budget = relationship("Budget", back_populates="usage_tracking")

    # Request information
    endpoint = Column(String, nullable=False)  # API endpoint used
    method = Column(String, nullable=False)  # HTTP method
    model = Column(String, nullable=True)  # Model used (if applicable)

    # Usage metrics
    request_tokens = Column(Integer, default=0)  # Input tokens
    response_tokens = Column(Integer, default=0)  # Output tokens
    total_tokens = Column(Integer, default=0)  # Total tokens used

    # Cost tracking
    cost_cents = Column(Integer, default=0)  # Cost in cents
    cost_currency = Column(String, default="USD")  # Currency

    # Response information
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    status_code = Column(Integer, nullable=True)  # HTTP status code

    # Request metadata
    request_id = Column(String, nullable=True)  # Unique request identifier
    session_id = Column(String, nullable=True)  # Session identifier
    ip_address = Column(String, nullable=True)  # Client IP address
    user_agent = Column(String, nullable=True)  # User agent

    # Additional metadata
    request_metadata = Column(JSON, default=dict)  # Additional request metadata

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UsageTracking(id={self.id}, api_key_id={self.api_key_id}, endpoint='{self.endpoint}')>"

    def to_dict(self):
        """Convert usage tracking to dictionary for API responses"""
        return {
            "id": self.id,
            "api_key_id": self.api_key_id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "model": self.model,
            "request_tokens": self.request_tokens,
            "response_tokens": self.response_tokens,
            "total_tokens": self.total_tokens,
            "cost_cents": self.cost_cents,
            "cost_currency": self.cost_currency,
            "response_time_ms": self.response_time_ms,
            "status_code": self.status_code,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_metadata": self.request_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def create_tracking_record(
        cls,
        api_key_id: int,
        user_id: int,
        endpoint: str,
        method: str,
        model: Optional[str] = None,
        request_tokens: int = 0,
        response_tokens: int = 0,
        cost_cents: int = 0,
        response_time_ms: Optional[int] = None,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_metadata: Optional[dict] = None,
    ) -> "UsageTracking":
        """Create a new usage tracking record"""
        return cls(
            api_key_id=api_key_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            model=model,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=request_tokens + response_tokens,
            cost_cents=cost_cents,
            response_time_ms=response_time_ms,
            status_code=status_code,
            request_id=request_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_metadata=request_metadata or {},
        )
