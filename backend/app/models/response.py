"""
Response model for storing Responses API interactions
"""

from datetime import datetime, timedelta
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class Response(Base):
    """Response storage model for Responses API.

    Stores both the input and output of a response creation request,
    including tool calls, usage metrics, and statefulness information.
    """

    __tablename__ = "responses"

    # Primary identification
    id = Column(String(50), primary_key=True, index=True)  # resp_xxx format
    object = Column(String(20), default="response", nullable=False)

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True, index=True)

    # Model configuration
    model = Column(String(100), nullable=False)
    instructions = Column(Text, nullable=True)  # System prompt

    # Input/Output (stored as JSON)
    input_items = Column(JSON, nullable=False)  # List of input items
    output_items = Column(JSON, nullable=False)  # List of output items

    # Status
    status = Column(
        String(20),
        nullable=False,
        default="completed",
        index=True
    )  # completed, failed, cancelled, incomplete
    error = Column(JSON, nullable=True)  # Error details if failed

    # Statefulness
    previous_response_id = Column(String(50), nullable=True, index=True)
    conversation_id = Column(String(50), nullable=True, index=True)

    # Usage metrics
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Storage configuration
    store = Column(Boolean, nullable=False, default=True)  # Whether content was persisted

    # Response metadata (named to avoid conflict with SQLAlchemy's reserved 'metadata')
    response_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # TTL and archival
    expires_at = Column(DateTime, nullable=True, index=True)  # TTL expiration
    archived_at = Column(DateTime, nullable=True, index=True)  # NULL = active, set = archived

    # Relationships
    user = relationship("User", back_populates="responses", foreign_keys=[user_id])
    api_key = relationship("APIKey", foreign_keys=[api_key_id])

    # Indexes are defined in table args
    __table_args__ = (
        # Primary lookups
        Index("idx_responses_id", "id"),
        Index("idx_responses_conversation_id", "conversation_id", postgresql_where=(conversation_id.isnot(None))),
        Index("idx_responses_previous_response_id", "previous_response_id", postgresql_where=(previous_response_id.isnot(None))),

        # Ownership lookups
        Index("idx_responses_api_key_id", "api_key_id", postgresql_where=(api_key_id.isnot(None))),
        Index("idx_responses_user_id", "user_id", postgresql_where=(user_id.isnot(None))),

        # Archival/cleanup queries
        Index("idx_responses_expires_at", "expires_at", postgresql_where=((expires_at.isnot(None)) & (archived_at.is_(None)))),
        Index("idx_responses_archived_at", "archived_at", postgresql_where=(archived_at.isnot(None))),
        Index("idx_responses_created_at", "created_at"),
        Index("idx_responses_status", "status"),
    )

    def __repr__(self):
        return f"<Response(id={self.id}, status={self.status}, model={self.model})>"

    def to_dict(self):
        """Convert response to dictionary for API responses."""
        return {
            "id": self.id,
            "object": self.object,
            "created_at": int(self.created_at.timestamp()) if self.created_at else 0,
            "model": self.model,
            "output": self.output_items,
            "output_text": self._extract_output_text(),
            "status": self.status,
            "error": self.error,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
            },
            "conversation": {"id": self.conversation_id} if self.conversation_id else None,
            "previous_response_id": self.previous_response_id,
            "metadata": self.response_metadata,
        }

    def _extract_output_text(self) -> str:
        """Extract text content from output items for convenience."""
        if not self.output_items:
            return None

        text_parts = []
        for item in self.output_items:
            if item.get("type") == "message":
                content = item.get("content")
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if part.get("type") == "output_text":
                            text_parts.append(part.get("text", ""))

        return " ".join(text_parts) if text_parts else None

    def is_expired(self) -> bool:
        """Check if response has expired based on TTL."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def is_archived(self) -> bool:
        """Check if response is archived."""
        return self.archived_at is not None

    def archive(self):
        """Mark response as archived."""
        self.archived_at = datetime.utcnow()

    @staticmethod
    def get_default_ttl() -> timedelta:
        """Get default TTL for responses."""
        return timedelta(days=30)

    @staticmethod
    def get_archived_retention() -> timedelta:
        """Get retention period for archived responses."""
        return timedelta(days=90)
