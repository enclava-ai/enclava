"""
Built-in Tool Base Class

Base class and data structures for built-in tools (RAG, web search, code execution).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolExecutionContext:
    """Context provided to built-in tools during execution.

    Attributes:
        user_id: User executing the tool
        db: Async database session for queries
        config: Optional configuration dict for tool-specific settings
        tool_resources: Optional tool resources from agent config (e.g., file_search.vector_store_ids)
    """
    user_id: int
    db: Any  # AsyncSession - using Any to avoid circular imports
    config: Dict[str, Any] = field(default_factory=dict)
    tool_resources: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    """Result from built-in tool execution.

    Attributes:
        success: Whether the tool executed successfully
        output: Tool output data (any serializable type)
        error: Error message if execution failed
    """
    success: bool
    output: Any
    error: Optional[str] = None


class BuiltinTool(ABC):
    """Base class for built-in tools.

    Built-in tools have the same interface as custom Tool models from the database,
    allowing ToolCallingService to convert them uniformly to OpenAI format.

    IMPORTANT: These return a Tool-like interface (with name, description,
    display_name, parameters_schema attributes) so _convert_tools_to_openai_format
    can handle them uniformly with custom Tool model objects.

    The display_name attribute is REQUIRED because _convert_tools_to_openai_format
    (line 192) accesses tool.display_name for fallback description text.

    Attributes:
        name: Unique tool identifier (used in function calling)
        display_name: Human-readable name (REQUIRED by converter)
        description: Tool description for LLM
        parameters_schema: JSON Schema for tool parameters
    """

    # Class attributes that must be defined by subclasses
    name: str
    display_name: str  # REQUIRED: accessed by _convert_tools_to_openai_format
    description: str
    parameters_schema: Dict[str, Any]

    @abstractmethod
    async def execute(
        self, params: Dict[str, Any], ctx: ToolExecutionContext
    ) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            params: Tool parameters (validated against parameters_schema)
            ctx: Execution context with user_id, db session, and config

        Returns:
            ToolResult with success status, output, and optional error
        """
        pass

    # NOTE: Do NOT add to_openai_format() here - let ToolCallingService handle
    # conversion uniformly to avoid double-conversion bugs
