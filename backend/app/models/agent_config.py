"""
Agent Configuration model for pre-configured agents with tool sets
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class AgentConfig(Base):
    """Pre-configured agent template with specific tool sets and prompts.

    Agents are reusable configurations that combine:
    - System prompts and personality
    - Tool configurations (built-in, MCP, custom)
    - Model settings
    - Use case specific settings

    Examples:
    - "Research Assistant" - web_search + rag_search tools
    - "Code Helper" - code_execution + rag_search tools
    - "Customer Support" - order-api MCP tools + knowledge base
    """

    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Agent personality and behavior
    system_prompt = Column(Text, nullable=False)
    model = Column(String(100), nullable=False, default="gpt-oss-120b")
    temperature = Column(Float, nullable=False, default=0.7)  # 0.0 to 1.0
    max_tokens = Column(Integer, nullable=False, default=2000)

    # Tool configuration
    tools_config = Column(JSON, nullable=False, default=dict)
    # Expected structure:
    # {
    #     "builtin_tools": ["rag_search", "web_search"],
    #     "mcp_servers": ["order-api"],
    #     "include_custom_tools": True,
    #     "tool_choice": "auto",
    #     "max_iterations": 5
    # }

    # Categories and tags for organization
    category = Column(String(50), nullable=True, index=True)  # "support", "development", "research"
    tags = Column(JSON, default=list)  # ["coding", "debugging", "analysis"]

    # Access control
    is_public = Column(Boolean, default=False)  # Public agents available to all users
    is_template = Column(Boolean, default=False)  # Official templates from platform
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL for templates

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    created_by = relationship("User", back_populates="created_agent_configs", foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<AgentConfig(id={self.id}, name='{self.name}', category='{self.category}')>"

    def to_dict(self):
        """Convert agent config to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools_config": self.tools_config,
            "category": self.category,
            "tags": self.tags,
            "is_public": self.is_public,
            "is_template": self.is_template,
            "created_by_user_id": self.created_by_user_id,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
