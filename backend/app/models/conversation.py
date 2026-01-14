"""
Conversation model for Responses API
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class Conversation(Base):
    """Conversation model for multi-turn responses.

    Stores conversation state including all items (messages, function calls, etc.)
    across multiple response turns.
    """

    __tablename__ = "conversations"

    # Primary identification
    id = Column(String(50), primary_key=True, index=True)  # conv_xxx format
    object = Column(String(20), default="conversation", nullable=False)

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True, index=True)

    # Conversation data
    items = Column(JSON, nullable=False, default=list)  # All items in conversation

    # Conversation metadata (named to avoid conflict with SQLAlchemy's reserved 'metadata')
    conversation_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="conversations", foreign_keys=[user_id])
    api_key = relationship("APIKey", foreign_keys=[api_key_id])

    # Indexes
    __table_args__ = (
        Index("idx_conversations_id", "id"),
        Index("idx_conversations_user_id", "user_id", postgresql_where=(user_id.isnot(None))),
        Index("idx_conversations_api_key_id", "api_key_id", postgresql_where=(api_key_id.isnot(None))),
        Index("idx_conversations_created_at", "created_at"),
        Index("idx_conversations_updated_at", "updated_at"),
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, items={len(self.items)})>"

    def to_dict(self):
        """Convert conversation to dictionary for API responses."""
        return {
            "id": self.id,
            "object": self.object,
            "items": self.items,
            "metadata": self.conversation_metadata,
            "created_at": int(self.created_at.timestamp()) if self.created_at else 0,
            "updated_at": int(self.updated_at.timestamp()) if self.updated_at else 0,
        }

    def add_items(self, new_items: list):
        """Add items to the conversation."""
        if not self.items:
            self.items = []
        self.items.extend(new_items)
        self.updated_at = datetime.utcnow()

    def get_items_count(self) -> int:
        """Get total number of items in conversation."""
        return len(self.items) if self.items else 0
