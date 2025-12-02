"""
Database models for chatbot module
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
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

from app.db.database import Base


class ChatbotInstance(Base):
    """Configured chatbot instance"""

    __tablename__ = "chatbot_instances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Configuration stored as JSON
    config = Column(JSON, nullable=False)

    # Metadata
    created_by = Column(String, nullable=False)  # User ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    conversations = relationship(
        "ChatbotConversation", back_populates="chatbot", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ChatbotInstance(id='{self.id}', name='{self.name}')>"


class ChatbotConversation(Base):
    """Conversation state and history"""

    __tablename__ = "chatbot_conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = Column(String, ForeignKey("chatbot_instances.id"), nullable=False)
    user_id = Column(String, nullable=False)  # User ID

    # Conversation metadata
    title = Column(String(255))  # Auto-generated or user-defined title
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Conversation context and settings
    context_data = Column(JSON, default=dict)  # Additional context

    # Relationships
    chatbot = relationship("ChatbotInstance", back_populates="conversations")
    messages = relationship(
        "ChatbotMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ChatbotConversation(id='{self.id}', chatbot_id='{self.chatbot_id}')>"


class ChatbotMessage(Base):
    """Individual chat messages in conversations"""

    __tablename__ = "chatbot_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String, ForeignKey("chatbot_conversations.id"), nullable=False
    )

    # Message content
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_metadata = Column(JSON, default=dict)  # Token counts, model used, etc.

    # RAG sources if applicable
    sources = Column(JSON)  # RAG sources used for this message

    # Relationships
    conversation = relationship("ChatbotConversation", back_populates="messages")

    def __repr__(self):
        return f"<ChatbotMessage(id='{self.id}', role='{self.role}')>"


class ChatbotAnalytics(Base):
    """Analytics and metrics for chatbot usage"""

    __tablename__ = "chatbot_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chatbot_id = Column(String, ForeignKey("chatbot_instances.id"), nullable=False)
    user_id = Column(String, nullable=False)

    # Event tracking
    event_type = Column(
        String(50), nullable=False
    )  # 'message_sent', 'response_generated', etc.
    event_data = Column(JSON, default=dict)

    # Performance metrics
    response_time_ms = Column(Integer)
    token_count = Column(Integer)
    cost_cents = Column(Integer)

    # Context
    model_used = Column(String(100))
    rag_used = Column(Boolean, default=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChatbotAnalytics(id={self.id}, event_type='{self.event_type}')>"
