"""
Tool schemas for API requests and responses
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

# Tool Creation and Update Schemas


class ToolCreate(BaseModel):
    """Schema for creating a new tool"""

    name: str = Field(..., min_length=1, max_length=100, description="Unique tool name")
    display_name: str = Field(
        ..., min_length=1, max_length=200, description="Display name for the tool"
    )
    description: Optional[str] = Field(None, description="Tool description")
    tool_type: str = Field(..., description="Tool type (python, bash, docker, api)")
    code: str = Field(..., min_length=1, description="Tool implementation code")
    parameters_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for parameters"
    )
    return_schema: Optional[Dict[str, Any]] = Field(
        None, description="Expected return format schema"
    )
    timeout_seconds: Optional[int] = Field(
        30, ge=1, le=300, description="Execution timeout in seconds"
    )
    max_memory_mb: Optional[int] = Field(
        256, ge=1, le=1024, description="Maximum memory in MB"
    )
    max_cpu_seconds: Optional[float] = Field(
        10.0, ge=0.1, le=60.0, description="Maximum CPU time in seconds"
    )
    docker_image: Optional[str] = Field(
        None, max_length=200, description="Docker image for execution"
    )
    docker_command: Optional[str] = Field(None, description="Docker command to run")
    category: Optional[str] = Field(None, max_length=50, description="Tool category")
    tags: Optional[List[str]] = Field(None, description="Tool tags")
    is_public: Optional[bool] = Field(False, description="Whether tool is public")

    @validator("tool_type")
    def validate_tool_type(cls, v):
        valid_types = ["python", "bash", "docker", "api", "custom"]
        if v not in valid_types:
            raise ValueError(f"Tool type must be one of: {valid_types}")
        return v

    @validator("tags")
    def validate_tags(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return v


class ToolUpdate(BaseModel):
    """Schema for updating a tool"""

    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    code: Optional[str] = Field(None, min_length=1)
    parameters_schema: Optional[Dict[str, Any]] = None
    return_schema: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    max_memory_mb: Optional[int] = Field(None, ge=1, le=1024)
    max_cpu_seconds: Optional[float] = Field(None, ge=0.1, le=60.0)
    docker_image: Optional[str] = Field(None, max_length=200)
    docker_command: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None

    @validator("tags")
    def validate_tags(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return v


# Tool Response Schemas


class ToolResponse(BaseModel):
    """Schema for tool response"""

    id: int
    name: str
    display_name: str
    description: Optional[str]
    tool_type: str
    parameters_schema: Dict[str, Any]
    return_schema: Dict[str, Any]
    timeout_seconds: int
    max_memory_mb: int
    max_cpu_seconds: float
    docker_image: Optional[str]
    is_public: bool
    is_approved: bool
    created_by_user_id: int
    category: Optional[str]
    tags: List[str]
    usage_count: int
    last_used_at: Optional[datetime]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ToolListResponse(BaseModel):
    """Schema for tool list response"""

    tools: List[ToolResponse]
    total: int
    skip: int
    limit: int


# Tool Execution Schemas


class ToolExecutionCreate(BaseModel):
    """Schema for creating a tool execution"""

    parameters: Dict[str, Any] = Field(..., description="Parameters for tool execution")
    timeout_override: Optional[int] = Field(
        None, ge=1, le=300, description="Override default timeout"
    )


class ToolExecutionResponse(BaseModel):
    """Schema for tool execution response"""

    id: int
    tool_id: int
    tool_name: Optional[str]
    executed_by_user_id: int
    parameters: Dict[str, Any]
    status: str
    output: Optional[str]
    error_message: Optional[str]
    return_code: Optional[int]
    execution_time_ms: Optional[int]
    memory_used_mb: Optional[float]
    cpu_time_ms: Optional[int]
    container_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ToolExecutionListResponse(BaseModel):
    """Schema for tool execution list response"""

    executions: List[ToolExecutionResponse]
    total: int
    skip: int
    limit: int


# Tool Category Schemas


class ToolCategoryCreate(BaseModel):
    """Schema for creating a tool category"""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Unique category name"
    )
    display_name: str = Field(
        ..., min_length=1, max_length=100, description="Display name"
    )
    description: Optional[str] = Field(None, description="Category description")
    icon: Optional[str] = Field(None, max_length=50, description="Icon name")
    color: Optional[str] = Field(None, max_length=20, description="Color code")
    sort_order: Optional[int] = Field(0, description="Sort order")


class ToolCategoryResponse(BaseModel):
    """Schema for tool category response"""

    id: int
    name: str
    display_name: str
    description: Optional[str]
    icon: Optional[str]
    color: Optional[str]
    sort_order: int
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Statistics Schema


class ToolStatisticsResponse(BaseModel):
    """Schema for tool statistics response"""

    total_tools: int
    public_tools: int
    tools_by_type: Dict[str, int]
    total_executions: int
    executions_by_status: Dict[str, int]
    recent_executions: int
    top_tools: List[Dict[str, Any]]
    user_tools: Optional[int] = None
    user_executions: Optional[int] = None
