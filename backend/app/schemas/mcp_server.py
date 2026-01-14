"""
MCP Server schemas for API requests and responses.

These schemas handle validation for MCP server CRUD operations,
connection testing, and tool discovery.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re


# =============================================================================
# MCP Server Create/Update Schemas
# =============================================================================


class MCPServerCreate(BaseModel):
    """Schema for creating a new MCP server configuration."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier for the server (e.g., 'order-api', 'weather')"
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable display name"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description of the server's purpose"
    )
    server_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Base URL for the MCP server"
    )
    api_key: Optional[str] = Field(
        None,
        description="API key for authentication (will be encrypted)"
    )
    api_key_header_name: str = Field(
        default="Authorization",
        max_length=100,
        description="HTTP header name for API key (e.g., 'Authorization', 'X-API-Key')"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed requests"
    )
    is_global: bool = Field(
        default=False,
        description="Make this server available to all users (admin only)"
    )

    @validator("name")
    def validate_name(cls, v):
        """Validate server name follows naming conventions."""
        # Allow lowercase letters, numbers, and hyphens
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$", v):
            raise ValueError(
                "Name must start with a letter, contain only lowercase letters, "
                "numbers, and hyphens, and end with a letter or number"
            )
        return v

    @validator("server_url")
    def validate_url(cls, v):
        """Validate server URL is well-formed."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Server URL must start with http:// or https://")
        return v.rstrip("/")  # Remove trailing slash for consistency


class MCPServerUpdate(BaseModel):
    """Schema for updating an MCP server configuration."""

    display_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Human-readable display name"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional description"
    )
    server_url: Optional[str] = Field(
        None,
        min_length=1,
        max_length=500,
        description="Base URL for the MCP server"
    )
    api_key: Optional[str] = Field(
        None,
        description="New API key (set to empty string to remove)"
    )
    api_key_header_name: Optional[str] = Field(
        None,
        max_length=100,
        description="HTTP header name for API key"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        ge=5,
        le=300,
        description="Request timeout in seconds"
    )
    max_retries: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Maximum retry attempts"
    )
    is_global: Optional[bool] = Field(
        None,
        description="Global availability (admin only)"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether the server is active"
    )

    @validator("server_url")
    def validate_url(cls, v):
        """Validate server URL if provided."""
        if v is not None:
            if not v.startswith(("http://", "https://")):
                raise ValueError("Server URL must start with http:// or https://")
            return v.rstrip("/")
        return v


# =============================================================================
# Connection Test Schemas
# =============================================================================


class MCPServerTestRequest(BaseModel):
    """Schema for testing an MCP server connection without saving."""

    server_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Base URL for the MCP server"
    )
    api_key: Optional[str] = Field(
        None,
        description="API key for authentication"
    )
    api_key_header_name: str = Field(
        default="Authorization",
        max_length=100,
        description="HTTP header name for API key (e.g., 'Authorization', 'X-API-Key')"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=60,
        description="Request timeout for test"
    )

    @validator("server_url")
    def validate_url(cls, v):
        """Validate server URL is well-formed."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Server URL must start with http:// or https://")
        return v.rstrip("/")


class MCPToolInfo(BaseModel):
    """Schema for MCP tool information."""

    name: str = Field(..., description="Tool name/identifier")
    description: Optional[str] = Field(None, description="Tool description")
    parameters_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON schema for tool parameters"
    )


class MCPServerTestResponse(BaseModel):
    """Schema for MCP server connection test response."""

    success: bool = Field(..., description="Whether the connection test succeeded")
    message: str = Field(..., description="Status message")
    tools: List[MCPToolInfo] = Field(
        default_factory=list,
        description="List of discovered tools"
    )
    tool_count: int = Field(default=0, description="Number of tools discovered")
    response_time_ms: Optional[int] = Field(
        None,
        description="Response time in milliseconds"
    )
    error: Optional[str] = Field(None, description="Error details if failed")


# =============================================================================
# Response Schemas
# =============================================================================


class MCPServerResponse(BaseModel):
    """Schema for MCP server response."""

    id: int
    name: str
    display_name: str
    description: Optional[str]
    server_url: str
    has_api_key: bool = Field(..., description="Whether an API key is configured")
    api_key_header_name: str = Field(default="Authorization")
    timeout_seconds: int
    max_retries: int
    is_global: bool
    is_active: bool
    created_by_user_id: int
    cached_tools: List[Dict[str, Any]] = Field(default_factory=list)
    tool_count: int = Field(default=0)
    last_connected_at: Optional[datetime]
    last_connection_status: Optional[str]
    last_connection_error: Optional[str]
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class MCPServerListResponse(BaseModel):
    """Schema for MCP server list response."""

    servers: List[MCPServerResponse]
    total: int
    user_servers: int = Field(
        ...,
        description="Number of servers created by the current user"
    )
    global_servers: int = Field(
        ...,
        description="Number of global servers"
    )


class MCPServerRefreshResponse(BaseModel):
    """Schema for tool refresh response."""

    success: bool
    tools: List[MCPToolInfo] = Field(default_factory=list)
    tool_count: int = Field(default=0)
    message: str
    error: Optional[str] = None


# =============================================================================
# Utility Response Schemas
# =============================================================================


class MCPServerDeleteResponse(BaseModel):
    """Schema for delete operation response."""

    success: bool
    message: str
    deleted_id: int


class MCPServerBulkActionResponse(BaseModel):
    """Schema for bulk action response."""

    success: bool
    affected_count: int
    message: str
    errors: List[str] = Field(default_factory=list)
