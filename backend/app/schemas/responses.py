"""
Responses API Schemas

OpenAI-compatible Responses API schemas for agentic interactions with tool execution.
Implements the Items-based format for input/output rather than the Messages format.
"""

from typing import List, Optional, Union, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Input Item Types
# ============================================================================

class InputTextContent(BaseModel):
    """Text content for input items"""
    type: Literal["input_text"] = "input_text"
    text: str


class InputImageContent(BaseModel):
    """Image content for input items (future support)"""
    type: Literal["input_image"] = "input_image"
    source: Dict[str, Any]  # URL or base64 data


InputContent = Union[InputTextContent, InputImageContent]


class MessageInputItem(BaseModel):
    """Message input item"""
    type: Literal["message"] = "message"
    role: Literal["user", "assistant", "system"]
    content: Union[str, List[InputContent]]


class FunctionCallOutputItem(BaseModel):
    """Function call output item (tool execution result)"""
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: str  # JSON string


InputItem = Union[MessageInputItem, FunctionCallOutputItem]


# ============================================================================
# Output Item Types
# ============================================================================

class OutputTextContent(BaseModel):
    """Text content for output items"""
    type: Literal["output_text"] = "output_text"
    text: str


class OutputImageContent(BaseModel):
    """Image content for output items (future support)"""
    type: Literal["output_image"] = "output_image"
    source: Dict[str, Any]


OutputContent = Union[OutputTextContent, OutputImageContent]


class MessageOutputItem(BaseModel):
    """Message output item"""
    type: Literal["message"] = "message"
    id: str
    role: Literal["assistant"]
    content: Union[str, List[OutputContent]]
    status: Literal["completed", "incomplete"] = "completed"


class FunctionCallItem(BaseModel):
    """Function call item (tool invocation)"""
    type: Literal["function_call"] = "function_call"
    id: str
    call_id: str
    name: str
    arguments: str  # JSON string
    status: Literal["completed", "failed", "in_progress"] = "completed"


class FunctionCallOutputItemOutput(BaseModel):
    """Function call output in output items"""
    type: Literal["function_call_output"] = "function_call_output"
    id: str
    call_id: str
    output: str


OutputItem = Union[MessageOutputItem, FunctionCallItem, FunctionCallOutputItemOutput]


# ============================================================================
# Tool Definitions
# ============================================================================

class FileSearchTool(BaseModel):
    """File search (RAG) tool"""
    type: Literal["file_search"] = "file_search"
    vector_store_ids: Optional[List[str]] = None  # Enclava extension


class WebSearchTool(BaseModel):
    """Web search tool"""
    type: Literal["web_search"] = "web_search"


class FunctionTool(BaseModel):
    """Custom function tool"""
    type: Literal["function"] = "function"
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]


class MCPTool(BaseModel):
    """MCP server tool"""
    type: Literal["mcp"] = "mcp"
    server: Optional[str] = None  # Enclava shorthand (references configured server)
    server_url: Optional[str] = None  # OpenAI format (explicit URL)
    api_key: Optional[str] = None  # OpenAI format (explicit key)


Tool = Union[FileSearchTool, WebSearchTool, FunctionTool, MCPTool]


class ToolChoice(BaseModel):
    """Tool choice configuration"""
    type: Literal["auto", "required", "none", "function"]
    function: Optional[Dict[str, str]] = None  # {"name": "tool_name"}


# ============================================================================
# Prompt Reference
# ============================================================================

class PromptRef(BaseModel):
    """Reference to an agent config (prompt)"""
    id: str  # Agent config name/ID


# ============================================================================
# Conversation Reference
# ============================================================================

class ConversationRef(BaseModel):
    """Reference to a conversation"""
    id: str


# ============================================================================
# Token Usage
# ============================================================================

class TokenUsage(BaseModel):
    """Token usage statistics"""
    input_tokens: int
    output_tokens: int
    total_tokens: int


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ResponseCreateRequest(BaseModel):
    """Request to create a response"""

    # Model configuration
    model: str

    # Input
    input: Union[str, List[InputItem]]  # String or items
    instructions: Optional[str] = None  # System prompt

    # Tools
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, ToolChoice]] = "auto"

    # Generation parameters
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Statefulness
    previous_response_id: Optional[str] = None
    conversation: Optional[str] = None  # Conversation ID
    store: bool = True  # Whether to persist the response

    # Agent reference (Enclava extension)
    prompt: Optional[PromptRef] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "model": "gpt-oss-120b",
                "instructions": "You are a helpful support agent.",
                "input": "What's the status of order #123?",
                "tools": [
                    {"type": "file_search"},
                    {"type": "web_search"},
                    {"type": "mcp", "server": "order-api"}
                ],
                "store": True
            }
        }


class ResponseObject(BaseModel):
    """Response object"""

    id: str
    object: Literal["response"] = "response"
    created_at: int  # Unix timestamp
    model: str

    # Output
    output: List[OutputItem]
    output_text: Optional[str] = None  # Helper for text content

    # Status
    status: Literal["completed", "failed", "cancelled", "incomplete"] = "completed"
    error: Optional[Dict[str, Any]] = None

    # Usage
    usage: TokenUsage

    # Statefulness
    conversation: Optional[ConversationRef] = None
    previous_response_id: Optional[str] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "resp_abc123",
                "object": "response",
                "created_at": 1234567890,
                "model": "gpt-oss-120b",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_xyz789",
                        "role": "assistant",
                        "content": "Order #123 is currently being processed...",
                        "status": "completed"
                    }
                ],
                "output_text": "Order #123 is currently being processed...",
                "status": "completed",
                "usage": {
                    "input_tokens": 150,
                    "output_tokens": 75,
                    "total_tokens": 225
                }
            }
        }


class ResponseListResponse(BaseModel):
    """List of responses"""
    object: Literal["list"] = "list"
    data: List[ResponseObject]
    has_more: bool = False
    first_id: Optional[str] = None
    last_id: Optional[str] = None
