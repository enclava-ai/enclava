"""
Database models for agent module conversations

Agent conversations are separate from chatbot conversations to:
1. Maintain clean separation between chatbot and agent systems
2. Allow agent-specific conversation metadata
3. Enable independent scaling and optimization
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.database import Base


class AgentConversation(Base):
    """Conversation with a pre-configured agent"""

    __tablename__ = "agent_conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_config_id = Column(Integer, ForeignKey("agent_configs.id"), nullable=False)
    user_id = Column(String, nullable=False)  # User ID

    # Conversation metadata
    title = Column(String(255))  # Auto-generated or user-defined title
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Conversation context and settings
    context_data = Column(JSON, default=dict)  # Additional context

    # Relationships
    agent_config = relationship("AgentConfig", backref="conversations")
    messages = relationship(
        "AgentMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AgentConversation(id='{self.id}', agent_config_id={self.agent_config_id})>"


class AgentMessage(Base):
    """Individual messages in agent conversations"""

    __tablename__ = "agent_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String, ForeignKey("agent_conversations.id"), nullable=False
    )

    # Message content
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system', 'tool'
    content = Column(Text, nullable=True)  # Nullable for tool-call messages

    # Tool-related fields (for function calling support)
    tool_calls = Column(JSON, nullable=True)  # List of tool calls made by assistant
    tool_call_id = Column(String(100), nullable=True)  # For tool response messages
    tool_name = Column(String(100), nullable=True)  # Which tool was called

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_metadata = Column(JSON, default=dict)  # Token counts, model used, etc.

    # RAG sources if applicable
    sources = Column(JSON)  # RAG sources used for this message

    # Relationships
    conversation = relationship("AgentConversation", back_populates="messages")

    def __repr__(self):
        return f"<AgentMessage(id='{self.id}', role='{self.role}')>"
