"""
Tool calling schemas for API requests and responses
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ToolExecutionRequest(BaseModel):
    """Schema for executing a tool by name"""

    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters for tool execution"
    )


class ToolCallResponse(BaseModel):
    """Schema for tool call response"""

    success: bool = Field(..., description="Whether the tool call was successful")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")


class ToolValidationRequest(BaseModel):
    """Schema for validating tool availability"""

    tool_names: List[str] = Field(..., description="List of tool names to validate")


class ToolValidationResponse(BaseModel):
    """Schema for tool validation response"""

    tool_availability: Dict[str, bool] = Field(
        ..., description="Tool name to availability mapping"
    )


class ToolHistoryItem(BaseModel):
    """Schema for tool execution history item"""

    id: int = Field(..., description="Execution ID")
    tool_name: str = Field(..., description="Tool name")
    parameters: Dict[str, Any] = Field(..., description="Execution parameters")
    status: str = Field(..., description="Execution status")
    output: Optional[str] = Field(None, description="Tool output")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: Optional[int] = Field(
        None, description="Execution time in milliseconds"
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")


class ToolHistoryResponse(BaseModel):
    """Schema for tool execution history response"""

    history: List[ToolHistoryItem] = Field(..., description="Tool execution history")
    total: int = Field(..., description="Total number of history items")


class ToolCallRequest(BaseModel):
    """Schema for tool call request (placeholder for future use)"""

    message: str = Field(..., description="Chat message")
    tools: Optional[List[str]] = Field(
        None, description="Specific tools to make available"
    )
