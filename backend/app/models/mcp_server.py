"""
MCP Server model for storing external MCP server configurations.

MCP (Model Context Protocol) servers provide external tools that can be
used by agents. This model stores the connection details and tool cache
for configured MCP servers.
"""

from datetime import datetime
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
from app.db.database import Base


class MCPServer(Base):
    """
    MCP Server configuration for external tool providers.

    Stores connection details, API keys, and cached tool definitions
    for MCP-compliant servers that provide tools to agents.

    Access Control:
    - Users can create their own MCP servers
    - Admins can create global servers available to all users
    - Users see: their servers + active global servers
    - Only the creator (or admin) can edit/delete a server

    Examples:
    - Order API MCP server for e-commerce tools
    - Weather API MCP server for weather lookups
    - Custom business logic MCP servers
    """

    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    name = Column(String(100), nullable=False, index=True)  # Unique identifier like "order-api"
    display_name = Column(String(200), nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)  # Optional description

    # Connection settings
    server_url = Column(String(500), nullable=False)  # Base URL for MCP server
    api_key = Column(Text, nullable=True)  # API key for authentication
    api_key_header_name = Column(String(100), nullable=False, default="Authorization")  # Header name for API key
    timeout_seconds = Column(Integer, nullable=False, default=30)  # Request timeout
    max_retries = Column(Integer, nullable=False, default=3)  # Max retry attempts

    # Access control
    is_global = Column(Boolean, default=False, index=True)  # Admin-created, available to all
    is_active = Column(Boolean, default=True, index=True)  # Can be disabled without deletion
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Cached tool discovery
    cached_tools = Column(JSON, default=list)  # List of discovered tools from server
    last_connected_at = Column(DateTime, nullable=True)  # Last successful connection
    last_connection_status = Column(String(50), nullable=True)  # "success" or "failed"
    last_connection_error = Column(Text, nullable=True)  # Error message if failed

    # Usage tracking
    usage_count = Column(Integer, default=0)  # Number of tool calls
    last_used_at = Column(DateTime, nullable=True)  # Last time a tool was called

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    created_by = relationship(
        "User",
        back_populates="created_mcp_servers",
        foreign_keys=[created_by_user_id]
    )

    def __repr__(self):
        return f"<MCPServer(id={self.id}, name='{self.name}', is_global={self.is_global})>"

    def to_dict(self, include_tools: bool = True) -> dict:
        """
        Convert MCP server to dictionary for API responses.

        Args:
            include_tools: Whether to include cached_tools in response (can be large)

        Returns:
            Dictionary representation of the MCP server (without encrypted API key)
        """
        result = {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "server_url": self.server_url,
            "has_api_key": bool(self.api_key),  # Don't expose the key value
            "api_key_header_name": self.api_key_header_name,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "is_global": self.is_global,
            "is_active": self.is_active,
            "created_by_user_id": self.created_by_user_id,
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None,
            "last_connection_status": self.last_connection_status,
            "last_connection_error": self.last_connection_error,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_tools:
            result["cached_tools"] = self.cached_tools or []
            result["tool_count"] = len(self.cached_tools) if self.cached_tools else 0
        else:
            result["tool_count"] = len(self.cached_tools) if self.cached_tools else 0

        return result

    def to_config_dict(self) -> dict:
        """
        Return configuration dict for use with MCPClient.

        Note: API key decryption must happen in the service layer.

        Returns:
            Configuration dictionary for MCPClient instantiation
        """
        return {
            "url": self.server_url,
            "api_key_header_name": self.api_key_header_name,
            "timeout": self.timeout_seconds,
            "max_retries": self.max_retries,
            # api_key must be decrypted separately in service layer
        }

    def update_connection_status(self, success: bool, error: str = None):
        """
        Update connection status after a test or tool call.

        Args:
            success: Whether the connection was successful
            error: Error message if connection failed
        """
        self.last_connected_at = datetime.utcnow()
        self.last_connection_status = "success" if success else "failed"
        self.last_connection_error = error if not success else None

    def record_usage(self):
        """Record a tool call usage."""
        self.usage_count = (self.usage_count or 0) + 1
        self.last_used_at = datetime.utcnow()
